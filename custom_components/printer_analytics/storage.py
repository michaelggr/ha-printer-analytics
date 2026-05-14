"""历史数据存储管理"""
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

if TYPE_CHECKING:
    from .coordinator import PrinterAnalyticsCoordinator

LOGGER = logging.getLogger(__name__)


class StorageManager:
    """历史数据存储管理器 - 支持脏标记只写变化年份"""

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

    def mark_dirty(self, year: int | None = None) -> None:
        """标记需要保存的年份"""
        if year is not None:
            self._dirty_years.add(year)
        elif self.coordinator.history:
            last = self.coordinator.history[-1]
            y = self._extract_year_from_end_time(last.get("end_time", ""))
            self._dirty_years.add(y)

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

    @staticmethod
    def _extract_year_from_end_time(end_time: str) -> int:
        """从结束时间提取年份（直接切片，避免正则开销）"""
        if not end_time or len(end_time) < 4:
            return 2020
        try:
            return int(end_time[:4])
        except ValueError:
            return 2020

    def _save_year_data(self, year: int, records: list[dict]) -> None:
        """保存单年份数据（直接写入，由外层 executor 调度）"""
        os.makedirs(self._history_dir, exist_ok=True)
        year_file = os.path.join(self._history_dir, f"{self.entry.entry_id}_{year}.json")
        data = {"version": HISTORY_VERSION, "year": year, "history": records}
        with open(year_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        LOGGER.debug("已保存 %d 年数据: %d 条记录", year, len(records))

    async def load_history(self) -> list[dict]:
        """加载历史记录（支持100年数据存储）"""
        try:

            def _load():
                os.makedirs(self._history_dir, exist_ok=True)
                os.makedirs(self._archive_dir, exist_ok=True)
                os.makedirs(self._exports_dir, exist_ok=True)

                all_records = []

                if os.path.exists(self._legacy_history_file):
                    LOGGER.info("检测到旧版数据文件，开始迁移到分片存储...")
                    self.migrate_legacy_data()

                year_files = [
                    f
                    for f in os.listdir(self._history_dir)
                    if f.startswith(f"{self.entry.entry_id}_") and f.endswith(".json")
                ]

                if not year_files:
                    self._restore_from_backup_dir()
                    year_files = [
                        f
                        for f in os.listdir(self._history_dir)
                        if f.startswith(f"{self.entry.entry_id}_") and f.endswith(".json")
                    ]

                for year_file in sorted(year_files):
                    file_path = os.path.join(self._history_dir, year_file)
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            if isinstance(data, dict) and "history" in data:
                                records = data["history"]
                                all_records.extend(records)
                                year = (
                                    year_file.replace(f"{self.entry.entry_id}_", "")
                                    .replace(".json", "")
                                )
                                self.coordinator._yearly_stats[year] = len(records)
                                LOGGER.debug("加载 %s 年数据: %d 条记录", year, len(records))
                    except Exception as err:
                        LOGGER.warning("加载年份文件失败 %s: %s", year_file, err)
                        from .utils import BackupManager

                        BackupManager.restore_from_backup(file_path)

                all_records.sort(key=lambda x: x.get("end_time", ""))
                return all_records

            history = await self.hass.async_add_executor_job(_load)
            LOGGER.info(
                "成功加载 %d 条历史记录（%d 个年份）",
                len(history),
                len(self.coordinator._yearly_stats),
            )
            return history

        except Exception as err:
            LOGGER.error("加载历史数据失败: %s", err)
            return []

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

                self._cleanup_old_backups()
                self._create_full_backup()

            await self.hass.async_add_executor_job(_write)
            LOGGER.debug("历史数据已保存（%s）", "全量" if save_all else f"增量: {dirty}")

        except Exception as err:
            LOGGER.error("保存历史数据失败: %s", err)

    def _save_year_file(self, year: int, records: list[dict]) -> None:
        """保存单年份文件（直接写入，外层已在 executor 中）"""
        os.makedirs(self._history_dir, exist_ok=True)
        year_file = os.path.join(self._history_dir, f"{self.entry.entry_id}_{year}.json")
        data = {"version": HISTORY_VERSION, "year": year, "history": records}

        try:
            with open(year_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self._sync_to_ha_backup_dir()
        except Exception as err:
            LOGGER.error("保存年份文件失败 %d: %s", year, err)

    def _create_compressed_backup(self, year_file: str, year: int) -> None:
        """创建压缩备份"""
        year_path = os.path.join(self._history_dir, year_file)
        if not os.path.exists(year_path):
            return

        os.makedirs(self._archive_dir, exist_ok=True)
        archive_file = os.path.join(
            self._archive_dir, f"{self.entry.entry_id}_{year}_archive_{len(self.coordinator.history)}.json.gz"
        )

        try:
            with gzip.open(archive_file, "wt", encoding="utf-8") as gz:
                with open(year_path, "r", encoding="utf-8") as f:
                    gz.write(f.read())
            LOGGER.info("已创建压缩备份: %s", os.path.basename(archive_file))
        except Exception as err:
            LOGGER.warning("创建压缩备份失败: %s", err)

    def _create_full_backup(self) -> None:
        """创建完整备份"""
        os.makedirs(self._archive_dir, exist_ok=True)
        timestamp = len(self.coordinator.history)
        backup_file = os.path.join(
            self._archive_dir, f"{self.entry.entry_id}_full_backup_{timestamp}.json.gz"
        )

        try:
            with gzip.open(backup_file, "wt", encoding="utf-8") as gz:
                json.dump({"history": self.coordinator.history}, gz, ensure_ascii=False)
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
                    if f.startswith(f"{self.entry.entry_id}_full_backup_")
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
                and f.startswith(f"{self.entry.entry_id}_full_backup_")
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
                    int(f.replace(f"{self.entry.entry_id}_", "").replace(".json", ""))
                    for f in os.listdir(self._history_dir)
                    if f.startswith(f"{self.entry.entry_id}_") and f.endswith(".json")
                ),
                default=None,
            )

            if latest_year is None:
                return

            current_file = os.path.join(
                self._history_dir, f"{self.entry.entry_id}_{latest_year}.json"
            )

            sync_file = os.path.join(
                self._ha_backup_dir, f"{self.entry.entry_id}_current.json.gz"
            )

            with gzip.open(sync_file, "wt", encoding="utf-8") as gz:
                with open(current_file, "r", encoding="utf-8") as f:
                    gz.write(f.read())

            archives = [
                f
                for f in os.listdir(self._ha_backup_dir)
                if f.endswith(".json.gz")
                and f.startswith(f"{self.entry.entry_id}_archive_")
            ]
            archives.sort(reverse=True)
            for old in archives[SYNC_ARCHIVE_COUNT:]:
                try:
                    os.remove(os.path.join(self._ha_backup_dir, old))
                except OSError:
                    pass

        except Exception as err:
            LOGGER.debug("同步到HA备份目录失败: %s", err)

    async def export_history_json(self, filepath: str | None = None) -> str:
        """导出历史数据为JSON文件"""

        def _write():
            if not filepath:
                os.makedirs(self._exports_dir, exist_ok=True)
                filepath = os.path.join(
                    self._exports_dir,
                    f"{self.coordinator.printer_name}_history_{len(self.coordinator.history)}.json",
                )

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(
                    {"version": HISTORY_VERSION, "history": self.coordinator.history},
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
                "total_records": len(self.coordinator.history),
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
