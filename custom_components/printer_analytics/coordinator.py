from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import uuid
import gzip
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from homeassistant.util import dt as dt_util

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, Event, callback
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry
from homeassistant.helpers.device_registry import async_get as async_get_device_registry
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    ACTIVE_PRINT_STATUSES,
    BAMBULAB_ENTITY_KEYS,
    BAMBULAB_IMAGE_KEYS,
    BAMBULAB_CAMERA_KEYS,
    CHAMBER_TEMP_WINDOW_MINUTES,
    COLOR_CONFIRM_THRESHOLD,
    CONF_CHAMBER_TEMP_ENTITY,
    CONF_ENERGY_ENTITY,
    CONF_POWER_ENTITY,
    CONF_PRINTER_NAME,
    CONF_PRINT_STATUS_ENTITY,
    DURATION_BUCKETS,
    ENERGY_MAX_DELTA_KWH,
    ENTITY_DISCOVERY_DELAY_SECS,
    ENTITY_DISCOVERY_RETRY_SECS,
    FAILURE_STAGE_BUCKETS,
    DOMAIN,
    END_PRINT_STATUSES,
    HISTORY_VERSION,
    HTTP_CONNECTION_LIMIT,
    HTTP_CONNECTION_PER_HOST,
    HTTP_REQUEST_TIMEOUT_SECS,
    HTTP_SESSION_TIMEOUT_SECS,
    IMAGE_MIN_SIZE_BYTES,
    MATERIAL_CACHE_INTERVAL_SECONDS,
    MAX_FULL_BACKUPS,
    MAX_HISTORY_RECORDS,
    PRINT_STATUS_CANCELLED,
    PRINT_STATUS_FAIL,
    PRINT_STATUS_FINISH,
    PRINT_STATUS_IDLE,
    PRINT_STATUS_RUNNING,
    SYNC_ARCHIVE_COUNT,
    TASK_NAME_CAPTURE_WINDOW_SECS,
)
from .utils import BackupManager, SecureFileHandler, URLValidator

LOGGER = logging.getLogger(__name__)

_INVALID_ENTITY_STATES = frozenset({"unknown", "unavailable", ""})


@dataclass
class PrinterStats:
    total_prints: int = 0
    successful_prints: int = 0
    failed_prints: int = 0
    cancelled_prints: int = 0
    success_rate: float = 0.0
    average_duration_hours: float = 0.0
    total_duration_hours: float = 0.0
    total_weight_g: float = 0.0
    total_length_m: float = 0.0
    total_energy_kwh: float = 0.0
    stats_7d: dict = field(default_factory=dict)
    stats_30d: dict = field(default_factory=dict)
    stats_lifetime: dict = field(default_factory=dict)
    duration_distribution: dict = field(default_factory=dict)
    activity_heatmap: dict = field(default_factory=dict)
    failure_stage_distribution: dict = field(default_factory=dict)
    filament_success_stats: dict = field(default_factory=dict)
    history: list = field(default_factory=list)
    current_print: dict | None = None
    is_printing: bool = False
    last_update: str = ""
    _entity_map_debug: dict = field(default_factory=dict)


