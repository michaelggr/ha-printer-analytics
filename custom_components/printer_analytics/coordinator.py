"""Printer Analytics Coordinator - 主协调器"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, Event, callback
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry
from homeassistant.helpers.device_registry import async_get as async_get_device_registry
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    ACTIVE_PRINT_STATUSES,
    CHAMBER_TEMP_WINDOW_MINUTES,
    CONF_CHAMBER_TEMP_ENTITY,
    CONF_ENERGY_ENTITY,
    CONF_POWER_ENTITY,
    CONF_PRINTER_NAME,
    CONF_PRINT_STATUS_ENTITY,
    HTTP_CONNECTION_LIMIT,
    HTTP_CONNECTION_PER_HOST,
    HTTP_SESSION_TIMEOUT_SECS,
    INVALID_ENTITY_STATES,
    MATERIAL_CACHE_INTERVAL_SECONDS,
    PRINT_STATUS_CANCELLED,
    PRINT_STATUS_FAIL,
    PRINT_STATUS_FINISH,
    PRINT_STATUS_IDLE,
    PRINT_STATUS_RUNNING,
    TASK_NAME_CAPTURE_WINDOW_SECS,
)
from .utils import SecureFileHandler, is_param_description

from .data_models import PrinterStats
from .storage import StorageManager
from .entity_discovery import EntityDiscovery
from .print_tracker import PrintTracker
from .image_manager import ImageManager
from .statistics import StatisticsCalculator

LOGGER = logging.getLogger(__name__)


class PrinterAnalyticsCoordinator(DataUpdateCoordinator[PrinterStats]):
    """Printer Analytics 主协调器"""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            logger=LOGGER,
            name=f"Printer Analytics - {entry.data.get(CONF_PRINTER_NAME, 'Unknown')}",
        )
        self.entry = entry
        self.printer_name: str = entry.data.get(CONF_PRINTER_NAME, "Printer")
        self.print_status_entity: str = entry.data.get(CONF_PRINT_STATUS_ENTITY, "")
        self.power_entity: str = entry.data.get(CONF_POWER_ENTITY, "")
        self.energy_entity: str = entry.data.get(CONF_ENERGY_ENTITY, "")
        self.chamber_temp_entity: str = entry.data.get(CONF_CHAMBER_TEMP_ENTITY, "")

        self.history: list[dict] = []
        self.current_print: dict | None = None
        self._previous_status: str | None = None
        self._entity_map: dict[str, str] = {}
        self._locked_task_name: str = ""
        self._unsub_listener = None
        self._material_cache_interval = None
        self._http_session: aiohttp.ClientSession | None = None
        self._time_cache: dict[str, datetime] = {}

        # 存储路径
        self._history_base_dir = hass.config.path(".printer_analytics")
        self._history_dir = os.path.join(self._history_base_dir, "history_by_year")
        self._archive_dir = os.path.join(self._history_base_dir, "archives")
        self._exports_dir = os.path.join(self._history_base_dir, "exports")
        self._ha_backup_dir = hass.config.path("www", "printer_analytics_data")
        self._legacy_history_file = os.path.join(self._history_base_dir, f"{entry.entry_id}.json")
        self._images_dir = hass.config.path("www", "printer_analytics")

        # 数据统计
        self._total_records = 0
        self._yearly_stats: dict[str, int] = {}

        # 子模块
        self.storage: StorageManager | None = None
        self.entity_discovery: EntityDiscovery | None = None
        self.print_tracker: PrintTracker | None = None
        self.image_manager: ImageManager | None = None
        self.statistics: StatisticsCalculator | None = None

    async def async_setup(self) -> None:
        """初始化设置"""
        self.storage = StorageManager(self)
        self.entity_discovery = EntityDiscovery(self)
        self.print_tracker = PrintTracker(self)
        self.image_manager = ImageManager(self)
        self.statistics = StatisticsCalculator(self)

        await self._load_history()
        await self.entity_discovery.discover()
        await self.hass.async_add_executor_job(self.image_manager.detect_placeholder_images)

        # 如果配置中没有指定打印状态实体，使用自动发现的实体
        if not self.print_status_entity:
            self.print_status_entity = self._entity_map.get("print_status", "")
        
        self._previous_status = self._get_current_print_status()
        if self._previous_status in ACTIVE_PRINT_STATUSES:
            self.print_tracker.recover_active_print()

        # 订阅状态变化
        if self.print_status_entity:
            self._unsub_listener = async_track_state_change_event(
                self.hass, [self.print_status_entity], self._handle_state_change
            )
        else:
            LOGGER.warning("No print status entity configured for %s, state changes will not be tracked", self.printer_name)
        LOGGER.info("Printer Analytics setup for %s", self.printer_name)

    async def async_shutdown(self) -> None:
        """关闭清理"""
        if self.print_tracker:
            self.print_tracker.stop_material_cache()
        if self._unsub_listener:
            self._unsub_listener()
            self._unsub_listener = None
        await self._close_http_session()
        await self._save_history()

    async def _get_http_session(self) -> aiohttp.ClientSession:
        """获取共享HTTP会话"""
        if self._http_session is None or self._http_session.closed:
            self._http_session = aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(
                    limit=HTTP_CONNECTION_LIMIT,
                    limit_per_host=HTTP_CONNECTION_PER_HOST,
                    force_close=False,
                    enable_cleanup_closed=True,
                ),
                timeout=aiohttp.ClientTimeout(total=HTTP_SESSION_TIMEOUT_SECS),
            )
        return self._http_session

    def _get_ha_base_url(self) -> str:
        """获取HA基础URL"""
        if hasattr(self.hass.config.api, 'base_url'):
            return self.hass.config.api.base_url
        return f"http://127.0.0.1:{self.hass.config.api.port}"

    def _get_auth_headers(self) -> dict[str, str]:
        """获取认证头"""
        headers: dict[str, str] = {}
        token = self.entry.data.get("ha_token") or self.entry.options.get("ha_token")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    async def _close_http_session(self) -> None:
        """关闭HTTP会话"""
        if self._http_session and not self._http_session.closed:
            try:
                await self._http_session.close()
            except Exception as err:
                LOGGER.warning("Error closing HTTP session: %s", err)
            finally:
                self._http_session = None

    async def _load_history(self) -> None:
        """加载历史数据"""
        if self.storage:
            self.history = await self.storage.load_history() or []
        else:
            self.history = []
        self._total_records = len(self.history)
        LOGGER.debug("_load_history: 加载了 %d 条历史记录", len(self.history))
        await self._fix_duration_hours()
        migrated = self._migrate_history_records()
        LOGGER.debug("_load_history: 迁移结果=%s, 当前记录数=%d", migrated, len(self.history))
        if migrated:
            await self._save_history()
        if self.statistics:
            self.statistics.invalidate_cache()

    async def _save_history(self) -> None:
        """保存历史数据"""
        if self.storage:
            await self.storage.save_history()

    async def _fix_duration_hours(self) -> None:
        """修复duration_hours"""
        fixed = 0
        for r in self.history:
            if (not r.get('duration_hours') or r.get('duration_hours') == 0) and r.get('start_time') and r.get('end_time'):
                start_dt = self._normalize_to_utc(r['start_time'])
                end_dt = self._normalize_to_utc(r['end_time'])
                if start_dt and end_dt:
                    duration = (end_dt - start_dt).total_seconds() / 3600
                    if duration > 0:
                        r['duration_hours'] = round(duration, 2)
                        fixed += 1
        if fixed > 0:
            LOGGER.info("Fixed %d records with duration_hours", fixed)
            await self._save_history()

    async def _fix_multi_color_misclassification(self) -> None:
        """修复多色误判"""
        fixed = 0
        for r in self.history:
            colors_used = r.get("colors_used", [])
            if not colors_used or len(colors_used) <= 1:
                continue
            unique_colors = list(dict.fromkeys(
                c.lower() if isinstance(c, str) else c for c in colors_used
            ))
            if len(unique_colors) == 1:
                self._fix_record_to_single_color(r, unique_colors)
                fixed += 1
        if fixed > 0:
            LOGGER.info("Fixed %d multi-color misclassification", fixed)
            await self._save_history()

    def _fix_record_to_single_color(self, record: dict, colors: list) -> None:
        """修正单色记录"""
        if len(colors) == 1:
            record["colors_used"] = colors
            record["total_colors"] = 1
            if record.get("multi_color_summary"):
                record["multi_color_summary"]["total_colors"] = 1
                record["multi_color_summary"]["all_colors"] = colors

    # 老格式 status 中文到英文的映射
    _STATUS_MAP = {
        "完成": PRINT_STATUS_FINISH,
        "失败": PRINT_STATUS_FAIL,
        "取消": PRINT_STATUS_CANCELLED,
        "空闲": PRINT_STATUS_IDLE,
        "运行中": PRINT_STATUS_RUNNING,
    }

    def _migrate_history_records(self) -> bool:
        """迁移历史记录：老格式→新格式，确保所有字段完整，返回是否有变更"""
        migrated = 0
        for record in self.history:
            changed = False

            # 转换老格式 status（中文→英文）
            old_status = record.get("status", "")
            if old_status in self._STATUS_MAP:
                record["status"] = self._STATUS_MAP[old_status]
                changed = True
            elif old_status not in (PRINT_STATUS_FINISH, PRINT_STATUS_FAIL,
                                     PRINT_STATUS_CANCELLED, PRINT_STATUS_IDLE, PRINT_STATUS_RUNNING):
                if old_status:
                    LOGGER.warning("未知 status '%s'，保留原值", old_status)

            # 转换 duration_minutes → duration_hours
            if "duration_minutes" in record and "duration_hours" not in record:
                dm = record.pop("duration_minutes", 0) or 0
                record["duration_hours"] = round(dm / 60, 2) if dm else 0
                changed = True
            elif "duration_minutes" in record and "duration_hours" in record:
                record.pop("duration_minutes", None)
                changed = True

            # 转换 timestamp → end_time
            if "timestamp" in record and "end_time" not in record:
                record["end_time"] = record.pop("timestamp")
                changed = True
            elif "timestamp" in record and "end_time" in record:
                record.pop("timestamp", None)
                changed = True

            # 转换 energy_wh → energy_kwh
            if "energy_wh" in record and "energy_kwh" not in record:
                wh = record.pop("energy_wh", 0) or 0
                record["energy_kwh"] = round(wh / 1000, 4) if wh else None
                changed = True
            elif "energy_wh" in record and "energy_kwh" in record:
                record.pop("energy_wh", None)
                changed = True

            # 移除老格式独有字段
            for old_key in ("printer", "file_name"):
                if old_key in record:
                    record.pop(old_key, None)
                    changed = True

            # 确保 id 存在
            if "id" not in record:
                record["id"] = str(uuid.uuid4())
                changed = True

            # 确保 progress 存在
            if "progress" not in record:
                status = record.get("status", "")
                record["progress"] = 100 if status == PRINT_STATUS_FINISH else 0
                changed = True

            # 确保颜色相关字段存在
            if "colors_used" not in record:
                color = record.get("filament_color")
                record["colors_used"] = [color] if color else []
                changed = True

            if "types_used" not in record:
                ftype = record.get("filament_type")
                record["types_used"] = [ftype] if ftype else []
                changed = True

            if "total_colors" not in record:
                record["total_colors"] = len(record.get("colors_used", []))
                changed = True

            if "color_changes_count" not in record:
                record["color_changes_count"] = 0
                changed = True

            if "color_usage" not in record:
                record["color_usage"] = []
                changed = True

            # 确保其他新版本字段存在
            new_fields = {
                "nozzle_type": None,
                "nozzle_size": None,
                "print_bed_type": None,
                "total_layer_count": None,
                "chamber_temp_final": None,
                "chamber_temp_last5min": None,
                "cover_image_local": None,
                "snapshot_image_local": None,
                "multi_color_summary": None,
            }
            for key, default in new_fields.items():
                if key not in record:
                    record[key] = default
                    changed = True

            if changed:
                migrated += 1

        if migrated > 0:
            LOGGER.info("Migrated %d history records to new format", migrated)
        return migrated > 0

    async def _discover_entities(self) -> None:
        """发现实体"""
        if self.entity_discovery:
            await self.entity_discovery.discover()

    def _get_entity_state(self, entity_id: str, default: any = None) -> any:
        """获取实体状态"""
        if self.entity_discovery:
            return self.entity_discovery.get_entity_state(entity_id, default)
        return default

    def _get_entity_attr(self, entity_id: str, attr: str, default: any = None) -> any:
        """获取实体属性"""
        if self.entity_discovery:
            return self.entity_discovery.get_entity_attr(entity_id, attr, default)
        return default

    def _get_float_state(self, entity_id: str, default: float = 0.0) -> float:
        """获取浮点状态"""
        if self.entity_discovery:
            return self.entity_discovery.get_float_state(entity_id, default)
        return default

    def _get_best_task_name(self) -> str:
        """获取最佳任务名"""
        task_entity = self._entity_map.get("task_name", "")
        gcode_entity = self._entity_map.get("gcode_filename", "")
        raw_task = self._get_entity_state(task_entity, "") or ""
        raw_gcode = self._get_entity_state(gcode_entity, "") or ""
        if raw_task and not self._is_param_description(raw_task):
            return raw_task
        if raw_gcode:
            basename = os.path.basename(raw_gcode)
            if basename and basename != raw_gcode and not self._is_param_description(basename):
                return basename
        return ""

    def _lock_task_name(self, name: str) -> None:
        """锁定任务名"""
        self._locked_task_name = name

    def _clear_locked_task_name(self) -> None:
        """清除任务名锁定"""
        self._locked_task_name = ""

    def _is_param_description(self, task_name: str) -> bool:
        """判断是否为参数描述（兼容旧调用）"""
        return is_param_description(task_name)

    def _extract_real_task_name(self, task_name: str) -> str | None:
        """提取真实任务名"""
        if not task_name or task_name in INVALID_ENTITY_STATES:
            return None
        if task_name.startswith("/data/") or self._is_param_description(task_name) or len(task_name) < 3:
            return None
        return task_name

    def _get_current_print_status(self) -> str | None:
        """获取当前打印状态"""
        return self._get_entity_state(self.print_status_entity)

    def _recover_active_print(self) -> None:
        """恢复活跃打印"""
        if self.print_tracker:
            self.print_tracker.recover_active_print()

    def _handle_state_change(self, event: Event) -> None:
        """处理状态变化"""
        if self.print_tracker:
            self.print_tracker.handle_state_change(event)

    def _build_tray_color_map(self) -> dict[str, dict]:
        """构建AMS tray颜色映射（使用缓存的实体列表）"""
        result = {}
        active_entity = self._entity_map.get("active_tray", "")
        if not active_entity:
            return result

        # 复用 print_tracker 的 AMS 实体缓存
        ams_entities = []
        if self.print_tracker:
            ams_entities = self.print_tracker._get_ams_tray_entities()
        else:
            for state in self.hass.states.async_all():
                eid = state.entity_id
                if "ams" in eid and "tray" in eid and eid.startswith("sensor."):
                    ams_entities.append(eid)

        for eid in ams_entities:
            state = self.hass.states.get(eid)
            if not state:
                continue
            attrs = state.attributes
            parts = eid.split("_")
            ams_idx = tray_idx = None
            for i, p in enumerate(parts):
                if p == "ams" and i + 1 < len(parts):
                    try:
                        ams_idx = int(parts[i + 1])
                    except ValueError:
                        pass
                if p == "tray" and i + 1 < len(parts):
                    try:
                        tray_idx = int(parts[i + 1])
                    except ValueError:
                        pass
            if ams_idx is not None and tray_idx is not None:
                key = f"AMS {ams_idx} Tray {tray_idx}"
                color = attrs.get("color", "")
                name = state.state if state.state not in INVALID_ENTITY_STATES else ""
                result[key] = {"color": color, "type": name}
        return result

    def _on_print_start(self) -> None:
        """打印开始"""
        if self.print_tracker:
            self.print_tracker.on_print_start()

    async def _on_print_end(self, end_status: str) -> None:
        """打印结束"""
        if self.print_tracker:
            await self.print_tracker._on_print_end(end_status)

    def _detect_placeholder_images(self) -> None:
        """检测占位图"""
        if self.image_manager:
            self.image_manager.detect_placeholder_images()

    async def _delayed_cover_download(self, task_name: str, start_time: str) -> None:
        """延迟下载封面"""
        await asyncio.sleep(10)
        if not self.current_print or self.current_print.get("cover_image_local"):
            return
        if self.image_manager:
            local_path = await self.image_manager._download_cover_image(
                self.current_print.get("cover_image_url", ""), task_name, start_time,
            )
            if local_path and self.current_print:
                self.current_print["cover_image_local"] = local_path

    async def _delayed_snapshot_download(self, task_name: str, start_time: str) -> None:
        """延迟下载快照 - 每30秒获取最新快照，新快照替换旧快照，只保留最新一张"""
        interval = 30
        max_iterations = 2880  # 最多运行24小时（30s * 2880 = 86400s）
        iteration = 0

        while iteration < max_iterations:
            await asyncio.sleep(interval)
            iteration += 1

            if not self.current_print:
                return
            status = self.current_print.get("status", "")
            if status in (PRINT_STATUS_FINISH, PRINT_STATUS_FAIL, PRINT_STATUS_CANCELLED, "idle"):
                return

            old_path = self.current_print.get("snapshot_image_local")
            if self.image_manager:
                local_path = await self.image_manager._download_print_snapshot(start_time, task_name)
                if local_path and self.current_print:
                    self.current_print["snapshot_image_local"] = local_path
                    if old_path:
                        self.hass.async_create_task(self.image_manager._delete_image_file(old_path))

        LOGGER.warning("Snapshot download reached max iterations (24h), stopping")

    async def _save_full_print_info(self, record: dict, end_time: str) -> str | None:
        """保存完整打印信息"""
        try:
            safe_task_name = SecureFileHandler.sanitize_filename(record.get("task_name", "unknown"))
            safe_time = re.sub(r'[^\dT]', '_', (end_time or '')[:19])
            filename = f"{safe_task_name}_{safe_time}.json"

            def _ensure_dir():
                info_dir = os.path.join(self._images_dir, "print_info")
                os.makedirs(info_dir, exist_ok=True)
                return info_dir

            info_dir = await self.hass.async_add_executor_job(_ensure_dir)
            filepath = SecureFileHandler.safe_join(info_dir, filename)
            if not filepath:
                return None

            full_info = {"record": record, "printer_name": self.printer_name, "timestamp": end_time}

            def _write():
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(full_info, f, ensure_ascii=False, indent=2)

            await self.hass.async_add_executor_job(_write)
            return f"/local/printer_analytics/print_info/{filename}"
        except Exception as err:
            LOGGER.error("Failed to save full print info: %s", err)
            return None

    def _ensure_timezone(self, dt_str: str) -> str:
        """确保时区信息"""
        if not dt_str:
            return datetime.now(timezone.utc).isoformat()
        try:
            dt = datetime.fromisoformat(dt_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
            return dt.astimezone(timezone.utc).isoformat()
        except Exception:
            return datetime.now(timezone.utc).isoformat()

    def _normalize_to_utc(self, dt_str: str) -> datetime | None:
        """标准化为UTC（带缓存，避免重复解析同一时间字符串）"""
        if not dt_str:
            return None
        cached = self._time_cache.get(dt_str)
        if cached is not None:
            return cached
        try:
            dt = datetime.fromisoformat(dt_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
            result = dt.astimezone(timezone.utc)
            if len(self._time_cache) < 512:
                self._time_cache[dt_str] = result
            return result
        except Exception as err:
            LOGGER.warning("Failed to normalize time '%s': %s", dt_str[:30], err)
            return None

    def _build_color_data(self, end_status: str, progress: int) -> tuple:
        """构建颜色数据"""
        raw_colors_used = self.current_print.get("colors_used", [])
        types_used = self.current_print.get("types_used", [])
        color_changes = self.current_print.get("color_changes", [])
        color_usage = self.current_print.get("color_usage", [])

        colors_used = list(dict.fromkeys(
            c.lower() if isinstance(c, str) else c for c in raw_colors_used
        )) if raw_colors_used else []

        if color_usage:
            actual_colors = list(dict.fromkeys(
                entry["color"].lower() if isinstance(entry.get("color"), str) else entry.get("color")
                for entry in color_usage if entry.get("weight_g", 0) > 0 and entry.get("color")
            ))
            if actual_colors and len(actual_colors) < len(colors_used):
                colors_used = actual_colors

        total_colors = len(colors_used) if colors_used else (1 if self.current_print.get("filament_color") else 0)
        multi_color_summary = None

        if len(colors_used) > 1:
            status_label = '完成' if end_status == PRINT_STATUS_FINISH else ('取消' if end_status == PRINT_STATUS_CANCELLED else '失败')
            multi_color_summary = {
                "total_colors": total_colors,
                "primary_color": colors_used[0] if colors_used else None,
                "all_colors": colors_used,
                "all_types": types_used,
                "change_count": len(color_changes),
                "print_status": end_status,
                "completion_progress": progress if end_status != PRINT_STATUS_FINISH else 100,
                "is_partial": end_status != PRINT_STATUS_FINISH,
                "status_label": status_label,
            }

        clean_color_usage = [
            {"color": entry["color"], "type": entry["type"],
             "weight_g": round(entry.get("weight_g", 0), 2),
             "length_m": round(entry.get("length_m", 0), 2), "tray": entry.get("tray")}
            for entry in color_usage
        ]
        return colors_used, types_used, color_changes, color_usage, total_colors, multi_color_summary, clean_color_usage

    def _build_chamber_temp_data(self, end_dt: datetime | None) -> tuple[dict | None, float | None]:
        """构建腔体温度数据"""
        timeline = self.current_print.get("chamber_temp_timeline", [])
        if not timeline:
            return None, None
        chamber_temp_final = timeline[-1].get("temp")
        cutoff = (end_dt - timedelta(minutes=CHAMBER_TEMP_WINDOW_MINUTES)).isoformat() if end_dt else None
        last5 = [e for e in timeline if e["time"] >= cutoff] if cutoff else timeline[-5:]
        if not last5:
            return None, chamber_temp_final
        chamber_temp_last5min = {
            "entries": last5,
            "avg": round(sum(e["temp"] for e in last5) / len(last5), 1),
            "max": round(max(e["temp"] for e in last5), 1),
            "min": round(min(e["temp"] for e in last5), 1),
        }
        return chamber_temp_last5min, chamber_temp_final

    async def backfill_cover_images(self) -> int:
        """补全封面图"""
        if self.image_manager:
            return await self.image_manager.backfill_cover_images()
        return 0

    async def backfill_snapshots(self) -> int:
        """补全快照"""
        if self.image_manager:
            return await self.image_manager.backfill_snapshots()
        return 0

    async def backfill_task_names(self) -> int:
        """补全任务名"""
        if not self.image_manager:
            LOGGER.warning("No image manager")
            return 0
        cloud = self.image_manager._get_bambu_cloud_client()
        if not cloud:
            LOGGER.warning("No Bambu Cloud client")
            return 0
        serial = self.image_manager._get_printer_serial()
        if not serial:
            return 0
        try:
            def _get_tasks():
                return cloud.get_tasklist_for_printer(serial)
            tasks = await self.hass.async_add_executor_job(_get_tasks)
        except Exception as err:
            LOGGER.error("Failed to get cloud tasks: %s", err)
            return 0
        if not tasks:
            return 0

        cloud_tasks = []
        for task in tasks:
            end_str = task.get("endTime", "")
            start_str = task.get("startTime", "")
            title = task.get("designTitle", "") or task.get("title", "") or task.get("name", "")
            if not title or not end_str:
                continue
            try:
                end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00")) if start_str else None
                cloud_tasks.append({"title": title, "end_dt": end_dt, "start_dt": start_dt})
            except (ValueError, TypeError):
                continue

        updated = 0
        for record in self.history:
            old_name = record.get("task_name", "")
            if old_name and not self._is_param_description(old_name) and not old_name.startswith("/data/"):
                continue
            end_time = record.get("end_time", "")
            start_time = record.get("start_time", "")
            if not end_time:
                continue
            rec_dt = self._normalize_to_utc(end_time)
            if not rec_dt:
                continue

            best_match = None
            best_score = 999999
            for ct in cloud_tasks:
                end_diff = abs((ct["end_dt"] - rec_dt).total_seconds())
                if end_diff > 600:
                    continue
                score = end_diff
                if ct.get("start_dt") and start_time:
                    rec_start_dt = self._normalize_to_utc(start_time)
                    if rec_start_dt:
                        score = end_diff + abs((ct["start_dt"] - rec_start_dt).total_seconds())
                if score < best_score:
                    best_score = score
                    best_match = ct

            if not best_match or not best_match.get("title") or best_score > 300:
                continue
            new_name = best_match["title"]
            if new_name != old_name:
                LOGGER.info("Task name updated: '%s' -> '%s'", (old_name or "")[:40], new_name[:40])
                record["task_name"] = new_name
                updated += 1

        if updated > 0:
            self.hass.async_create_task(self._save_history())
            LOGGER.info("Backfilled %d task names", updated)
        return updated

    def _calculate_statistics(self) -> PrinterStats:
        """计算统计数据"""
        if self.statistics:
            return self.statistics.calculate()
        return PrinterStats()

    async def _async_update_data(self) -> PrinterStats:
        """异步更新数据"""
        return self._calculate_statistics()

    async def async_reset_history(self) -> None:
        """重置历史"""
        self.history = []
        self.current_print = None
        if self.statistics:
            self.statistics.invalidate_cache()
        await self._save_history()
        self.async_set_updated_data(self._calculate_statistics())
        LOGGER.info("History reset for %s", self.printer_name)

    async def async_delete_history_records(self, record_ids: list[str]) -> int:
        """删除历史记录"""
        if not record_ids:
            return 0
        ids_set = set(record_ids)
        original_count = len(self.history)
        self.history = [r for r in self.history if r.get("id") not in ids_set]
        deleted_count = original_count - len(self.history)
        if deleted_count > 0:
            if self.statistics:
                self.statistics.invalidate_cache()
            await self._save_history()
            self.async_set_updated_data(self._calculate_statistics())
            LOGGER.info("Deleted %d records", deleted_count)
        return deleted_count

    def update_options(self, options: dict) -> None:
        """更新选项"""
        self.power_entity = options.get(CONF_POWER_ENTITY, self.power_entity)
        self.energy_entity = options.get(CONF_ENERGY_ENTITY, self.energy_entity)
        self.chamber_temp_entity = options.get(CONF_CHAMBER_TEMP_ENTITY, self.chamber_temp_entity)
        if CONF_PRINTER_NAME in options:
            self.printer_name = options[CONF_PRINTER_NAME]

    async def export_history_json(self, filepath: str | None = None) -> str:
        """导出历史JSON"""
        if self.storage:
            return await self.storage.export_history_json(filepath)
        return ""

    async def get_storage_statistics(self) -> dict:
        """获取存储统计"""
        if self.storage:
            return await self.storage.get_storage_statistics()
        return {}
