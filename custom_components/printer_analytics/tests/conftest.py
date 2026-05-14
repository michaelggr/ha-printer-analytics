"""
Printer Analytics 测试套件 - 配置和Fixtures
提供共享的测试数据和mock对象
"""

import pytest
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, AsyncMock, MagicMock
from pathlib import Path


# ====== 测试数据工厂 ======

def create_mock_history_record(
    status: str = "finish",
    duration_minutes: float = 120.5,
    total_weight: float = 50.0,
    total_length: float = 200.0,
    energy_kwh: float = 0.5,
    task_name: str = "Test Print",
    progress: int = 100,
    days_ago: int = 1
) -> dict:
    """
    创建模拟的历史记录条目

    Args:
        status: 打印状态 (finish/fail/cancelled)
        duration_minutes: 打印时长（分钟）
        total_weight: 耗材重量（克）
        total_length: 耗材长度（米）
        energy_kwh: 能耗（千瓦时）
        task_name: 任务名称
        progress: 完成进度 (0-100)
        days_ago: 多少天前的记录

    Returns:
        模拟的历史记录字典
    """
    end_time = datetime.now(timezone.utc) - timedelta(days=days_ago)

    return {
        "id": f"test-{status}-{days_ago}d",
        "start_time": (end_time - timedelta(minutes=duration_minutes)).isoformat(),
        "end_time": end_time.isoformat(),
        "duration_minutes": round(duration_minutes, 1),
        "status": status,
        "progress": progress if status != "finish" else 100,
        "total_weight": total_weight if status == "finish" else None,
        "total_length": total_length if status == "finish" else None,
        "energy_kwh:": energy_kwh,
        "task_name": task_name,
        "filament_type": "PLA",
        "filament_color": "#FF0000",
        "nozzle_type": "Standard",
        "nozzle_size": "0.4mm",
        "print_bed_type": "PEI",
        "total_layer_count": 250,
        "cover_image_url": "/api/image/test",
        "cover_image_local": None,
        "snapshot_image_local": None,
        "full_print_info_path": None,
    }


def create_test_history(count: int = 100) -> list[dict]:
    """
    创建测试用历史数据集

    Args:
        count: 要生成的记录数量

    Returns:
        历史记录列表，包含成功/失败/取消的混合数据
    """
    history = []
    for i in range(count):
        # 80% 成功, 15% 失败, 5% 取消
        rand_val = i % 20
        if rand_val < 16:
            status = "finish"
            duration = 60 + (i % 180)  # 1-4小时
        elif rand_val < 19:
            status = "fail"
            duration = 30 + (i % 120) * (rand_val / 20)  # 按进度比例
        else:
            status = "cancelled"
            duration = 10 + (i % 60) * 0.5

        history.append(create_mock_history_record(
            status=status,
            duration_minutes=duration,
            task_name=f"Test Print {i+1}",
            days_ago=(i % 90),  # 分布在最近90天
            progress=int(50 + (i % 50)) if status != "finish" else 100
        ))

    return history


# ====== pytest Fixtures ======

@pytest.fixture
def temp_dir():
    """创建临时目录用于文件操作测试"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def sample_history():
    """提供标准的100条测试历史数据"""
    return create_test_history(100)


@pytest.fixture
def large_history():
    """提供大规模测试数据（2000条）用于性能测试"""
    return create_test_history(2000)


@pytest.fixture
def mock_hass():
    """创建模拟的Home Assistant实例"""
    hass = Mock()
    hass.states = Mock()
    hass.config.path = Mock(return_value="/tmp/test_config")
    hass.async_add_executor_job = AsyncMock()
    hass.data = {}
    hass.config_entries = Mock()

    # 模拟实体状态
    def mock_get_state(entity_id):
        state_map = {
            "sensor.print_status": Mock(state="idle"),
            "sensor.power": Mock(state="150"),
            "sensor.energy": Mock(state="12.5"),
        }
        return state_map.get(entity_id)

    hass.states.get = mock_get_state

    return hass


@pytest.fixture
def mock_entry():
    """创建模拟的ConfigEntry"""
    entry = Mock()
    entry.entry_id = "test_entry_123"
    entry.data = {
        "printer_name": "Test Printer",
        "print_status_entity": "sensor.print_status",
        "power_entity": "sensor.power",
        "energy_entity": "sensor.energy",
    }
    entry.add_update_listener = Mock(return_value=Mock())
    return entry


# ====== 性能测试工具 ======

class PerformanceTimer:
    """简单的性能计时器"""

    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.elapsed_ms = 0

    def __enter__(self):
        import time
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, *args):
        import time
        self.end_time = time.perf_counter()
        self.elapsed_ms = (self.end_time - self.start_time) * 1000

    def assert_under(self, max_ms: int, msg: str = ""):
        """断言执行时间在阈值内"""
        assert self.elapsed_ms < max_ms, (
            f"Performance regression: {self.elapsed_ms:.2f}ms > {max_ms}ms. {msg}"
        )


# ====== 自定义pytest标记 ======

def pytest_configure(config):
    """注册自定义标记"""
    config.addinivalue_line("markers", "slow: 标记运行较慢的测试")
    config.addinivalue_line("markers", "integration: 集成测试")
    config.addinivalue_line("markers", "performance: 性能基准测试")
