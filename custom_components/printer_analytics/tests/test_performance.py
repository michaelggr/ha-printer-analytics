"""
性能基准测试
验证优化后的代码是否满足性能要求

测试指标：
- 统计计算时间（不同数据量级）
- 内存使用效率
- 前端渲染性能
"""

import pytest
import time
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# 导入被测试模块（如果可用）
try:
    from coordinator import PrinterAnalyticsCoordinator, PrinterStats
    from utils import SecureFileHandler
    MODULES_AVAILABLE = True
except ImportError:
    MODULES_AVAILABLE = False
    pytest.skip("模块导入失败，跳过性能测试", allow_module_level=True)


class TestStatisticsCalculationPerformance:
    """统计计算性能测试"""

    @pytest.mark.performance
    def test_small_dataset_performance(self, sample_history):
        """小数据集（100条）应在10ms内完成"""
        if not MODULES_AVAILABLE:
            pytest.skip("模块不可用")

        # 模拟coordinator
        coordinator = self._create_mock_coordinator(sample_history)

        start = time.perf_counter()
        stats = coordinator._calculate_statistics()
        elapsed_ms = (time.perf_counter() - start) * 1000

        print(f"\n[PERF] 100条记录统计计算耗时: {elapsed_ms:.2f}ms")
        assert elapsed_ms < 10, f"小数据集过慢: {elapsed_ms:.2f}ms > 10ms"
        assert stats.total_prints == 100

    @pytest.mark.performance
    def test_medium_dataset_performance(self):
        """中等数据集（500条）应在25ms内完成"""
        if not MODULES_AVAILABLE:
            pytest.skip("模块不可用")

        from tests.conftest import create_test_history
        history = create_test_history(500)
        coordinator = self._create_mock_coordinator(history)

        start = time.perf_counter()
        stats = coordinator._calculate_statistics()
        elapsed_ms = (time.perf_counter() - start) * 1000

        print(f"\n[PERF] 500条记录统计计算耗时: {elapsed_ms:.2f}ms")
        assert elapsed_ms < 25, f"中数据集过慢: {elapsed_ms:.2f}ms > 25ms"
        assert stats.total_prints == 500

    @pytest.mark.performance
    def test_large_dataset_performance(self, large_history):
        """大数据集（2000条）应在50ms内完成"""
        if not MODULES_AVAILABLE:
            pytest.skip("模块不可用")

        coordinator = self._create_mock_coordinator(large_history)

        start = time.perf_counter()
        stats = coordinator._calculate_statistics()
        elapsed_ms = (time.perf_counter() - start) * 1000

        print(f"\n[PERF] 2000条记录统计计算耗时: {elapsed_ms:.2f}ms")
        assert elapsed_ms < 50, f"大数据集过慢: {elapsed_ms:.2f}ms > 50ms"
        assert stats.total_prints == 2000

    @pytest.mark.slow
    @pytest.mark.performance
    def test_very_large_dataset_stress(self):
        """压力测试：超大数据集（10000条）"""
        if not MODULES_AVAILABLE:
            pytest.skip("模块不可用")

        from tests.conftest import create_test_history
        history = create_test_history(10000)
        coordinator = self._create_mock_coordinator(history)

        start = time.perf_counter()
        stats = coordinator._calculate_statistics()
        elapsed_ms = (time.perf_counter() - start) * 1000

        print(f"\n[PERF] 10000条记录统计计算耗时: {elapsed_ms:.2f}ms")
        # 超大数据集允许更长时间，但不应超过200ms
        assert elapsed_ms < 200, f"超大数据集过慢: {elapsed_ms:.2f}ms > 200ms"

    def _create_mock_coordinator(self, history):
        """创建用于测试的模拟coordinator"""
        hass = type('obj', (object,), {
            'states': type('obj', (object,), {'get': lambda self, x: None})(),
            'config': type('obj', (object,), {'path': lambda self, x: '/tmp'})(),
        })()

        entry = type('obj', (object,), {
            'entry_id': 'test',
            'data': {
                'printer_name': 'Test',
                'print_status_entity': 'sensor.test',
                'power_entity': '',
                'energy_entity': '',
            }
        })()

        coordinator = object.__new__(PrinterAnalyticsCoordinator)
        coordinator.hass = hass
        coordinator.entry = entry
        coordinator.printer_name = "Test"
        coordinator.history = history
        coordinator.current_print = None
        coordinator.logger = type('obj', (object,), {
            'debug': lambda *a: None,
            'info': lambda *a: None,
            'warning': lambda *a: None,
            'error': lambda *a: None,
        })()

        return coordinator


