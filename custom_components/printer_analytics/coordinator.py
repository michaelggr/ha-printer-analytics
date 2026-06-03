"""Printer Analytics Coordinator - 主协调器"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, Event, callback
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry
from homeassistant.helpers.device_registry import async_get as async_get_device_registry
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval
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
    END_PRINT_STATUSES,
    HISTORY_VERSION,
    HTTP_CONNECTION_LIMIT,
    HTTP_CONNECTION_PER_HOST,
    HTTP_SESSION_TIMEOUT_SECS,
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
)
from .utils import SecureFileHandler, extract_model_from_gcode_filename, is_param_description

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
        self.printer_serial: str = ""  # 打印机序列号，在实体发现后填充
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
        self._unsub_task_name_listener = None
        self._unsub_gcode_listener = None
        self._pre_print_model_name: str = ""  # 打印开始前缓存的模型名
        self._pre_print_project_name: str = ""  # 打印开始前缓存的项目名（模型名之后出现的非参数描述值）
        self._material_cache_interval = None
        self._health_check_interval = None  # 周期性健康检查（兜底检测卡住的打印）
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

        # 先发现实体，获取打印机序列号（序列号用于存储键）
        try:
            await self.entity_discovery.discover()
        except Exception as err:
            LOGGER.warning("Entity discovery failed: %s", err)

        # 实体发现后，填充打印机序列号
        self._update_printer_serial()
        LOGGER.info("打印机序列号=%s, entry_id=%s", self.printer_serial, self.entry.entry_id)

        # 序列号更新后，重新发现实体（用序列号前缀匹配 Bambu Lab 实体）
        # 首次发现时 printer_serial 为空，只能用 printer_name 匹配；
        # 序列号填充后，可以用序列号前缀匹配更多实体
        if self.printer_serial:
            try:
                await self.entity_discovery.discover()
            except Exception as err:
                LOGGER.warning("Entity discovery retry failed: %s", err)

        # 序列号更新后，迁移旧文件名并更新存储键
        # 必须在 _load_history 之前执行，否则 _storage_key 还是 entry_id，找不到序列号命名的文件
        if self.printer_serial and self.storage:
            try:
                await self.hass.async_add_executor_job(self.storage.migrate_entry_id_to_serial)
                self.storage.update_storage_key()
                LOGGER.info("存储键已更新=%s", self.storage._storage_key)
            except Exception as err:
                LOGGER.warning("存储键迁移失败: %s", err)
        else:
            LOGGER.warning("无法更新存储键: printer_serial=%s, storage=%s", self.printer_serial, self.storage)

        # 加载历史数据（此时 _storage_key 已更新为序列号）
        try:
            await self._load_history()
            LOGGER.info("历史数据加载完成=%d 条记录", len(self.history))
        except Exception as err:
            LOGGER.warning("Failed to load history (will start fresh): %s", err)
            self.history = []

        try:
            await self.hass.async_add_executor_job(self.image_manager.detect_placeholder_images)
        except Exception as err:
            LOGGER.warning("Placeholder image detection failed: %s", err)

        # 如果配置中没有指定打印状态实体，使用自动发现的实体
        if not self.print_status_entity:
            self.print_status_entity = self._entity_map.get("print_status", "")

        # 获取当前打印状态（包括 unknown/unavailable 等无效状态）
        current_state = self.hass.states.get(self.print_status_entity)
        self._previous_status = current_state.state if current_state else None

        # 保护逻辑：如果当前状态是活跃状态，尝试恢复或开始打印追踪
        if self._previous_status in ACTIVE_PRINT_STATUSES:
            self.print_tracker.recover_active_print()
        # 二次保护：如果状态是 running 但 current_print 为空，强制恢复
        elif self._previous_status == "running" and not self.current_print:
            LOGGER.warning("检测到 running 状态但 current_print 为空，强制恢复")
            self.print_tracker.recover_active_print()

        # 孤儿打印检测：HA 重启时如果打印已结束(idle/finish)，正常恢复不会触发
        # 此检测通过对比 gcode_file_downloaded 和历史记录发现未记录的打印
        if not self.current_print:
            self.print_tracker.detect_orphan_print()

        # 订阅状态变化
        if self.print_status_entity:
            self._unsub_listener = async_track_state_change_event(
                self.hass, [self.print_status_entity], self._handle_state_change
            )
        else:
            LOGGER.warning("No print status entity configured for %s, state changes will not be tracked", self.printer_name)

        # 订阅 task_name 实体变化，在打印开始前提前缓存模型名
        task_name_entity = self._entity_map.get("task_name", "")
        if task_name_entity:
            self._unsub_task_name_listener = async_track_state_change_event(
                self.hass, [task_name_entity], self._handle_task_name_change
            )
            LOGGER.info("已订阅 task_name 实体变化: %s", task_name_entity)

        # 订阅 gcode_file_downloaded 变化，当 gcode 更新时重新提取模型名
        gcode_entity = self._entity_map.get("gcode_file_downloaded", "")
        if gcode_entity:
            self._unsub_gcode_listener = async_track_state_change_event(
                self.hass, [gcode_entity], self._handle_gcode_file_change
            )
            LOGGER.info("已订阅 gcode_file_downloaded 变化: %s", gcode_entity)

        # 启动周期性健康检查（兜底：检测卡住的打印状态）
        self._health_check_interval = async_track_time_interval(
            self.hass,
            self._health_check_stuck_print,
            timedelta(minutes=3),
        )

        LOGGER.info("Printer Analytics setup for %s", self.printer_name)

    async def async_shutdown(self) -> None:
        """关闭清理"""
        if self.print_tracker:
            self.print_tracker.stop_material_cache()
        if self._health_check_interval:
            self._health_check_interval()
            self._health_check_interval = None
        if self._unsub_listener:
            self._unsub_listener()
            self._unsub_listener = None
        if self._unsub_task_name_listener:
            self._unsub_task_name_listener()
            self._unsub_task_name_listener = None
        if self._unsub_gcode_listener:
            self._unsub_gcode_listener()
            self._unsub_gcode_listener = None
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
        "失败": PRINT_STATUS_FAILED,
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
                                     PRINT_STATUS_FAILED, PRINT_STATUS_CANCELLED,
                                     PRINT_STATUS_IDLE, PRINT_STATUS_RUNNING):
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
                "printer_serial": self.printer_serial or None,
                "ams_used": None,
                "multi_color": None,
                "speed_profile": None,
                "prepare_time_minutes": None,
                "slice_mode": None,
                "over_500g": None,
                "design_id": None,
            }
            for key, default in new_fields.items():
                if key not in record:
                    record[key] = default
                    changed = True

            # 推断已有记录的派生字段
            if record.get("multi_color") is None:
                total_c = record.get("total_colors", 0) or 0
                record["multi_color"] = total_c > 1
                changed = True
            if record.get("over_500g") is None:
                w = record.get("total_weight", 0) or 0
                record["over_500g"] = w > 500
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
            self._update_printer_serial()

    def _update_printer_serial(self) -> None:
        """从实体映射中更新打印机序列号"""
        # 优先从 serial_number 实体获取
        serial_entity = self._entity_map.get("serial_number", "")
        if serial_entity:
            state = self.hass.states.get(serial_entity)
            if state and state.state not in INVALID_ENTITY_STATES:
                self.printer_serial = state.state
                return
        # 回退：从 cover_image 实体 ID 正则提取
        import re
        cover_entity = self._entity_map.get("cover_image", "")
        if cover_entity:
            match = re.search(r'image\.\w+_(\w+)_cover_image', cover_entity)
            if match:
                self.printer_serial = match.group(1).upper()
                return
        # 回退：从 print_status 实体 ID 提取（sensor.xxx_SERIAL_print_status）
        status_entity = self._entity_map.get("print_status", "") or self.print_status_entity
        if status_entity:
            match = re.search(r'sensor\.\w+_(\w+)_print_status', status_entity)
            if match:
                self.printer_serial = match.group(1).upper()
                return

    def _get_entity_state(self, entity_id: str, default: any = None) -> any:
        """获取实体状态"""
        if self.entity_discovery:
            return self.entity_discovery.get_entity_state(entity_id, default)
        return default

    def get_entity_state(self, entity_id: str, default: any = None) -> any:
        """获取实体状态（公共接口）"""
        return self._get_entity_state(entity_id, default)

    def _get_entity_attr(self, entity_id: str, attr: str, default: any = None) -> any:
        """获取实体属性"""
        if self.entity_discovery:
            return self.entity_discovery.get_entity_attr(entity_id, attr, default)
        return default

    def get_entity_attr(self, entity_id: str, attr: str, default: any = None) -> any:
        """获取实体属性（公共接口）"""
        return self._get_entity_attr(entity_id, attr, default)

    def _get_float_state(self, entity_id: str, default: float = 0.0) -> float:
        """获取浮点状态"""
        if self.entity_discovery:
            return self.entity_discovery.get_float_state(entity_id, default)
        return default

    def get_float_state(self, entity_id: str, default: float = 0.0) -> float:
        """获取浮点状态（公共接口）"""
        return self._get_float_state(entity_id, default)

    def get_bambu_original_cover_url(self) -> str:
        """从 Bambu Lab 集成获取原始封面图 CDN URL

        HA 的 image proxy 隐藏了原始 CDN URL（返回 /api/image_proxy/...），
        无法通过 entity_picture 属性判断封面图来源（public-cdn vs bbl-private）。
        此方法直接访问 Bambu Lab 集成的协调器数据，获取 _task_data 中的原始 cover URL。

        CDN URL 规律（已验证）：
            public-cdn.bblmw.cn → 公共 CDN，永不过期 → 云端类型（cloud_slice/cloud_file/auto_repeat）
            bbl-prod-model.oss-cn-shanghai.aliyuncs.com/private/ → 私有 OSS，30分钟过期 → lan_file

        Returns:
            str: 原始 CDN URL，获取失败返回空字符串
        """
        try:
            bambu_data = self.hass.data.get("bambu_lab", {})
            for _entry_id, coordinator in bambu_data.items():
                try:
                    model = coordinator.get_model()
                    if model and hasattr(model, 'print_job'):
                        print_job = model.print_job
                        if hasattr(print_job, '_task_data') and print_job._task_data:
                            cover_url = print_job._task_data.get('cover', '')
                            if cover_url:
                                serial = getattr(model, 'info', None)
                                if serial and hasattr(serial, 'serial') and serial.serial == self.printer_serial:
                                    LOGGER.info("获取到 Bambu Lab 原始封面 URL: %s", cover_url[:80])
                                    return cover_url
                except Exception:
                    continue
        except Exception as err:
            LOGGER.debug("获取 Bambu Lab 原始封面 URL 失败: %s", err)
        return ""

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

    async def _health_check_stuck_print(self, now: datetime) -> None:
        """周期性健康检查：检测卡住的打印状态

        兜底机制：当状态变化事件和 material_cache_tick 都未能检测到打印结束时，
        此方法每3分钟检查一次，如果 current_print 存在但打印机已空闲，则触发结束流程。

        常见卡住场景：
        1. HA 事件循环繁忙，状态变化事件丢失
        2. material_cache_tick 异常退出或未运行
        3. Bambu Lab 集成状态更新与事件触发不同步
        """
        if not self.current_print or not self.print_tracker:
            return

        current_status = self.print_tracker.get_current_status()

        # 打印机已空闲或已结束，但 current_print 仍存在 → 卡住了
        if current_status in END_PRINT_STATUSES:
            LOGGER.warning("健康检查：检测到打印已结束(%s)但记录未保存，强制结束", current_status)
            await self.print_tracker._on_print_end(current_status)
        elif current_status == PRINT_STATUS_IDLE:
            LOGGER.warning("健康检查：检测到 idle 但 current_print 仍存在，视为异常中断")
            await self.print_tracker._on_print_end("cancelled")
        # 打印机已离线超过30分钟，current_print 仍存在 → 可能卡住
        elif current_status == OFFLINE_STATUS:
            start_time = self.current_print.get("start_time", "")
            if start_time:
                try:
                    start_dt = self._normalize_to_utc(start_time)
                    if start_dt and (datetime.now(timezone.utc) - start_dt).total_seconds() > 30 * 60:
                        LOGGER.warning("健康检查：打印机离线超30分钟且 current_print 存在，视为异常中断")
                        await self.print_tracker._on_print_end("cancelled")
                except (ValueError, TypeError):
                    pass

    def _handle_state_change(self, event: Event) -> None:
        """处理状态变化"""
        if self.print_tracker:
            self.print_tracker.handle_state_change(event)

    def _handle_task_name_change(self, event: Event) -> None:
        """处理 task_name 实体变化

        BambuLab 的 task_name 实际行为（通过历史数据验证）：
        - 打印空闲/完成后：task_name 停留在上一次打印的项目名（如"适合 X2D"）
        - 新打印即将开始前（homing 前15~25秒）：先短暂显示模型名，再切换为项目名
        - 局域网文件：没有模型名过渡，只有项目名

        佐证手段：
        - gcode_file_downloaded 包含真正的项目名（如 "891278-适合 X2D.gcode.gcode"）
        - 如果 task_name 的非参数描述值匹配 gcode 项目名 → 是项目名，不是模型名

        策略（idle 状态下只关注变化事件，不缓存静态值）：
        1. 非参数描述 → 参数描述：old_value 可能是模型名或项目名，用 gcode 佐证
        2. 非参数描述 → 不同的非参数描述：old_value 是模型名，new_value 是项目名
        3. 参数描述 → 非参数描述：new_value 可能是模型名，用 gcode 佐证
        4. 打印中收到参数描述，更新 config_name
        """
        new_state = event.data.get("new_state")
        old_state = event.data.get("old_state")
        if not new_state:
            return
        new_value = (new_state.state or "").strip()
        if not new_value or new_value in INVALID_ENTITY_STATES:
            return

        old_value = ""
        if old_state:
            old_value = (old_state.state or "").strip()

        current_status = self._previous_status

        # 如果当前正在打印中，task_name 变化只更新 config_name
        if current_status in ACTIVE_PRINT_STATUSES and self.current_print:
            if is_param_description(new_value):
                if not self.current_print.get("task_name_config"):
                    self.current_print["task_name_config"] = new_value
                    self.current_print["config_name"] = new_value
                    LOGGER.info("打印中捕获到配置名: %s", new_value)
            return

        # idle/prepare/slicing 状态下，只关注变化事件（old_value != new_value）
        if not old_value or old_value == new_value:
            return

        # 从 gcode_file_downloaded 提取项目名作为佐证
        gcode_project = self._get_gcode_project_name()

        # 辅助函数：判断值是否为项目名（而非模型名）
        def _is_project_name(val: str) -> bool:
            if val == self._pre_print_project_name:
                return True
            if gcode_project and val == gcode_project:
                return True
            return False

        # 场景1：非参数描述 → 参数描述
        # old_value 可能是模型名，也可能是上一次打印的项目名
        if is_param_description(new_value) and not is_param_description(old_value) and len(old_value) >= 3:
            if _is_project_name(old_value):
                LOGGER.debug("忽略旧项目名（→参数描述）: %s (gcode项目名=%s)", old_value, gcode_project)
                return
            self._pre_print_model_name = old_value
            self._pre_print_project_name = ""
            LOGGER.info("捕获模型名（→参数描述）: %s", old_value)
            return

        # 场景2：非参数描述 → 不同的非参数描述
        # old_value 是模型名，new_value 是项目名（如"适合 X2D"）
        if not is_param_description(new_value) and not is_param_description(old_value) and len(old_value) >= 3 and new_value != old_value:
            # 如果 new_value 匹配 gcode 项目名 → 确认是项目名
            if gcode_project and new_value == gcode_project:
                self._pre_print_model_name = old_value
                self._pre_print_project_name = new_value
                LOGGER.info("捕获模型名（→项目名，gcode佐证）: %s, 项目名: %s", old_value, new_value)
                return
            # 如果 old_value 匹配 gcode 项目名 → old_value 是项目名，new_value 是模型名
            if gcode_project and old_value == gcode_project:
                self._pre_print_model_name = new_value
                self._pre_print_project_name = old_value
                LOGGER.info("捕获模型名（项目名→模型名，gcode佐证）: %s, 项目名: %s", new_value, old_value)
                return
            # 无法确定，默认 old_value 是模型名
            self._pre_print_model_name = old_value
            self._pre_print_project_name = new_value
            LOGGER.info("捕获模型名（→非参数描述）: %s, 候选项目名: %s", old_value, new_value)
            return

        # 场景3：参数描述 → 非参数描述
        # new_value 可能是模型名或项目名，用 gcode 佐证
        if is_param_description(old_value) and not is_param_description(new_value) and len(new_value) >= 3:
            if gcode_project and new_value == gcode_project:
                # new_value 是项目名，不是模型名
                self._pre_print_project_name = new_value
                LOGGER.info("识别项目名（参数→项目名，gcode佐证）: %s", new_value)
                return
            # 缓存为模型名候选
            self._pre_print_model_name = new_value
            self._pre_print_project_name = ""
            LOGGER.info("缓存模型名候选（参数→非参数）: %s", new_value)

    def _handle_gcode_file_change(self, event: Event) -> None:
        """处理 gcode_file_downloaded 实体变化

        当 gcode 文件更新时，如果当前正在打印且模型名不正确，重新提取项目名。
        解决时序竞争：gcode 更新比 print_status 慢几秒，导致打印开始时提取到旧项目名。

        gcode 格式规律（已验证）：
            cloud_slice:  {taskId}-{项目名}{参数描述}.gcode.gcode → 有项目名
            cloud_file:   {taskId}-{参数描述}.gcode.gcode → 无项目名
            auto_repeat:  {taskId}-{项目名}_{参数描述}.gcode.gcode → _分隔
            lan_file:     {taskId}-{参数描述}.gcode.gcode → 无项目名（局域网也有taskId）

        ⚠️ 防护：当新打印排队时，gcode 会提前更新为新打印的值。
        判断策略：
        - 如果 current_print 无 gcode_task_id → 打印刚开始的时序延迟，接受更新
        - 如果 current_print 有 gcode_task_id 且与新 gcode 的 task_id 相同 → 正常更新
        - 如果 current_print 有 gcode_task_id 且与新 gcode 的 task_id 不同：
          → 可能是 on_print_start 时 gcode 还没更新，存入了上一个打印的 task_id
          → 也可能是新打印排队
          → 通过检查 running_start_time 判断：如果打印刚开始（<60秒），允许覆盖
        """
        new_state = event.data.get("new_state")
        if not new_state:
            return
        new_value = (new_state.state or "").strip()
        if not new_value or new_value in INVALID_ENTITY_STATES:
            return

        LOGGER.info("gcode_file_downloaded 变化: %s", new_value[:80])

        if not self.current_print:
            return

        # 防护：检查 gcode 变化是否属于当前打印
        from .utils import extract_task_id_from_gcode_filename
        new_task_id = extract_task_id_from_gcode_filename(new_value)
        current_task_id = self.current_print.get("gcode_task_id", "")
        if current_task_id and new_task_id and str(current_task_id) != str(new_task_id):
            # task_id 不匹配，检查是否打印刚开始（允许覆盖错误的 task_id）
            from datetime import datetime, timezone
            running_start = self.current_print.get("running_start_time", "")
            allow_override = False
            if running_start:
                try:
                    if isinstance(running_start, str):
                        start_dt = datetime.fromisoformat(running_start)
                    else:
                        start_dt = running_start
                    if hasattr(start_dt, 'tzinfo') and start_dt.tzinfo is None:
                        start_dt = start_dt.replace(tzinfo=timezone.utc)
                    elapsed = (datetime.now(timezone.utc) - start_dt).total_seconds()
                    if elapsed < 60:
                        allow_override = True
                        LOGGER.info("gcode task_id 不匹配但打印刚开始(%.0fs)，允许覆盖: %s → %s",
                                    elapsed, current_task_id, new_task_id)
                except Exception:
                    pass
            if not allow_override:
                LOGGER.info("gcode 变化的 task_id=%s 与当前打印的 task_id=%s 不匹配，"
                            "可能是新打印排队，忽略此更新", new_task_id, current_task_id)
                return

        current_model = self.current_print.get("task_name_model", "")
        current_config = self.current_print.get("config_name", "")

        # 重新判断 slice_mode（gcode 更新后可能有更准确的信息）
        cover_image_url = self.current_print.get("cover_image_url", "")
        gcode_filename = self.current_print.get("gcode_filename", "")
        new_slice_mode = self.print_tracker._detect_slice_mode(gcode_filename, new_value, cover_image_url)
        if new_slice_mode and new_slice_mode != self.current_print.get("slice_mode"):
            old_mode = self.current_print.get("slice_mode")
            self.current_print["slice_mode"] = new_slice_mode
            LOGGER.info("gcode 更新后重新判断 slice_mode: %s → %s (gcode: %s)",
                        old_mode, new_slice_mode, new_value[:60])

        # 从新的 gcode 值提取项目名（非模型名）
        new_project = extract_model_from_gcode_filename(new_value)
        if new_project:
            need_update = (
                not current_model
                or is_param_description(current_model)
                or current_model.startswith("/data/")
            )
            if need_update and new_project != current_model:
                if not self._locked_task_name or self._locked_task_name == current_model:
                    self.current_print["task_name_model"] = new_project
                    self.current_print["task_name"] = new_project
                    self._lock_task_name(new_project)
                LOGGER.info("gcode 更新后重新提取项目名: %s (gcode: %s)", new_project, new_value[:60])
        else:
            # gcode 中无项目名（cloud_file 场景），尝试从历史记录查找模型名
            if new_task_id and self.history:
                for r in self.history:
                    if str(r.get("gcode_task_id", "")) == str(new_task_id):
                        hist_model = r.get("task_name_model", "") or r.get("task_name", "")
                        if hist_model and not is_param_description(hist_model) and hist_model != current_model:
                            if not self._locked_task_name or self._locked_task_name == current_model:
                                self.current_print["task_name_model"] = hist_model
                                self.current_print["task_name"] = hist_model
                                self._lock_task_name(hist_model)
                            LOGGER.info("gcode 更新后从历史记录找到模型名: %s (task_id=%s)", hist_model, new_task_id)
                        break

        # 存储 gcode_task_id（gcode 文件 ID，用于关联同一 gcode 的不同打印）
        # ⚠️ 允许覆盖：on_print_start 时 gcode 可能还没更新，存入了上一个打印的 task_id
        if new_task_id:
            if not self.current_print.get("gcode_task_id") or str(self.current_print.get("gcode_task_id")) != str(new_task_id):
                self.current_print["gcode_task_id"] = new_task_id
                LOGGER.info("gcode 更新后存储 task_id: %s", new_task_id)

    def _get_gcode_project_name(self) -> str:
        """从 gcode_file_downloaded 实体提取项目名"""
        gcode_entity = self._entity_map.get("gcode_file_downloaded", "")
        if not gcode_entity:
            return ""
        gcode_value = self.get_entity_state(gcode_entity, "") or ""
        return extract_model_from_gcode_filename(gcode_value)

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
        """延迟下载快照 - 每30秒获取最新快照，连续失败3次后停止重试"""
        interval = 30
        max_iterations = 2880  # 最多运行24小时（30s * 2880 = 86400s）
        consecutive_failures = 0  # 连续失败计数
        max_consecutive_failures = 3  # 连续失败3次后停止
        iteration = 0

        while iteration < max_iterations:
            await asyncio.sleep(interval)
            iteration += 1

            if not self.current_print:
                return
            status = self.current_print.get("status", "")
            if status in END_PRINT_STATUSES or status == PRINT_STATUS_IDLE:
                return

            old_path = self.current_print.get("snapshot_image_local")
            if self.image_manager:
                local_path = await self.image_manager._download_print_snapshot(start_time, task_name)
                if local_path and self.current_print:
                    consecutive_failures = 0  # 成功则重置计数
                    self.current_print["snapshot_image_local"] = local_path
                    if old_path:
                        self.hass.async_create_task(self.image_manager._delete_image_file(old_path))
                else:
                    consecutive_failures += 1
                    if consecutive_failures >= max_consecutive_failures:
                        LOGGER.warning("快照下载连续失败 %d 次，停止重试", consecutive_failures)
                        return

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
            design_id = task.get("designId", "") or ""
            if not title or not end_str:
                continue
            try:
                end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00")) if start_str else None
                cloud_tasks.append({"title": title, "end_dt": end_dt, "start_dt": start_dt, "design_id": design_id})
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
            # 补全 design_id（仅当记录没有时才填充）
            cloud_design_id = best_match.get("design_id", "")
            if cloud_design_id and not record.get("design_id"):
                record["design_id"] = cloud_design_id
                updated += 1

        if updated > 0:
            self.hass.async_create_task(self._save_history())
            LOGGER.info("Backfilled %d task names", updated)
        return updated

    async def backfill_task_names_from_history(self) -> int:
        """从HA历史状态中反查补全任务名

        使用 current_stage 过渡方法从 HA 实体历史中推断模型名和项目名。
        """
        if self.print_tracker:
            return await self.print_tracker.backfill_model_names_from_history()
        return 0

    def _calculate_statistics(self) -> PrinterStats:
        """计算统计数据"""
        if self.statistics:
            return self.statistics.calculate()
        return PrinterStats()

    async def _async_update_data(self) -> PrinterStats:
        """异步更新数据"""
        try:
            return self._calculate_statistics()
        except Exception as err:
            LOGGER.error("Statistics calculation failed: %s", err, exc_info=True)
            return PrinterStats()

    async def _delete_from_files(self, ids_set: set[str]) -> int:
        """从年份文件中删除指定ID的记录（处理不在内存缓存中的记录）"""
        if not self.storage or not ids_set:
            return 0

        def _do_delete():
            import os, json
            history_dir = self.storage._history_dir
            if not os.path.isdir(history_dir):
                return 0

            total_deleted = 0
            # 遍历所有年份文件
            for f in sorted(os.listdir(history_dir)):
                if not f.endswith(".json") or f.endswith("_stats.json"):
                    continue
                file_path = os.path.join(history_dir, f)
                try:
                    with open(file_path, "r", encoding="utf-8") as fh:
                        data = json.load(fh)
                    records = data.get("history", []) if isinstance(data, dict) else data
                    original = len(records)
                    # 过滤掉要删除的记录
                    filtered = [r for r in records if r.get("id") not in ids_set]
                    deleted = original - len(filtered)
                    if deleted > 0:
                        # 写回文件
                        if isinstance(data, dict):
                            data["history"] = filtered
                        else:
                            data = filtered
                        with open(file_path, "w", encoding="utf-8") as fh:
                            json.dump(data, fh, ensure_ascii=False, indent=2)
                        total_deleted += deleted
                        LOGGER.info("从文件 %s 删除了 %d 条记录", f, deleted)
                except Exception as err:
                    LOGGER.warning("处理文件 %s 失败: %s", f, err)

            # 更新 _total_records
            if total_deleted > 0:
                self._total_records = max(0, self._total_records - total_deleted)

            return total_deleted

        return await self.hass.async_add_executor_job(_do_delete)

    async def async_reset_history(self) -> None:
        """重置历史（同时清空内存缓存和文件）"""
        self.history = []
        self.current_print = None
        self._total_records = 0
        if self.statistics:
            self.statistics.invalidate_cache()
        # 清空文件中的历史记录
        if self.storage:
            await self.storage.clear_all_history_files()
        self.async_set_updated_data(self._calculate_statistics())
        LOGGER.info("History reset for %s", self.printer_name)

    async def async_delete_history_records(self, record_ids: list[str]) -> int:
        """删除历史记录（从内存缓存移除，标记待删除，由 save_history 统一写入文件）"""
        if not record_ids:
            return 0
        ids_set = set(record_ids)

        # 从内存缓存中删除
        original_count = len(self.history)
        self.history = [r for r in self.history if r.get("id") not in ids_set]
        deleted_count = original_count - len(self.history)

        # 记录待删除 ID（不在内存中的记录由 save_history 合并写入时排除）
        if self.storage:
            self.storage._pending_delete_ids.update(ids_set)
            # 统计文件中可能存在的待删除记录数（不在内存中的）
            file_only_ids = ids_set - {r.get("id") for r in self.history}
            deleted_count += len(file_only_ids)

        if deleted_count > 0:
            self._total_records = max(0, self._total_records - len(ids_set))
            if self.statistics:
                self.statistics.invalidate_cache()
            await self._save_history()
            self.async_set_updated_data(self._calculate_statistics())
            LOGGER.info("Deleted %d records (memory=%d, file_pending=%d)",
                        len(ids_set), original_count - len(self.history),
                        len(ids_set) - (original_count - len(self.history)))
        return len(ids_set)

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

    def query_history(self, filters: dict = None, page: int = 1, page_size: int = 20) -> dict:
        """查询历史记录（同步方法，供WebSocket调用）"""
        if self.storage:
            return self.storage.query_records(filters=filters, page=page, page_size=page_size)
        return {"records": [], "pagination": {"page": 1, "page_size": page_size, "total": 0, "total_pages": 1}, "filter_options": {}}

    # 判断空/默认值的逻辑在 _is_empty_value 方法中实现

    def _is_empty_value(self, val: any) -> bool:
        """判断值是否为空/默认值（导入合并时判断是否可填充）"""
        if val is None:
            return True
        if isinstance(val, str) and val.strip() == "":
            return True
        if isinstance(val, (int, float)) and val == 0:
            return True
        if isinstance(val, bool):
            return val is False  # False 视为默认值
        if isinstance(val, (list, dict)) and len(val) == 0:
            return True
        return False

    def _find_duplicate_record(self, record: dict) -> dict | None:
        """根据设备序列号+结束时间(±2分钟)查找已有重复记录"""
        for existing in self.history:
            if self._is_duplicate_record(existing, record):
                return existing
        return None

    @staticmethod
    def _is_duplicate_record(existing: dict, record: dict) -> bool:
        """判断两条记录是否重复（序列号+结束时间±2分钟）"""
        serial = record.get("printer_serial") or record.get("deviceId") or ""
        ex_serial = existing.get("printer_serial") or existing.get("deviceId") or ""
        if serial != ex_serial or not serial:
            return False

        end_time_str = record.get("end_time") or record.get("endTime") or ""
        ex_end_str = existing.get("end_time") or existing.get("endTime") or ""
        if not end_time_str or not ex_end_str:
            return False

        # 简单时间比较（避免依赖 _normalize_to_utc 的实例方法）
        try:
            from datetime import datetime, timezone
            def _parse(t):
                t = t.replace("Z", "+00:00")
                if "T" in t:
                    return datetime.fromisoformat(t)
                return datetime.fromisoformat(t.replace(" ", "T"))
            dt1 = _parse(end_time_str)
            dt2 = _parse(ex_end_str)
            # 统一到无时区比较
            if dt1.tzinfo:
                dt1 = dt1.replace(tzinfo=None)
            if dt2.tzinfo:
                dt2 = dt2.replace(tzinfo=None)
            return abs((dt1 - dt2).total_seconds()) <= 120
        except Exception:
            return False

    def _merge_record(self, existing: dict, incoming: dict, overwrite_fields: set | None = None) -> bool:
        """合并导入记录到已有记录

        默认策略：仅填充空/默认字段，不覆盖已有有效数据
        overwrite_fields：指定字段即使已有值也用导入值覆盖（如 config_name, slice_mode）
        """
        changed = False

        # 先做单位转换（在字段名映射之前，避免被映射覆盖）
        if "duration_minutes" in incoming and "duration_hours" not in incoming:
            dm = incoming.pop("duration_minutes", 0) or 0
            incoming["duration_hours"] = round(dm / 60, 2) if dm else 0
        if "costTime" in incoming and "duration_hours" not in incoming:
            # 拓竹格式：costTime 是秒数
            ct = incoming.pop("costTime", 0) or 0
            incoming["duration_hours"] = round(ct / 3600, 2) if ct else 0
        if "energy_wh" in incoming and "energy_kwh" not in incoming:
            wh = incoming.pop("energy_wh", 0) or 0
            incoming["energy_kwh"] = round(wh / 1000, 4) if wh else None
        # 拓竹格式：length 是毫米，转换为米
        if "length" in incoming and "total_length" not in incoming:
            mm = incoming.pop("length", 0) or 0
            incoming["total_length"] = round(mm / 1000, 2) if mm else 0

        # 字段名映射：老格式/拓竹格式 → 新格式
        field_map = {
            "endTime": "end_time",
            "startTime": "start_time",
            "deviceId": "printer_serial",
            "designId": "design_id",
            "title": "task_name",
            "designTitle": "config_name",
            "weight": "total_weight",
            "length": "total_length",
            "mode": "slice_mode",
            "cover": "cover_image_url",
            "bedType": "print_bed_type",
            "deviceName": "_printer_name",
            "useAms": "ams_used",
            "repetitions": "repetitions",
        }
        for old_key, new_key in field_map.items():
            if old_key in incoming and new_key not in incoming:
                incoming[new_key] = incoming.pop(old_key)

        # 状态映射
        status_map = {"完成": "finish", "失败": "failed", "取消": "cancelled"}
        # 拓竹数字状态映射：2=成功, 3=失败, 4=取消
        bambu_status_map = {2: "finish", 3: "failed", 4: "cancelled"}
        if incoming.get("status") in status_map:
            incoming["status"] = status_map[incoming["status"]]
        elif incoming.get("status") in bambu_status_map:
            incoming["status"] = bambu_status_map[incoming["status"]]

        # 拓竹时间格式转换：ISO → "YYYY-MM-DD HH:MM"
        for tf in ("start_time", "end_time", "startTime", "endTime"):
            val = incoming.get(tf, "")
            if val and isinstance(val, str) and "T" in val:
                # "2026-05-23T22:24:53Z" → "2026-05-23 22:24"
                incoming[tf] = val.replace("T", " ").replace("Z", "")[:16]

        for key, value in incoming.items():
            if key.startswith("_"):
                continue  # 跳过内部字段
            if self._is_empty_value(value):
                continue  # 导入值也是空的，无需填充
            existing_val = existing.get(key)
            # 如果该字段在覆盖列表中，且导入值非空，直接覆盖
            if overwrite_fields and key in overwrite_fields:
                if existing.get(key) != value:
                    existing[key] = value
                    changed = True
            elif self._is_empty_value(existing_val):
                existing[key] = value
                changed = True
        return changed

    async def async_import_history(self, json_data: str, overwrite_fields: set | None = None) -> dict:
        """导入历史记录（向后兼容，重复记录合并填充空字段）

        重复判定：设备序列号(printer_serial) + 结束时间(end_time) ±2分钟
        合并策略：仅填充已有记录中为空/默认的字段，不覆盖已有有效数据
        支持导入不属于当前打印机的记录（按 serial 写入对应文件）

        返回结构化导入统计：
            input: 读取的记录总数
            added: 新增记录数
            merged: 命中重复且实际更新了字段的记录数
            duplicate_skipped: 命中重复且无需更新的记录数
            other_serial: 属于其他打印机序列号的记录数
            final_total: 导入后当前打印机的总记录数
        """
        try:
            data = json.loads(json_data)
        except json.JSONDecodeError as err:
            raise ValueError(f"JSON 格式错误: {err}") from err

        records = []
        if isinstance(data, list):
            records = data
        elif isinstance(data, dict):
            if "history" in data:
                records = data["history"]
            else:
                for v in data.values():
                    if isinstance(v, dict) and "history" in v:
                        records.extend(v["history"])

        if not records:
            raise ValueError("导入数据中没有找到有效记录")

        for i, rec in enumerate(records[:5]):
            if not rec.get("task_name") and not rec.get("name") and not rec.get("title"):
                raise ValueError(f"第 {i + 1} 条记录缺少任务名称(task_name)")
            if not rec.get("status"):
                raise ValueError(f"第 {i + 1} 条记录缺少状态(status)")

        my_serial = (self.printer_serial or "").upper()
        my_records = []
        other_by_serial: dict[str, list[dict]] = {}

        for rec in records:
            rec = {k: v for k, v in rec.items() if not k.startswith("_") or k == "_pending_color_validation"}
            if "id" not in rec:
                rec["id"] = str(uuid.uuid4())

            rec_serial = (rec.get("printer_serial") or rec.get("deviceId") or "").upper()
            if not rec_serial:
                rec_serial = my_serial

            if rec_serial == my_serial and my_serial:
                if "printer_serial" not in rec:
                    rec["printer_serial"] = self.printer_serial or None
                my_records.append(rec)
            else:
                if "printer_serial" not in rec and rec_serial:
                    rec["printer_serial"] = rec_serial
                other_by_serial.setdefault(rec_serial, []).append(rec)

        added = 0
        merged = 0
        matched = 0
        for rec in my_records:
            duplicate = self._find_duplicate_record(rec)
            if duplicate:
                matched += 1
                if self._merge_record(duplicate, rec, overwrite_fields=overwrite_fields):
                    merged += 1
            else:
                self.history.append(rec)
                added += 1

        if added > 0 or merged > 0:
            self._migrate_history_records()
            if self.statistics:
                self.statistics.invalidate_cache()
            await self._save_history()
            self.async_set_updated_data(self._calculate_statistics())

        other_count = 0
        other_added = 0
        other_merged = 0
        if other_by_serial and self.storage:
            other_added, other_merged = await self.hass.async_add_executor_job(
                self._import_other_serial_records_v2, other_by_serial
            )
            other_count = other_added + other_merged

        duplicate_skipped = matched - merged
        final_total = len(self.history)

        LOGGER.info(
            "Import history completed: input=%d, added=%d, merged=%d, duplicate_skipped=%d, other_serial=%d, final_total=%d",
            len(records), added, merged, duplicate_skipped, other_count, final_total,
        )

        return {
            "input": len(records),
            "added": added,
            "merged": merged,
            "duplicate_skipped": duplicate_skipped,
            "other_serial": other_count,
            "final_total": final_total,
        }

    async def async_bambu_sync(self) -> dict:
        """从 Bambu Cloud 拉取历史并导入"""
        from .bambu_cloud import (
            load_bambu_token, save_bambu_token,
            fetch_all_history, convert_to_ha_format, check_token,
        )

        LOGGER.info("[Bambu同步] ===== 开始 Bambu Cloud 同步流程 =====")

        # 步骤1: 加载本地 Token
        auth = await load_bambu_token(self.hass)
        if not auth or not auth.get("token"):
            LOGGER.warning("[Bambu同步] 未找到本地 Token，请先登录")
            return {"success": False, "error": "未登录 Bambu Cloud"}

        phone = auth.get("phone", "")
        token_preview = auth["token"][:8] + "..." if len(auth["token"]) > 8 else "***"
        LOGGER.info("[Bambu同步] 步骤1: Token 已加载, 手机号=%s, token=%s", phone, token_preview)

        # 步骤2: 验证 Token 有效性
        token = auth["token"]
        try:
            check_result = await check_token(token)
        except Exception as err:
            LOGGER.error("[Bambu同步] 步骤2: Token 验证异常: %s", err, exc_info=True)
            return {"success": False, "error": f"Token验证异常: {err}"}

        if check_result == "expired":
            LOGGER.warning("[Bambu同步] 步骤2: Token 已过期，清除本地 Token")
            auth["token"] = ""
            auth["token_valid"] = False
            await save_bambu_token(self.hass, auth)
            return {"success": False, "error": "登录已过期，请重新登录"}

        if check_result == "unknown":
            LOGGER.warning("[Bambu同步] 步骤2: 网络异常无法验证 Token，跳过本次同步")
            return {"success": False, "error": "网络异常，无法验证登录状态，请稍后重试"}

        # check_result == "valid"
        auth["last_token_check"] = time.time()
        auth["token_valid"] = True
        LOGGER.info("[Bambu同步] 步骤2: Token 验证通过")

        # 步骤3: 拉取 Bambu Cloud 历史记录
        LOGGER.info("[Bambu同步] 步骤3: 开始拉取云端历史记录...")
        try:
            items = await fetch_all_history(token)
        except Exception as err:
            LOGGER.error("[Bambu同步] 步骤3: 拉取云端历史异常: %s", err, exc_info=True)
            return {"success": False, "error": f"拉取云端历史异常: {err}"}

        if not items:
            LOGGER.info("[Bambu同步] 步骤3: 云端无历史记录")
            return {"success": True, "added": 0, "merged": 0, "total": 0, "message": "Bambu Cloud 无新记录"}

        LOGGER.info("[Bambu同步] 步骤3: 拉取到 %d 条云端记录", len(items))

        # 步骤4: 转换为 HA 格式
        LOGGER.info("[Bambu同步] 步骤4: 开始转换数据格式...")
        try:
            ha_data = convert_to_ha_format(items)
        except Exception as err:
            LOGGER.error("[Bambu同步] 步骤4: 数据转换异常: %s", err, exc_info=True)
            return {"success": False, "error": f"数据转换异常: {err}"}

        ha_count = len(ha_data.get("history", []))
        LOGGER.info("[Bambu同步] 步骤4: 转换完成, %d 条 HA 格式记录", ha_count)

        # 步骤5: 导入到本地
        json_str = json.dumps(ha_data, ensure_ascii=False)
        LOGGER.info("[Bambu同步] 步骤5: 开始导入到本地 (JSON 大小: %d 字节)...", len(json_str))
        try:
            import_result = await self.async_import_history(json_str)
        except Exception as err:
            LOGGER.error("[Bambu同步] 步骤5: 导入异常: %s", err, exc_info=True)
            return {"success": False, "error": f"导入异常: {err}"}

        added = import_result.get("added", 0)
        merged = import_result.get("merged", 0)
        dup = import_result.get("duplicate_skipped", 0)
        other = import_result.get("other_serial", 0)
        LOGGER.info(
            "[Bambu同步] 步骤5: 导入完成 — 新增=%d, 合并=%d, 重复跳过=%d, 其他序列号=%d",
            added, merged, dup, other,
        )

        # 步骤6: 更新同步时间戳
        auth["last_sync"] = time.time()
        auth["last_sync_count"] = added + merged
        auth["last_token_check"] = time.time()
        auth["token_valid"] = True
        await save_bambu_token(self.hass, auth)
        LOGGER.info("[Bambu同步] 步骤6: 同步时间戳已更新, last_sync_count=%d", auth["last_sync_count"])

        # 步骤7: 异步下载新增记录的封面图
        if added > 0 and self.image_manager:
            LOGGER.info("[Bambu同步] 步骤7: 启动封面图异步下载 (新增 %d 条)", added)
            self.hass.async_create_task(self._download_synced_covers())
        else:
            LOGGER.info("[Bambu同步] 步骤7: 无需下载封面图 (added=%d)", added)

        LOGGER.info(
            "[Bambu同步] ===== 同步完成: 云端=%d, 新增=%d, 合并=%d, 重复=%d =====",
            len(items), added, merged, dup,
        )

        return {
            "success": True,
            "added": added,
            "merged": merged,
            "duplicate_skipped": dup,
            "other_serial": other,
            "total": len(items),
        }

    async def _download_synced_covers(self) -> None:
        """异步下载同步新增记录的封面图"""
        try:
            count = await self.backfill_cover_images()
            LOGGER.info("同步后下载了 %d 张封面图", count)
        except Exception as err:
            LOGGER.warning("同步后下载封面图失败: %s", err)

    def _import_other_serial_records(self, records_by_serial: dict[str, list[dict]]) -> int:
        """导入不属于当前 coordinator 的记录，直接写入对应序列号的文件"""
        from .storage import StorageManager as _SM

        total = 0
        for serial, records in records_by_serial.items():
            if not serial:
                continue
            # 读取该序列号现有的所有记录
            existing_records = []
            year_files = []
            if os.path.isdir(self._history_dir):
                for f in os.listdir(self._history_dir):
                    if f.startswith(f"{serial}_") and f.endswith(".json"):
                        year_files.append(f)

            for yf in year_files:
                fp = os.path.join(self._history_dir, yf)
                try:
                    with open(fp, "r", encoding="utf-8") as fh:
                        d = json.load(fh)
                    existing_records.extend(d.get("history", []) if isinstance(d, dict) else d)
                except Exception:
                    continue

            # 合并新记录
            for rec in records:
                # 查找重复
                is_dup = False
                for ex in existing_records:
                    if self._is_duplicate_record(ex, rec):
                        if self._merge_record(ex, rec):
                            total += 1
                        is_dup = True
                        break
                if not is_dup:
                    existing_records.append(rec)
                    total += 1

            # 按年份分组写回
            records_by_year: dict[int, list[dict]] = {}
            for r in existing_records:
                year = _SM._extract_year_from_end_time(r.get("end_time", ""))
                records_by_year.setdefault(year, []).append(r)

            for year, year_records in records_by_year.items():
                year_file = os.path.join(self._history_dir, f"{serial}_{year}.json")
                data = {"version": HISTORY_VERSION, "year": year, "history": year_records}
                try:
                    with open(year_file, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                except Exception as err:
                    LOGGER.warning("写入序列号 %s 的 %d 年数据失败: %s", serial, year, err)

        return total

    def _import_other_serial_records_v2(self, records_by_serial: dict[str, list[dict]]) -> tuple[int, int]:
        """导入不属于当前 coordinator 的记录，返回 (added, merged)"""
        from .storage import StorageManager as _SM

        total_added = 0
        total_merged = 0
        for serial, records in records_by_serial.items():
            if not serial:
                continue
            existing_records = []
            year_files = []
            if os.path.isdir(self._history_dir):
                for f in os.listdir(self._history_dir):
                    if f.startswith(f"{serial}_") and f.endswith(".json"):
                        year_files.append(f)

            for yf in year_files:
                fp = os.path.join(self._history_dir, yf)
                try:
                    with open(fp, "r", encoding="utf-8") as fh:
                        d = json.load(fh)
                    existing_records.extend(d.get("history", []) if isinstance(d, dict) else d)
                except Exception:
                    continue

            for rec in records:
                is_dup = False
                for ex in existing_records:
                    if self._is_duplicate_record(ex, rec):
                        if self._merge_record(ex, rec):
                            total_merged += 1
                        is_dup = True
                        break
                if not is_dup:
                    existing_records.append(rec)
                    total_added += 1

            records_by_year: dict[int, list[dict]] = {}
            for r in existing_records:
                year = _SM._extract_year_from_end_time(r.get("end_time", ""))
                records_by_year.setdefault(year, []).append(r)

            for year, year_records in records_by_year.items():
                year_file = os.path.join(self._history_dir, f"{serial}_{year}.json")
                data = {"version": HISTORY_VERSION, "year": year, "history": year_records}
                try:
                    with open(year_file, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                except Exception as err:
                    LOGGER.warning("写入序列号 %s 的 %d 年数据失败: %s", serial, year, err)

        return total_added, total_merged

    async def async_backup_history(self) -> str:
        """备份历史记录到 HA 备份目录"""
        if self.storage:
            return await self.storage.export_history_json()
        return ""
