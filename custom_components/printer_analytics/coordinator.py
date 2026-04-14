from __future__ import annotations

import json
import logging
import os
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant, Event, callback
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry
from homeassistant.helpers.device_registry import async_get as async_get_device_registry
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    ACTIVE_PRINT_STATUSES,
    BAMBULAB_ENTITY_KEYS,
    BAMBULAB_IMAGE_KEYS,
    BAMBULAB_CAMERA_KEYS,
    CONF_ENERGY_ENTITY,
    CONF_POWER_ENTITY,
    CONF_PRINTER_NAME,
    CONF_PRINT_STATUS_ENTITY,
    DURATION_BUCKETS,
    DOMAIN,
    END_PRINT_STATUSES,
    HISTORY_VERSION,
    MAX_HISTORY_RECORDS,
    PRINT_STATUS_FAIL,
    PRINT_STATUS_FINISH,
    PRINT_STATUS_IDLE,
    PRINT_STATUS_RUNNING,
)

LOGGER = logging.getLogger(__name__)


@dataclass
class PrinterStats:
    total_prints: int = 0
    successful_prints: int = 0
    failed_prints: int = 0
    cancelled_prints: int = 0
    success_rate: float = 0.0
    average_duration_minutes: float = 0.0
    total_duration_minutes: float = 0.0
    total_weight_g: float = 0.0
    total_length_m: float = 0.0
    total_energy_kwh: float = 0.0
    stats_7d: dict = field(default_factory=dict)
    stats_30d: dict = field(default_factory=dict)
    stats_lifetime: dict = field(default_factory=dict)
    duration_distribution: dict = field(default_factory=dict)
    activity_heatmap: dict = field(default_factory=dict)
    history: list = field(default_factory=list)
    current_print: dict | None = None
    is_printing: bool = False
    last_update: str = ""