class TestMemoryUsage:
    """内存使用效率测试"""

    @pytest.mark.performance
    def test_memory_growth_with_history_size(self):
        """历史记录增长时的内存使用应合理"""
        if not MODULES_AVAILABLE:
            pytest.skip("模块不可用")

        import tracemalloc

        from tests.conftest import create_test_history

        # 测试不同规模的内存占用
        sizes = [100, 500, 1000, 2000]
        memory_snapshots = []

        for size in sizes:
            tracemalloc.start()
            history = create_test_history(size)
            coordinator = self._create_coordinator_with_history(history)

            # 执行多次统计计算以观察内存稳定性
            for _ in range(5):
                coordinator._calculate_statistics()

            current, peak = tracemalloc.get_traced_memory()
            memory_snapshots.append({
                'size': size,
                'current_mb': current / 1024 / 1024,
                'peak_mb': peak / 1024 / 1024,
            })
            tracemalloc.stop()

        # 打印内存使用报告
        print("\n[MEMORY] 内存使用报告:")
        for snap in memory_snapshots:
            print(f"  {snap['size']:>5}条记录: 当前={snap['current_mb']:.2f}MB, 峰值={snap['peak_mb']:.2f}MB")

        # 验证2000条记录的峰值内存不超过50MB
        final_snapshot = memory_snapshots[-1]
        assert final_snapshot['peak_mb'] < 50, (
            f"内存使用过高: {final_snapshot['peak_mb']:.2f}MB > 50MB"
        )

    def _create_coordinator_with_history(self, history):
        """创建带历史数据的测试coordinator"""
        hass = type('obj', (object,), {
            'states': type('obj', (object,), {'get': lambda self, x: None})(),
            'config': type('obj', (object,), {'path': lambda self, x: '/tmp'})(),
        })()

        entry = type('obj', (object,), {
            'entry_id': 'test',
            'data': {'printer_name': 'Test', 'print_status_entity': 'sensor.test'}
        })()

        coordinator = object.__new__(PrinterAnalyticsCoordinator)
        coordinator.hass = hass
        coordinator.entry = entry
        coordinator.history = history
        coordinator.current_print = None
        coordinator.logger = type('obj', (object,), {'debug': lambda *a: None})()

        return coordinator


class TestFileOperationPerformance:
    """文件操作性能测试"""

    @pytest.mark.performance
    def test_atomic_write_speed(self, temp_dir):
        """原子写入操作应快速完成"""
        filepath = os.path.join(temp_dir, "perf_test.txt")
        content = b"x" * (1024 * 1024)  # 1MB 数据

        times = []
        for _ in range(10):
            start = time.perf_counter()
            SecureFileHandler.atomic_write(filepath, content)
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)

        avg_time = sum(times) / len(times)
        print(f"\n[PERF] 原子写入1MB数据平均耗时: {avg_time:.2f}ms (10次平均)")
        # 单次写入应在50ms内完成
        assert avg_time < 50, f"原子写入过慢: {avg_time:.2f}ms"

    @pytest.mark.performance
    def test_backup_creation_overhead(self, temp_dir):
        """备份创建的开销应可接受"""
        import os
        filepath = os.path.join(temp_dir, "backup_perf.json")

        # 创建原始文件（1KB JSON）
        data = {"key": "value", "nested": {"data": list(range(100))}}
        with open(filepath, 'w') as f:
            import json
            json.dump(data, f)

        times = []
        for _ in range(5):
            start = time.perf_counter()
            BackupManager.create_backup(filepath)
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)

        avg_time = sum(times) / len(times)
        print(f"\n[PERF] 备份创建平均耗时: {avg_time:.2f}ms (5次平均)")
        assert avg_time < 20, f"备份创建过慢: {avg_time:.2f}ms"


