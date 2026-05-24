"""打印跟踪模块"""
import asyncio
import json
import logging
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.history import get_significant_states
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
    OFFLINE_STATUS,
    PRINT_STATUS_CANCELLED,
    PRINT_STATUS_FAIL,
    PRINT_STATUS_FAILED,
    PRINT_STATUS_FINISH,
    PRINT_STATUS_IDLE,
    PRINT_STATUS_RUNNING,
    TASK_NAME_CAPTURE_WINDOW_SECS,
    TRANSITIONAL_STATUSES,
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
        self._recovered_from_disk = False  # 防止恢复后首次tick误判

    def get_current_status(self) -> str | None:
        """获取当前打印状态"""
        status_entity = self.coordinator.print_status_entity
        if not status_entity:
            return None
        state = self.hass.states.get(status_entity)
        return state.state if state and state.state not in INVALID_ENTITY_STATES else None

    def _current_print_file(self) -> str:
        """获取 current_print 持久化文件路径"""
        return os.path.join(
            self.coordinator._history_base_dir,
            f"{self.coordinator.entry.entry_id}_current_print.json"
        )

    def _save_current_print(self) -> None:
        """持久化 current_print 到磁盘"""
        if not self.coordinator.current_print:
            return
        try:
            filepath = self._current_print_file()
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            # 清理内部字段再保存
            data = {k: v for k, v in self.coordinator.current_print.items()
                    if not k.startswith("_") or k in ("_pending_color_validation",)}
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as err:
            LOGGER.warning("保存 current_print 失败: %s", err)

    def _load_current_print(self) -> dict | None:
        """从磁盘加载 current_print"""
        try:
            filepath = self._current_print_file()
            if not os.path.exists(filepath):
                return None
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data
        except Exception as err:
            LOGGER.warning("加载 current_print 失败: %s", err)
            return None

    def _delete_current_print_file(self) -> None:
        """删除 current_print 持久化文件"""
        try:
            filepath = self._current_print_file()
            if os.path.exists(filepath):
                os.remove(filepath)
        except Exception as err:
            LOGGER.warning("删除 current_print 文件失败: %s", err)

    def recover_active_print(self) -> None:
        """恢复活跃打印 - 完整收集打印信息"""
        if self.coordinator.current_print:
            return

        # 检查当前状态是否在打印中
        current_status = self.get_current_status()
        if current_status not in ACTIVE_PRINT_STATUSES:
            # 状态不可用时，先检查磁盘是否有持久化数据
            saved = self._load_current_print()
            if saved:
                self.coordinator.current_print = saved
                self.coordinator.current_print["_pending_color_validation"] = True
                self.start_material_cache()
                LOGGER.info("状态不可用但磁盘有持久化数据，先恢复: %s", saved.get("task_name", ""))
                self.coordinator.async_set_updated_data(self.coordinator._calculate_statistics())
                return
            self._delete_current_print_file()
            return

        # 获取开始时间
        start_time = datetime.now(timezone.utc).isoformat()  # 默认
        start_time_entity = self._entity_map.get("start_time")
        if start_time_entity:
            start_time_val = self.coordinator.get_entity_state(start_time_entity)
            if start_time_val and start_time_val not in INVALID_ENTITY_STATES:
                start_time = self.coordinator._ensure_timezone(start_time_val)

        # 收集任务名称
        task_entity = self._entity_map.get("task_name", "")
        immediate_name = ""
        if task_entity:
            immediate_name = self.coordinator.get_entity_state(task_entity, "") or ""

        model_name = ""
        config_name = ""

        # 优先使用预缓存的模型名
        pre_cached_model = self.coordinator._pre_print_model_name
        if pre_cached_model:
            model_name = pre_cached_model
            self.coordinator._pre_print_model_name = ""

        if immediate_name and immediate_name not in INVALID_ENTITY_STATES:
            self._task_name_variants = [immediate_name]
            if self._is_param_description(immediate_name):
                config_name = immediate_name
                if not model_name:
                    model_name = self._infer_model_name_from_history(immediate_name) or ""
            else:
                if not model_name:
                    model_name = immediate_name

        task_name = model_name or config_name or ""
        self.coordinator._lock_task_name(task_name)

        # 收集耗材信息
        filament_type, filament_color = self._get_current_filament_info()
        if filament_color:
            filament_color = filament_color.lower()

        # 收集封面图
        cover_entity = self._entity_map.get("cover_image", "")
        if not cover_entity:
            prefix = self.coordinator.printer_name.lower()
            image_entities = list(self.hass.states.async_entity_ids("image"))
            for eid in image_entities:
                if eid.startswith(f"image.{prefix}_") and eid.endswith("_cover_image"):
                    cover_entity = eid
                    break
        cover_image_url = self.coordinator.get_entity_attr(cover_entity, "entity_picture", "")

        # 收集开始能耗
        start_energy = self.coordinator.get_float_state(self.coordinator.energy_entity)

        # 收集其他信息
        nozzle_type = self.coordinator.get_entity_state(self._entity_map.get("nozzle_type", ""), "")
        nozzle_size = self.coordinator.get_entity_state(self._entity_map.get("nozzle_size", ""), "")
        print_bed_type = self.coordinator.get_entity_state(self._entity_map.get("print_bed_type", ""), "")
        total_layer_count = self.coordinator.get_float_state(self._entity_map.get("total_layer_count", ""), 0)

        # 构建完整的 current_print
        self.coordinator.current_print = {
            "id": str(uuid.uuid4()),
            "start_time": start_time,
            "status": "running",
            "start_energy": start_energy,
            "energy_valid": start_energy > 0,
            "task_name": task_name or None,
            "task_name_model": model_name or None,
            "task_name_config": config_name or None,
            "config_name": config_name or None,
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

        # 如果能耗无效，尝试重新获取 start_energy
        if not self.coordinator.current_print.get("energy_valid") and self.coordinator.energy_entity:
            current_energy = self.coordinator.get_float_state(self.coordinator.energy_entity)
            if current_energy > 0:
                self.coordinator.current_print["start_energy"] = current_energy
                self.coordinator.current_print["energy_valid"] = True
                LOGGER.info("恢复时重新获取 start_energy: %.4f kWh", current_energy)
        self._validate_colors_on_recovery()
        self._save_current_print()

        self.start_material_cache()
        LOGGER.info("已完整恢复活跃打印记录: %s | 初始颜色: %s (%s)", task_name, filament_color, filament_type)

        # 触发封面图和快照下载
        self.hass.add_job(self.coordinator._delayed_cover_download(task_name or "unknown", start_time))
        self.hass.add_job(self.coordinator._delayed_snapshot_download(task_name or "unknown", start_time))

        # 通过事件循环安全地通知数据更新，避免线程安全违规
        self.hass.loop.call_soon_threadsafe(
            self.coordinator.async_set_updated_data,
            self.coordinator._calculate_statistics()
        )

    def handle_state_change(self, event: Any) -> None:
        """处理状态变化"""
        new_status = event.data.get("new_state")
        if new_status:
            new_status = new_status.state
        else:
            return

        old_status = self.coordinator._previous_status

        # 离线状态不更新 previous_status，保持之前的活跃状态
        if new_status == OFFLINE_STATUS:
            LOGGER.debug("打印机离线，保持之前状态: %s", old_status)
            return

        # 中间过渡状态只更新 previous_status，不触发任何操作
        if new_status in TRANSITIONAL_STATUSES:
            self.coordinator._previous_status = new_status
            LOGGER.debug("中间过渡状态: %s", new_status)
            return

        self.coordinator._previous_status = new_status

        # 开始打印
        if new_status in ACTIVE_PRINT_STATUSES and old_status not in ACTIVE_PRINT_STATUSES:
            if self.coordinator.current_print:
                # current_print 已存在（可能是恢复后的状态更新），只更新状态
                self.coordinator.current_print["status"] = new_status
                self._validate_colors_on_recovery()
                self._save_current_print()
            else:
                # 先检查磁盘是否有持久化数据
                saved = self._load_current_print()
                if saved:
                    self.coordinator.current_print = saved
                    self.coordinator.current_print["status"] = new_status
                    self.coordinator.current_print["_recovered_from_disk"] = True
                    self._recovered_from_disk = True
                    # 如果能耗无效，尝试重新获取 start_energy
                    if not saved.get("energy_valid") and self.coordinator.energy_entity:
                        current_energy = self.coordinator.get_float_state(self.coordinator.energy_entity)
                        if current_energy > 0:
                            self.coordinator.current_print["start_energy"] = current_energy
                            self.coordinator.current_print["energy_valid"] = True
                            LOGGER.info("handle_state_change 恢复时重新获取 start_energy: %.4f kWh", current_energy)
                    self._validate_colors_on_recovery()
                    self._save_current_print()
                    self.start_material_cache()
                else:
                    self.on_print_start()
        # 结束打印
        elif new_status in END_PRINT_STATUSES:
            # 正常情况：从活跃状态变为结束
            if old_status in ACTIVE_PRINT_STATUSES:
                self.hass.add_job(self._on_print_end(new_status))
            # 离线期间完成：current_print 存在但 old_status 不是活跃状态
            elif self.coordinator.current_print:
                LOGGER.info("检测到离线期间完成打印，保存记录: %s", new_status)
                self.hass.add_job(self._on_print_end(new_status))

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
            # 延迟颜色验证（AMS 恢复后重试）
            if self.coordinator.current_print.get("_pending_color_validation"):
                self._validate_colors_on_recovery()
            # 延迟能耗恢复
            if not self.coordinator.current_print.get("energy_valid") and self.coordinator.energy_entity:
                current_energy = self.coordinator.get_float_state(self.coordinator.energy_entity)
                if current_energy > 0:
                    self.coordinator.current_print["start_energy"] = current_energy
                    self.coordinator.current_print["energy_valid"] = True
                    LOGGER.info("延迟恢复 start_energy: %.4f kWh", current_energy)
            # 延迟状态验证（防止恢复后状态已变但未触发事件）
            current_status = self.get_current_status()
            if self._recovered_from_disk:
                self._recovered_from_disk = False  # 首次tick后清除标记
            elif current_status and current_status in END_PRINT_STATUSES:
                LOGGER.info("延迟检测到打印已结束: %s，保存记录", current_status)
                self.hass.add_job(self._on_print_end(current_status))
                return
            elif current_status == PRINT_STATUS_IDLE:
                LOGGER.warning("延迟检测到 idle，视为异常中断")
                self.hass.add_job(self._on_print_end("cancelled"))
                return
            self._cache_print_material_data()
            self._track_color_changes()
            self._cache_delayed_fields()
            self._try_capture_task_name()
            self._cache_chamber_temperature(now)
            # 持久化 current_print 到磁盘
            self._save_current_print()
            # 通过事件循环安全地通知数据更新，避免线程安全违规
            self.hass.loop.call_soon_threadsafe(
                self.coordinator.async_set_updated_data,
                self.coordinator._calculate_statistics()
            )

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

    def _get_ams_known_colors(self) -> set[str]:
        """获取 AMS 中所有已知颜色"""
        colors = set()
        ams_entities = self._get_ams_tray_entities()
        for eid in ams_entities:
            state = self.hass.states.get(eid)
            if not state:
                continue
            color = state.attributes.get("color", "")
            if color and isinstance(color, str):
                colors.add(color.lower())
        return colors

    def _validate_colors_on_recovery(self) -> None:
        """恢复时验证 colors_used，移除不在 AMS 中的误报颜色"""
        cp = self.coordinator.current_print
        if not cp:
            return
        colors_used = cp.get("colors_used", [])
        if not colors_used:
            return
        ams_colors = self._get_ams_known_colors()
        active_type, active_color = self._get_current_filament_info()
        valid_colors = set()
        if active_color:
            valid_colors.add(active_color.lower())
        if ams_colors:
            valid_colors.update(ams_colors)
        LOGGER.info("恢复验证颜色: colors_used=%s, ams=%s, active=%s, valid=%s",
                     colors_used, ams_colors, active_color, valid_colors)
        if not valid_colors:
            # AMS 不可用，标记延迟验证
            cp["_pending_color_validation"] = True
            LOGGER.info("AMS 不可用，标记延迟颜色验证")
            return
        self._do_color_validation(colors_used, valid_colors, active_color)

    def _do_color_validation(self, colors_used: list, valid_colors: set,
                             active_color: str) -> None:
        """执行颜色验证和清理"""
        cp = self.coordinator.current_print
        if not cp:
            return
        cleaned = [c for c in colors_used if c.lower() in valid_colors]
        if len(cleaned) < len(colors_used):
            removed = [c for c in colors_used if c not in cleaned]
            LOGGER.info("恢复时清理误报颜色: %s → %s (移除: %s)", colors_used, cleaned, removed)
            cp["colors_used"] = cleaned
            init_color = cp.get("filament_color", "")
            if init_color and init_color.lower() not in valid_colors:
                cp["filament_color"] = active_color or (cleaned[0] if cleaned else "")
                LOGGER.info("修正 filament_color: %s → %s", init_color, cp["filament_color"])
            color_changes = cp.get("color_changes", [])
            cp["color_changes"] = [cc for cc in color_changes
                                   if cc.get("to_color", "").lower() in valid_colors]
            cp["total_colors"] = len(cleaned)
        else:
            LOGGER.info("恢复验证颜色: 无需清理")
        cp.pop("_pending_color_validation", None)

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
        """捕获任务名称（同时捕获模型名和配置名）"""
        if not self.coordinator.current_print:
            return

        current_name = self.coordinator.current_print.get("task_name")
        current_config = self.coordinator.current_print.get("config_name")

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

        is_param = self._is_param_description(new_name)

        # 非参数描述 → 作为主任务名称（模型名）
        if not is_param:
            if new_name != current_name:
                self.coordinator.current_print["task_name"] = new_name
                self.coordinator._lock_task_name(new_name)
                LOGGER.info("成功捕获任务名称(模型): %s", new_name)
            return

        # 参数描述 → 作为配置名（如 "5mm版"），与模型名共存
        if is_param and new_name != current_name and new_name != current_config:
            self.coordinator.current_print["config_name"] = new_name
            LOGGER.info("捕获到配置名称: %s", new_name)

    def _cache_delayed_fields(self) -> None:
        """缓存延迟字段"""
        if not self.coordinator.current_print:
            return

        current_name = self.coordinator.current_print.get("task_name", "")
        current_config = self.coordinator.current_print.get("config_name")
        raw_task_name = self.coordinator.get_entity_state(self._entity_map.get("task_name", ""), "")

        # 尝试获取更好的模型名（非参数描述）
        need_better_model = not current_name or self._is_param_description(current_name) or current_name.startswith("/data/")
        if need_better_model and raw_task_name and raw_task_name not in INVALID_ENTITY_STATES:
            candidate = self._extract_real_task_name(raw_task_name)
            if candidate and candidate != current_name:
                LOGGER.info("Task name improved: '%s' -> '%s'", (current_name or "")[:40], candidate[:40])
                self.coordinator.current_print["task_name"] = candidate
                self.coordinator._lock_task_name(candidate)
                current_name = candidate

        # 尝试捕获配置名（参数描述，如 "5mm版"）
        if raw_task_name and raw_task_name not in INVALID_ENTITY_STATES:
            is_raw_param = self._is_param_description(raw_task_name)
            if is_raw_param and raw_task_name != current_name and raw_task_name != current_config:
                self.coordinator.current_print["config_name"] = raw_task_name
                LOGGER.info("延迟捕获到配置名称: %s", raw_task_name)

        if not self.coordinator.current_print.get("nozzle_size"):
            nozzle_size = self.coordinator.get_entity_state(self._entity_map.get("nozzle_size", ""), "")
            if nozzle_size:
                self.coordinator.current_print["nozzle_size"] = nozzle_size

        if not self.coordinator.current_print.get("total_layer_count"):
            total_layer_count = self.coordinator.get_float_state(self._entity_map.get("total_layer_count", ""), 0)
            if total_layer_count:
                self.coordinator.current_print["total_layer_count"] = int(total_layer_count)

        if not self.coordinator.current_print.get("speed_profile"):
            speed_profile = self.coordinator.get_entity_state(self._entity_map.get("speed_profile", ""), "")
            if speed_profile and speed_profile not in INVALID_ENTITY_STATES:
                self.coordinator.current_print["speed_profile"] = speed_profile

        if not self.coordinator.current_print.get("energy_valid"):
            start_energy = self.coordinator.get_float_state(self.coordinator.energy_entity)
            if start_energy > 0:
                self.coordinator.current_print["start_energy"] = start_energy
                self.coordinator.current_print["energy_valid"] = True

    def _cache_chamber_temperature(self, now: datetime) -> None:
        """缓存腔体温度"""
        if not self.coordinator.current_print:
            return

        chamber_entity = self.coordinator.chamber_temp_entity
        if not chamber_entity:
            chamber_entity = self._entity_map.get("chamber_temperature")
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

    def _infer_model_name_from_history(self, config_name: str) -> str | None:
        """从历史记录中查找上一次使用该配置名称的打印，获取模型名"""
        if not config_name:
            return None
        target = config_name.strip()
        if not target:
            return None

        searched = 0
        for record in reversed(self.coordinator.history):
            searched += 1
            stored_model = (record.get("task_name_model") or "").strip()
            stored_config = (record.get("task_name_config") or "").strip()
            stored_task = (record.get("task_name") or "").strip()

            if stored_config == target and stored_model:
                LOGGER.info("从历史记录找到上一次使用配置 '%s' 的模型名: %s (搜索了 %d 条)", target, stored_model, searched)
                return stored_model
            if stored_task and " + " in stored_task:
                model_part, config_part = stored_task.rsplit(" + ", 1)
                if config_part == target and model_part.strip() and not self._is_param_description(model_part.strip()):
                    LOGGER.info("从历史记录 task_name 解析出模型名: %s (配置: %s)", model_part.strip(), target)
                    return model_part.strip()
            if stored_task == target and stored_model:
                LOGGER.info("从历史记录 task_name 匹配到模型名: %s", stored_model)
                return stored_model
        LOGGER.debug("历史记录中未找到配置 '%s' 对应的模型名 (共搜索 %d 条)", target, searched)
        return None

    def _extract_model_config_from_states(self, task_states: list, stage_states: list) -> tuple:
        """从 task_name 和 current_stage 历史状态中提取模型名和项目名

        利用 current_stage 的过渡时间精确定位：
        Bambu 在 current_stage 从"空闲"变为"归位工具头/热床预热"时，
        task_name 先显示模型名（几秒），然后切换为项目名/配置名。
        """
        STAGE_IDLE_VALUES = {"idle", "空闲", ""}
        STAGE_START_VALUES = {"homing_toolhead", "heatbed_preheating", "归位工具头", "热床预热"}

        # 找到 current_stage 过渡时间
        transition_time = None
        for i in range(1, len(stage_states)):
            prev_val = (stage_states[i-1].state or "").strip().lower()
            curr_val = (stage_states[i].state or "").strip().lower()
            if prev_val in STAGE_IDLE_VALUES and curr_val in STAGE_START_VALUES:
                transition_time = stage_states[i].last_changed
                break

        model_name = ""
        config_name = ""

        if transition_time and task_states:
            # 方法1：以 current_stage 过渡时间为分界
            try:
                trans_dt = transition_time if isinstance(transition_time, datetime) else \
                           datetime.fromisoformat(str(transition_time).replace("Z", "+00:00"))
            except Exception:
                trans_dt = None

            if trans_dt:
                before_values = []
                after_values = []
                for s in task_states:
                    value = (s.state or "").strip()
                    if not value or value in INVALID_ENTITY_STATES:
                        continue
                    try:
                        s_time = s.last_changed if isinstance(s.last_changed, datetime) else \
                                 datetime.fromisoformat(str(s.last_changed).replace("Z", "+00:00"))
                    except Exception:
                        continue
                    if s_time <= trans_dt:
                        before_values.append(value)
                    else:
                        after_values.append(value)

                # 过渡前的 task_name = 模型名
                for v in before_values:
                    if not self._is_param_description(v):
                        model_name = v
                        break
                    else:
                        config_name = config_name or v

                # 过渡后的 task_name = 项目名/配置名
                if model_name:
                    for v in after_values:
                        if v != model_name and not self._is_param_description(v):
                            config_name = v
                            break
                    if not config_name:
                        for v in after_values:
                            if self._is_param_description(v):
                                config_name = v
                                break

        # 方法2（回退）：按时间顺序
        if not model_name and task_states:
            seen_values = []
            for state in task_states:
                value = (state.state or "").strip()
                if not value or value in INVALID_ENTITY_STATES:
                    continue
                seen_values.append(value)
            if seen_values:
                for v in seen_values:
                    if not self._is_param_description(v):
                        model_name = v
                        break
                    else:
                        config_name = config_name or v
                if model_name:
                    for v in seen_values:
                        if v != model_name and not self._is_param_description(v):
                            config_name = v
                            break

        return model_name, config_name

    async def _infer_model_name_from_entity_history(self, task_entity: str, start_time: str) -> None:
        """从 task_name 和 current_stage 实体的 HA 历史记录中反查模型名和项目名

        利用 current_stage 的过渡时间精确定位模型名：
        Bambu 在 current_stage 从"空闲"变为"归位工具头/热床预热"时，
        task_name 先显示模型名（几秒），然后切换为项目名/配置名。
        """
        if not self.coordinator.current_print or not task_entity or not start_time:
            return
        if self.coordinator.current_print.get("task_name_model"):
            return

        start_dt = self.coordinator._normalize_to_utc(start_time)
        if not start_dt:
            return

        # 同时查询 task_name 和 current_stage
        stage_entity = self._entity_map.get("current_stage", "")
        query_start = start_dt - timedelta(minutes=5)
        query_end = start_dt + timedelta(minutes=5)
        query_entities = [task_entity]
        if stage_entity:
            query_entities.append(stage_entity)

        try:
            history_by_entity = await get_instance(self.hass).async_add_executor_job(
                get_significant_states,
                self.hass,
                query_start,
                query_end,
                query_entities,
                None,
                True,
                False,
            )
        except Exception as err:
            LOGGER.warning("读取实体历史失败: %s", err)
            return

        task_states = history_by_entity.get(task_entity, [])
        stage_states = history_by_entity.get(stage_entity, []) if stage_entity else []

        # 使用共用的推断方法
        model_name, config_name = self._extract_model_config_from_states(task_states, stage_states)

        if not self.coordinator.current_print:
            return
        if model_name:
            self.coordinator.current_print["task_name_model"] = model_name
            self.coordinator.current_print["task_name"] = model_name
            self.coordinator._lock_task_name(model_name)
            LOGGER.info("从 HA 历史反查到模型名: %s", model_name)
        if config_name and not self.coordinator.current_print.get("task_name_config"):
            self.coordinator.current_print["task_name_config"] = config_name
            self.coordinator.current_print["config_name"] = config_name
            LOGGER.info("从 HA 历史反查到配置名: %s", config_name)

    def on_print_start(self) -> None:
        """打印开始"""
        if not self._entity_map.get("print_weight"):
            self.hass.add_job(self.coordinator._discover_entities())

        start_time_entity = self._entity_map.get("start_time")
        start_time_val = self.coordinator.get_entity_state(start_time_entity)
        if start_time_val:
            start_time = self.coordinator._ensure_timezone(start_time_val)
        else:
            start_time = datetime.now(timezone.utc).isoformat()

        task_entity = self._entity_map.get("task_name", "")
        immediate_name = ""
        if task_entity:
            immediate_name = self.coordinator.get_entity_state(task_entity, "") or ""

        self._task_name_variants = []
        model_name = ""
        config_name = ""

        # 优先使用打印开始前预缓存的模型名（来自 task_name 实体变化监听）
        pre_cached_model = self.coordinator._pre_print_model_name
        if pre_cached_model:
            LOGGER.info("使用预缓存的模型名: %s", pre_cached_model)
            model_name = pre_cached_model
            self.coordinator._pre_print_model_name = ""  # 使用后清空

        if immediate_name and immediate_name not in INVALID_ENTITY_STATES:
            self._task_name_variants.append(immediate_name)
            if self._is_param_description(immediate_name):
                config_name = immediate_name
                # 如果没有预缓存模型名，尝试从历史推断
                if not model_name:
                    model_name = self._infer_model_name_from_history(immediate_name) or ""
            else:
                # 当前 task_name 是模型名（非参数描述），直接使用
                if not model_name:
                    model_name = immediate_name

        async def _delayed_task_name_capture() -> None:
            await asyncio.sleep(8)
            if not self.coordinator.current_print:
                return
            delayed_name = self.coordinator.get_entity_state(task_entity, "") or ""
            if not delayed_name or delayed_name in INVALID_ENTITY_STATES or delayed_name in self._task_name_variants:
                return
            self._task_name_variants.append(delayed_name)
            if self._is_param_description(delayed_name):
                if not self.coordinator.current_print.get("task_name_config"):
                    self.coordinator.current_print["task_name_config"] = delayed_name
                    self.coordinator.current_print["config_name"] = delayed_name
                    LOGGER.info("延迟捕获 task_name 配置名: %s", delayed_name)
                return
            if not self.coordinator.current_print.get("task_name_model"):
                self.coordinator.current_print["task_name_model"] = delayed_name
                self.coordinator.current_print["task_name"] = delayed_name
                self.coordinator._lock_task_name(delayed_name)
                LOGGER.info("延迟捕获 task_name 模型名: %s", delayed_name)

        if task_entity:
            self.hass.add_job(_delayed_task_name_capture())
            self.hass.add_job(self._infer_model_name_from_entity_history(task_entity, start_time))

        if config_name and not model_name:
            model_name = self._infer_model_name_from_history(config_name) or ""

        if not model_name:
            for variant in self._task_name_variants:
                if not self._is_param_description(variant):
                    model_name = variant
                    break
        if not config_name:
            for variant in self._task_name_variants:
                if self._is_param_description(variant):
                    config_name = variant
                    break

        task_name = model_name or config_name or ""
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
            "task_name_model": model_name or None,
            "task_name_config": config_name or None,
            "config_name": config_name or None,
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
            "printer_serial": self.coordinator.printer_serial or None,
        }

        self.start_material_cache()
        self._save_current_print()
        LOGGER.info("Print started: %s | 初始颜色: %s (%s)", task_name, filament_color, filament_type)

        self.hass.add_job(self.coordinator._delayed_cover_download(task_name or "unknown", start_time))
        self.hass.add_job(self.coordinator._delayed_snapshot_download(task_name or "unknown", start_time))

        # 通过事件循环安全地通知数据更新，避免线程安全违规
        self.hass.loop.call_soon_threadsafe(
            self.coordinator.async_set_updated_data,
            self.coordinator._calculate_statistics()
        )

    async def _on_print_end(self, end_status: str) -> None:
        """打印结束"""
        self.stop_material_cache()
        self.coordinator._clear_locked_task_name()

        if self.coordinator.current_print is None:
            LOGGER.warning("Print end detected but no active print record")
            return

        # 防重复触发：先检查 → 立即清空 → 再删文件
        cp = self.coordinator.current_print
        self.coordinator.current_print = None
        self._delete_current_print_file()

        end_time = datetime.now(timezone.utc).isoformat()
        start_dt = self.coordinator._normalize_to_utc(cp["start_time"])
        end_dt = self.coordinator._normalize_to_utc(end_time)

        if start_dt and end_dt:
            duration_hours = (end_dt - start_dt).total_seconds() / 3600
        else:
            duration_hours = 0

        progress = 100
        if end_status in (PRINT_STATUS_FAIL, PRINT_STATUS_CANCELLED):
            progress = int(self.coordinator.get_float_state(self._entity_map.get("print_progress", ""), 0))

        total_weight = cp.get("cached_weight") or self.coordinator.get_float_state(self._entity_map.get("print_weight", ""))
        total_length = cp.get("cached_length") or self.coordinator.get_float_state(self._entity_map.get("print_length", ""))

        energy_kwh = None
        if self.coordinator.energy_entity and cp.get("energy_valid"):
            end_energy = self.coordinator.get_float_state(self.coordinator.energy_entity)
            start_energy = cp.get("start_energy", 0)
            delta = end_energy - start_energy
            if 0 < delta < ENERGY_MAX_DELTA_KWH:
                energy_kwh = round(delta, 4)
            elif delta < 0 or delta >= ENERGY_MAX_DELTA_KWH:
                LOGGER.warning("Abnormal energy delta %.2f kWh, skipped", delta)

        task_name = cp.get("task_name") or ""
        config_name = cp.get("config_name") or ""
        # 拼接模型名 + 配置名（如 "宜家洞洞板适配...三重钩 + 5mm版"）
        if config_name and config_name != task_name:
            task_name = f"{task_name} + {config_name}"
        cover_image_url = cp.get("cover_image_url") or ""
        cover_image_local = cp.get("cover_image_local")
        start_time = cp.get("start_time") or ""

        if not cover_image_local and self.coordinator.image_manager:
            cover_image_local = await self.coordinator.image_manager._download_cover_from_cloud(task_name, end_time, start_time)
        if not cover_image_local and self.coordinator.image_manager:
            cover_image_local = await self.coordinator.image_manager._download_cover_image(cover_image_url, task_name, end_time)

        # 实时颜色 AMS 验证：移除不在 AMS 中的误报颜色
        ams_colors = self._get_ams_known_colors()
        if ams_colors and cp.get("colors_used"):
            _, active_color = self._get_current_filament_info()
            valid = set(ams_colors)
            if active_color:
                valid.add(active_color.lower())
            cleaned = [c for c in cp["colors_used"] if c.lower() in valid]
            if len(cleaned) < len(cp["colors_used"]):
                LOGGER.info("打印结束时清理误报颜色: %s → %s", cp["colors_used"], cleaned)
                cp["colors_used"] = cleaned
                cp["total_colors"] = len(cleaned)

        colors_used, types_used, color_changes, color_usage, total_colors, multi_color_summary, clean_color_usage = \
            self.coordinator._build_color_data(end_status, progress)

        chamber_temp_last5min, chamber_temp_final = self.coordinator._build_chamber_temp_data(end_dt)

        base_record = {
            "id": cp["id"],
            "start_time": cp["start_time"],
            "end_time": end_time,
            "duration_hours": round(duration_hours, 2),
            "status": end_status,
            "progress": progress,
            "total_weight": round(total_weight, 2) if total_weight else None,
            "total_length": round(total_length, 2) if total_length else None,
            "filament_type": types_used[0] if types_used else cp.get("filament_type"),
            "filament_color": colors_used[0] if colors_used else cp.get("filament_color"),
            "colors_used": colors_used,
            "types_used": types_used,
            "total_colors": total_colors,
            "color_changes_count": len(color_changes),
            "multi_color_summary": multi_color_summary,
            "color_usage": clean_color_usage,
            "energy_kwh": round(energy_kwh, 4) if energy_kwh else None,
            "task_name": task_name or None,
            "task_name_model": cp.get("task_name_model") or None,
            "task_name_config": cp.get("task_name_config") or None,
            "config_name": cp.get("task_name_config") or None,
            "nozzle_type": cp.get("nozzle_type"),
            "nozzle_size": cp.get("nozzle_size"),
            "speed_profile": cp.get("speed_profile"),
            "print_bed_type": cp.get("print_bed_type"),
            "total_layer_count": cp.get("total_layer_count"),
            "cover_image_url": cover_image_url or None,
            "chamber_temp_final": chamber_temp_final,
            "chamber_temp_last5min": chamber_temp_last5min,
        }

        snapshot_image_local = cp.get("snapshot_image_local")
        if not snapshot_image_local and self.coordinator.image_manager:
            full_print_info, snapshot_image_local = await asyncio.gather(
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
        self.hass.async_create_task(self.coordinator._save_history())
        # 通知 coordinator 数据已更新，触发 sensor 属性重新计算
        self.coordinator.async_set_updated_data(self.coordinator._calculate_statistics())
        LOGGER.info("Print ended: status=%s, duration=%.2f hours", end_status, duration_hours)

    async def backfill_model_names_from_history(self) -> int:
        """从 HA 实体历史反查补全历史记录的模型名和项目名"""
        task_entity = self._entity_map.get("task_name", "")
        stage_entity = self._entity_map.get("current_stage", "")
        if not task_entity:
            LOGGER.warning("backfill_model_names: task_name 实体未找到")
            return 0

        updated = 0
        for record in self.coordinator.history:
            model = (record.get("task_name_model") or "").strip()
            if model:
                continue
            start_time = record.get("start_time", "")
            if not start_time:
                continue
            start_dt = self.coordinator._normalize_to_utc(start_time)
            if not start_dt:
                continue

            query_start = start_dt - timedelta(minutes=5)
            query_end = start_dt + timedelta(minutes=5)
            query_entities = [task_entity]
            if stage_entity:
                query_entities.append(stage_entity)

            try:
                history_by_entity = await get_instance(self.hass).async_add_executor_job(
                    get_significant_states, self.hass, query_start, query_end,
                    query_entities, None, False, False)
            except Exception as err:
                continue

            if not isinstance(history_by_entity, dict):
                continue

            task_states = history_by_entity.get(task_entity, [])
            stage_states = history_by_entity.get(stage_entity, []) if stage_entity else []
            model_name, config_name = self._extract_model_config_from_states(task_states, stage_states)

            if model_name:
                record["task_name_model"] = model_name
                old_task = record.get("task_name", "")
                if not old_task or self._is_param_description(old_task) or old_task.startswith("/data/"):
                    record["task_name"] = model_name
                if config_name and config_name != model_name:
                    record["task_name_config"] = config_name
                    old_task = record.get("task_name", "")
                    if " + " not in old_task:
                        record["task_name"] = f"{model_name} + {config_name}"
                updated += 1

        if updated > 0:
            await self.coordinator._save_history()
            if self.coordinator.statistics:
                self.coordinator.statistics.invalidate_cache()
            self.coordinator.async_set_updated_data(self.coordinator._calculate_statistics())
        return updated