class PrinterAnalyticsCoordinator(DataUpdateCoordinator[PrinterStats]):
    def __init__(self, hass: HomeAssistant, entry) -> None:
        super().__init__(
            hass,
            logger=LOGGER,
            name=f"Printer Analytics - {entry.data.get(CONF_PRINTER_NAME, 'Unknown')}",
            update_interval=timedelta(minutes=5),
        )
        self.entry = entry
        self.printer_name: str = entry.data.get(CONF_PRINTER_NAME, "Printer")
        self.print_status_entity: str = entry.data.get(CONF_PRINT_STATUS_ENTITY, "")
        self.power_entity: str = entry.data.get(CONF_POWER_ENTITY, "")
        self.energy_entity: str = entry.data.get(CONF_ENERGY_ENTITY, "")

        self.history: list[dict] = []
        self.current_print: dict | None = None
        self._previous_status: str | None = None
        self._entity_map: dict[str, str] = {}
        self._unsub_listener = None

        self._history_dir = hass.config.path(".printer_analytics")
        self._history_file = os.path.join(
            self._history_dir, f"{entry.entry_id}.json"
        )
        self._images_dir = hass.config.path("www", "printer_analytics")

    async def async_setup(self) -> None:
        await self._load_history()
        await self._discover_entities()
        self._previous_status = self._get_current_print_status()
        if self._previous_status in ACTIVE_PRINT_STATUSES:
            self._recover_active_print()
        self._unsub_listener = async_track_state_change_event(
            self.hass, [self.print_status_entity], self._handle_state_change
        )
        LOGGER.info(
            "Printer Analytics setup for %s, monitoring %s, discovered entities: %s",
            self.printer_name,
            self.print_status_entity,
            self._entity_map,
        )

    async def async_shutdown(self) -> None:
        if self._unsub_listener:
            self._unsub_listener()
            self._unsub_listener = None
        await self._save_history()

    async def _load_history(self) -> None:
        try:
            def _load():
                os.makedirs(self._history_dir, exist_ok=True)
                if not os.path.exists(self._history_file):
                    return None
                with open(self._history_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            data = await self.hass.async_add_executor_job(_load)
            if data:
                version = data.get("version", 1)
                self.history = data.get("history", [])
                if version < HISTORY_VERSION:
                    for record in self.history:
                        for key in ("task_name", "nozzle_type", "nozzle_size",
                                    "print_bed_type", "total_layer_count",
                                    "cover_image_url", "cover_image_local",
                                    "snapshot_image_local", "full_print_info_path"):
                            record.setdefault(key, None)
                        old_ft = record.get("filament_type")
                        if old_ft and not isinstance(old_ft, str):
                            record["filament_type"] = str(old_ft)
                    LOGGER.info(
                        "Migrated history from v%d to v%d for %s",
                        version, HISTORY_VERSION, self.printer_name,
                    )
                LOGGER.info(
                    "Loaded %d history records for %s",
                    len(self.history),
                    self.printer_name,
                )
                return
            self.history = []
        except Exception as err:
            LOGGER.error("Failed to load history for %s: %s", self.printer_name, err)
            self.history = []

    async def _save_history(self) -> None:
        try:
            def _write():
                os.makedirs(self._history_dir, exist_ok=True)
                data = {
                    "version": HISTORY_VERSION,
                    "printer_name": self.printer_name,
                    "history": self.history[-MAX_HISTORY_RECORDS:],
                }
                with open(self._history_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            await self.hass.async_add_executor_job(_write)
        except Exception as err:
            LOGGER.error("Failed to save history for %s: %s", self.printer_name, err)

    async def _discover_entities(self) -> None:
        try:
            entity_reg = async_get_entity_registry(self.hass)
            device_reg = async_get_device_registry(self.hass)
            reg_entry = entity_reg.async_get(self.print_status_entity)
            if reg_entry is None or reg_entry.device_id is None:
                LOGGER.warning(
                    "Could not find device for %s", self.print_status_entity
                )
                return
            entities = entity_reg.async_entries_for_device(
                reg_entry.device_id
            )
            for ent in entities:
                for key, suffix in BAMBULAB_ENTITY_KEYS.items():
                    if ent.unique_id.endswith(f"_{suffix}"):
                        self._entity_map[key] = ent.entity_id
                        break
                for key, suffix in BAMBULAB_IMAGE_KEYS.items():
                    if ent.unique_id.endswith(f"_{suffix}") and ent.domain == "image":
                        self._entity_map[key] = ent.entity_id
                        break
                for key, suffix in BAMBULAB_CAMERA_KEYS.items():
                    if ent.unique_id.endswith(f"_{suffix}") and ent.domain == "camera":
                        self._entity_map[key] = ent.entity_id
                        break
            LOGGER.info(
                "Discovered entities for %s: %s",
                self.printer_name,
                self._entity_map,
            )
        except Exception as err:
            LOGGER.error(
                "Entity discovery failed for %s: %s", self.printer_name, err
            )

    def _get_entity_state(self, entity_id: str, default: Any = None) -> Any:
        if not entity_id:
            return default
        state = self.hass.states.get(entity_id)
        if state is None:
            return default
        return state.state

    def _get_entity_attr(self, entity_id: str, attr: str, default: Any = None) -> Any:
        if not entity_id:
            return default
        state = self.hass.states.get(entity_id)
        if state is None:
            return default
        return state.attributes.get(attr, default)

    def _get_float_state(self, entity_id: str, default: float = 0.0) -> float:
        val = self._get_entity_state(entity_id)
        if val is None or val in ("unknown", "unavailable", ""):
            return default
        try:
            return float(val)
        except (ValueError, TypeError):
            return default

    def _get_current_print_status(self) -> str | None:
        state = self.hass.states.get(self.print_status_entity)
        if state is None:
            return None
        return state.state

    def _recover_active_print(self) -> None:
        self.current_print = {
            "id": str(uuid.uuid4()),
            "start_time": datetime.now(timezone.utc).isoformat(),
            "status": "running",
            "start_energy": self._get_float_state(self.energy_entity),
        }
        self._previous_status = PRINT_STATUS_RUNNING
        LOGGER.info("Recovered active print for %s", self.printer_name)

    @callback
    def _handle_state_change(self, event: Event) -> None:
        entity_id = event.data.get("entity_id")
        if entity_id != self.print_status_entity:
            return
        new_state = event.data.get("new_state")
        if new_state is None:
            return
        new_status = new_state.state
        if new_status in ("unknown", "unavailable"):
            return
        old_status = self._previous_status
        if old_status == new_status:
            return
        LOGGER.debug(
            "Print status change for %s: %s -> %s",
            self.printer_name, old_status, new_status,
        )
        if old_status not in ACTIVE_PRINT_STATUSES and new_status == PRINT_STATUS_RUNNING:
            self._on_print_start()
        elif old_status in ACTIVE_PRINT_STATUSES and new_status in END_PRINT_STATUSES:
            self.hass.async_create_task(self._on_print_end(new_status))
        elif old_status in ACTIVE_PRINT_STATUSES and new_status == PRINT_STATUS_IDLE:
            self.hass.async_create_task(self._on_print_end("cancelled"))
        self._previous_status = new_status
        self.async_set_updated_data(self._calculate_statistics())

    def _on_print_start(self) -> None:
        start_time_entity = self._entity_map.get("start_time")
        if start_time_entity:
            start_time_val = self._get_entity_state(start_time_entity)
            start_time = start_time_val if start_time_val else datetime.now(timezone.utc).isoformat()
        else:
            start_time = datetime.now(timezone.utc).isoformat()
        task_name = self._get_entity_state(self._entity_map.get("task_name", ""), "")
        nozzle_type = self._get_entity_state(self._entity_map.get("nozzle_type", ""), "")
        nozzle_size = self._get_entity_state(self._entity_map.get("nozzle_size", ""), "")
        print_bed_type = self._get_entity_state(self._entity_map.get("print_bed_type", ""), "")
        total_layer_count = self._get_float_state(self._entity_map.get("total_layer_count", ""), 0)
        filament_type = self._get_entity_attr(
            self._entity_map.get("active_tray", ""), "name", ""
        )
        filament_color = self._get_entity_attr(
            self._entity_map.get("active_tray", ""), "color", ""
        )
        cover_image_url = self._get_entity_attr(
            self._entity_map.get("cover_image", ""), "entity_picture", ""
        )
        self.current_print = {
            "id": str(uuid.uuid4()),
            "start_time": start_time,
            "status": "running",
            "start_energy": self._get_float_state(self.energy_entity),
            "task_name": task_name or None,
            "nozzle_type": nozzle_type or None,
            "nozzle_size": nozzle_size or None,
            "print_bed_type": print_bed_type or None,
            "total_layer_count": int(total_layer_count) if total_layer_count else None,
            "filament_type": filament_type or None,
            "filament_color": filament_color or None,
            "cover_image_url": cover_image_url or None,
        }
        LOGGER.info("Print started on %s: %s", self.printer_name, task_name)

    async def _download_cover_image(self, image_url: str, task_name: str, end_time: str) -> str | None:
        if not image_url:
            return None
        try:
            safe_name = re.sub(r'[\\/:*?"<>|]', '_', task_name or "unknown")
            safe_time = re.sub(r'[^\dT]', '_', end_time[:19])
            filename = f"{safe_name}_{safe_time}.jpg"

            def _ensure_dir():
                os.makedirs(self._images_dir, exist_ok=True)
            await self.hass.async_add_executor_job(_ensure_dir)

            filepath = os.path.join(self._images_dir, filename)
            base_url = self.hass.config.api.base_url if hasattr(self.hass.config.api, 'base_url') else f"http://127.0.0.1:{self.hass.config.api.port}"
            full_url = f"{base_url}{image_url}"
            async with aiohttp.ClientSession() as session:
                async with session.get(full_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        LOGGER.warning("Failed to download cover image: HTTP %d", resp.status)
                        return None
                    content = await resp.read()

            def _write():
                with open(filepath, "wb") as f:
                    f.write(content)
            await self.hass.async_add_executor_job(_write)
            local_path = f"/local/printer_analytics/{filename}"
            LOGGER.info("Cover image saved: %s", local_path)
            return local_path
        except Exception as err:
            LOGGER.error("Failed to download cover image: %s", err)
            return None

    async def _save_full_print_info(self, record: dict, end_time: str) -> str | None:
        try:
            safe_name = re.sub(r'[\\/:*?"<>|]', '_', record.get("task_name", "unknown"))
            safe_time = re.sub(r'[^\dT]', '_', end_time[:19])
            filename = f"{safe_name}_{safe_time}.json"
            
            def _ensure_dir():
                info_dir = os.path.join(self._images_dir, "print_info")
                os.makedirs(info_dir, exist_ok=True)
                return info_dir
            info_dir = await self.hass.async_add_executor_job(_ensure_dir)
            
            filepath = os.path.join(info_dir, filename)
            
            full_info = {
                "record": record,
                "printer_name": self.printer_name,
                "print_status_entity": self.print_status_entity,
                "timestamp": end_time,
                "entities": {},
            }
            
            for key, entity_id in self._entity_map.items():
                try:
                    state = self.hass.states.get(entity_id)
                    if state:
                        full_info["entities"][key] = {
                            "state": state.state,
                            "attributes": state.attributes,
                        }
                except Exception as e:
                    LOGGER.warning("Failed to get entity %s: %s", entity_id, e)
            
            def _write():
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(full_info, f, ensure_ascii=False, indent=2)
            await self.hass.async_add_executor_job(_write)
            
            local_path = f"/local/printer_analytics/print_info/{filename}"
            LOGGER.info("Full print info saved: %s", local_path)
            return local_path
        except Exception as err:
            LOGGER.error("Failed to save full print info: %s", err)
            return None

    async def _download_print_snapshot(self, end_time: str, task_name: str) -> str | None:
        try:
            camera_entity = self._entity_map.get("camera")
            if not camera_entity:
                return None
            
            safe_name = re.sub(r'[\\/:*?"<>|]', '_', task_name or "unknown")
            safe_time = re.sub(r'[^\dT]', '_', end_time[:19])
            filename = f"{safe_name}_{safe_time}_snapshot.jpg"
            
            def _ensure_dir():
                snapshots_dir = os.path.join(self._images_dir, "snapshots")
                os.makedirs(snapshots_dir, exist_ok=True)
                return snapshots_dir
            snapshots_dir = await self.hass.async_add_executor_job(_ensure_dir)
            
            filepath = os.path.join(snapshots_dir, filename)
            base_url = self.hass.config.api.base_url if hasattr(self.hass.config.api, 'base_url') else f"http://127.0.0.1:{self.hass.config.api.port}"
            snapshot_url = f"{base_url}/api/camera_proxy/{camera_entity}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(snapshot_url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status != 200:
                        LOGGER.warning("Failed to download snapshot: HTTP %d", resp.status)
                        return None
                    content = await resp.read()
            
            def _write():
                with open(filepath, "wb") as f:
                    f.write(content)
            await self.hass.async_add_executor_job(_write)
            
            local_path = f"/local/printer_analytics/snapshots/{filename}"
            LOGGER.info("Print snapshot saved: %s", local_path)
            return local_path
        except Exception as err:
            LOGGER.error("Failed to download print snapshot: %s", err)
            return None

    async def _on_print_end(self, end_status: str) -> None:
        if self.current_print is None:
            LOGGER.warning(
                "Print end detected for %s but no active print record", self.printer_name
            )
            return
        end_time = datetime.now(timezone.utc).isoformat()
        try:
            start_dt = datetime.fromisoformat(self.current_print["start_time"])
            end_dt = datetime.fromisoformat(end_time)
            duration_minutes = (end_dt - start_dt).total_seconds() / 60
        except (ValueError, TypeError):
            duration_minutes = 0
        progress = 100
        if end_status in (PRINT_STATUS_FAIL, "cancelled"):
            progress = int(self._get_float_state(
                self._entity_map.get("print_progress", ""), 0
            ))
        total_weight = self._get_float_state(
            self._entity_map.get("print_weight", "")
        )
        total_length = self._get_float_state(
            self._entity_map.get("print_length", "")
        )
        energy_kwh = 0.0
        if self.energy_entity:
            end_energy = self._get_float_state(self.energy_entity)
            start_energy = self.current_print.get("start_energy", 0)
            energy_kwh = max(0, end_energy - start_energy)
        task_name = self.current_print.get("task_name") or ""
        cover_image_url = self.current_print.get("cover_image_url") or ""
        cover_image_local = await self._download_cover_image(
            cover_image_url, task_name, end_time
        )
        
        # 保存完整打印信息文档和快照
        # 先构建记录，然后保存完整信息和快照
        temp_record = {
            "id": self.current_print["id"],
            "start_time": self.current_print["start_time"],
            "end_time": end_time,
            "duration_minutes": round(duration_minutes, 1),
            "status": end_status,
            "progress": progress,
            "total_weight": round(total_weight, 2) if total_weight else None,
            "total_length": round(total_length, 2) if total_length else None,
            "filament_type": self.current_print.get("filament_type"),
            "filament_color": self.current_print.get("filament_color"),
            "energy_kwh": round(energy_kwh, 4) if energy_kwh else None,
            "task_name": task_name or None,
            "nozzle_type": self.current_print.get("nozzle_type"),
            "nozzle_size": self.current_print.get("nozzle_size"),
            "print_bed_type": self.current_print.get("print_bed_type"),
            "total_layer_count": self.current_print.get("total_layer_count"),
            "cover_image_url": cover_image_url or None,
        }
        # 并行处理保存完整信息和下载快照
        import asyncio
        full_print_info, snapshot_image_local = await asyncio.gather(
            self._save_full_print_info(temp_record, end_time),
            self._download_print_snapshot(end_time, task_name)
        )
        record = {
            "id": self.current_print["id"],
            "start_time": self.current_print["start_time"],
            "end_time": end_time,
            "duration_minutes": round(duration_minutes, 1),
            "status": end_status,
            "progress": progress,
            "total_weight": round(total_weight, 2) if total_weight else None,
            "total_length": round(total_length, 2) if total_length else None,
            "filament_type": self.current_print.get("filament_type"),
            "filament_color": self.current_print.get("filament_color"),
            "energy_kwh": round(energy_kwh, 4) if energy_kwh else None,
            "task_name": task_name or None,
            "nozzle_type": self.current_print.get("nozzle_type"),
            "nozzle_size": self.current_print.get("nozzle_size"),
            "print_bed_type": self.current_print.get("print_bed_type"),
            "total_layer_count": self.current_print.get("total_layer_count"),
            "cover_image_url": cover_image_url or None,
            "cover_image_local": cover_image_local,
            "snapshot_image_local": snapshot_image_local,
            "full_print_info_path": full_print_info,
        }
        self.history.append(record)
        if len(self.history) > MAX_HISTORY_RECORDS:
            self.history = self.history[-MAX_HISTORY_RECORDS:]
        self.current_print = None
        self.hass.async_create_task(self._save_history())
        LOGGER.info(
            "Print ended on %s: status=%s, duration=%.1f min",
            self.printer_name, end_status, duration_minutes,
        )

    def _calculate_statistics(self) -> PrinterStats:
        stats = PrinterStats()
        now = datetime.now(timezone.utc)
        seven_days_ago = now - timedelta(days=7)
        thirty_days_ago = now - timedelta(days=30)
        
        # 预计算常用数据，避免多次遍历历史记录
        total_prints = len(self.history)
        successful = []
        failed = []
        cancelled = []
        completed_with_duration = []
        total_weight = 0.0
        failed_weight = 0.0
        total_length = 0.0
        failed_length = 0.0
        total_energy = 0.0
        
        for r in self.history:
            status = r.get("status")
            if status == PRINT_STATUS_FINISH:
                successful.append(r)
                total_weight += r.get("total_weight", 0) or 0
                total_length += r.get("total_length", 0) or 0
            elif status == PRINT_STATUS_FAIL:
                failed.append(r)
                if r.get("total_weight"):
                    failed_weight += (r.get("total_weight", 0) or 0) * (r.get("progress", 0) or 0) / 100
                if r.get("total_length"):
                    failed_length += (r.get("total_length", 0) or 0) * (r.get("progress", 0) or 0) / 100
            elif status == "cancelled":
                cancelled.append(r)
            
            duration = r.get("duration_minutes")
            if duration and duration > 0:
                completed_with_duration.append(r)
            
            total_energy += r.get("energy_kwh", 0) or 0
        
        # 计算基本统计数据
        stats.total_prints = total_prints
        stats.successful_prints = len(successful)
        stats.failed_prints = len(failed)
        stats.cancelled_prints = len(cancelled)
        stats.success_rate = (
            round(len(successful) / total_prints * 100, 1) if total_prints > 0 else 0
        )
        
        # 计算时长统计
        if completed_with_duration:
            total_duration = sum(r["duration_minutes"] for r in completed_with_duration)
            stats.total_duration_minutes = round(total_duration, 1)
            stats.average_duration_minutes = round(total_duration / len(completed_with_duration), 1)
        
        # 计算耗材统计
        stats.total_weight_g = round(total_weight + failed_weight, 2)
        stats.total_length_m = round(total_length + failed_length, 2)
        stats.total_energy_kwh = round(total_energy, 4)
        
        # 计算时间过滤统计
        stats.stats_lifetime = self._calc_time_filtered_stats(self.history, None)
        stats.stats_7d = self._calc_time_filtered_stats(self.history, seven_days_ago)
        stats.stats_30d = self._calc_time_filtered_stats(self.history, thirty_days_ago)
        
        # 计算分布和热力图
        stats.duration_distribution = self._calc_duration_distribution()
        stats.activity_heatmap = self._calc_activity_heatmap()
        
        # 设置其他数据
        stats.history = self.history[-50:]
        stats.current_print = self.current_print
        stats.is_printing = self.current_print is not None
        stats.last_update = now.isoformat()
        return stats

    def _calc_time_filtered_stats(
        self, history: list[dict], cutoff: datetime | None
    ) -> dict:
        total = 0
        success = 0
        failed = 0
        weight = 0.0
        length = 0.0
        energy = 0.0
        durations = []
        
        for r in history:
            # 检查时间是否在 cutoff 之后
            if cutoff:
                end_time = self._parse_time(r.get("end_time", ""))
                if end_time is None or end_time < cutoff:
                    continue
            
            total += 1
            status = r.get("status")
            
            if status == PRINT_STATUS_FINISH:
                success += 1
                weight += r.get("total_weight", 0) or 0
                length += r.get("total_length", 0) or 0
            elif status == PRINT_STATUS_FAIL:
                failed += 1
                if r.get("total_weight"):
                    weight += (r.get("total_weight", 0) or 0) * (r.get("progress", 0) or 0) / 100
                if r.get("total_length"):
                    length += (r.get("total_length", 0) or 0) * (r.get("progress", 0) or 0) / 100
            
            energy += r.get("energy_kwh", 0) or 0
            duration = r.get("duration_minutes")
            if duration and duration > 0:
                durations.append(duration)
        
        avg_duration = round(sum(durations) / len(durations), 1) if durations else 0
        return {
            "total_prints": total,
            "successful": success,
            "failed": failed,
            "success_rate": round(success / total * 100, 1) if total > 0 else 0,
            "total_weight_g": round(weight, 2),
            "total_length_m": round(length, 2),
            "total_energy_kwh": round(energy, 4),
            "average_duration_minutes": avg_duration,
        }

    def _calc_duration_distribution(self) -> dict:
        dist = {label: 0 for label, _, _ in DURATION_BUCKETS}
        # 缓存 DURATION_BUCKETS 以避免每次循环都访问
        buckets = list(DURATION_BUCKETS)
        for record in self.history:
            duration = record.get("duration_minutes", 0) or 0
            if duration <= 0:
                continue
            # 使用快速查找
            for label, low, high in buckets:
                if low <= duration < high:
                    dist[label] += 1
                    break
        return dist

    def _calc_activity_heatmap(self) -> dict:
        heatmap: dict[str, int] = {}
        for record in self.history:
            end_time_str = record.get("end_time", "")
            if not end_time_str:
                continue
            end_time = self._parse_time(end_time_str)
            if end_time is None:
                continue
            date_key = end_time.strftime("%Y-%m-%d")
            # 使用字典的 get 方法提高性能
            heatmap[date_key] = heatmap.get(date_key, 0) + 1
        return heatmap

    # 缓存时间解析结果，避免重复解析相同的时间字符串
    _time_parse_cache: dict[str, datetime | None] = {}
    
    @classmethod
    def _parse_time(cls, time_str: str) -> datetime | None:
        if not time_str:
            return None
        
        # 检查缓存
        if time_str in cls._time_parse_cache:
            return cls._time_parse_cache[time_str]
        
        try:
            result = datetime.fromisoformat(time_str)
            cls._time_parse_cache[time_str] = result
            return result
        except (ValueError, TypeError):
            cls._time_parse_cache[time_str] = None
            return None

    async def _async_update_data(self) -> PrinterStats:
        return self._calculate_statistics()

    async def async_reset_history(self) -> None:
        self.history = []
        self.current_print = None
        await self._save_history()
        self.async_set_updated_data(self._calculate_statistics())
        LOGGER.info("History reset for %s", self.printer_name)

    def update_options(self, options: dict) -> None:
        self.power_entity = options.get(CONF_POWER_ENTITY, self.power_entity)
        self.energy_entity = options.get(CONF_ENERGY_ENTITY, self.energy_entity)
        if CONF_PRINTER_NAME in options:
            self.printer_name = options[CONF_PRINTER_NAME]
