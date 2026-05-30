"""历史数据存储管理 - 支持按需读取和增量统计"""
import gzip
import json
import logging
import os
import shutil
from typing import TYPE_CHECKING

from .const import (
    DOMAIN,
    HISTORY_VERSION,
    MAX_FULL_BACKUPS,
    MAX_HISTORY_RECORDS,
    SYNC_ARCHIVE_COUNT,
)
from .utils import match_record_filter

if TYPE_CHECKING:
    from .coordinator import PrinterAnalyticsCoordinator

LOGGER = logging.getLogger(__name__)

# 内部字段集合，查询时自动清理
_INTERNAL_KEYS = frozenset({"_pending_color", "_pending_color_count", "_color_change_cooldown"})


class StorageManager:
    """历史数据存储管理器 - 支持按需读取、增量统计、脏标记只写变化年份

    文件命名规则：{serial}_{year}.json（优先使用序列号，回退到 entry_id）
    这样即使打印机从 HA 删除后重新添加（entry_id 变化但 serial 不变），
    也能自动关联到同一份历史数据。
    """

    def __init__(self, coordinator: "PrinterAnalyticsCoordinator") -> None:
        self.coordinator = coordinator
        self.hass = coordinator.hass
        self.entry = coordinator.entry
        self._history_dir = coordinator._history_dir
        self._archive_dir = coordinator._archive_dir
        self._exports_dir = coordinator._exports_dir
        self._legacy_history_file = coordinator._legacy_history_file
        self._images_dir = coordinator._images_dir
        self._ha_backup_dir = coordinator._ha_backup_dir
        self._dirty_years: set[int] = set()
        self._save_debounce = None

        # 存储键：优先用序列号，回退到 entry_id
        self._storage_key = self._resolve_storage_key()

        # 统计缓存文件路径
        self._stats_file = os.path.join(self._history_dir, f"{self._storage_key}_stats.json")

    def _resolve_storage_key(self) -> str:
        """确定存储键：优先使用序列号，回退到 entry_id

        序列号作为文件前缀，确保同一台打印机即使重新添加到 HA
        （entry_id 变化）也能关联到同一份历史数据。
        """
        serial = self.coordinator.printer_serial
        if serial:
            return serial
        return self.entry.entry_id

    def update_storage_key(self) -> None:
        """序列号更新后重新计算存储键并迁移文件"""
        new_key = self._resolve_storage_key()
        if new_key == self._storage_key:
            return

        old_key = self._storage_key
        LOGGER.info("存储键变更: %s → %s，开始迁移文件...", old_key, new_key)

        # 重命名所有年份文件
        if os.path.isdir(self._history_dir):
            for f in os.listdir(self._history_dir):
                if f.startswith(f"{old_key}_") and f.endswith(".json"):
                    old_path = os.path.join(self._history_dir, f)
                    new_name = f.replace(f"{old_key}_", f"{new_key}_", 1)
                    new_path = os.path.join(self._history_dir, new_name)
                    if not os.path.exists(new_path):
                        os.rename(old_path, new_path)
                        LOGGER.debug("重命名: %s → %s", f, new_name)

        # 重命名统计文件
        old_stats = os.path.join(self._history_dir, f"{old_key}_stats.json")
        new_stats = os.path.join(self._history_dir, f"{new_key}_stats.json")
        if os.path.exists(old_stats) and not os.path.exists(new_stats):
            os.rename(old_stats, new_stats)

        self._storage_key = new_key
        self._stats_file = new_stats

    # ================================================================
    # 脏标记
    # ================================================================

    def mark_dirty(self, year: int | None = None) -> None:
        """标记需要保存的年份"""
        if year is not None:
            self._dirty_years.add(year)
        elif self.coordinator.history:
            last = self.coordinator.history[-1]
            y = self._extract_year_from_end_time(last.get("end_time", ""))
            self._dirty_years.add(y)

    # ================================================================
    # 旧版数据迁移
    # ================================================================

    def migrate_legacy_data(self) -> None:
        """迁移旧版数据到分片存储"""
        if not os.path.exists(self._legacy_history_file):
            return

        try:
            with open(self._legacy_history_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            records = data.get("history", []) if isinstance(data, dict) else data
            if not records:
                return

            LOGGER.info("开始迁移 %d 条历史记录到分片存储...", len(records))

            records_by_year = {}
            for record in records:
                year = self._extract_year_from_end_time(record.get("end_time", ""))
                if year not in records_by_year:
                    records_by_year[year] = []
                records_by_year[year].append(record)

            for year, year_records in records_by_year.items():
                self._save_year_data(year, year_records)

            backup_path = self._legacy_history_file + f".migrated_{len(records)}.bak"
            shutil.move(self._legacy_history_file, backup_path)
            LOGGER.info("迁移完成，旧文件已备份到 %s", backup_path)

        except Exception as err:
            LOGGER.error("迁移旧版数据失败: %s", err)

    def migrate_entry_id_to_serial(self) -> None:
        """将 entry_id 前缀的文件迁移为 serial 前缀

        启动时调用，确保旧版文件名（entry_id_2025.json）自动重命名为
        新版格式（SERIAL_2025.json），支持打印机重新添加后数据自动关联。
        """
        entry_id = self.entry.entry_id
        serial = self.coordinator.printer_serial
        if not serial or serial == entry_id:
            return  # 没有序列号或已经是 serial 格式，无需迁移

        if not os.path.isdir(self._history_dir):
            return

        migrated = 0
        for f in os.listdir(self._history_dir):
            if f.startswith(f"{entry_id}_") and f.endswith(".json"):
                old_path = os.path.join(self._history_dir, f)
                new_name = f.replace(f"{entry_id}_", f"{serial}_", 1)
                new_path = os.path.join(self._history_dir, new_name)
                if not os.path.exists(new_path):
                    os.rename(old_path, new_path)
                    migrated += 1
                    LOGGER.debug("迁移文件: %s → %s", f, new_name)

        # 迁移统计文件
        old_stats = os.path.join(self._history_dir, f"{entry_id}_stats.json")
        new_stats = os.path.join(self._history_dir, f"{serial}_stats.json")
        if os.path.exists(old_stats) and not os.path.exists(new_stats):
            os.rename(old_stats, new_stats)
            migrated += 1

        if migrated > 0:
            LOGGER.info("已迁移 %d 个文件: entry_id=%s → serial=%s", migrated, entry_id, serial)

    @staticmethod
    def scan_all_history_files(history_dir: str) -> list[dict]:
        """全局扫描所有历史文件，返回所有记录（用于全部历史和统计）

        扫描 history_by_year/ 下所有 JSON 文件，包括已删除打印机的记录。
        每条记录会附加 _source_serial 字段标识来源。
        """
        if not os.path.isdir(history_dir):
            return []

        all_records = []
        for f in sorted(os.listdir(history_dir)):
            if not f.endswith(".json") or f.endswith("_stats.json"):
                continue
            file_path = os.path.join(history_dir, f)
            try:
                with open(file_path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                records = data.get("history", []) if isinstance(data, dict) else data
                # 从文件名提取序列号
                serial = f.rsplit("_", 1)[0] if "_" in f else ""
                for r in records:
                    r["_source_serial"] = serial
                all_records.extend(records)
            except Exception as err:
                LOGGER.warning("全局扫描读取文件失败 %s: %s", f, err)

        # 按时间降序排序
        all_records.sort(key=lambda x: x.get("end_time") or x.get("start_time") or "", reverse=True)
        return all_records

    @staticmethod
    def get_all_serials(history_dir: str) -> list[str]:
        """获取历史目录中所有序列号（去重排序）"""
        if not os.path.isdir(history_dir):
            return []
        serials = set()
        for f in os.listdir(history_dir):
            if f.endswith(".json") and not f.endswith("_stats.json") and "_" in f:
                serial = f.rsplit("_", 1)[0]
                serials.add(serial)
        return sorted(serials)

    @staticmethod
    def _extract_year_from_end_time(end_time: str) -> int:
        """从结束时间提取年份（直接切片，避免正则开销）"""
        if not end_time or len(end_time) < 4:
            return 2020
        try:
            return int(end_time[:4])
        except ValueError:
            return 2020

    def _get_year_files(self) -> list[str]:
        """获取当前存储键的所有年份文件名（已排序）"""
        if not os.path.isdir(self._history_dir):
            return []
        return sorted(
            f for f in os.listdir(self._history_dir)
            if f.startswith(f"{self._storage_key}_") and f.endswith(".json")
        )

    def _year_file_path(self, year: int) -> str:
        """获取年份文件路径"""
        return os.path.join(self._history_dir, f"{self._storage_key}_{year}.json")

    # ================================================================
    # 按需查询（核心新增 - 不加载全量到内存）
    # ================================================================

    def query_records(self, filters: dict | None = None,
                      page: int = 1, page_size: int = 20) -> dict:
        """从文件逐条筛选+分页，只把匹配的分页结果加载到内存

        筛选逻辑委托给 utils.match_record_filter 统一实现。
        """
        filters = filters or {}
        status_filter = filters.get("status", "")
        color_filter = filters.get("color", "")
        printer_filter = filters.get("printer", "")
        date_from = filters.get("date_from", "")
        date_to = filters.get("date_to", "")
        search = filters.get("search", "").lower()
        slice_mode_filter = filters.get("slice_mode", "")
        over_500g_filter = filters.get("over_500g", "")

        # 收集所有颜色（筛选项，不受筛选影响）
        all_colors: set[str] = set()
        total_records = 0
        # 筛选后的记录
        filtered_keys: list[tuple[str, str]] = []

        # 按年份文件倒序扫描（最新年份优先）
        year_files = list(reversed(self._get_year_files()))

        for year_file in year_files:
            file_path = os.path.join(self._history_dir, year_file)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                records = data.get("history", []) if isinstance(data, dict) else data
            except Exception as err:
                LOGGER.warning("读取年份文件失败 %s: %s", year_file, err)
                continue

            total_records += len(records)

            for r in records:
                # 收集颜色选项（始终执行，不受筛选影响）
                self._collect_colors(r, all_colors)

                # 使用统一的筛选匹配函数
                if not match_record_filter(r, status_filter, color_filter, printer_filter,
                                           date_from, date_to, search, slice_mode_filter, over_500g_filter):
                    continue

                sort_key = r.get("end_time") or r.get("start_time") or ""
                filtered_keys.append((sort_key, r))

        # 排序（按时间降序）
        filtered_keys.sort(key=lambda x: x[0], reverse=True)

        # 分页
        total = len(filtered_keys)
        total_pages = max(1, (total + page_size - 1) // page_size)
        page = max(1, min(page, total_pages))
        start = (page - 1) * page_size
        page_items = filtered_keys[start:start + page_size]

        # 清理内部字段
        clean_records = []
        for _, r in page_items:
            clean_records.append({k: v for k, v in r.items() if k not in _INTERNAL_KEYS})

        # 基于筛选后全量数据计算统计（供前端摘要展示）
        stats = self._calc_quick_stats(filtered_keys)

        return {
            "records": clean_records,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": total_pages,
            },
            "filter_options": {
                "colors": sorted(all_colors),
                "printer_name": self.coordinator.printer_name,
                "printer_serial": self.coordinator.printer_serial,
                "total_records": total_records,
            },
            "stats": stats,
        }

    @staticmethod
    def _collect_colors(r: dict, colors: set[str]) -> None:
        """从单条记录中收集颜色"""
        for c in (r.get("colors_used") or []):
            if c:
                colors.add(c)
        fc = r.get("filament_color")
        if fc and not (r.get("colors_used") or []):
            if isinstance(fc, str) and fc.startswith("#"):
                colors.add(fc)
        for cu in (r.get("color_usage") or []):
            if cu and cu.get("color") and cu.get("weight_g", 0) > 0:
                colors.add(cu["color"])

    @staticmethod
    def _calc_quick_stats(filtered_keys: list[tuple]) -> dict:
        """基于筛选后的全量记录快速计算统计摘要"""
        from .const import SUCCESS_STATUSES

        total = len(filtered_keys)
        success = 0
        total_weight = 0.0
        total_duration_hours = 0.0

        for _, r in filtered_keys:
            status = r.get("status", "")
            if status in SUCCESS_STATUSES:
                success += 1
            total_weight += float(r.get("total_weight") or 0)

            # 时长计算
            dur = r.get("duration_hours")
            if dur is not None and str(dur).strip() not in ("", "None", "null"):
                try:
                    total_duration_hours += float(dur)
                except (ValueError, TypeError):
                    pass
            else:
                st = r.get("start_time")
                et = r.get("end_time")
                if st and et:
                    try:
                        from datetime import datetime
                        fmt = "%Y-%m-%d %H:%M" if " " in st else "%Y-%m-%dT%H:%M:%S"
                        sd = datetime.strptime(str(st)[:16], "%Y-%m-%d %H:%M")
                        ed = datetime.strptime(str(et)[:16], "%Y-%m-%d %H:%M")
                        delta = (ed - sd).total_seconds() / 3600
                        if delta > 0:
                            total_duration_hours += delta
                    except Exception:
                        pass

        success_rate = round(success / total * 100, 1) if total > 0 else 0

        return {
            "total": total,
            "success": success,
            "success_rate": success_rate,
            "total_weight": round(total_weight, 1),
            "total_duration_hours": round(total_duration_hours, 2),
        }

    # ================================================================
    # 加载历史（启动时只加载最近缓存 + 统计数据）
    # ================================================================

    async def load_history(self) -> list[dict]:
        """加载历史记录（只加载最近N条到内存缓存，其余按需读取）"""
        try:
            def _load():
                os.makedirs(self._history_dir, exist_ok=True)
                os.makedirs(self._archive_dir, exist_ok=True)
                os.makedirs(self._exports_dir, exist_ok=True)

                # 迁移旧版数据
                if os.path.exists(self._legacy_history_file):
                    LOGGER.info("检测到旧版数据文件，开始迁移到分片存储...")
                    self.migrate_legacy_data()

                year_files = self._get_year_files()

                if not year_files:
                    self._restore_from_backup_dir()
                    year_files = self._get_year_files()

                # 统计各年份记录数（不加载内容）
                total_count = 0
                for year_file in year_files:
                    file_path = os.path.join(self._history_dir, year_file)
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        records = data.get("history", []) if isinstance(data, dict) else data
                        count = len(records)
                        total_count += count
                        year = year_file.replace(f"{self._storage_key}_", "").replace(".json", "")
                        self.coordinator._yearly_stats[year] = count
                    except Exception as err:
                        LOGGER.warning("加载年份文件失败 %s: %s", year_file, err)
                        from .utils import BackupManager
                        BackupManager.restore_from_backup(file_path)

                # 只加载最近年份的记录到内存缓存
                recent_records = []
                cache_limit = 50  # 内存中只保留最近50条

                for year_file in reversed(year_files):
                    if len(recent_records) >= cache_limit:
                        break
                    file_path = os.path.join(self._history_dir, year_file)
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        records = data.get("history", []) if isinstance(data, dict) else data
                        remaining = cache_limit - len(recent_records)
                        LOGGER.info("load_history: %s 有 %d 条记录, 取前 %d 条, first_end_time=%s",
                                    year_file, len(records), remaining,
                                    records[0].get("end_time", "?") if records else "empty")
                        recent_records = records[:remaining] + recent_records
                    except Exception as err:
                        LOGGER.warning("加载最近记录失败 %s: %s", year_file, err)

                recent_records.sort(key=lambda x: x.get("end_time", ""))
                LOGGER.info("加载 %d 条最近记录到缓存（总记录数: %d）", len(recent_records), total_count)
                # 在 executor 内部设置 _total_records
                self.coordinator._total_records = total_count
                return recent_records

            history = await self.hass.async_add_executor_job(_load)
            return history

        except Exception as err:
            LOGGER.error("加载历史数据失败: %s", err)
            return []

    # ================================================================
    # 增量统计持久化
    # ================================================================

    def load_stats(self) -> dict | None:
        """从文件加载持久化的统计数据"""
        if not os.path.exists(self._stats_file):
            return None
        try:
            with open(self._stats_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as err:
            LOGGER.warning("加载统计数据失败: %s", err)
            return None

    def save_stats(self, stats_data: dict) -> None:
        """持久化统计数据到文件"""
        try:
            os.makedirs(self._history_dir, exist_ok=True)
            with open(self._stats_file, "w", encoding="utf-8") as f:
                json.dump(stats_data, f, ensure_ascii=False, indent=2)
        except Exception as err:
            LOGGER.warning("保存统计数据失败: %s", err)

    # ================================================================
    # 保存历史（增量写入）
    # ================================================================

    def _save_year_data(self, year: int, records: list[dict]) -> None:
        """保存单年份数据（直接写入，由外层 executor 调度）"""
        os.makedirs(self._history_dir, exist_ok=True)
        year_file = os.path.join(self._history_dir, f"{self._storage_key}_{year}.json")
        data = {"version": HISTORY_VERSION, "year": year, "history": records}
        with open(year_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        LOGGER.debug("已保存 %d 年数据: %d 条记录", year, len(records))

    async def save_history(self) -> None:
        """保存历史记录到分片存储（只写脏年份，减少 I/O）"""
        try:
            dirty = set(self._dirty_years)
            self._dirty_years.clear()

            # 如果没有脏标记，保存所有年份（兼容旧调用方式）
            save_all = len(dirty) == 0

            def _write():
                records_by_year: dict[int, list[dict]] = {}
                for record in self.coordinator.history:
                    year = self._extract_year_from_end_time(record.get("end_time", ""))
                    if year not in records_by_year:
                        records_by_year[year] = []
                    records_by_year[year].append(record)

                years_to_save = records_by_year.keys() if save_all else dirty & records_by_year.keys()

                for year in years_to_save:
                    records = records_by_year.get(year, [])
                    self._save_year_file(year, records)
                    self.coordinator._yearly_stats[str(year)] = len(records)

                # 增量保存时只备份变化的年份
                if save_all:
                    self._cleanup_old_backups()
                    self._create_full_backup()

            await self.hass.async_add_executor_job(_write)
            LOGGER.debug("历史数据已保存（%s）", "全量" if save_all else f"增量: {dirty}")

        except Exception as err:
            LOGGER.error("保存历史数据失败: %s", err)

    def _save_year_file(self, year: int, records: list[dict]) -> None:
        """保存单年份文件（直接写入，外层已在 executor 中）"""
        os.makedirs(self._history_dir, exist_ok=True)
        year_file = os.path.join(self._history_dir, f"{self._storage_key}_{year}.json")
        data = {"version": HISTORY_VERSION, "year": year, "history": records}

        try:
            with open(year_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self._sync_to_ha_backup_dir()
        except Exception as err:
            LOGGER.error("保存年份文件失败 %d: %s", year, err)

    # ================================================================
    # 备份相关
    # ================================================================

    def _create_compressed_backup(self, year_file: str, year: int) -> None:
        """创建压缩备份"""
        year_path = os.path.join(self._history_dir, year_file)
        if not os.path.exists(year_path):
            return

        os.makedirs(self._archive_dir, exist_ok=True)
        archive_file = os.path.join(
            self._archive_dir, f"{self._storage_key}_{year}_archive_{self.coordinator._total_records}.json.gz"
        )

        try:
            with gzip.open(archive_file, "wt", encoding="utf-8") as gz:
                with open(year_path, "r", encoding="utf-8") as f:
                    gz.write(f.read())
            LOGGER.info("已创建压缩备份: %s", os.path.basename(archive_file))
        except Exception as err:
            LOGGER.warning("创建压缩备份失败: %s", err)

    def _create_full_backup(self) -> None:
        """创建完整备份（从文件读取，不依赖内存全量数据）"""
        os.makedirs(self._archive_dir, exist_ok=True)
        timestamp = self.coordinator._total_records
        backup_file = os.path.join(
            self._archive_dir, f"{self._storage_key}_full_backup_{timestamp}.json.gz"
        )

        try:
            # 从年份文件流式读取并写入备份
            with gzip.open(backup_file, "wt", encoding="utf-8") as gz:
                gz.write('{"history": [')
                first = True
                for year_file in self._get_year_files():
                    file_path = os.path.join(self._history_dir, year_file)
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        records = data.get("history", []) if isinstance(data, dict) else data
                        for record in records:
                            if not first:
                                gz.write(", ")
                            first = False
                            gz.write(json.dumps(record, ensure_ascii=False))
                    except Exception:
                        continue
                gz.write(']}')
            LOGGER.info("已创建完整备份: %s", os.path.basename(backup_file))
        except Exception as err:
            LOGGER.warning("创建完整备份失败: %s", err)

    def _cleanup_old_backups(self) -> None:
        """清理旧备份"""
        try:
            archives = sorted(
                [
                    f
                    for f in os.listdir(self._archive_dir)
                    if f.startswith(f"{self._storage_key}_full_backup_")
                ],
                reverse=True,
            )

            for old_backup in archives[MAX_FULL_BACKUPS:]:
                backup_path = os.path.join(self._archive_dir, old_backup)
                try:
                    os.remove(backup_path)
                    LOGGER.debug("已删除旧备份: %s", old_backup)
                except OSError as err:
                    LOGGER.warning("删除旧备份失败 %s: %s", old_backup, err)
        except OSError:
            pass

    def _restore_from_backup_dir(self) -> None:
        """从备份目录恢复数据"""
        try:
            if not os.path.isdir(self._ha_backup_dir):
                return

            backups = [
                f
                for f in os.listdir(self._ha_backup_dir)
                if f.endswith(".json.gz")
                and f.startswith(f"{self._storage_key}_full_backup_")
            ]

            if not backups:
                return

            latest_backup = sorted(backups, reverse=True)[0]
            backup_path = os.path.join(self._ha_backup_dir, latest_backup)

            LOGGER.info("从备份恢复数据: %s", latest_backup)

            try:
                with gzip.open(backup_path, "rt", encoding="utf-8") as gz:
                    data = json.load(gz)
                records = data.get("history", [])
                if records:
                    LOGGER.info("恢复 %d 条历史记录", len(records))
            except Exception as err:
                LOGGER.warning("解压备份失败: %s，尝试直接读取", err)
                with open(backup_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                records = data.get("history", [])

            records_by_year = {}
            for record in records:
                year = self._extract_year_from_end_time(record.get("end_time", ""))
                if year not in records_by_year:
                    records_by_year[year] = []
                records_by_year[year].append(record)

            for year, year_records in records_by_year.items():
                self._save_year_file(year, year_records)

        except Exception as err:
            LOGGER.error("从备份恢复失败: %s", err)

    def _sync_to_ha_backup_dir(self) -> None:
        """同步到HA标准备份目录"""
        try:
            os.makedirs(self._ha_backup_dir, exist_ok=True)

            latest_year = max(
                (
                    int(f.replace(f"{self._storage_key}_", "").replace(".json", ""))
                    for f in os.listdir(self._history_dir)
                    if f.startswith(f"{self._storage_key}_") and f.endswith(".json")
                ),
                default=None,
            )

            if latest_year is None:
                return

            current_file = os.path.join(
                self._history_dir, f"{self._storage_key}_{latest_year}.json"
            )

            sync_file = os.path.join(
                self._ha_backup_dir, f"{self._storage_key}_current.json.gz"
            )

            with gzip.open(sync_file, "wt", encoding="utf-8") as gz:
                with open(current_file, "r", encoding="utf-8") as f:
                    gz.write(f.read())

            archives = [
                f
                for f in os.listdir(self._ha_backup_dir)
                if f.endswith(".json.gz")
                and f.startswith(f"{self._storage_key}_archive_")
            ]
            archives.sort(reverse=True)
            for old in archives[SYNC_ARCHIVE_COUNT:]:
                try:
                    os.remove(os.path.join(self._ha_backup_dir, old))
                except OSError:
                    pass

        except Exception as err:
            LOGGER.debug("同步到HA备份目录失败: %s", err)

    # ================================================================
    # 导出
    # ================================================================

    async def export_history_json(self, filepath: str | None = None) -> str:
        """导出历史数据为JSON文件（从文件流式读取，不依赖内存全量）"""

        def _write():
            if not filepath:
                os.makedirs(self._exports_dir, exist_ok=True)
                filepath = os.path.join(
                    self._exports_dir,
                    f"{self.coordinator.printer_name}_history_{self.coordinator._total_records}.json",
                )

            # 从年份文件流式读取
            all_records = []
            for year_file in self._get_year_files():
                file_path = os.path.join(self._history_dir, year_file)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    records = data.get("history", []) if isinstance(data, dict) else data
                    all_records.extend(records)
                except Exception:
                    continue

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(
                    {"version": HISTORY_VERSION, "history": all_records},
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
            return filepath

        return await self.hass.async_add_executor_job(_write)

    async def get_storage_statistics(self) -> dict:
        """获取存储统计信息"""

        def _calc():
            stats = {
                "total_records": self.coordinator._total_records,
                "yearly_stats": dict(self.coordinator._yearly_stats),
                "storage_dirs": {
                    "history": self._history_dir,
                    "archives": self._archive_dir,
                    "exports": self._exports_dir,
                    "images": self._images_dir,
                    "ha_backup": self._ha_backup_dir,
                },
                "file_counts": {},
                "total_size_bytes": 0,
            }

            for dir_path, key in [
                (self._history_dir, "history"),
                (self._archive_dir, "archives"),
                (self._exports_dir, "exports"),
            ]:
                if os.path.isdir(dir_path):
                    files = os.listdir(dir_path)
                    stats["file_counts"][key] = len(files)
                    total_size = sum(
                        os.path.getsize(os.path.join(dir_path, f)) for f in files
                    )
                    stats["total_size_bytes"] += total_size
                    stats[f"{key}_size_mb"] = round(total_size / 1024 / 1024, 2)

            return stats

        return await self.hass.async_add_executor_job(_calc)
