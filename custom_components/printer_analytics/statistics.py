"""统计计算模块"""
import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from .const import (
    DURATION_BUCKETS,
    FAILURE_STAGE_BUCKETS,
    PRINT_STATUS_CANCELLED,
    PRINT_STATUS_FINISH,
    PRINT_STATUS_FAIL,
    PRINT_STATUS_FAILED,
)
from .data_models import PrinterStats

if TYPE_CHECKING:
    from .coordinator import PrinterAnalyticsCoordinator

LOGGER = logging.getLogger(__name__)


class StatisticsCalculator:
    """统计计算管理器 - 支持增量缓存，无数据变化时直接返回缓存"""

    def __init__(self, coordinator: "PrinterAnalyticsCoordinator") -> None:
        self.coordinator = coordinator
        self._cache: PrinterStats | None = None
        self._cache_history_len: int = -1
        self._cache_last_id: str = ""
        self._cache_current_print_id: str = ""

    def calculate(self) -> PrinterStats:
        """计算打印统计数据（带缓存）"""
        history = self.coordinator.history
        current_print = self.coordinator.current_print

        # 快速路径：历史未变化且无活跃打印变化
        current_len = len(history)
        last_id = history[-1].get("id", "") if history and len(history) > 0 else ""
        current_print_id = current_print.get("id", "") if current_print else ""

        if (self._cache is not None
                and current_len == self._cache_history_len
                and last_id == self._cache_last_id
                and current_print_id == self._cache_current_print_id):
            self._cache.last_update = datetime.now(timezone.utc).isoformat()
            return self._cache

        stats = self._calculate_full(history, current_print)

        self._cache = stats
        self._cache_history_len = current_len
        self._cache_last_id = last_id
        self._cache_current_print_id = current_print_id
        return stats

    def invalidate_cache(self) -> None:
        """主动失效缓存（历史变化时调用）"""
        self._cache = None

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

            if status == PRINT_STATUS_FINISH:
                successful_count += 1
                total_weight += weight
                total_length += length
            elif status in (PRINT_STATUS_FAIL, PRINT_STATUS_FAILED):
                failed_count += 1
                failed_weight += weight
                failed_length += length
            elif status == PRINT_STATUS_CANCELLED:
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

            if status in (PRINT_STATUS_FAIL, PRINT_STATUS_FAILED, PRINT_STATUS_CANCELLED):
                bucket_label = self._get_failure_stage_bucket(progress)
                if bucket_label:
                    failure_stages[bucket_label] += 1

            filament_type = record.get("filament_type")
            if filament_type:
                if filament_type not in filament_stats:
                    filament_stats[filament_type] = {"total": 0, "success": 0, "failed": 0, PRINT_STATUS_CANCELLED: 0, "weight": 0.0}
                fs = filament_stats[filament_type]
                fs["total"] += 1
                fs["weight"] += weight
                if status == PRINT_STATUS_FINISH:
                    fs["success"] += 1
                elif status in (PRINT_STATUS_FAIL, PRINT_STATUS_FAILED):
                    fs["failed"] += 1
                elif status == PRINT_STATUS_CANCELLED:
                    fs[PRINT_STATUS_CANCELLED] += 1

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

        if status == PRINT_STATUS_FINISH:
            period_data['success'] += 1
            period_data['weight'] += weight
            period_data['length'] += length
        elif status in (PRINT_STATUS_FAIL, PRINT_STATUS_FAILED):
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
                PRINT_STATUS_CANCELLED: data[PRINT_STATUS_CANCELLED],
                "success_rate": round(data["success"] / total * 100, 1) if total > 0 else 0,
                "weight_g": round(data["weight"], 2),
            }
        return result