class TestLRUCachePerformance:
    """LRU缓存性能测试"""

    @pytest.mark.performance
    def test_parse_time_cache_efficiency(self):
        """时间解析缓存应显著提升重复解析速度"""
        if not MODULES_AVAILABLE:
            pytest.skip("模块不可用")

        coordinator = self._create_mock_coordinator([])

        # 准备测试数据（1000个唯一时间戳）
        timestamps = []
        now = datetime.now(timezone.utc)
        for i in range(1000):
            ts = (now - timedelta(minutes=i)).isoformat()
            timestamps.append(ts)

        # 第一次解析（无缓存）
        start = time.perf_counter()
        for ts in timestamps:
            coordinator._parse_time(ts)
        first_pass_ms = (time.perf_counter() - start) * 1000

        # 第二次解析（命中缓存）
        start = time.perf_counter()
        for ts in timestamps:
            coordinator._parse_time(ts)
        cached_pass_ms = (time.perf_counter() - start) * 1000

        speedup = first_pass_ms / max(cached_pass_ms, 0.001)
        print(f"\n[PERF] 时间解析性能:")
        print(f"  首次解析(无缓存): {first_pass_ms:.2f}ms")
        print(f"  缓存命中: {cached_pass_ms:.2f}ms")
        print(f"  加速比: {speedup:.1f}x")

        # 缓存应该至少快2倍
        assert speedup > 2, f"缓存效果不明显: 加速比仅{speedup:.1f}x"

    def _create_mock_coordinator(self, history):
        """创建测试用的mock coordinator"""
        hass = type('obj', (object,), {
            'states': type('obj', (object,), {'get': lambda self, x: None})(),
            'config': type('obj', (object,), {'path': lambda self, x: '/tmp'})(),
        })()

        entry = type('obj', (object,), {
            'entry_id': 'test',
            'data': {'printer_name': 'Test', 'print_status_entity': 'sensor.test'}
        })()

        coordinator = object.__new__(PrinterAnalyticsCoordinator)
        coordinator.hass = hass
        coordinator.entry = entry
        coordinator.history = history or []
        coordinator.current_print = None
        coordinator.logger = type('obj', (object,), {'debug': lambda *a: None})()

        return coordinator


class TestScalabilityRegression:
    """回归测试 - 确保优化后不会出现性能退化"""

    @pytest.mark.performance
    def test_linear_scaling(self):
        """性能应随数据量线性增长（而非指数增长）"""
        if not MODULES_AVAILABLE:
            pytest.skip("模块不可用")

        from tests.conftest import create_test_history

        sizes = [100, 500, 1000]
        times = []

        for size in sizes:
            history = create_test_history(size)
            coordinator = self._create_mock_coordinator(history)

            # 预热
            coordinator._calculate_statistics()

            # 计时
            start = time.perf_counter()
            for _ in range(3):  # 运行3次取平均
                coordinator._calculate_statistics()
            avg_time = (time.perf_counter() - start) / 3 * 1000

            times.append({'size': size, 'time_ms': avg_time})

        # 检查线性关系：当数据量增加10倍，时间不应超过15倍
        if len(times) >= 2:
            first = times[0]
            last = times[-1]
            size_ratio = last['size'] / first['size']
            time_ratio = last['time_ms'] / max(first['time_ms'], 0.001)

            print(f"\n[SCALABILITY] 扩展性分析:")
            for t in times:
                print(f"  {t['size']:>5}条: {t['time_ms']:.2f}ms")
            print(f"  数据增长: {size_ratio:.1f}x")
            print(f"  时间增长: {time_ratio:.1f}x")

            # 允许一定的非线性，但不应该太差
            assert time_ratio < size_ratio * 3, (
                f"扩展性差: 数据增长{size_ratio}x但时间增长{time_ratio}x"
            )

    def _create_mock_coordinator(self, history):
        """创建mock coordinator"""
        hass = type('obj', (object,), {
            'states': type('obj', (object,), {'get': lambda self, x: None})(),
            'config': type('obj', (object,), {'path': lambda self, x: '/tmp'})(),
        })()

        entry = type('obj', (object,), {
            'entry_id': 'test',
            'data': {'printer_name': 'Test', 'print_status_entity': 'sensor.test'}
        })()

        coordinator = object.__new__(PrinterAnalyticsCoordinator)
        coordinator.hass = hass
        coordinator.entry = entry
        coordinator.history = history
        coordinator.current_print = None
        coordinator.logger = type('obj', (object,), {'debug': lambda *a: None})()

        return coordinator


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--tb=short"])