class PrinterAnalyticsCoordinator(DataUpdateCoordinator[PrinterStats]):
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

        # 修复#5: 共享HTTP会话（避免每次下载都创建新连接）
        self._http_session: aiohttp.ClientSession | None = None

        # 改为按年分片存储（支持100年数据）
        # 主存储目录：.printer_analytics（工作目录）
        self._history_base_dir = hass.config.path(".printer_analytics")
        self._history_dir = os.path.join(self._history_base_dir, "history_by_year")
        self._archive_dir = os.path.join(self._history_base_dir, "archives")
        self._exports_dir = os.path.join(self._history_base_dir, "exports")
        
        # HA标准备份路径：www/printer_analytics_data/（确保被HA快照备份）
        self._ha_backup_dir = hass.config.path("www", "printer_analytics_data")
        
        # 兼容旧版本的主文件路径（用于迁移）
        self._legacy_history_file = os.path.join(
            self._history_base_dir, f"{entry.entry_id}.json"
        )
        self._images_dir = hass.config.path("www", "printer_analytics")
        
        # 数据统计信息
        self._total_records = 0
        self._yearly_stats = {}  # {year: count}

    async def async_setup(self) -> None:
        await self._load_history()
        await self._discover_entities()
        self._detect_placeholder_images()
        if not self._entity_map.get("print_weight"):
            self.hass.loop.call_later(
                ENTITY_DISCOVERY_DELAY_SECS,
                lambda: self.hass.async_create_task(self._discover_entities()),
            )
            self.hass.loop.call_later(
                ENTITY_DISCOVERY_RETRY_SECS,
                lambda: self.hass.async_create_task(self._discover_entities()),
            )
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
        self._stop_material_cache()
        if self._unsub_listener:
            self._unsub_listener()
            self._unsub_listener = None
        await self._close_http_session()
        await self._save_history()

    async def _get_http_session(self) -> aiohttp.ClientSession:
        """获取或创建共享的HTTP会话"""
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
            LOGGER.debug("Created new HTTP session")
        return self._http_session

    def _get_ha_base_url(self) -> str:
        """获取 HA 基础 URL"""
        if hasattr(self.hass.config.api, 'base_url'):
            return self.hass.config.api.base_url
        return f"http://127.0.0.1:{self.hass.config.api.port}"

    def _get_auth_headers(self) -> dict[str, str]:
        """获取带认证的 HTTP 请求头"""
        headers: dict[str, str] = {}
        long_lived_token = self.entry.data.get("ha_token") or self.entry.options.get("ha_token")
        if long_lived_token:
            headers["Authorization"] = f"Bearer {long_lived_token}"
        return headers

    async def _close_http_session(self) -> None:
        """安全关闭HTTP会话"""
        if self._http_session and not self._http_session.closed:
            try:
                await self._http_session.close()
                LOGGER.debug("HTTP session closed")
            except Exception as err:
                LOGGER.warning("Error closing HTTP session: %s", err)
            finally:
                self._http_session = None

    async def _load_history(self) -> None:
        """加载历史记录（支持100年数据存储 + 重装后自动恢复）"""
        try:
            def _load():
                os.makedirs(self._history_dir, exist_ok=True)
                os.makedirs(self._archive_dir, exist_ok=True)
                os.makedirs(self._exports_dir, exist_ok=True)
                
                all_records = []
                
                if os.path.exists(self._legacy_history_file):
                    LOGGER.info("检测到旧版数据文件，开始迁移到分片存储...")
                    self._migrate_legacy_data()
                
                year_files = [f for f in os.listdir(self._history_dir) 
                             if f.startswith(f"{self.entry.entry_id}_") and f.endswith(".json")]
                
                # 如果当前entry_id没有数据，尝试从备份目录恢复
                if not year_files:
                    self._restore_from_backup_dir()
                    year_files = [f for f in os.listdir(self._history_dir) 
                                 if f.startswith(f"{self.entry.entry_id}_") and f.endswith(".json")]
                
                for year_file in sorted(year_files):
                    file_path = os.path.join(self._history_dir, year_file)
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            if isinstance(data, dict) and "history" in data:
                                records = data["history"]
                                all_records.extend(records)
                                year = year_file.replace(f"{self.entry.entry_id}_", "").replace(".json", "")
                                self._yearly_stats[year] = len(records)
                                LOGGER.debug("加载 %s 年数据: %d 条记录", year, len(records))
                    except Exception as err:
                        LOGGER.warning("加载年份文件失败 %s: %s", year_file, err)
                        BackupManager.restore_from_backup(file_path)
                
                all_records.sort(key=lambda x: x.get("end_time", ""))
                self._total_records = len(all_records)
                return all_records

            self.history = await self.hass.async_add_executor_job(_load)
            
            await self._fix_duration_hours()
            await self._fix_multi_color_misclassification()
            
            LOGGER.info(
                "成功加载 %d 条历史记录（%d 个年份），支持100年数据存储",
                self._total_records, len(self._yearly_stats),
            )
            
        except Exception as err:
            LOGGER.error("加载历史数据失败: %s", err)
            self.history = []

    async def _fix_duration_hours(self) -> None:
        """数据迁移：修复 duration_hours=0 的历史记录"""
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
            LOGGER.info("数据迁移：修复了 %d 条记录的 duration_hours", fixed)
            await self._save_history()

    async def _fix_multi_color_misclassification(self) -> None:
        """数据迁移：修复单色打印被误判为多色的历史记录"""
        fixed = 0
        for r in self.history:
            colors_used = r.get("colors_used", [])
            if not colors_used or len(colors_used) <= 1:
                continue

            # 先对 colors_used 去重（同一颜色可能因多 tray 或大小写差异重复）
            unique_colors = list(dict.fromkeys(
                c.lower() if isinstance(c, str) else c for c in colors_used
            ))

            # 去重后已经是单色，直接修正
            if len(unique_colors) == 1:
                self._fix_record_to_single_color(r, unique_colors)
                fixed += 1
                LOGGER.info(
                    "修复颜色去重: %s | %d色(含重复) → 1色%s",
                    r.get("task_name", "未知"),
                    len(colors_used), unique_colors
                )
                continue

            color_usage = r.get("color_usage", [])
            if not color_usage:
                continue

            # 从 color_usage 中提取实际有耗材消耗的颜色（统一小写去重）
            actual_colors = list(dict.fromkeys(
                entry.get("color", "").lower()
                for entry in color_usage
                if entry.get("weight_g", 0) > 0 and entry.get("color")
            ))

            if not actual_colors or len(actual_colors) >= len(unique_colors):
                continue

            # 实际消耗颜色数 < 记录的去重颜色数，说明是误判
            if len(actual_colors) == 1:
                self._fix_record_to_single_color(r, actual_colors)
            else:
                r["colors_used"] = actual_colors
                r["total_colors"] = len(actual_colors)
                if r.get("multi_color_summary"):
                    r["multi_color_summary"]["total_colors"] = len(actual_colors)
                    r["multi_color_summary"]["all_colors"] = actual_colors

            r["color_usage"] = [
                entry for entry in color_usage
                if entry.get("weight_g", 0) > 0
            ]
            fixed += 1
            LOGGER.info(
                "修复多色误判: %s | 原记录%d色 → 实际%d色",
                r.get("task_name", "未知"),
                len(colors_used), len(actual_colors)
            )

        if fixed > 0:
            LOGGER.info("数据迁移：修复了 %d 条记录的多色误判", fixed)
            await self._save_history()

    @staticmethod
    def _fix_record_to_single_color(record: dict, colors: list) -> None:
        """将记录修正为单色打印"""
        record["colors_used"] = colors
        record["total_colors"] = 1
        record["color_changes_count"] = 0
        record["multi_color_summary"] = None
        record["color_changes"] = []
        record["filament_color"] = colors[0]

    def _migrate_legacy_data(self) -> None:
        """将旧版本的单文件数据迁移到按年分片存储"""
        try:
            with open(self._legacy_history_file, "r", encoding="utf-8") as f:
                legacy_data = json.load(f)
            
            if not isinstance(legacy_data, dict) or "history" not in legacy_data:
                return
            
            records = legacy_data.get("history", [])
            if not records:
                return
            
            by_year = self._group_records_by_year(records)
            
            for year, year_records in by_year.items():
                year_file = os.path.join(self._history_dir, f"{self.entry.entry_id}_{year}.json")
                with open(year_file, "w", encoding="utf-8") as f:
                    json.dump({
                        "version": HISTORY_VERSION,
                        "printer_name": self.printer_name,
                        "year": year,
                        "history": year_records,
                    }, f, ensure_ascii=False, indent=2)
                
                self._yearly_stats[str(year)] = len(year_records)
                LOGGER.info("迁移 %d 年数据: %d 条记录", year, len(year_records))
            
            backup_path = self._legacy_history_file + ".legacy_backup"
            shutil.copy2(self._legacy_history_file, backup_path)
            os.remove(self._legacy_history_file)
            LOGGER.info("旧数据迁移完成，原文件已备份为: %s", backup_path)
            
        except Exception as err:
            LOGGER.error("迁移旧数据失败: %s", err)

    async def _save_history(self) -> None:
        """保存历史记录（按年分片存储 + 自动备份）"""
        try:
            def _write():
                os.makedirs(self._history_dir, exist_ok=True)
                os.makedirs(self._archive_dir, exist_ok=True)
                
                by_year = self._group_records_by_year(self.history)
                
                total_saved = 0
                for year, records in by_year.items():
                    year_file = os.path.join(self._history_dir, f"{self.entry.entry_id}_{year}.json")
                    
                    data = {
                        "version": HISTORY_VERSION,
                        "printer_name": self.printer_name,
                        "year": year,
                        "record_count": len(records),
                        "last_updated": datetime.now(timezone.utc).isoformat(),
                        "history": records,
                    }
                    
                    json_str = json.dumps(data, ensure_ascii=False, indent=2)
                    success = SecureFileHandler.atomic_write(year_file, json_str, encoding='utf-8')
                    
                    if success:
                        total_saved += len(records)
                        self._yearly_stats[str(year)] = len(records)
                        self._create_compressed_backup(year_file, year)
                        LOGGER.debug("保存 %d 年数据: %d 条记录", year, len(records))
                    else:
                        LOGGER.error("保存年份文件失败: %s", year_file)
                
                self._total_records = total_saved
                return True

            write_success = await self.hass.async_add_executor_job(_write)

            if write_success:
                LOGGER.info(
                    "历史数据已保存，共 %d 条记录（%d 个年份），支持100年数据存储",
                    self._total_records, len(self._yearly_stats),
                )
                
                await self.hass.async_add_executor_job(self._sync_to_ha_backup_dir)
                
                if datetime.now().day == 1:
                    await self.hass.async_add_executor_job(self._create_full_backup)
            else:
                LOGGER.error("保存历史数据失败")

        except Exception as err:
            LOGGER.error("保存历史数据失败: %s", err)

    def _create_compressed_backup(self, year_file: str, year: int) -> None:
        """为每年的数据创建压缩备份"""
        try:
            archive_file = os.path.join(self._archive_dir, f"{self.entry.entry_id}_{year}.json.gz")
            
            with open(year_file, 'rb') as f_in:
                with gzip.open(archive_file, 'wb', compresslevel=9) as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            LOGGER.debug("创建压缩备份: %s", archive_file)
            
        except Exception as err:
            LOGGER.warning("创建压缩备份失败: %s", err)

    def _create_full_backup(self) -> None:
        """创建完整备份"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = os.path.join(self._archive_dir, f"full_backup_{self.printer_name}_{timestamp}.json.gz")
            
            all_data = {
                "version": HISTORY_VERSION,
                "printer_name": self.printer_name,
                "backup_type": "full",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "total_records": len(self.history),
                "yearly_breakdown": dict(self._yearly_stats),
                "history": self.history,
            }
            
            json_str = json.dumps(all_data, ensure_ascii=False)
            with gzip.open(backup_file, 'wt', encoding='utf-8', compresslevel=9) as f:
                f.write(json_str)
            
            size_mb = os.path.getsize(backup_file) / (1024 * 1024)
            LOGGER.info("完整备份已创建: %s (%.2f MB, %d 条记录)", backup_file, size_mb, len(self.history))
            
            self._cleanup_old_backups()
            
        except Exception as err:
            LOGGER.error("创建完整备份失败: %s", err)

    def _cleanup_old_backups(self) -> None:
        """清理旧的完整备份"""
        try:
            backups = sorted([
                f for f in os.listdir(self._archive_dir)
                if f.startswith(f"full_backup_{self.printer_name}_") and f.endswith(".json.gz")
            ])
            
            while len(backups) > MAX_FULL_BACKUPS:
                old_backup = backups.pop(0)
                old_path = os.path.join(self._archive_dir, old_backup)
                os.remove(old_path)
                LOGGER.debug("删除旧备份: %s", old_backup)
                
        except Exception as err:
            LOGGER.warning("清理旧备份失败: %s", err)

    def _restore_from_backup_dir(self) -> None:
        """从HA备份目录恢复数据（重装集成后entry_id变化时自动恢复）"""
        try:
            ha_history_dir = os.path.join(self._ha_backup_dir, "history_by_year")
            if not os.path.exists(ha_history_dir):
                LOGGER.info("备份目录不存在，跳过恢复: %s", ha_history_dir)
                return

            # 读取metadata获取打印机名称匹配
            metadata_path = os.path.join(self._ha_backup_dir, "_backup_metadata.json")
            target_printer = self.printer_name

            # 查找备份中所有年份文件（可能来自不同entry_id）
            backup_files = [f for f in os.listdir(ha_history_dir) if f.endswith(".json")]
            if not backup_files:
                LOGGER.info("备份目录中无数据文件")
                return

            restored_count = 0
            for backup_file in backup_files:
                src_path = os.path.join(ha_history_dir, backup_file)
                try:
                    with open(src_path, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    # 验证数据格式
                    if not isinstance(data, dict) or "history" not in data:
                        continue

                    records = data.get("history", [])
                    if not records:
                        continue

                    # 按当前entry_id重命名并复制到主数据目录
                    # 从原文件名提取年份部分
                    parts = backup_file.replace(".json", "").split("_", 1)
                    year = parts[-1] if len(parts) > 1 else backup_file.replace(".json", "")

                    dst_file = f"{self.entry.entry_id}_{year}.json"
                    dst_path = os.path.join(self._history_dir, dst_file)
                    shutil.copy2(src_path, dst_path)
                    restored_count += 1
                    LOGGER.info("从备份恢复: %s -> %s (%d 条记录)", backup_file, dst_file, len(records))

                except Exception as err:
                    LOGGER.warning("恢复备份文件失败 %s: %s", backup_file, err)

            if restored_count > 0:
                LOGGER.info("从备份目录恢复了 %d 个年份数据文件（打印机: %s）", restored_count, target_printer)
            else:
                LOGGER.info("备份目录中无可恢复的数据")

        except Exception as err:
            LOGGER.error("从备份目录恢复数据失败: %s", err)

    def _sync_to_ha_backup_dir(self) -> None:
        """同步数据到HA标准备份路径"""
        try:
            ha_history_dir = os.path.join(self._ha_backup_dir, "history_by_year")
            ha_archive_dir = os.path.join(self._ha_backup_dir, "archives")
            os.makedirs(ha_history_dir, exist_ok=True)
            os.makedirs(ha_archive_dir, exist_ok=True)
            
            year_files = [f for f in os.listdir(self._history_dir) if f.endswith(".json")]
            
            for year_file in year_files:
                src = os.path.join(self._history_dir, year_file)
                dst = os.path.join(ha_history_dir, year_file)
                shutil.copy2(src, dst)
                LOGGER.debug("同步年份数据: %s", year_file)
            
            archive_files = sorted([f for f in os.listdir(self._archive_dir) if f.endswith(".gz")], reverse=True)[:SYNC_ARCHIVE_COUNT]
            
            for archive_file in archive_files:
                src = os.path.join(self._archive_dir, archive_file)
                dst = os.path.join(ha_archive_dir, archive_file)
                shutil.copy2(src, dst)
                LOGGER.debug("同步压缩备份: %s", archive_file)
            
            metadata = {
                "sync_version": "1.0",
                "last_sync_time": datetime.now(timezone.utc).isoformat(),
                "source_directory": self._history_base_dir,
                "target_directory": self._ha_backup_dir,
                "total_records": self._total_records,
                "yearly_statistics": dict(self._yearly_stats),
                "printer_name": self.printer_name,
                "note": "此目录由打印机分析插件自动生成，用于HA快照备份",
            }
            
            metadata_path = os.path.join(self._ha_backup_dir, "_backup_metadata.json")
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
            
            total_size = sum(os.path.getsize(os.path.join(dp, f)) for dp, dn, filenames in os.walk(self._ha_backup_dir) for f in filenames)
            
            size_mb = total_size / (1024 * 1024)
            LOGGER.info("数据已同步到HA备份路径: %s (%.2f MB, %d 个文件)", self._ha_backup_dir, size_mb, len(year_files) + len(archive_files) + 1)
            
        except Exception as err:
            LOGGER.error("同步到HA备份路径失败: %s", err)

    async def export_history_json(self, filepath: str | None = None) -> str:
        """导出所有历史数据为JSON文件"""
        try:
            if not filepath:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filepath = os.path.join(self._exports_dir, f"export_{self.printer_name}_{timestamp}.json")
            
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            export_data = {
                "export_version": "2.0",
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "printer_name": self.printer_name,
                "total_records": len(self.history),
                "yearly_statistics": dict(self._yearly_stats),
                "data": self.history,
            }
            
            def _write():
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, ensure_ascii=False, indent=2)
                return filepath
            
            result_path = await self.hass.async_add_executor_job(_write)
            
            size_mb = os.path.getsize(result_path) / (1024 * 1024)
            LOGGER.info("数据导出完成: %s (%.2f MB, %d 条记录)", result_path, size_mb, len(self.history))
            
            return result_path
            
        except Exception as err:
            LOGGER.error("导出数据失败: %s", err)
            raise

    async def get_storage_statistics(self) -> dict:
        """获取存储统计信息"""
        def _calc():
            stats = {
                "total_records": len(self.history),
                "total_years": len(self._yearly_stats),
                "yearly_breakdown": dict(self._yearly_stats),
                "storage_size": {},
                "oldest_record": None,
                "newest_record": None,
            }
            
            for dir_path, name in [(self._history_dir, "history_by_year"), (self._archive_dir, "archives"), (self._exports_dir, "exports")]:
                if os.path.exists(dir_path):
                    total_size = sum(os.path.getsize(os.path.join(dir_path, f)) for f in os.listdir(dir_path) if os.path.isfile(os.path.join(dir_path, f)))
                    stats["storage_size"][name] = round(total_size / (1024 * 1024), 2)
            
            if self.history:
                try:
                    stats["oldest_record"] = min(r.get("end_time", "") for r in self.history) or None
                    stats["newest_record"] = max(r.get("end_time", "") for r in self.history) or None
                except (ValueError, TypeError):
                    pass
            
            return stats
        
        return await self.hass.async_add_executor_job(_calc)

    async def _discover_entities(self) -> None:
        try:
            entity_reg = async_get_entity_registry(self.hass)
            device_reg = async_get_device_registry(self.hass)
            reg_entry = entity_reg.async_get(self.print_status_entity)
            self._discover_debug = f"status_entity={self.print_status_entity}, reg_entry={reg_entry is not None}, device_id={reg_entry.device_id if reg_entry else 'N/A'}"
            if reg_entry is None or reg_entry.device_id is None:
                LOGGER.warning("Could not find device for %s (reg_entry=%s)", self.print_status_entity, reg_entry)
                return
            LOGGER.info("Found device for %s: device_id=%s, platform=%s", self.print_status_entity, reg_entry.device_id, reg_entry.platform)
            
            all_entries = list(entity_reg.entities.values()) if hasattr(entity_reg, 'entities') else []
            if not all_entries:
                all_entries = list(entity_reg._registry.values()) if hasattr(entity_reg, '_registry') else []
            if not all_entries and hasattr(entity_reg, 'async_entries_for_device'):
                all_entries = list(entity_reg.async_entries_for_device(reg_entry.device_id))
            entities = [e for e in all_entries if getattr(e, 'device_id', None) == reg_entry.device_id]
            self._discover_debug = f"all={len(all_entries)}, matching={len(entities)}, device={reg_entry.device_id}"
            LOGGER.info("Found %d entities for device %s", len(entities), reg_entry.device_id)
            
            for ent in entities:
                uid = getattr(ent, 'unique_id', '')
                eid = getattr(ent, 'entity_id', '')
                domain = getattr(ent, 'domain', '')
                for key, suffixes in BAMBULAB_ENTITY_KEYS.items():
                    if any(uid.endswith(f"_{s}") for s in suffixes):
                        self._entity_map[key] = eid
                for key, suffix in BAMBULAB_IMAGE_KEYS.items():
                    if uid.endswith(f"_{suffix}") and getattr(ent, 'domain', '') == "image":
                        self._entity_map[key] = eid
                        break
                for key, suffix in BAMBULAB_CAMERA_KEYS.items():
                    if uid.endswith(f"_{suffix}") and getattr(ent, 'domain', '') == "camera":
                        self._entity_map[key] = eid
                        break
            
            LOGGER.info("Discovered entities for %s: %s", self.print_status_entity, self._entity_map)
            self._discover_debug += f"\n  FINAL entity_map: {dict(self._entity_map)}"
        except Exception as err:
            self._discover_debug = f"ERROR: {err}"
            LOGGER.error("Entity discovery failed for %s: %s", self.print_status_entity, err)

    @staticmethod
    def _extract_year_from_end_time(end_time: str) -> int:
        """从 end_time 字符串提取年份，失败则返回当前年"""
        if end_time:
            try:
                return datetime.fromisoformat(end_time).year
            except (ValueError, TypeError):
                pass
        return datetime.now().year

    def _group_records_by_year(self, records: list[dict]) -> dict[int, list[dict]]:
        """将记录按 end_time 的年份分组"""
        by_year: dict[int, list[dict]] = {}
        for record in records:
            year = self._extract_year_from_end_time(record.get("end_time", ""))
            by_year.setdefault(year, []).append(record)
        return by_year

    def _get_entity_state(self, entity_id: str, default: Any = None) -> Any:
        if not entity_id:
            return default
        state = self.hass.states.get(entity_id)
        if state is None:
            return default
        return state.state

    def _get_best_task_name(self) -> str:
        """
        获取最佳任务名称
        
        策略：
        1. 如果已锁定过名称（打印开始时捕获），直接返回
        2. 否则优先使用task_name（云端任务名或原始文件名）
        3. 仅当task_name为空时才回退gcode_filename（取basename去路径）
        
        BambuLab的task_name在云打印时显示云端任务名(如'宜家IKEA Skadis...')，
        gcode_filename通常是本地文件路径(如'/data/Metadata/plate_1.gcode')
        """
        if self._locked_task_name:
            return self._locked_task_name

        task_name = self._get_entity_state(self._entity_map.get("task_name", ""), "")
        gcode_filename = self._get_entity_state(self._entity_map.get("gcode_filename", ""), "")

        # 优先task_name（云端任务名），但过滤参数描述
        if task_name and task_name not in _INVALID_ENTITY_STATES:
            real_name = self._extract_real_task_name(task_name)
            if real_name:
                return real_name

        # 回退gcode_filename，去掉路径前缀只保留文件名
        if gcode_filename and gcode_filename not in _INVALID_ENTITY_STATES:
            basename = os.path.basename(gcode_filename)
            if basename and basename != gcode_filename:
                return basename
            return gcode_filename

        return ""

    def _lock_task_name(self, name: str) -> None:
        """锁定任务名称，防止后续被BambuLab更新为参数描述覆盖"""
        if name and name not in _INVALID_ENTITY_STATES:
            self._locked_task_name = name
            LOGGER.debug("Task name locked: %s", name)

    def _clear_locked_task_name(self) -> None:
        """清除锁定的任务名称（打印结束时调用）"""
        self._locked_task_name = ""

    def _is_param_description(self, task_name: str) -> bool:
        """检测任务名称是否包含BambuLab的打印参数描述"""
        if not task_name:
            return False

        param_patterns = [
            r'层高',
            r'层墙',
            r'填充',
            r'layer_height',
            r'shell',
            r'infill',
            r'^\d+\.\d+mm\s',
            r'\d+%\s*填充',
            r'\d+%\s*infill',
        ]

        for pattern in param_patterns:
            if re.search(pattern, task_name, re.IGNORECASE):
                return True

        return False

    def _extract_real_task_name(self, task_name: str) -> str | None:
        """从混合了参数描述的任务名中提取真实名称
        
        如 "添加进料微动安装孔位 0.28mm 层高, 2 层墙, 15% 填充"
        -> "添加进料微动安装孔位"
        
        如 "0.2mm 层高, 2 层墙, 15% 填充  心愿点击器大合集"
        -> "心愿点击器大合集"
        
        如 "0.24mm 层高, 2 层墙, 15% 填充" -> None（纯参数描述）
        """
        if not task_name:
            return None
        
        if not self._is_param_description(task_name):
            return task_name
        
        # 以数字+mm开头，尝试提取参数描述之后的真实名称
        if re.match(r'^\d+\.\d+mm', task_name) or re.match(r'^\d+mm', task_name):
            # Bambu Lab格式: "0.2mm 层高, 2 层墙, 15% 填充  真实名称"
            # 用连续2+空格分割，取最后一段
            parts = re.split(r'\s{2,}', task_name.strip())
            if len(parts) >= 2:
                real_name = parts[-1].strip()
                if real_name and len(real_name) >= 2 and not re.match(r'^\d+\.\d+mm', real_name):
                    return real_name
            # 也尝试 "15% 填充" 之后的内容
            match = re.search(r'\d+%\s*填充\s+(.+)$', task_name)
            if match:
                real_name = match.group(1).strip()
                if real_name and len(real_name) >= 2:
                    return real_name
            return None
        
        # 尝试在参数描述前截取真实名称
        separators = [
            r'\s+\d+\.\d+mm',       # "名称 0.2mm"
            r'\s+\d+mm\s',          # "名称 2mm "
            r',\s*\d+\.\d+mm',      # "名称, 0.2mm"
            r'\s+layer_height',      # "名称 layer_height"
            r'\s+层高',              # "名称 层高"
        ]
        
        for sep in separators:
            match = re.search(sep, task_name, re.IGNORECASE)
            if match:
                real_name = task_name[:match.start()].strip().rstrip(',').strip()
                if real_name and len(real_name) >= 2 and not re.match(r'^\d+\.\d+mm', real_name):
                    return real_name
        
        # 纯参数描述，没有真实名称
        return None

    def _get_entity_attr(self, entity_id: str, attr: str, default: Any = None) -> Any:
        if not entity_id:
            return default
        state = self.hass.states.get(entity_id)
        if state is None:
            return default
        return state.attributes.get(attr, default)

    def _get_float_state(self, entity_id: str, default: float = 0.0) -> float:
        val = self._get_entity_state(entity_id)
        if val is None or val in _INVALID_ENTITY_STATES:
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
        start_energy = self._get_float_state(self.energy_entity)
        self.current_print = {
            "id": str(uuid.uuid4()),
            "start_time": datetime.now(timezone.utc).isoformat(),
            "status": "running",
            "start_energy": start_energy,
            "energy_valid": start_energy > 0,
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
        
        if not self._entity_map.get("print_weight"):
            self.hass.async_create_task(self._discover_entities())
        
        old_status = self._previous_status
        if old_status == new_status:
            return
        
        LOGGER.debug("Print status change for %s: %s -> %s", self.printer_name, old_status, new_status)

        if self.current_print is not None and new_status in ACTIVE_PRINT_STATUSES:
            self._cache_print_material_data()

        if old_status not in ACTIVE_PRINT_STATUSES and new_status == PRINT_STATUS_RUNNING:
            self._on_print_start()
        elif old_status in ACTIVE_PRINT_STATUSES and new_status in END_PRINT_STATUSES:
            self.hass.async_create_task(self._on_print_end(new_status))
        elif old_status in ACTIVE_PRINT_STATUSES and new_status == PRINT_STATUS_IDLE:
            self.hass.async_create_task(self._on_print_end(PRINT_STATUS_CANCELLED))
        
        self._previous_status = new_status
        self.async_set_updated_data(self._calculate_statistics())

    def _cache_print_material_data(self) -> None:
        """打印过程中持续缓存耗材数据（基于 AMS tray attributes 的多色用量追踪）"""
        if not self._entity_map.get("print_weight") or not self._entity_map.get("print_length"):
            self.hass.async_create_task(self._discover_entities())
        
        weight_entity = self._entity_map.get("print_weight", "")
        length_entity = self._entity_map.get("print_length", "")
        
        total_weight = self._get_float_state(weight_entity)
        total_length = self._get_float_state(length_entity)
        current_type, current_color = self._get_current_filament_info()
        
        if total_weight:
            self.current_print["cached_weight"] = total_weight
        if total_length:
            self.current_print["cached_length"] = total_length

        if not current_color or not total_weight:
            return

        # 从 print_weight/print_length 的 attributes 中提取 AMS tray 用量
        weight_state = self.hass.states.get(weight_entity)
        length_state = self.hass.states.get(length_entity)
        
        if weight_state and length_state:
            weight_attrs = weight_state.attributes
            length_attrs = length_state.attributes
            
            # 提取 "AMS X Tray Y" 格式的属性值
            ams_weights = {}
            ams_lengths = {}
            for k, v in weight_attrs.items():
                if k.startswith("AMS") and "Tray" in k:
                    try:
                        ams_weights[k] = float(v)
                    except (ValueError, TypeError):
                        pass
            for k, v in length_attrs.items():
                if k.startswith("AMS") and "Tray" in k:
                    try:
                        ams_lengths[k] = float(v)
                    except (ValueError, TypeError):
                        pass
            
            if ams_weights:
                active_state = self.hass.states.get(self._entity_map.get("active_tray", ""))
                tray_color_map = self._build_tray_color_map()
                
                # 按颜色聚合：同色不同 tray 合并为一条记录
                color_agg: dict[str, dict] = {}
                
                for tray_key, weight in ams_weights.items():
                    if weight <= 0:
                        continue
                    length = ams_lengths.get(tray_key, 0)
                    color_info = tray_color_map.get(tray_key, {})
                    raw_color = color_info.get("color", current_color) or current_color
                    color_key = raw_color.lower() if isinstance(raw_color, str) else str(raw_color)
                    
                    if color_key not in color_agg:
                        color_agg[color_key] = {
                            "color": raw_color,
                            "type": color_info.get("type", current_type),
                            "weight_g": 0.0,
                            "length_m": 0.0,
                            "trays": [],
                            "start_time": self.current_print.get("start_time"),
                        }
                    
                    entry = color_agg[color_key]
                    entry["weight_g"] += weight
                    entry["length_m"] += length
                    entry["trays"].append(tray_key)
                
                color_usage = self.current_print.setdefault("color_usage", [])
                color_usage.clear()
                
                for entry in color_agg.values():
                    color_usage.append({
                        "color": entry["color"],
                        "type": entry["type"],
                        "weight_g": round(entry["weight_g"], 2),
                        "length_m": round(entry["length_m"], 2),
                        "tray": ", ".join(entry["trays"]) if len(entry["trays"]) > 1 else (entry["trays"][0] if entry["trays"] else ""),
                        "start_time": entry["start_time"],
                    })
                
                self.current_print["ams_tray_data"] = True

    def _build_tray_color_map(self) -> dict[str, dict]:
        """构建 AMS tray -> (color, type) 的映射"""
        result = {}
        active_entity = self._entity_map.get("active_tray", "")
        if not active_entity:
            return result
        
        # 遍历所有 AMS tray 实体获取颜色信息
        for state in self.hass.states.async_all():
            eid = state.entity_id
            if "ams" in eid and "tray" in eid and eid.startswith("sensor."):
                attrs = state.attributes
                tray_name = attrs.get("friendly_name", "")
                # 从 entity_id 提取 tray 编号，如 ams_1_tray_1
                # 从 friendly_name 提取 "AMS 1 Tray 1" 格式
                parts = eid.split("_")
                ams_idx = None
                tray_idx = None
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
                    name = state.state if state.state not in _INVALID_ENTITY_STATES else ""
                    result[key] = {
                        "color": color,
                        "type": name,
                    }
        
        return result

    def _start_material_cache(self) -> None:
        """启动定时缓存耗材数据"""
        self._stop_material_cache()
        self._material_cache_interval = async_track_time_interval(self.hass, self._on_material_cache_tick, timedelta(seconds=MATERIAL_CACHE_INTERVAL_SECONDS))

    def _stop_material_cache(self) -> None:
        """停止定时缓存"""
        if self._material_cache_interval:
            self._material_cache_interval()
            self._material_cache_interval = None

    @callback
    def _on_material_cache_tick(self, now: datetime) -> None:
        """定时缓存耗材数据（支持多色追踪 + 任务名持续捕获）"""
        if self.current_print is not None:
            self._cache_print_material_data()
            self._track_color_changes()
            self._cache_delayed_fields()
            self._try_capture_task_name()
            self._cache_chamber_temperature(now)

    def _try_capture_task_name(self) -> None:
        """
        在打印开始后的1分钟窗口期内捕获任务名称
        
        BambuLab的task_name实体在打印开始后的变化：
        - 0-10秒：空/"unknown"
        - 10-30秒：云任务名出现 "洞洞板拓展（兼容宜家IKEA Skadis）" ← 目标！
        - 30秒+：被覆盖为 "0.24mm 层高, 2 层墙, 15% 填充"
        
        只需在开始后1分钟内持续检查，一旦发现有效非参数描述就锁定
        """
        if not self.current_print:
            return

        current_name = self.current_print.get("task_name")
        if current_name and not self._is_param_description(current_name):
            return

        start_time = self.current_print.get("start_time", "")
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

        new_name = self._get_entity_state(task_entity, "")
        if not new_name or new_name in _INVALID_ENTITY_STATES:
            return

        if self._is_param_description(new_name):
            LOGGER.debug("[%ds] task_name是参数描述，跳过: %s", int(elapsed), new_name)
            return

        if new_name != current_name:
            self.current_print["task_name"] = new_name
            self._lock_task_name(new_name)
            LOGGER.info("✅ [%ds] 成功捕获任务名称: %s", int(elapsed), new_name)

    def _cache_delayed_fields(self) -> None:
        """补获打印开始时可能延迟就绪的字段（task_name 等）"""
        if not self.current_print:
            return

        current_name = self.current_print.get("task_name", "")
        need_better = not current_name or self._is_param_description(current_name) or current_name.startswith("/data/")
        if need_better:
            raw_task_name = self._get_entity_state(self._entity_map.get("task_name", ""), "")
            raw_gcode = self._get_entity_state(self._entity_map.get("gcode_filename", ""), "")
            candidate = None
            if raw_task_name and raw_task_name not in _INVALID_ENTITY_STATES:
                candidate = self._extract_real_task_name(raw_task_name)
            if not candidate and raw_gcode and raw_gcode not in _INVALID_ENTITY_STATES:
                basename = os.path.basename(raw_gcode)
                if basename and basename != raw_gcode and not self._is_param_description(basename):
                    candidate = basename
            if candidate and candidate != current_name:
                LOGGER.info("Task name improved: '%s' -> '%s'", (current_name or "")[:40], candidate[:40])
                self.current_print["task_name"] = candidate
                self._lock_task_name(candidate)

        if not self.current_print.get("nozzle_size"):
            nozzle_size = self._get_entity_state(self._entity_map.get("nozzle_size", ""), "")
            if nozzle_size:
                self.current_print["nozzle_size"] = nozzle_size

        if not self.current_print.get("total_layer_count"):
            total_layer_count = self._get_float_state(self._entity_map.get("total_layer_count", ""), 0)
            if total_layer_count:
                self.current_print["total_layer_count"] = int(total_layer_count)

        if not self.current_print.get("energy_valid"):
            start_energy = self._get_float_state(self.energy_entity)
            if start_energy > 0:
                self.current_print["start_energy"] = start_energy
                self.current_print["energy_valid"] = True

    def _cache_chamber_temperature(self, now: datetime) -> None:
        """定时采集腔体温度（每60秒记录一次，打印结束时取最后5分钟）
        
        优先使用打印机内置chamber_temperature实体，
        若不存在则使用用户配置的外部温度传感器（如环境温湿度计）
        """
        if not self.current_print:
            return
        # 优先使用自动发现的chamber_temperature实体
        chamber_entity = self._entity_map.get("chamber_temperature")
        # 若未发现，回退到用户配置的外部温度传感器
        if not chamber_entity:
            chamber_entity = self.chamber_temp_entity
        if not chamber_entity:
            # 调试：每10分钟输出一次未配置腔温传感器的警告
            if not hasattr(self, '_chamber_warn_count'):
                self._chamber_warn_count = 0
            self._chamber_warn_count += 1
            if self._chamber_warn_count <= 1:
                LOGGER.warning("[%s] 未配置腔体温度传感器，entity_map=%s, user_config=%s",
                    self.printer_name, self._entity_map.get("chamber_temperature"), self.chamber_temp_entity)
            return
        temp = self._get_float_state(chamber_entity, None)
        if temp is None:
            return
        if "chamber_temp_timeline" not in self.current_print:
            self.current_print["chamber_temp_timeline"] = []
        self.current_print["chamber_temp_timeline"].append({
            "time": now.isoformat(),
            "temp": round(temp, 1),
        })

    def _get_current_filament_info(self) -> tuple[str, str]:
        """获取当前激活的耗材信息（类型, 颜色）"""
        ftype = self._get_entity_attr(
            self._entity_map.get("active_tray", ""), "name", ""
        )
        color = self._get_entity_attr(
            self._entity_map.get("active_tray", ""), "color", ""
        )
        return (ftype or "", color or "")

    def _track_color_changes(self) -> None:
        """
        追踪打印过程中的颜色变化（支持最多16色）
        
        防误判策略：
        1. 颜色统一转小写比较，避免大小写差异误判
        2. 新颜色必须连续3次被检测到才确认
        """
        if not self.current_print:
            return
        
        current_type, current_color = self._get_current_filament_info()
        
        # 颜色统一转小写，避免 #FF0000 vs #ff0000 误判
        if current_color:
            current_color = current_color.lower()
        
        colors_used = [c.lower() if isinstance(c, str) else c for c in self.current_print.get("colors_used", [])]
        types_used = self.current_print.get("types_used", [])
        
        old_color = self.current_print.get("filament_color")
        old_type = self.current_print.get("filament_type")
        
        if not colors_used and old_color:
            colors_used = [old_color.lower()]
        if not types_used and old_type:
            types_used = [old_type]
        
        # 颜色变化确认机制：连续3次检测到新颜色才确认
        if current_color and current_color not in colors_used:
            pending = self.current_print.get("_pending_color")
            pending_count = self.current_print.get("_pending_color_count", 0)
            
            if pending == current_color:
                pending_count += 1
                if pending_count >= COLOR_CONFIRM_THRESHOLD:
                    # 连续N次检测到同一新颜色，确认为真正的颜色切换
                    colors_used.append(current_color)
                    change_count = len(colors_used) - 1
                    
                    if "color_changes" not in self.current_print:
                        self.current_print["color_changes"] = []
                    
                    self.current_print["color_changes"].append({
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "from_color": colors_used[-2] if len(colors_used) > 1 else None,
                        "to_color": current_color,
                        "from_type": types_used[-1] if types_used else None,
                        "to_type": current_type,
                        "change_number": change_count,
                    })
                    
                    LOGGER.info(
                        "耗材切换 #%d: %s → %s (%s)",
                        change_count,
                        colors_used[-2] if len(colors_used) > 1 else "初始",
                        current_color,
                        current_type or "未知"
                    )
                    self.current_print["_pending_color"] = None
                    self.current_print["_pending_color_count"] = 0
                else:
                    self.current_print["_pending_color_count"] = pending_count
                    LOGGER.debug("待确认颜色切换: %s (%s) %d/%d", current_color, current_type, pending_count, COLOR_CONFIRM_THRESHOLD)
            else:
                # 检测到不同颜色，重置计数
                self.current_print["_pending_color"] = current_color
                self.current_print["_pending_color_count"] = 1
                LOGGER.debug("新颜色检测: %s (%s) 1/%d", current_color, current_type, COLOR_CONFIRM_THRESHOLD)
        else:
            # 当前颜色已在列表中，清除待确认状态
            self.current_print["_pending_color"] = None
            self.current_print["_pending_color_count"] = 0
        
        if current_type and current_type not in types_used:
            types_used.append(current_type)
        
        self.current_print["colors_used"] = colors_used
        self.current_print["types_used"] = types_used
        
        if colors_used:
            self.current_print["filament_color"] = colors_used[0]
            self.current_print["filament_type"] = types_used[0] if types_used else None

    def _on_print_start(self) -> None:
        """打印开始初始化（支持多色追踪）"""
        if not self._entity_map.get("print_weight"):
            self.hass.async_create_task(self._discover_entities())
        
        start_time_entity = self._entity_map.get("start_time")
        start_time_val = self._get_entity_state(start_time_entity)
        if start_time_val:
            start_time = self._ensure_timezone(start_time_val)
        else:
            start_time = datetime.now(timezone.utc).isoformat()
        
        task_name = self._get_best_task_name()
        self._lock_task_name(task_name)
        nozzle_type = self._get_entity_state(self._entity_map.get("nozzle_type", ""), "")
        nozzle_size = self._get_entity_state(self._entity_map.get("nozzle_size", ""), "")
        print_bed_type = self._get_entity_state(self._entity_map.get("print_bed_type", ""), "")
        total_layer_count = self._get_float_state(self._entity_map.get("total_layer_count", ""), 0)
        
        # 获取初始耗材信息，颜色统一转小写
        filament_type, filament_color = self._get_current_filament_info()
        if filament_color:
            filament_color = filament_color.lower()
        cover_entity = self._entity_map.get("cover_image", "")
        if not cover_entity:
            prefix = self.printer_name.lower()
            image_entities = list(self.hass.states.async_entity_ids("image"))
            for eid in image_entities:
                if eid.startswith(f"image.{prefix}_") and eid.endswith("_cover_image"):
                    cover_entity = eid
                    break
        cover_image_url = self._get_entity_attr(cover_entity, "entity_picture", "")
        
        start_energy = self._get_float_state(self.energy_entity)

        self.current_print = {
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
        
        self._start_material_cache()
        LOGGER.info(
            "Print started on %s: %s | 初始颜色: %s (%s)",
            self.printer_name, task_name, filament_color, filament_type
        )
        self.hass.async_create_task(self._delayed_cover_download(task_name or "unknown", start_time))
        self.hass.async_create_task(self._delayed_snapshot_download(task_name or "unknown", start_time))

    async def _delayed_cover_download(self, task_name: str, start_time: str) -> None:
        """打印开始后延迟下载封面图，等待 Bambu Lab 集成更新 cover_image 实体"""
        await asyncio.sleep(10)
        if not self.current_print:
            return
        if self.current_print.get("cover_image_local"):
            return
        local_path = await self._download_cover_image(
            self.current_print.get("cover_image_url", ""),
            task_name,
            start_time,
        )
        if local_path and self.current_print:
            self.current_print["cover_image_local"] = local_path
            LOGGER.info("Cover image downloaded at print start for %s: %s", task_name[:30], local_path)

    async def _delayed_snapshot_download(self, task_name: str, start_time: str) -> None:
        """打印期间每30秒截取摄像头快照，始终只保留最新的，打印结束/失败/取消时停止"""
        interval = 30
        while True:
            await asyncio.sleep(interval)
            if not self.current_print:
                return
            status = self.current_print.get("status", "")
            if status in (PRINT_STATUS_FINISH, PRINT_STATUS_FAIL, PRINT_STATUS_CANCELLED, "idle"):
                return
            old_path = self.current_print.get("snapshot_image_local")
            local_path = await self._download_print_snapshot(start_time, task_name)
            if local_path and self.current_print:
                self.current_print["snapshot_image_local"] = local_path
                if old_path:
                    self.hass.async_create_task(self._delete_image_file(old_path))
                LOGGER.debug("Snapshot updated for %s: %s", task_name[:30], local_path)

    _PLACEHOLDER_IMAGE_HASHES: set[str] = {
        "5a52bcafb0656745b398b5a811640c90",
        "c1aad0332d82134d188d487939f7e978",
    }

    def _detect_placeholder_images(self) -> None:
        """扫描已有封面图，自动检测占位图（内容完全相同且出现多次的图片）"""
        import hashlib
        if not os.path.isdir(self._images_dir):
            return
        hash_counts: dict[str, int] = {}
        for fname in os.listdir(self._images_dir):
            if not fname.lower().endswith((".jpg", ".jpeg", ".png")):
                continue
            fpath = os.path.join(self._images_dir, fname)
            if not os.path.isfile(fpath):
                continue
            try:
                with open(fpath, "rb") as f:
                    h = hashlib.md5(f.read()).hexdigest()
                hash_counts[h] = hash_counts.get(h, 0) + 1
            except OSError:
                pass
        for h, count in hash_counts.items():
            if count >= 3:
                self._PLACEHOLDER_IMAGE_HASHES.add(h)
                LOGGER.info("Detected placeholder image hash %s (%d identical files)", h[:12], count)

    @classmethod
    def _is_placeholder_image(cls, content: bytes) -> bool:
        """检查下载的图片是否为占位图"""
        if not cls._PLACEHOLDER_IMAGE_HASHES:
            return False
        import hashlib
        return hashlib.md5(content).hexdigest() in cls._PLACEHOLDER_IMAGE_HASHES

    def _get_bambu_cloud_client(self):
        """获取 Bambu Lab 集成的 cloud 客户端"""
        bambu_domain = "bambu_lab"
        if bambu_domain not in self.hass.data:
            return None
        for entry_id, coord in self.hass.data[bambu_domain].items():
            if entry_id == "service_call_future":
                continue
            client = getattr(coord, "client", None)
            if client and hasattr(client, "bambu_cloud"):
                cloud = client.bambu_cloud
                if getattr(cloud, "bambu_connected", False):
                    serial = getattr(client, "_serial", "")
                    if serial.upper() == self._get_printer_serial().upper():
                        return cloud
        for entry_id, coord in self.hass.data[bambu_domain].items():
            if entry_id == "service_call_future":
                continue
            client = getattr(coord, "client", None)
            if client and hasattr(client, "bambu_cloud"):
                cloud = client.bambu_cloud
                if getattr(cloud, "bambu_connected", False):
                    return cloud
        return None

    def _get_printer_serial(self) -> str:
        """从实体 ID 中提取打印机序列号"""
        serial_entity = self._entity_map.get("serial_number", "")
        if serial_entity:
            state = self.hass.states.get(serial_entity)
            if state and state.state not in _INVALID_ENTITY_STATES:
                return state.state
        cover_entity = self._entity_map.get("cover_image", "")
        if cover_entity:
            match = re.search(r'image\.\w+_(\w+)_cover_image', cover_entity)
            if match:
                return match.group(1).upper()
        return ""

    async def _download_cover_from_cloud(self, task_name: str, end_time: str, start_time: str = "") -> str | None:
        """通过 Bambu Cloud API 获取历史任务的封面图"""
        try:
            cloud = self._get_bambu_cloud_client()
            if not cloud:
                LOGGER.warning("No Bambu Cloud client available for cover download")
                return None

            serial = self._get_printer_serial()
            if not serial:
                LOGGER.warning("Cannot determine printer serial for cloud cover download")
                return None

            def _get_cloud_tasks():
                return cloud.get_tasklist_for_printer(serial)

            tasks = await self.hass.async_add_executor_job(_get_cloud_tasks)
            if not tasks:
                LOGGER.info("No cloud tasks found for printer %s", serial)
                return None

            end_dt = self._normalize_to_utc(end_time) if end_time else None
            start_dt = self._normalize_to_utc(start_time) if start_time else None
            LOGGER.info("Cloud cover lookup for %s: end_time=%s, start_time=%s, end_dt=%s, start_dt=%s, total_cloud_tasks=%d", (task_name or "unknown")[:30], end_time[:25] if end_time else "N/A", start_time[:25] if start_time else "N/A", end_dt, start_dt, len(tasks))
            best_match = None
            best_score = 999999
            for task in tasks:
                task_end = task.get("endTime", "")
                task_start = task.get("startTime", "")
                if not task_end:
                    continue
                try:
                    task_end_dt = datetime.fromisoformat(task_end.replace("Z", "+00:00"))
                    if not end_dt:
                        continue
                    end_diff = abs((task_end_dt - end_dt).total_seconds())
                    LOGGER.debug("Cloud task: endTime=%s, end_diff=%.0fs, cover=%s", task_end[:25], end_diff, task.get("cover", "")[:50] if task.get("cover") else "NONE")
                    if end_diff > 600:
                        continue
                    score = end_diff
                    task_start_dt = datetime.fromisoformat(task_start.replace("Z", "+00:00")) if task_start else None
                    if task_start_dt and start_dt:
                        start_diff = abs((task_start_dt - start_dt).total_seconds())
                        score = end_diff + start_diff
                    if score < best_score:
                        best_score = score
                        cover_url = task.get("cover", "")
                        if cover_url:
                            best_match = {"cover_url": cover_url, "score": score, "title": task.get("designTitle", "")}
                except (ValueError, TypeError):
                    continue

            if not best_match or not best_match["cover_url"]:
                LOGGER.info("No matching cloud task found for %s (end_time=%s, start_time=%s)", (task_name or "unknown")[:30], end_time[:25] if end_time else "N/A", start_time[:25] if start_time else "N/A")
                return None

            if best_score > 600:
                LOGGER.info("Cloud task match too imprecise for %s (score=%d), skipping", (task_name or "unknown")[:30], best_score)
                return None

            LOGGER.info("Matched cloud task for %s: cover=%s, score=%d, title=%s", (task_name or "unknown")[:30], best_match["cover_url"][:80], best_score, best_match["title"][:40])
            cover_url = best_match["cover_url"]

            safe_task_name = SecureFileHandler.sanitize_filename(task_name or "unknown")
            safe_time = re.sub(r'[^\dT]', '_', (end_time or '')[:19])
            filename = f"{safe_task_name}_{safe_time}.jpg"

            def _ensure_dir():
                os.makedirs(self._images_dir, exist_ok=True)
            await self.hass.async_add_executor_job(_ensure_dir)

            filepath = SecureFileHandler.safe_join(self._images_dir, filename)
            if not filepath:
                return None

            def _download():
                return cloud.download(cover_url)

            content = await self.hass.async_add_executor_job(_download)
            if not content or len(content) < IMAGE_MIN_SIZE_BYTES:
                LOGGER.warning("Cloud cover download failed or too small for %s", (task_name or "unknown")[:30])
                return None

            if self._is_placeholder_image(content):
                LOGGER.warning("Cloud cover is a placeholder for %s", (task_name or "unknown")[:30])
                return None

            def _write():
                with open(filepath, "wb") as f:
                    f.write(content)
            await self.hass.async_add_executor_job(_write)

            local_path = f"/local/printer_analytics/{filename}"
            LOGGER.info("Cloud cover image saved: %s (%d bytes)", local_path, len(content))
            return local_path
        except Exception as err:
            LOGGER.error("Failed to download cover from cloud for %s: %s", (task_name or "unknown")[:30], err)
            return None

    async def _download_cover_image(self, image_url: str, task_name: str, end_time: str) -> str | None:
        """下载封面图片到本地 - 优先使用 image 组件 API，无需 HTTP 请求"""
        try:
            cover_entity = self._entity_map.get("cover_image")
            if not cover_entity:
                prefix = self.printer_name.lower()
                image_entities = list(self.hass.states.async_entity_ids("image"))
                for eid in image_entities:
                    if eid.startswith(f"image.{prefix}_") and eid.endswith("_cover_image"):
                        cover_entity = eid
                        break

            content = None
            if cover_entity:
                try:
                    from homeassistant.components.image import async_get_image as async_get_cover_image
                    img = await async_get_cover_image(self.hass, cover_entity)
                    content = img.content
                    LOGGER.debug("Cover image obtained via image API for %s (%d bytes)", cover_entity, len(content))
                except Exception as img_err:
                    LOGGER.debug("image async_get_image failed for %s: %s, trying HTTP", cover_entity, img_err)
                    content = None

            if not content:
                download_url = image_url
                if cover_entity:
                    state = self.hass.states.get(cover_entity)
                    if state:
                        entity_picture = state.attributes.get("entity_picture", "")
                        if entity_picture:
                            download_url = entity_picture
                content = await self._download_image_via_http(download_url)
                if not content:
                    return None

            if len(content) < IMAGE_MIN_SIZE_BYTES:
                LOGGER.warning("Cover image too small (%d bytes), likely not a valid image", len(content))
                return None

            if self._is_placeholder_image(content):
                LOGGER.warning("Cover image is a known placeholder (%d bytes), skipping", len(content))
                return None

            safe_task_name = SecureFileHandler.sanitize_filename(task_name)
            safe_time = re.sub(r'[^\dT]', '_', (end_time or '')[:19])
            filename = f"{safe_task_name}_{safe_time}.jpg"

            def _ensure_dir():
                os.makedirs(self._images_dir, exist_ok=True)
            await self.hass.async_add_executor_job(_ensure_dir)

            filepath = SecureFileHandler.safe_join(self._images_dir, filename)
            if not filepath:
                LOGGER.error("Invalid file path for cover image (path traversal blocked)")
                return None

            def _write():
                with open(filepath, "wb") as f:
                    f.write(content)
            await self.hass.async_add_executor_job(_write)

            local_path = f"/local/printer_analytics/{filename}"
            LOGGER.info("Cover image saved: %s (%d bytes)", local_path, len(content))
            return local_path
        except Exception as err:
            LOGGER.error("Failed to download cover image: %s | url=%s entity=%s", err, image_url[:50] if image_url else 'None', cover_entity)
            return None

    async def _try_get_cover_from_entity(self, task_name: str, end_time: str) -> str | None:
        """从当前 cover_image 实体直接获取封面（最后手段，仅当打印机正在打印同一任务时有效）"""
        try:
            cover_entity = self._entity_map.get("cover_image")
            if not cover_entity:
                prefix = self.printer_name.lower()
                for eid in self.hass.states.async_entity_ids("image"):
                    if eid.startswith(f"image.{prefix}_") and eid.endswith("_cover_image"):
                        cover_entity = eid
                        break
            if not cover_entity:
                LOGGER.debug("No cover_image entity found for entity fallback")
                return None

            from homeassistant.components.image import async_get_image as async_get_cover_image
            img = await async_get_cover_image(self.hass, cover_entity)
            content = img.content
            if not content or len(content) < IMAGE_MIN_SIZE_BYTES:
                LOGGER.debug("Entity cover too small or empty (%d bytes)", len(content) if content else 0)
                return None
            if self._is_placeholder_image(content):
                LOGGER.debug("Entity cover is a placeholder, skipping")
                return None

            safe_task_name = SecureFileHandler.sanitize_filename(task_name)
            safe_time = re.sub(r'[^\dT]', '_', (end_time or '')[:19])
            filename = f"{safe_task_name}_{safe_time}.jpg"

            def _ensure_dir():
                os.makedirs(self._images_dir, exist_ok=True)
            await self.hass.async_add_executor_job(_ensure_dir)

            filepath = SecureFileHandler.safe_join(self._images_dir, filename)
            if not filepath:
                return None

            def _write():
                with open(filepath, "wb") as f:
                    f.write(content)
            await self.hass.async_add_executor_job(_write)

            local_path = f"/local/printer_analytics/{filename}"
            LOGGER.info("Cover from entity fallback for %s: %s (%d bytes)", (task_name or "unknown")[:30], local_path, len(content))
            return local_path
        except Exception as err:
            LOGGER.debug("Entity cover fallback failed for %s: %s", (task_name or "unknown")[:30], err)
            return None

    async def _download_image_via_http(self, download_url: str) -> bytes | None:
        """通过 HTTP 下载图片（备用方案）"""
        try:
            if not download_url:
                return None
            if download_url.startswith("http://") or download_url.startswith("https://"):
                full_url = download_url
            else:
                base_url = self._get_ha_base_url()
                full_url = f"{base_url}{download_url}"
            from homeassistant.helpers.aiohttp_client import async_get_clientsession
            session = async_get_clientsession(self.hass)
            headers = self._get_auth_headers()
            async with session.get(full_url, headers=headers,
                                   timeout=aiohttp.ClientTimeout(total=HTTP_REQUEST_TIMEOUT_SECS)) as resp:
                if resp.status != 200:
                    LOGGER.warning("HTTP download failed: HTTP %d for %s", resp.status, full_url[:80])
                    return None
                return await resp.read()
        except Exception as err:
            LOGGER.warning("HTTP download error: %s", err)
            return None

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
                LOGGER.error("Invalid file path for print info (path traversal blocked)")
                return None

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
                        full_info["entities"][key] = {"state": state.state, "attributes": state.attributes}
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
        """下载打印快照（摄像头截图）- 直接从 camera 组件获取，无需 HTTP 请求"""
        try:
            camera_entity = self._entity_map.get("camera")
            if not camera_entity:
                prefix = self.printer_name.lower()
                camera_entities = list(self.hass.states.async_entity_ids("camera"))
                for eid in camera_entities:
                    if eid.startswith(f"camera.{prefix}_") and eid.endswith("_camera"):
                        camera_entity = eid
                        break
            if not camera_entity:
                LOGGER.warning("No camera entity found for snapshot of %s", self.printer_name)
                return None

            from homeassistant.components.camera import async_get_image
            try:
                image = await async_get_image(self.hass, camera_entity)
                content = image.content
            except Exception as cam_err:
                LOGGER.warning("Camera async_get_image failed for %s: %s, trying HTTP fallback", camera_entity, cam_err)
                content = await self._snapshot_http_fallback(camera_entity)

            if not content or len(content) < IMAGE_MIN_SIZE_BYTES:
                LOGGER.warning("Snapshot too small or empty (%s bytes) for %s",
                               len(content) if content else 0, camera_entity)
                return None

            safe_task_name = SecureFileHandler.sanitize_filename(task_name or "unknown")
            safe_time = re.sub(r'[^\dT]', '_', (end_time or '')[:19])
            filename = f"{safe_task_name}_{safe_time}_snapshot.jpg"

            def _ensure_dir():
                snapshots_dir = os.path.join(self._images_dir, "snapshots")
                os.makedirs(snapshots_dir, exist_ok=True)
                return snapshots_dir
            snapshots_dir = await self.hass.async_add_executor_job(_ensure_dir)

            filepath = SecureFileHandler.safe_join(snapshots_dir, filename)
            if not filepath:
                LOGGER.error("Invalid file path for snapshot (path traversal blocked)")
                return None

            def _write():
                with open(filepath, "wb") as f:
                    f.write(content)
            await self.hass.async_add_executor_job(_write)

            local_path = f"/local/printer_analytics/snapshots/{filename}"
            LOGGER.info("Print snapshot saved: %s (%d bytes)", local_path, len(content))
            return local_path
        except Exception as err:
            LOGGER.error("Failed to download snapshot: %s", err)
            return None

    async def _snapshot_http_fallback(self, camera_entity: str) -> bytes | None:
        """HTTP 方式获取摄像头快照（备用方案）"""
        try:
            from homeassistant.helpers.aiohttp_client import async_get_clientsession
            session = async_get_clientsession(self.hass)
            base_url = self._get_ha_base_url()
            snapshot_url = f"{base_url}/api/camera_proxy/{camera_entity}"
            headers = self._get_auth_headers()
            async with session.get(snapshot_url, headers=headers,
                                   timeout=aiohttp.ClientTimeout(total=HTTP_REQUEST_TIMEOUT_SECS)) as resp:
                if resp.status != 200:
                    LOGGER.warning("HTTP snapshot fallback failed: HTTP %d", resp.status)
                    return None
                return await resp.read()
        except Exception as err:
            LOGGER.warning("HTTP snapshot fallback error: %s", err)
            return None

    async def _delete_image_file(self, local_path: str) -> None:
        """删除本地图片文件"""
        if not local_path:
            return
        try:
            full_path = os.path.join(self.hass.config.path("www"), local_path.lstrip("/"))
            if os.path.isfile(full_path):
                os.remove(full_path)
        except OSError:
            pass

    def _ensure_timezone(self, dt_str: str) -> str:
        """确保时间字符串带有时区信息，格式与end_time一致
        
        Bambu Lab的start_time实体返回本地时间无时区（如 2026-05-10 20:14:00），
        需要统一转为UTC+00:00格式（如 2026-05-10T12:14:00+00:00）
        """
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
        """将任意格式的时间字符串统一转为 UTC aware datetime
        
        无时区信息的时间字符串视为 HA 本地时区（bambu_lab 返回的 start_time 是本地时间）
        """
        if not dt_str:
            return None
        try:
            dt = datetime.fromisoformat(dt_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
            return dt.astimezone(timezone.utc)
        except Exception as err:
            LOGGER.warning("Failed to normalize time '%s': %s", dt_str[:30], err)
            return None

    def _build_color_data(self, end_status: str, progress: int) -> tuple[list, list, list, list, int, dict | None, list[dict]]:
        """构建多色打印数据，返回 (colors_used, types_used, color_changes, color_usage, total_colors, multi_color_summary, clean_color_usage)"""
        raw_colors_used = self.current_print.get("colors_used", [])
        types_used = self.current_print.get("types_used", [])
        color_changes = self.current_print.get("color_changes", [])
        color_usage = self.current_print.get("color_usage", [])

        # colors_used 去重（同一颜色因多个 tray 或大小写差异导致重复）
        colors_used = list(dict.fromkeys(
            c.lower() if isinstance(c, str) else c for c in raw_colors_used
        )) if raw_colors_used else []

        # 基于 color_usage 校验：只有实际有耗材消耗的颜色才算真正使用
        if color_usage:
            actual_colors = list(dict.fromkeys(
                entry["color"].lower() if isinstance(entry.get("color"), str) else entry.get("color")
                for entry in color_usage
                if entry.get("weight_g", 0) > 0 and entry.get("color")
            ))
            if actual_colors and len(actual_colors) < len(colors_used):
                LOGGER.info(
                    "颜色校验：colors_used=%d → 实际有消耗=%d，以实际消耗为准",
                    len(colors_used), len(actual_colors)
                )
                colors_used = actual_colors

        total_colors = len(colors_used) if colors_used else (1 if self.current_print.get("filament_color") else 0)

        # 构建多色统计摘要
        multi_color_summary = None
        if len(colors_used) > 1:
            status_label = '完成' if end_status == PRINT_STATUS_FINISH else \
                          ('取消' if end_status == PRINT_STATUS_CANCELLED else '失败')

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
                "color_details": [
                    {
                        "color": entry["color"],
                        "type": entry["type"],
                        "weight_g": round(entry.get("weight_g", 0), 2),
                        "length_m": round(entry.get("length_m", 0), 2),
                    }
                    for entry in color_usage
                ] if color_usage else [],
            }

            task_name = self.current_print.get("task_name") or ""
            LOGGER.info(
                "🎨 多色打印%s: %s | 使用%d种颜色(实际用到%d%%) | 切换%d次 | 状态:%s",
                status_label,
                task_name,
                total_colors,
                progress if end_status != PRINT_STATUS_FINISH else 100,
                len(color_changes),
                end_status
            )

        clean_color_usage = [
            {
                "color": entry["color"],
                "type": entry["type"],
                "weight_g": round(entry.get("weight_g", 0), 2),
                "length_m": round(entry.get("length_m", 0), 2),
                "tray": entry.get("tray"),
            }
            for entry in color_usage
        ]

        return colors_used, types_used, color_changes, color_usage, total_colors, multi_color_summary, clean_color_usage

    def _build_chamber_temp_data(self, end_dt: datetime | None) -> tuple[dict | None, float | None]:
        """构建腔体温度数据，返回 (chamber_temp_last5min, chamber_temp_final)"""
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

    async def _on_print_end(self, end_status: str) -> None:
        self._stop_material_cache()
        self._clear_locked_task_name()

        if self.current_print is None:
            LOGGER.warning("Print end detected for %s but no active print record", self.printer_name)
            return
        
        end_time = datetime.now(timezone.utc).isoformat()
        start_dt = self._normalize_to_utc(self.current_print["start_time"])
        end_dt = self._normalize_to_utc(end_time)
        LOGGER.debug("Duration calc: start='%s' => %s, end='%s' => %s", self.current_print["start_time"][:25], start_dt, end_time[:25], end_dt)
        if start_dt and end_dt:
            duration_hours = (end_dt - start_dt).total_seconds() / 3600
        else:
            duration_hours = 0
        
        progress = 100
        if end_status in (PRINT_STATUS_FAIL, PRINT_STATUS_CANCELLED):
            progress = int(self._get_float_state(self._entity_map.get("print_progress", ""), 0))

        total_weight = self.current_print.get("cached_weight") or self._get_float_state(self._entity_map.get("print_weight", ""))
        total_length = self.current_print.get("cached_length") or self._get_float_state(self._entity_map.get("print_length", ""))
        
        energy_kwh = None
        if self.energy_entity and self.current_print.get("energy_valid"):
            end_energy = self._get_float_state(self.energy_entity)
            start_energy = self.current_print.get("start_energy", 0)
            delta = end_energy - start_energy
            if 0 < delta < ENERGY_MAX_DELTA_KWH:
                energy_kwh = round(delta, 4)
            else:
                LOGGER.warning(
                    "Abnormal energy delta %.2f kWh (start=%.2f, end=%.2f) for %s, skipped",
                    delta, start_energy, end_energy, self.printer_name,
                )
        
        task_name = self.current_print.get("task_name") or ""
        cover_image_url = self.current_print.get("cover_image_url") or ""
        cover_image_local = self.current_print.get("cover_image_local")
        start_time = self.current_print.get("start_time") or ""
        if not cover_image_local:
            cover_image_local = await self._download_cover_from_cloud(task_name, end_time, start_time)
        if not cover_image_local:
            cover_image_local = await self._download_cover_image(cover_image_url, task_name, end_time)
        
        colors_used, types_used, color_changes, color_usage, total_colors, multi_color_summary, clean_color_usage = \
            self._build_color_data(end_status, progress)

        chamber_temp_last5min, chamber_temp_final = self._build_chamber_temp_data(end_dt)

        base_record = {
            "id": self.current_print["id"],
            "start_time": self.current_print["start_time"],
            "end_time": end_time,
            "duration_hours": round(duration_hours, 2),
            "status": end_status,
            "progress": progress,
            "total_weight": round(total_weight, 2) if total_weight else None,
            "total_length": round(total_length, 2) if total_length else None,
            "filament_type": types_used[0] if types_used else self.current_print.get("filament_type"),
            "filament_color": colors_used[0] if colors_used else self.current_print.get("filament_color"),
            "colors_used": colors_used,
            "types_used": types_used,
            "total_colors": total_colors,
            "color_changes_count": len(color_changes),
            "multi_color_summary": multi_color_summary,
            "color_usage": clean_color_usage,
            "energy_kwh": round(energy_kwh, 4) if energy_kwh else None,
            "task_name": task_name or None,
            "nozzle_type": self.current_print.get("nozzle_type"),
            "nozzle_size": self.current_print.get("nozzle_size"),
            "print_bed_type": self.current_print.get("print_bed_type"),
            "total_layer_count": self.current_print.get("total_layer_count"),
            "cover_image_url": cover_image_url or None,
            "chamber_temp_final": chamber_temp_final,
            "chamber_temp_last5min": chamber_temp_last5min,
        }

        snapshot_image_local = self.current_print.get("snapshot_image_local")
        if not snapshot_image_local:
            _, snapshot_image_local = await asyncio.gather(
                self._save_full_print_info(base_record, end_time),
                self._download_print_snapshot(end_time, task_name)
            )
        else:
            full_print_info = await self._save_full_print_info(base_record, end_time)

        record = {
            **base_record,
            "cover_image_local": cover_image_local,
            "snapshot_image_local": snapshot_image_local,
            "full_print_info_path": full_print_info,
        }

        self.history.append(record)
        self.current_print = None
        self.hass.async_create_task(self._save_history())
        LOGGER.info("Print ended on %s: status=%s, duration=%.2f hours", self.printer_name, end_status, duration_hours)

    async def backfill_cover_images(self) -> int:
        """为缺少本地封面图的历史记录补充下载，同时清理占位图"""
        import hashlib
        updated = 0
        cleaned = 0
        for record in self.history:
            existing = record.get("cover_image_local")
            if existing:
                local_file = os.path.join(
                    self.hass.config.path("www"),
                    existing.lstrip("/"),
                )
                if os.path.isfile(local_file):
                    # 检查是否为占位图
                    try:
                        with open(local_file, "rb") as f:
                            h = hashlib.md5(f.read()).hexdigest()
                        if h in self._PLACEHOLDER_IMAGE_HASHES:
                            os.remove(local_file)
                            record["cover_image_local"] = None
                            cleaned += 1
                            LOGGER.info("Removed placeholder cover: %s", existing)
                            continue
                    except OSError:
                        pass
                    continue
                record["cover_image_local"] = None
            cover_url = record.get("cover_image_url", "")
            task_name = record.get("task_name", "unknown")
            end_time = record.get("end_time", "")
            start_time = record.get("start_time", "")
            local_path = await self._download_cover_from_cloud(task_name or "unknown", end_time or "", start_time or "")
            if not local_path:
                local_path = await self._download_cover_image(cover_url, task_name or "unknown", end_time or "")
            if not local_path:
                local_path = await self._try_get_cover_from_entity(task_name or "unknown", end_time or "")
            if local_path:
                record["cover_image_local"] = local_path
                updated += 1
                LOGGER.info("Backfilled cover image for %s: %s", (task_name or "unknown")[:30], local_path)
        if updated > 0 or cleaned > 0:
            self.hass.async_create_task(self._save_history())
            LOGGER.info("Backfilled %d, cleaned %d placeholder covers for %s", updated, cleaned, self.printer_name)
        return updated

    async def backfill_snapshots(self) -> int:
        """为缺少快照的历史记录补充下载"""
        updated = 0
        for record in self.history:
            existing = record.get("snapshot_image_local")
            if existing:
                local_file = os.path.join(
                    self.hass.config.path("www"),
                    existing.lstrip("/"),
                )
                if os.path.isfile(local_file):
                    continue
                record["snapshot_image_local"] = None
            task_name = record.get("task_name", "unknown")
            end_time = record.get("end_time", "")
            local_path = await self._download_print_snapshot(end_time or "", task_name or "unknown")
            if local_path:
                record["snapshot_image_local"] = local_path
                updated += 1
                LOGGER.info("Backfilled snapshot for %s: %s", (task_name or "unknown")[:30], local_path)
        if updated > 0:
            self.hass.async_create_task(self._save_history())
            LOGGER.info("Backfilled %d snapshots for %s", updated, self.printer_name)
        return updated

    async def backfill_task_names(self) -> int:
        """从 Bambu Cloud API 获取真实任务名，更新历史记录"""
        cloud = self._get_bambu_cloud_client()
        if not cloud:
            LOGGER.warning("No Bambu Cloud client for task name backfill")
            return 0
        serial = self._get_printer_serial()
        if not serial:
            LOGGER.warning("Cannot determine printer serial for task name backfill")
            return 0
        try:
            def _get_cloud_tasks():
                return cloud.get_tasklist_for_printer(serial)
            tasks = await self.hass.async_add_executor_job(_get_cloud_tasks)
        except Exception as err:
            LOGGER.error("Failed to get cloud tasks for name backfill: %s", err)
            return 0
        if not tasks:
            LOGGER.info("No cloud tasks found for task name backfill")
            return 0
        # 构建云端任务的时间-名称映射
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
            try:
                rec_dt = self._normalize_to_utc(end_time)
                if not rec_dt:
                    continue
            except (ValueError, TypeError):
                continue
            best_match = None
            best_score = 999999
            for ct in cloud_tasks:
                end_diff = abs((ct["end_dt"] - rec_dt).total_seconds())
                if end_diff > 600:
                    continue
                score = end_diff
                if ct.get("start_dt") and start_time:
                    try:
                        rec_start_dt = self._normalize_to_utc(start_time)
                        if rec_start_dt:
                            start_diff = abs((ct["start_dt"] - rec_start_dt).total_seconds())
                            score = end_diff + start_diff
                    except (ValueError, TypeError):
                        pass
                if score < best_score:
                    best_score = score
                    best_match = ct
            if not best_match or not best_match.get("title"):
                continue
            if best_score > 300:
                LOGGER.debug("Skipping task name update for %s: best match score %d too high", (old_name or "")[:30], best_score)
                continue
            new_name = best_match["title"]
            if new_name != old_name:
                    LOGGER.info("Task name updated: '%s' -> '%s'", (old_name or "")[:40], new_name[:40])
                    record["task_name"] = new_name
                    updated += 1
        if updated > 0:
            self.hass.async_create_task(self._save_history())
            LOGGER.info("Backfilled %d task names for %s", updated, self.printer_name)
        return updated

    def _calculate_statistics(self) -> PrinterStats:
        """计算打印统计数据（高性能版本）"""
        stats = PrinterStats()
        now = datetime.now(timezone.utc)

        seven_days_ago = now - timedelta(days=7)
        thirty_days_ago = now - timedelta(days=30)

        precomputed = {
            'total': 0,
            'successful': [],
            'failed': [],
            'cancelled': [],
            'durations': [],
            'total_duration': 0.0,
            'total_weight': 0.0,
            'total_length': 0.0,
            'failed_weight': 0.0,
            'failed_length': 0.0,
            'total_energy': 0.0,
            'lifetime': {'count': 0, 'success': 0, 'failed': 0, 'weight': 0.0, 'length': 0.0, 'energy': 0.0, 'durations': []},
            '7d': {'count': 0, 'success': 0, 'failed': 0, 'weight': 0.0, 'length': 0.0, 'energy': 0.0, 'durations': []},
            '30d': {'count': 0, 'success': 0, 'failed': 0, 'weight': 0.0, 'length': 0.0, 'energy': 0.0, 'durations': []},
            'duration_dist': {label: 0 for label, _, _ in DURATION_BUCKETS},
            'heatmap': {},
            'failure_stages': {label: 0 for label, _, _ in FAILURE_STAGE_BUCKETS},
            'filament_stats': {},
        }

        for record in self.history:
            status = record.get("status")
            duration = record.get("duration_hours") or record.get("duration_minutes") or 0
            weight = record.get("total_weight") or 0
            length = record.get("total_length") or 0
            energy = record.get("energy_kwh") or 0
            progress = record.get("progress") or 0

            if "duration_minutes" in record and "duration_hours" not in record:
                duration = duration / 60

            if energy > 10:
                LOGGER.warning("Abnormal energy value %.2f kWh for %s, filtered out", energy, self.printer_name)
                energy = 0.0

            precomputed['total'] += 1
            if status == PRINT_STATUS_FINISH:
                precomputed['successful'].append(record)
                precomputed['total_weight'] += weight
                precomputed['total_length'] += length
            elif status == PRINT_STATUS_FAIL:
                precomputed['failed'].append(record)
                precomputed['failed_weight'] += weight
                precomputed['failed_length'] += length
            elif status == PRINT_STATUS_CANCELLED:
                precomputed['cancelled'].append(record)

            if duration > 0:
                precomputed['durations'].append(duration)
                precomputed['total_duration'] += duration

            precomputed['total_energy'] += energy

            end_time_str = record.get("end_time", "")
            if end_time_str:
                end_time = self._normalize_to_utc(end_time_str)
                if end_time:
                    period_data = precomputed['lifetime']
                    self._update_period_stats(period_data, status, weight, length, energy, duration, progress)

                    if end_time >= seven_days_ago:
                        period_data = precomputed['7d']
                        self._update_period_stats(period_data, status, weight, length, energy, duration, progress)

                    if end_time >= thirty_days_ago:
                        period_data = precomputed['30d']
                        self._update_period_stats(period_data, status, weight, length, energy, duration, progress)

                    date_key = end_time.strftime("%Y-%m-%d")
                    precomputed['heatmap'][date_key] = precomputed['heatmap'].get(date_key, 0) + 1

            if duration > 0:
                bucket_label = self._get_duration_bucket(duration)
                if bucket_label:
                    precomputed['duration_dist'][bucket_label] += 1

            if status in (PRINT_STATUS_FAIL, PRINT_STATUS_CANCELLED):
                bucket_label = self._get_failure_stage_bucket(progress)
                if bucket_label:
                    precomputed['failure_stages'][bucket_label] += 1

            filament_type = record.get("filament_type")
            if filament_type:
                if filament_type not in precomputed['filament_stats']:
                    precomputed['filament_stats'][filament_type] = {"total": 0, "success": 0, "failed": 0, PRINT_STATUS_CANCELLED: 0, "weight": 0.0}
                fs = precomputed['filament_stats'][filament_type]
                fs["total"] += 1
                fs["weight"] += weight
                if status == PRINT_STATUS_FINISH:
                    fs["success"] += 1
                elif status == PRINT_STATUS_FAIL:
                    fs["failed"] += 1
                elif status == PRINT_STATUS_CANCELLED:
                    fs[PRINT_STATUS_CANCELLED] += 1

        total = precomputed['total']
        successful_count = len(precomputed['successful'])
        stats.total_prints = total
        stats.successful_prints = successful_count
        stats.failed_prints = len(precomputed['failed'])
        stats.cancelled_prints = len(precomputed['cancelled'])
        stats.success_rate = round(successful_count / total * 100, 1) if total > 0 else 0

        durations = precomputed['durations']
        if durations:
            stats.total_duration_hours = round(precomputed['total_duration'], 2)
            stats.average_duration_hours = round(precomputed['total_duration'] / len(durations), 2)

        stats.total_weight_g = round(precomputed['total_weight'] + precomputed['failed_weight'], 2)
        stats.total_length_m = round(precomputed['total_length'] + precomputed['failed_length'], 2)
        stats.total_energy_kwh = round(precomputed['total_energy'], 4)

        stats.stats_lifetime = self._build_period_stats_dict(precomputed['lifetime'])
        stats.stats_7d = self._build_period_stats_dict(precomputed['7d'])
        stats.stats_30d = self._build_period_stats_dict(precomputed['30d'])

        stats.duration_distribution = precomputed['duration_dist']
        stats.activity_heatmap = precomputed['heatmap']
        stats.failure_stage_distribution = precomputed['failure_stages']
        stats.filament_success_stats = self._build_filament_stats(precomputed['filament_stats'])

        stats.history = self.history[-50:]
        stats.current_print = self.current_print
        stats.is_printing = self.current_print is not None
        stats.last_update = now.isoformat()
        stats._entity_map_debug = dict(self._entity_map) if self._entity_map else {"EMPTY": True, "map_id": id(self._entity_map)}
        stats._discover_debug = getattr(self, '_discover_debug', 'not set') + f"\n  _calculate_statistics called, _entity_map has {len(self._entity_map)} items"

        return stats

    @staticmethod
    def _update_period_stats(period_data: dict, status: str | None, weight: float, length: float, energy: float, duration: float, progress: int) -> None:
        """更新单个时间段的统计数据"""
        period_data['count'] += 1
        period_data['energy'] += energy

        if status == PRINT_STATUS_FINISH:
            period_data['success'] += 1
            period_data['weight'] += weight
            period_data['length'] += length
        elif status == PRINT_STATUS_FAIL:
            period_data['failed'] += 1
            period_data['weight'] += weight
            period_data['length'] += length

        if duration > 0:
            period_data['durations'].append(duration)

    @staticmethod
    def _build_period_stats_dict(period_data: dict) -> dict:
        """从预计算的时期数据构建最终的统计字典"""
        count = period_data['count']
        durations = period_data['durations']

        return {
            "total_prints": count,
            "successful": period_data['success'],
            "failed": period_data['failed'],
            "success_rate": round(period_data['success'] / count * 100, 1) if count > 0 else 0,
            "total_weight_g": round(period_data['weight'], 2),
            "total_length_m": round(period_data['length'], 2),
            "total_energy_kwh": round(period_data['energy'], 4),
            "average_duration_hours": round(sum(durations) / len(durations), 2) if durations else 0,
        }

    @staticmethod
    def _get_duration_bucket(duration: float) -> str | None:
        """快速查找时长所属的桶标签"""
        for label, low, high in DURATION_BUCKETS:
            if low <= duration < high:
                return label
        return None

    @staticmethod
    def _get_failure_stage_bucket(progress: int) -> str | None:
        """根据进度百分比判断失败阶段"""
        for label, low, high in FAILURE_STAGE_BUCKETS:
            if low <= progress < high:
                return label
        if progress >= 100:
            return None
        return FAILURE_STAGE_BUCKETS[0][0] if progress < 30 else FAILURE_STAGE_BUCKETS[-1][0]

    @staticmethod
    def _build_filament_stats(raw: dict) -> dict:
        """构建耗材成功率统计，含成功率计算"""
        result = {}
        for ft, data in raw.items():
            total = data["total"]
            result[ft] = {
                "total": total,
                "success": data["success"],
                "failed": data["failed"],
                PRINT_STATUS_CANCELLED: data[PRINT_STATUS_CANCELLED],
                "success_rate": round(data["success"] / total * 100, 1) if total > 0 else 0,
                "weight_g": round(data["weight"], 2),
            }
        return result

    async def _async_update_data(self) -> PrinterStats:
        return self._calculate_statistics()

    async def async_reset_history(self) -> None:
        self.history = []
        self.current_print = None
        await self._save_history()
        self.async_set_updated_data(self._calculate_statistics())
        LOGGER.info("History reset for %s", self.printer_name)

    async def async_delete_history_records(self, record_ids: list[str]) -> int:
        if not record_ids:
            return 0
        ids_set = set(record_ids)
        original_count = len(self.history)
        self.history = [r for r in self.history if r.get("id") not in ids_set]
        deleted_count = original_count - len(self.history)
        if deleted_count > 0:
            await self._save_history()
            self.async_set_updated_data(self._calculate_statistics())
            LOGGER.info("Deleted %d history records for %s", deleted_count, self.printer_name)
        return deleted_count

    def update_options(self, options: dict) -> None:
        self.power_entity = options.get(CONF_POWER_ENTITY, self.power_entity)
        self.energy_entity = options.get(CONF_ENERGY_ENTITY, self.energy_entity)
        self.chamber_temp_entity = options.get(CONF_CHAMBER_TEMP_ENTITY, self.chamber_temp_entity)
        if CONF_PRINTER_NAME in options:
            self.printer_name = options[CONF_PRINTER_NAME]
