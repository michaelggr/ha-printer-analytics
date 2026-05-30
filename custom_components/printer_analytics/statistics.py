"""统计计算模块 - 支持增量缓存和持久化"""
import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from .const import (
    DURATION_BUCKETS,
    FAILURE_STAGE_BUCKETS,
    SUCCESS_STATUSES,
    FAILURE_STATUSES,
    CANCELLED_STATUSES,
)
from .data_models import PrinterStats

if TYPE_CHECKING:
    from .coordinator import PrinterAnalyticsCoordinator

LOGGER = logging.getLogger(__name__)


class StatisticsCalculator:
    """统计计算管理器 - 支持增量缓存、持久化，无数据变化时直接返回缓存"""

    def __init__(self, coordinator: "PrinterAnalyticsCoordinator") -> None:
        self.coordinator = coordinator
        self._cache: PrinterStats | None = None
        self._cache_history_len: int = -1
        self._cache_last_id: str = ""
        self._cache_current_print_id: str = ""

    def calculate(self) -> PrinterStats:
        """计算打印统计数据（带缓存）"""
        # 使用 _total_records 而非 len(history)，因为 history 只是缓存
        history = self.coordinator.history
        current_print = self.coordinator.current_print
        total_records = self.coordinator._total_records

        # 快速路径：历史未变化且无活跃打印变化
        last_id = history[-1].get("id", "") if history else ""
        current_print_id = current_print.get("id", "") if current_print else ""

        if (self._cache is not None
                and total_records == self._cache_history_len
                and last_id == self._cache_last_id
                and current_print_id == self._cache_current_print_id):
            self._cache.last_update = datetime.now(timezone.utc).isoformat()
            return self._cache

        # 缓存未命中：从文件全量计算
        stats = self._calculate_from_files(current_print)

        self._cache = stats
        self._cache_history_len = total_records
        self._cache_last_id = last_id
        self._cache_current_print_id = current_print_id

        # 持久化统计到文件
        self._persist_stats(stats)

        return stats

    def _calculate_from_files(self, current_print: dict | None) -> PrinterStats:
        """从年份文件全量计算统计数据（不依赖内存全量 history）"""
        # 从文件读取全量记录
        all_records = []
        storage = self.coordinator.storage
        if storage:
            import json, os
            for year_file in storage._get_year_files():
                file_path = os.path.join(storage._history_dir, year_file)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    records = data.get("history", []) if isinstance(data, dict) else data
                    all_records.extend(records)
                except Exception:
                    continue

        # 合并内存缓存中尚未保存的记录
        cached_ids = {r.get("id") for r in all_records}
        for r in self.coordinator.history:
            if r.get("id") not in cached_ids:
                all_records.append(r)

        return self._calculate_full(all_records, current_print)

    def invalidate_cache(self) -> None:
        """主动失效缓存（历史变化时调用）"""
        self._cache = None

    def load_from_cache(self, cached_data: dict) -> None:
        """从持久化缓存加载统计数据（避免启动时全量计算）"""
        try:
            stats = PrinterStats()
            stats.total_prints = cached_data.get("total_prints", 0)
            stats.successful_prints = cached_data.get("successful_prints", 0)
            stats.failed_prints = cached_data.get("failed_prints", 0)
            stats.cancelled_prints = cached_data.get("cancelled_prints", 0)
            stats.success_rate = cached_data.get("success_rate", 0)
            stats.average_duration_hours = cached_data.get("average_duration_hours", 0)
            stats.total_duration_hours = cached_data.get("total_duration_hours", 0)
            stats.total_weight_g = cached_data.get("total_weight_g", 0)
            stats.total_length_m = cached_data.get("total_length_m", 0)
            stats.total_energy_kwh = cached_data.get("total_energy_kwh", 0)
            stats.stats_lifetime = cached_data.get("stats_lifetime", {})
            stats.stats_7d = cached_data.get("stats_7d", {})
            stats.stats_30d = cached_data.get("stats_30d", {})
            stats.duration_distribution = cached_data.get("duration_distribution", {})
            stats.activity_heatmap = cached_data.get("activity_heatmap", {})
            stats.failure_stage_distribution = cached_data.get("failure_stage_distribution", {})
            stats.filament_success_stats = cached_data.get("filament_success_stats", {})
            stats.multi_color_ratio = cached_data.get("multi_color_ratio", {})
            stats.prepare_time_by_filament = cached_data.get("prepare_time_by_filament", {})
            stats.slice_mode_distribution = cached_data.get("slice_mode_distribution", {})
            stats.over_500g_ratio = cached_data.get("over_500g_ratio", {})
            stats.nozzle_size_distribution = cached_data.get("nozzle_size_distribution", {})
            stats.failed_chamber_temp_distribution = cached_data.get("failed_chamber_temp_distribution", {})
            stats.history = self.coordinator.history[-50:]
            stats.current_print = self.coordinator.current_print
            stats.is_printing = self.coordinator.current_print is not None
            stats.last_update = datetime.now(timezone.utc).isoformat()

            self._cache = stats
            self._cache_history_len = self.coordinator._total_records
            self._cache_last_id = self.coordinator.history[-1].get("id", "") if self.coordinator.history else ""
            self._cache_current_print_id = (self.coordinator.current_print.get("id", "")
                                            if self.coordinator.current_print else "")
            LOGGER.info("从缓存加载统计数据（total_prints=%d）", stats.total_prints)
        except Exception as err:
            LOGGER.warning("加载统计缓存失败，将全量计算: %s", err)
            self._cache = None

    def _persist_stats(self, stats: PrinterStats) -> None:
        """持久化统计数据到文件"""
        if not self.coordinator.storage:
            return
        try:
            data = {
                "total_prints": stats.total_prints,
                "successful_prints": stats.successful_prints,
                "failed_prints": stats.failed_prints,
                "cancelled_prints": stats.cancelled_prints,
                "success_rate": stats.success_rate,
                "average_duration_hours": stats.average_duration_hours,
                "total_duration_hours": stats.total_duration_hours,
                "total_weight_g": stats.total_weight_g,
                "total_length_m": stats.total_length_m,
                "total_energy_kwh": stats.total_energy_kwh,
                "stats_lifetime": stats.stats_lifetime,
                "stats_7d": stats.stats_7d,
                "stats_30d": stats.stats_30d,
                "duration_distribution": stats.duration_distribution,
                "activity_heatmap": stats.activity_heatmap,
                "failure_stage_distribution": stats.failure_stage_distribution,
                "filament_success_stats": stats.filament_success_stats,
                "multi_color_ratio": stats.multi_color_ratio,
                "prepare_time_by_filament": stats.prepare_time_by_filament,
                "slice_mode_distribution": stats.slice_mode_distribution,
                "over_500g_ratio": stats.over_500g_ratio,
                "nozzle_size_distribution": stats.nozzle_size_distribution,
                "failed_chamber_temp_distribution": stats.failed_chamber_temp_distribution,
            }
            self.coordinator.storage.save_stats(data)
        except Exception as err:
            LOGGER.warning("持久化统计数据失败: %s", err)

    def _calculate_full(self, history: list[dict], current_print: dict | None) -> PrinterStats:
        """全量计算统计数据"""
        stats = PrinterStats()
        now = datetime.now(timezone.utc)

        seven_days_ago = now - timedelta(days=7)
        thirty_days_ago = now - timedelta(days=30)

        # 用计数器代替列表，减少内存分配
        successful_count = 0
        failed_count = 0
        cancelled_count = 0
        total_duration = 0.0
        duration_count = 0
        total_weight = 0.0
        total_length = 0.0
        failed_weight = 0.0
        failed_length = 0.0
        total_energy = 0.0

        lifetime = {'count': 0, 'success': 0, 'failed': 0, 'weight': 0.0, 'length': 0.0, 'energy': 0.0, 'duration_sum': 0.0, 'duration_count': 0}
        stats_7d = {'count': 0, 'success': 0, 'failed': 0, 'weight': 0.0, 'length': 0.0, 'energy': 0.0, 'duration_sum': 0.0, 'duration_count': 0}
        stats_30d = {'count': 0, 'success': 0, 'failed': 0, 'weight': 0.0, 'length': 0.0, 'energy': 0.0, 'duration_sum': 0.0, 'duration_count': 0}
        duration_dist = {label: 0 for label, _, _ in DURATION_BUCKETS}
        heatmap = {}
        failure_stages = {label: 0 for label, _, _ in FAILURE_STAGE_BUCKETS}
        filament_stats = {}
        # 新增统计
        multi_color_count = 0
        single_color_count = 0
        slice_mode_counts = {}  # {cloud: N, local: N, unknown: N}
        over_500g_count = 0
        under_500g_count = 0
        nozzle_size_counts = {}  # {0.4: N, ...}
        prepare_time_by_filament = {}  # {PLA: [time1, time2, ...], ...}
        failed_chamber_temps = []  # 失败记录的仓温列表

        for record in history:
            status = record.get("status")
            duration = record.get("duration_hours") or record.get("duration_minutes") or 0
            weight = record.get("total_weight") or 0
            length = record.get("total_length") or 0
            energy = record.get("energy_kwh") or 0
            progress = record.get("progress") or 0

            if "duration_minutes" in record and "duration_hours" not in record:
                duration = duration / 60

            if energy > 10:
                LOGGER.warning("Abnormal energy value %.2f kWh, filtered out", energy)
                energy = 0.0

            if status in SUCCESS_STATUSES:
                successful_count += 1
                total_weight += weight
                total_length += length
            elif status in FAILURE_STATUSES:
                failed_count += 1
                failed_weight += weight
                failed_length += length
            elif status in CANCELLED_STATUSES:
                cancelled_count += 1

            if duration > 0:
                total_duration += duration
                duration_count += 1

            total_energy += energy

            end_time_str = record.get("end_time", "")
            if end_time_str:
                end_time = self.coordinator._normalize_to_utc(end_time_str)
                if end_time:
                    self._update_period_stats(lifetime, status, weight, length, energy, duration)

                    if end_time >= seven_days_ago:
                        self._update_period_stats(stats_7d, status, weight, length, energy, duration)

                    if end_time >= thirty_days_ago:
                        self._update_period_stats(stats_30d, status, weight, length, energy, duration)

                    date_key = end_time.strftime("%Y-%m-%d")
                    heatmap[date_key] = heatmap.get(date_key, 0) + 1

            if duration > 0:
                bucket_label = self._get_duration_bucket(duration)
                if bucket_label:
                    duration_dist[bucket_label] += 1

            if status in FAILURE_STATUSES or status in CANCELLED_STATUSES:
                bucket_label = self._get_failure_stage_bucket(progress)
                if bucket_label:
                    failure_stages[bucket_label] += 1

            filament_type = record.get("filament_type")
            if filament_type:
                if filament_type not in filament_stats:
                    filament_stats[filament_type] = {"total": 0, "success": 0, "failed": 0, "cancelled": 0, "weight": 0.0}
                fs = filament_stats[filament_type]
                fs["total"] += 1
                fs["weight"] += weight
                if status in SUCCESS_STATUSES:
                    fs["success"] += 1
                elif status in FAILURE_STATUSES:
                    fs["failed"] += 1
                elif status in CANCELLED_STATUSES:
                    fs["cancelled"] += 1

            # 多色/单色统计
            if record.get("multi_color"):
                multi_color_count += 1
            else:
                single_color_count += 1

            # 切片模式统计
            sm = record.get("slice_mode") or "unknown"
            slice_mode_counts[sm] = slice_mode_counts.get(sm, 0) + 1

            # 超500g统计
            if record.get("over_500g"):
                over_500g_count += 1
            else:
                under_500g_count += 1

            # 喷嘴尺寸统计
            ns = record.get("nozzle_size")
            if ns:
                nozzle_size_counts[ns] = nozzle_size_counts.get(ns, 0) + 1

            # 准备时间按材料分类
            pt = record.get("prepare_time_minutes")
            ft = record.get("filament_type") or "unknown"
            if pt and pt > 0:
                if ft not in prepare_time_by_filament:
                    prepare_time_by_filament[ft] = []
                prepare_time_by_filament[ft].append(pt)

            # 失败记录的仓温
            if status in FAILURE_STATUSES or status in CANCELLED_STATUSES:
                ct = record.get("chamber_temp_final")
                if ct and ct > 0:
                    failed_chamber_temps.append(ct)

        total = len(history)
        stats.total_prints = total
        stats.successful_prints = successful_count
        stats.failed_prints = failed_count
        stats.cancelled_prints = cancelled_count
        stats.success_rate = round(successful_count / total * 100, 1) if total > 0 else 0

        if duration_count > 0:
            stats.total_duration_hours = round(total_duration, 2)
            stats.average_duration_hours = round(total_duration / duration_count, 2)

        stats.total_weight_g = round(total_weight + failed_weight, 2)
        stats.total_length_m = round(total_length + failed_length, 2)
        stats.total_energy_kwh = round(total_energy, 4)

        stats.stats_lifetime = self._build_period_stats_dict(lifetime)
        stats.stats_7d = self._build_period_stats_dict(stats_7d)
        stats.stats_30d = self._build_period_stats_dict(stats_30d)

        stats.duration_distribution = duration_dist
        stats.activity_heatmap = heatmap
        stats.failure_stage_distribution = failure_stages
        stats.filament_success_stats = self._build_filament_stats(filament_stats)

        # 新增统计图表
        stats.multi_color_ratio = {"multi": multi_color_count, "single": single_color_count}
        stats.slice_mode_distribution = slice_mode_counts
        stats.over_500g_ratio = {"over": over_500g_count, "under": under_500g_count}
        stats.nozzle_size_distribution = nozzle_size_counts

        # 准备时间：按材料类型计算平均值（排除异常值，使用 IQR 方法）
        prepare_time_result = {}
        for ft, times in prepare_time_by_filament.items():
            if not times:
                continue
            sorted_times = sorted(times)
            n = len(sorted_times)
            if n >= 4:
                q1 = sorted_times[n // 4]
                q3 = sorted_times[3 * n // 4]
                iqr = q3 - q1
                lower = q1 - 1.5 * iqr
                upper = q3 + 1.5 * iqr
                filtered = [t for t in sorted_times if lower <= t <= upper]
            else:
                filtered = sorted_times
            if filtered:
                prepare_time_result[ft] = {
                    "avg": round(sum(filtered) / len(filtered), 1),
                    "count": len(filtered),
                    "min": round(min(filtered), 1),
                    "max": round(max(filtered), 1),
                }
        stats.prepare_time_by_filament = prepare_time_result

        # 失败仓温分布：按温度区间分组
        if failed_chamber_temps:
            temp_buckets = {"<40°C": 0, "40-50°C": 0, "50-60°C": 0, "60-70°C": 0, ">70°C": 0}
            for t in failed_chamber_temps:
                if t < 40:
                    temp_buckets["<40°C"] += 1
                elif t < 50:
                    temp_buckets["40-50°C"] += 1
                elif t < 60:
                    temp_buckets["50-60°C"] += 1
                elif t < 70:
                    temp_buckets["60-70°C"] += 1
                else:
                    temp_buckets[">70°C"] += 1
            stats.failed_chamber_temp_distribution = temp_buckets

        stats.history = history[-50:]
        stats.current_print = current_print
        stats.is_printing = current_print is not None
        stats.last_update = now.isoformat()
        stats._entity_map_debug = dict(self.coordinator._entity_map) if self.coordinator._entity_map else {"EMPTY": True}

        return stats

    @staticmethod
    def _update_period_stats(period_data: dict, status: str | None, weight: float, length: float, energy: float, duration: float) -> None:
        """更新单个时间段的统计数据（用求和代替列表）"""
        period_data['count'] += 1
        period_data['energy'] += energy

        if status in SUCCESS_STATUSES:
            period_data['success'] += 1
            period_data['weight'] += weight
            period_data['length'] += length
        elif status in FAILURE_STATUSES:
            period_data['failed'] += 1
            period_data['weight'] += weight
            period_data['length'] += length

        if duration > 0:
            period_data['duration_sum'] += duration
            period_data['duration_count'] += 1

    @staticmethod
    def _build_period_stats_dict(period_data: dict) -> dict:
        """构建时期统计字典"""
        count = period_data['count']

        return {
            "total_prints": count,
            "successful": period_data['success'],
            "failed": period_data['failed'],
            "success_rate": round(period_data['success'] / count * 100, 1) if count > 0 else 0,
            "total_weight_g": round(period_data['weight'], 2),
            "total_length_m": round(period_data['length'], 2),
            "total_energy_kwh": round(period_data['energy'], 4),
            "average_duration_hours": round(period_data['duration_sum'] / period_data['duration_count'], 2) if period_data['duration_count'] > 0 else 0,
        }

    @staticmethod
    def _get_duration_bucket(duration: float) -> str | None:
        """获取时长桶标签"""
        for label, low, high in DURATION_BUCKETS:
            if low <= duration < high:
                return label
        return None

    @staticmethod
    def _get_failure_stage_bucket(progress: int) -> str | None:
        """获取失败阶段桶标签"""
        for label, low, high in FAILURE_STAGE_BUCKETS:
            if low <= progress < high:
                return label
        if progress >= 100:
            return None
        return FAILURE_STAGE_BUCKETS[0][0] if progress < 30 else FAILURE_STAGE_BUCKETS[-1][0]

    @staticmethod
    def _build_filament_stats(raw: dict) -> dict:
        """构建耗材统计"""
        result = {}
        for ft, data in raw.items():
            total = data["total"]
            result[ft] = {
                "total": total,
                "success": data["success"],
                "failed": data["failed"],
                "cancelled": data["cancelled"],
                "success_rate": round(data["success"] / total * 100, 1) if total > 0 else 0,
                "weight_g": round(data["weight"], 2),
            }
        return result
