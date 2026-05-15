"""打印跟踪模块"""
import asyncio
import logging
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from homeassistant.util import dt as dt_util

from .const import (
    ACTIVE_PRINT_STATUSES,
    CHAMBER_TEMP_WINDOW_MINUTES,
    COLOR_CONFIRM_THRESHOLD,
    DURATION_BUCKETS,
    END_PRINT_STATUSES,
    ENERGY_MAX_DELTA_KWH,
    FAILURE_STAGE_BUCKETS,
    INVALID_ENTITY_STATES,
    MATERIAL_CACHE_INTERVAL_SECONDS,
    PRINT_STATUS_CANCELLED,
    PRINT_STATUS_FAIL,
    PRINT_STATUS_FINISH,
    PRINT_STATUS_IDLE,
    PRINT_STATUS_RUNNING,
    TASK_NAME_CAPTURE_WINDOW_SECS,
)
from .utils import is_param_description

if TYPE_CHECKING:
    from .coordinator import PrinterAnalyticsCoordinator
    from .entity_discovery import EntityDiscovery

LOGGER = logging.getLogger(__name__)


class PrintTracker:
    """打印跟踪管理器"""

    def __init__(self, coordinator: "PrinterAnalyticsCoordinator") -> None:
        self.coordinator = coordinator
        self.hass = coordinator.hass
        self._entity_map = coordinator._entity_map
        self._material_cache_interval = None
        self._ams_tray_entity_ids: list[str] | None = None

    def get_current_status(self) -> str | None:
        """获取当前打印状态"""
        status_entity = self.coordinator.print_status_entity
        if not status_entity:
            return None
        state = self.hass.states.get(status_entity)
        return state.state if state and state.state not in INVALID_ENTITY_STATES else None

    def recover_active_print(self) -> None:
        """恢复活跃打印"""
        if self.coordinator.current_print:
            return

        start_time_entity = self._entity_map.get("start_time")
        if start_time_entity:
            start_time = self.coordinator.get_entity_state(start_time_entity)
            if start_time and start_time not in INVALID_ENTITY_STATES:
                self.coordinator.current_print = {
                    "id": str(uuid.uuid4()),
                    "start_time": self.coordinator._ensure_timezone(start_time),
                    "status": "running",
                    "colors_used": [],
                    "types_used": [],
                    "color_changes": [],
                    "color_usage": [],
                }
                LOGGER.info("已恢复活跃打印记录")

    def handle_state_change(self, event: Any) -> None:
        """处理状态变化"""
        new_status = event.data.get("new_state")
        if new_status:
            new_status = new_status.state
        else:
            return

        old_status = self.coordinator._previous_status
        self.coordinator._previous_status = new_status

        if new_status in ACTIVE_PRINT_STATUSES and old_status not in ACTIVE_PRINT_STATUSES:
            self._on_print_start()
        elif new_status in END_PRINT_STATUSES and old_status in ACTIVE_PRINT_STATUSES:
            self.hass.async_create_task(self._on_print_end(new_status))

    def start_material_cache(self) -> None:
        """启动耗材缓存"""
        self.stop_material_cache()
        from homeassistant.helpers.event import async_track_time_interval
        self._material_cache_interval = async_track_time_interval(
            self.hass,
            self._on_material_cache_tick,
            timedelta(seconds=MATERIAL_CACHE_INTERVAL_SECONDS)
        )

    def stop_material_cache(self) -> None:
        """停止耗材缓存"""
        if self._material_cache_interval:
            self._material_cache_interval()
            self._material_cache_interval = None

    def _on_material_cache_tick(self, now: datetime) -> None:
        """定时缓存耗材数据"""
        if self.coordinator.current_print:
            self._cache_print_material_data()
            self._track_color_changes()
            self._cache_delayed_fields()
            self._try_capture_task_name()
            self._cache_chamber_temperature(now)
            # 通知 coordinator 数据已更新，触发 sensor 属性重新计算
            self.coordinator.async_set_updated_data(self.coordinator._calculate_statistics())

    def _cache_print_material_data(self) -> None:
        """缓存耗材数据（支持多色追踪）"""
        if not self.coordinator.current_print:
            return

        weight_entity = self._entity_map.get("print_weight")
        length_entity = self._entity_map.get("print_length")

        if weight_entity:
            weight = self.coordinator.get_float_state(weight_entity, 0)
            if weight > 0:
                self.coordinator.current_print["cached_weight"] = weight

        if length_entity:
            length = self.coordinator.get_float_state(length_entity, 0)
            if length > 0:
                self.coordinator.current_print["cached_length"] = length

        self._update_ams_color_usage()

    def _get_ams_tray_entities(self) -> list[str]:
        """获取 AMS tray 实体列表（首次遍历后缓存）"""
        if self._ams_tray_entity_ids is not None:
            return self._ams_tray_entity_ids

        prefix = self.coordinator.printer_name.lower()
        result = []
        for eid in self.hass.states.async_entity_ids("sensor"):
            if eid.startswith(f"sensor.{prefix}_") and "ams" in eid and "tray" in eid:
                result.append(eid)
        self._ams_tray_entity_ids = result
        return result

    def invalidate_ams_cache(self) -> None:
        """失效 AMS 实体缓存"""
        self._ams_tray_entity_ids = None

    def _update_ams_color_usage(self) -> None:
        """更新AMS耗材使用情况（优化：只遍历已知 AMS 实体）"""
        tray_color_map = self.coordinator._build_tray_color_map()
        active_tray = self.coordinator.get_entity_state(self._entity_map.get("active_tray", ""), "")

        if not tray_color_map:
            return

        ams_entities = self._get_ams_tray_entities()

        color_agg = {}
        for eid in ams_entities:
            state = self.hass.states.get(eid)
            if not state:
                continue

            try:
                weight = float(state.state) if state.state not in INVALID_ENTITY_STATES else 0
            except (ValueError, TypeError):
                continue

            if weight <= 0:
                continue

            attrs = state.attributes
            color = attrs.get("color", "")
            name = attrs.get("name", "") or attrs.get("friendly_name", "")

            tray_key = eid.replace("sensor.", "")

            if tray_key not in color_agg:
                color_agg[tray_key] = {
                    "color": color.lower() if isinstance(color, str) else color,
                    "type": name,
                    "weight_g": 0,
                    "length_m": 0,
                    "trays": [],
                }

            color_agg[tray_key]["weight_g"] += weight

            if tray_key not in color_agg[tray_key]["trays"]:
                color_agg[tray_key]["trays"].append(tray_key)

        color_usage = self.coordinator.current_print.setdefault("color_usage", [])
        color_usage.clear()

        for entry in color_agg.values():
            color_usage.append({
                "color": entry["color"],
                "type": entry["type"],
                "weight_g": round(entry["weight_g"], 2),
                "length_m": round(entry.get("length_m", 0), 2),
                "tray": ", ".join(entry["trays"]) if len(entry["trays"]) > 1 else (entry["trays"][0] if entry["trays"] else ""),
                "start_time": entry.get("start_time", ""),
            })

        self.coordinator.current_print["ams_tray_data"] = True

    def _get_current_filament_info(self) -> tuple[str, str]:
        """获取当前耗材信息"""
        ftype = self.coordinator.get_entity_attr(
            self._entity_map.get("active_tray", ""), "name", ""
        )
        color = self.coordinator.get_entity_attr(
            self._entity_map.get("active_tray", ""), "color", ""
        )
        return (ftype or "", color or "")

    def _track_color_changes(self) -> None:
        """追踪颜色变化"""
        if not self.coordinator.current_print:
            return

        current_type, current_color = self._get_current_filament_info()

        if current_color:
            current_color = current_color.lower()

        colors_used = [c.lower() if isinstance(c, str) else c for c in self.coordinator.current_print.get("colors_used", [])]
        types_used = self.coordinator.current_print.get("types_used", [])

        if current_color and current_color not in colors_used:
            pending = self.coordinator.current_print.get("_pending_color")
            pending_count = self.coordinator.current_print.get("_pending_color_count", 0)

            if pending == current_color:
                pending_count += 1
                if pending_count >= COLOR_CONFIRM_THRESHOLD:
                    colors_used.append(current_color)
                    change_count = len(colors_used) - 1

                    if "color_changes" not in self.coordinator.current_print:
                        self.coordinator.current_print["color_changes"] = []

                    self.coordinator.current_print["color_changes"].append({
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "from_color": colors_used[-2] if len(colors_used) > 1 else None,
                        "to_color": current_color,
                        "from_type": types_used[-1] if types_used else None,
                        "to_type": current_type,
                        "change_number": change_count,
                    })

                    LOGGER.info("耗材切换 #%d: %s", change_count, current_color)
                    self.coordinator.current_print["_pending_color"] = None
                    self.coordinator.current_print["_pending_color_count"] = 0
                else:
                    self.coordinator.current_print["_pending_color_count"] = pending_count
            else:
                self.coordinator.current_print["_pending_color"] = current_color
                self.coordinator.current_print["_pending_color_count"] = 1
        else:
            self.coordinator.current_print["_pending_color"] = None
            self.coordinator.current_print["_pending_color_count"] = 0

        if current_type and current_type not in types_used:
            types_used.append(current_type)

        self.coordinator.current_print["colors_used"] = colors_used
        self.coordinator.current_print["types_used"] = types_used

        if colors_used:
            self.coordinator.current_print["filament_color"] = colors_used[0]
            self.coordinator.current_print["filament_type"] = types_used[0] if types_used else None

    def _try_capture_task_name(self) -> None:
        """捕获任务名称"""
        if not self.coordinator.current_print:
            return

        current_name = self.coordinator.current_print.get("task_name")
        if current_name and not self._is_param_description(current_name):
            return

        start_time = self.coordinator.current_print.get("start_time", "")
        if not start_time:
            return

        try:
            start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            elapsed = (datetime.now(timezone.utc) - start_dt).total_seconds()
            if elapsed > TASK_NAME_CAPTURE_WINDOW_SECS:
                return
        except (ValueError, TypeError):
            return

        task_entity = self._entity_map.get("task_name", "")
        if not task_entity:
            return

        new_name = self.coordinator.get_entity_state(task_entity, "")
        if not new_name or new_name in INVALID_ENTITY_STATES:
            return

        if self._is_param_description(new_name):
            return

        if new_name != current_name:
            self.coordinator.current_print["task_name"] = new_name
            self.coordinator._lock_task_name(new_name)
            LOGGER.info("成功捕获任务名称: %s", new_name)

    def _cache_delayed_fields(self) -> None:
        """缓存延迟字段"""
        if not self.coordinator.current_print:
            return

        current_name = self.coordinator.current_print.get("task_name", "")
        need_better = not current_name or self._is_param_description(current_name) or current_name.startswith("/data/")
        if need_better:
            raw_task_name = self.coordinator.get_entity_state(self._entity_map.get("task_name", ""), "")
            raw_gcode = self.coordinator.get_entity_state(self._entity_map.get("gcode_filename", ""), "")
            candidate = None
            if raw_task_name and raw_task_name not in INVALID_ENTITY_STATES:
                candidate = self._extract_real_task_name(raw_task_name)
            if not candidate and raw_gcode and raw_gcode not in INVALID_ENTITY_STATES:
                basename = os.path.basename(raw_gcode)
                if basename and basename != raw_gcode and not self._is_param_description(basename):
                    candidate = basename
            if candidate and candidate != current_name:
                LOGGER.info("Task name improved: '%s' -> '%s'", (current_name or "")[:40], candidate[:40])
                self.coordinator.current_print["task_name"] = candidate
                self.coordinator._lock_task_name(candidate)

        if not self.coordinator.current_print.get("nozzle_size"):
            nozzle_size = self.coordinator.get_entity_state(self._entity_map.get("nozzle_size", ""), "")
            if nozzle_size:
                self.coordinator.current_print["nozzle_size"] = nozzle_size

        if not self.coordinator.current_print.get("total_layer_count"):
            total_layer_count = self.coordinator.get_float_state(self._entity_map.get("total_layer_count", ""), 0)
            if total_layer_count:
                self.coordinator.current_print["total_layer_count"] = int(total_layer_count)

        if not self.coordinator.current_print.get("energy_valid"):
            start_energy = self.coordinator.get_float_state(self.coordinator.energy_entity)
            if start_energy > 0:
                self.coordinator.current_print["start_energy"] = start_energy
                self.coordinator.current_print["energy_valid"] = True

    def _cache_chamber_temperature(self, now: datetime) -> None:
        """缓存腔体温度"""
        if not self.coordinator.current_print:
            return

        chamber_entity = self._entity_map.get("chamber_temperature")
        if not chamber_entity:
            chamber_entity = self.coordinator.chamber_temp_entity
        if not chamber_entity:
            return

        temp = self.coordinator.get_float_state(chamber_entity, None)
        if temp is None:
            return

        if "chamber_temp_timeline" not in self.coordinator.current_print:
            self.coordinator.current_print["chamber_temp_timeline"] = []

        self.coordinator.current_print["chamber_temp_timeline"].append({
            "time": now.isoformat(),
            "temp": round(temp, 1),
        })

    def _is_param_description(self, task_name: str) -> bool:
        """判断是否为参数描述（使用公共函数）"""
        return is_param_description(task_name)

    def _extract_real_task_name(self, task_name: str) -> str | None:
        """提取真实任务名"""
        if not task_name or task_name in INVALID_ENTITY_STATES:
            return None
        if task_name.startswith("/data/"):
            return None
        if self._is_param_description(task_name):
            return None
        if len(task_name) < 3:
            return None
        return task_name

    def on_print_start(self) -> None:
        """打印开始"""
        if not self._entity_map.get("print_weight"):
            self.hass.async_create_task(self.coordinator._discover_entities())

        start_time_entity = self._entity_map.get("start_time")
        start_time_val = self.coordinator.get_entity_state(start_time_entity)
        if start_time_val:
            start_time = self.coordinator._ensure_timezone(start_time_val)
        else:
            start_time = datetime.now(timezone.utc).isoformat()

        task_name = self.coordinator._get_best_task_name()
        self.coordinator._lock_task_name(task_name)
        nozzle_type = self.coordinator.get_entity_state(self._entity_map.get("nozzle_type", ""), "")
        nozzle_size = self.coordinator.get_entity_state(self._entity_map.get("nozzle_size", ""), "")
        print_bed_type = self.coordinator.get_entity_state(self._entity_map.get("print_bed_type", ""), "")
        total_layer_count = self.coordinator.get_float_state(self._entity_map.get("total_layer_count", ""), 0)

        filament_type, filament_color = self._get_current_filament_info()
        if filament_color:
            filament_color = filament_color.lower()

        cover_entity = self._entity_map.get("cover_image", "")
        if not cover_entity:
            prefix = self.coordinator.printer_name.lower()
            image_entities = list(self.hass.states.async_entity_ids("image"))
            for eid in image_entities:
                if eid.startswith(f"image.{prefix}_") and eid.endswith("_cover_image"):
                    cover_entity = eid
                    break
        cover_image_url = self.coordinator.get_entity_attr(cover_entity, "entity_picture", "")

        start_energy = self.coordinator.get_float_state(self.coordinator.energy_entity)

        self.coordinator.current_print = {
            "id": str(uuid.uuid4()),
            "start_time": start_time,
            "status": "running",
            "start_energy": start_energy,
            "energy_valid": start_energy > 0,
            "task_name": task_name or None,
            "nozzle_type": nozzle_type or None,
            "nozzle_size": nozzle_size or None,
            "print_bed_type": print_bed_type or None,
            "total_layer_count": int(total_layer_count) if total_layer_count else None,
            "colors_used": [filament_color] if filament_color else [],
            "types_used": [filament_type] if filament_type else [],
            "color_changes": [],
            "total_colors": 1 if filament_color else 0,
            "filament_type": filament_type or None,
            "filament_color": filament_color or None,
            "cover_image_url": cover_image_url or None,
            "cover_image_local": None,
            "snapshot_image_local": None,
            "color_usage": [],
        }

        self.start_material_cache()
        LOGGER.info("Print started: %s | 初始颜色: %s (%s)", task_name, filament_color, filament_type)

        self.hass.async_create_task(self.coordinator._delayed_cover_download(task_name or "unknown", start_time))
        self.hass.async_create_task(self.coordinator._delayed_snapshot_download(task_name or "unknown", start_time))

        # 通知 coordinator 数据已更新，触发 sensor 属性重新计算
        self.coordinator.async_set_updated_data(self.coordinator._calculate_statistics())

    async def _on_print_end(self, end_status: str) -> None:
        """打印结束"""
        self.stop_material_cache()
        self.coordinator._clear_locked_task_name()

        if self.coordinator.current_print is None:
            LOGGER.warning("Print end detected but no active print record")
            return

        end_time = datetime.now(timezone.utc).isoformat()
        start_dt = self.coordinator._normalize_to_utc(self.coordinator.current_print["start_time"])
        end_dt = self.coordinator._normalize_to_utc(end_time)

        if start_dt and end_dt:
            duration_hours = (end_dt - start_dt).total_seconds() / 3600
        else:
            duration_hours = 0

        progress = 100
        if end_status in (PRINT_STATUS_FAIL, PRINT_STATUS_CANCELLED):
            progress = int(self.coordinator.get_float_state(self._entity_map.get("print_progress", ""), 0))

        total_weight = self.coordinator.current_print.get("cached_weight") or self.coordinator.get_float_state(self._entity_map.get("print_weight", ""))
        total_length = self.coordinator.current_print.get("cached_length") or self.coordinator.get_float_state(self._entity_map.get("print_length", ""))

        energy_kwh = None
        if self.coordinator.energy_entity and self.coordinator.current_print.get("energy_valid"):
            end_energy = self.coordinator.get_float_state(self.coordinator.energy_entity)
            start_energy = self.coordinator.current_print.get("start_energy", 0)
            delta = end_energy - start_energy
            if 0 < delta < ENERGY_MAX_DELTA_KWH:
                energy_kwh = round(delta, 4)
            else:
                LOGGER.warning("Abnormal energy delta %.2f kWh, skipped", delta)

        task_name = self.coordinator.current_print.get("task_name") or ""
        cover_image_url = self.coordinator.current_print.get("cover_image_url") or ""
        cover_image_local = self.coordinator.current_print.get("cover_image_local")
        start_time = self.coordinator.current_print.get("start_time") or ""

        if not cover_image_local and self.coordinator.image_manager:
            cover_image_local = await self.coordinator.image_manager._download_cover_from_cloud(task_name, end_time, start_time)
        if not cover_image_local and self.coordinator.image_manager:
            cover_image_local = await self.coordinator.image_manager._download_cover_image(cover_image_url, task_name, end_time)

        colors_used, types_used, color_changes, color_usage, total_colors, multi_color_summary, clean_color_usage = \
            self.coordinator._build_color_data(end_status, progress)

        chamber_temp_last5min, chamber_temp_final = self.coordinator._build_chamber_temp_data(end_dt)

        base_record = {
            "id": self.coordinator.current_print["id"],
            "start_time": self.coordinator.current_print["start_time"],
            "end_time": end_time,
            "duration_hours": round(duration_hours, 2),
            "status": end_status,
            "progress": progress,
            "total_weight": round(total_weight, 2) if total_weight else None,
            "total_length": round(total_length, 2) if total_length else None,
            "filament_type": types_used[0] if types_used else self.coordinator.current_print.get("filament_type"),
            "filament_color": colors_used[0] if colors_used else self.coordinator.current_print.get("filament_color"),
            "colors_used": colors_used,
            "types_used": types_used,
            "total_colors": total_colors,
            "color_changes_count": len(color_changes),
            "multi_color_summary": multi_color_summary,
            "color_usage": clean_color_usage,
            "energy_kwh": round(energy_kwh, 4) if energy_kwh else None,
            "task_name": task_name or None,
            "nozzle_type": self.coordinator.current_print.get("nozzle_type"),
            "nozzle_size": self.coordinator.current_print.get("nozzle_size"),
            "print_bed_type": self.coordinator.current_print.get("print_bed_type"),
            "total_layer_count": self.coordinator.current_print.get("total_layer_count"),
            "cover_image_url": cover_image_url or None,
            "chamber_temp_final": chamber_temp_final,
            "chamber_temp_last5min": chamber_temp_last5min,
        }

        snapshot_image_local = self.coordinator.current_print.get("snapshot_image_local")
        if not snapshot_image_local and self.coordinator.image_manager:
            _, snapshot_image_local = await asyncio.gather(
                self.coordinator._save_full_print_info(base_record, end_time),
                self.coordinator.image_manager._download_print_snapshot(end_time, task_name)
            )
        else:
            full_print_info = await self.coordinator._save_full_print_info(base_record, end_time)

        record = {
            **base_record,
            "cover_image_local": cover_image_local,
            "snapshot_image_local": snapshot_image_local,
            "full_print_info_path": full_print_info,
        }

        self.coordinator.history.append(record)
        self.coordinator.current_print = None
        self.hass.async_create_task(self.coordinator._save_history())
        # 通知 coordinator 数据已更新，触发 sensor 属性重新计算
        self.coordinator.async_set_updated_data(self.coordinator._calculate_statistics())
        LOGGER.info("Print ended: status=%s, duration=%.2f hours", end_status, duration_hours)
