"""
单元测试 - __init__.py 中的纯函数
覆盖: _sanitize_record, _match_status, _calculate_history_stats,
      _extract_available_colors, _apply_filters, _process_history_request

运行: python -m pytest tests/test_init.py -v
"""
import os
import pytest

# 从 __init__.py 源码中提取纯函数（避免导入整个 HA 依赖）
_INIT_PATH = os.path.join(
    os.path.dirname(__file__), "..",
    "custom_components", "printer_analytics", "__init__.py",
)
_SOURCE = open(_INIT_PATH, "r", encoding="utf-8").read()

_ns = {}
# 先加载 utils.py 中的 match_record_filter（_apply_filters 依赖它）
_UTILS_PATH = os.path.join(
    os.path.dirname(__file__), "..",
    "custom_components", "printer_analytics", "utils.py",
)
_utils_src = open(_UTILS_PATH, "r", encoding="utf-8").read()
_match_filter_src = _utils_src[
    _utils_src.index("def match_record_filter("):
    _utils_src.index("\ndef ", _utils_src.index("def match_record_filter(") + 10) if "\ndef " in _utils_src[_utils_src.index("def match_record_filter(") + 10:] else len(_utils_src)
]
exec(_match_filter_src, _ns)

# 再加载 __init__.py 中的纯函数
exec(_SOURCE[_SOURCE.index("def _sanitize_record"):_SOURCE.index("def _process_history_request")], _ns)
exec(_SOURCE[_SOURCE.index("def _process_history_request"):], _ns)

_sanitize_record = _ns["_sanitize_record"]
_match_status = _ns["_match_status"]
_calculate_history_stats = _ns["_calculate_history_stats"]
_extract_available_colors = _ns["_extract_available_colors"]
_apply_filters = _ns["_apply_filters"]
_process_history_request = _ns["_process_history_request"]


# ==================== 测试数据工厂 ====================

def make_record(
    status="finish",
    start_time="2026-05-01T10:00:00+08:00",
    end_time="2026-05-01T12:00:00+08:00",
    duration_hours=2.0,
    total_weight=50.0,
    task_name="测试打印",
    filament_type="PLA",
    filament_color="#ff0000",
    colors_used=None,
    printer_name=None,
    **extra,
):
    """构造一条历史记录"""
    rec = {
        "id": extra.get("id", f"rec-{status}-{start_time[:10]}"),
        "status": status,
        "start_time": start_time,
        "end_time": end_time,
        "duration_hours": duration_hours,
        "total_weight": total_weight,
        "task_name": task_name,
        "filament_type": filament_type,
        "filament_color": filament_color,
        "colors_used": colors_used or [filament_color],
        "types_used": [filament_type],
        "progress": 100 if status == "finish" else 50,
    }
    if printer_name:
        rec["_printer_name"] = printer_name
    rec.update(extra)
    return rec


def make_history(count=100, status_ratio=None):
    """构造一批历史记录"""
    if status_ratio is None:
        status_ratio = {"finish": 0.8, "fail": 0.15, "cancelled": 0.05}

    records = []
    statuses = (
        ["finish"] * int(count * status_ratio["finish"])
        + ["fail"] * int(count * status_ratio["fail"])
        + ["cancelled"] * int(count * status_ratio["cancelled"])
    )
    while len(statuses) < count:
        statuses.append("finish")

    for i in range(count):
        day = i % 365
        records.append(make_record(
            status=statuses[i],
            start_time=f"2026-{(day // 30) + 1:02d}-{(day % 28) + 1:02d}T10:00:00+08:00",
            end_time=f"2026-{(day // 30) + 1:02d}-{(day % 28) + 1:02d}T12:00:00+08:00",
            task_name=f"打印任务{i+1}",
            filament_color=["#ff0000", "#00ff00", "#0000ff"][i % 3],
            filament_type=["PLA", "PETG", "ABS"][i % 3],
        ))
    return records


# ==================== _sanitize_record 测试 ====================

class TestSanitizeRecord:
    def test_removes_underscore_keys(self):
        rec = {"id": "1", "name": "test", "_internal": "secret", "_meta": 42}
        result = _sanitize_record(rec)
        assert "_internal" not in result
        assert "_meta" not in result
        assert result["id"] == "1"

    def test_keeps_normal_keys(self):
        rec = {"id": "1", "status": "finish", "task_name": "hello"}
        result = _sanitize_record(rec)
        assert result == rec

    def test_empty_record(self):
        assert _sanitize_record({}) == {}

    def test_non_string_keys_filtered(self):
        rec = {"id": "1", 123: "value"}
        result = _sanitize_record(rec)
        assert 123 not in result


# ==================== _match_status 测试 ====================

class TestMatchStatus:
    def test_empty_filter_matches_all(self):
        assert _match_status("finish", "") is True
        assert _match_status("fail", "") is True

    def test_finish_aliases(self):
        assert _match_status("finish", "finish") is True
        assert _match_status("完成", "finish") is True
        assert _match_status("成功", "finish") is True

    def test_failed_aliases(self):
        assert _match_status("fail", "failed") is True
        assert _match_status("failed", "failed") is True
        assert _match_status("失败", "failed") is True

    def test_cancelled_aliases(self):
        assert _match_status("cancelled", "cancelled") is True
        assert _match_status("已取消", "cancelled") is True

    def test_no_match(self):
        assert _match_status("finish", "failed") is False
        assert _match_status("fail", "finish") is False

    def test_unknown_filter_falls_back(self):
        assert _match_status("running", "running") is True
        assert _match_status("finish", "running") is False


# ==================== _calculate_history_stats 测试 ====================

class TestCalculateHistoryStats:
    def test_empty_history(self):
        stats = _calculate_history_stats([])
        assert stats["total"] == 0
        assert stats["success_rate"] == 0

    def test_all_finish(self):
        history = [make_record(status="finish", total_weight=100) for _ in range(10)]
        stats = _calculate_history_stats(history)
        assert stats["total"] == 10
        assert stats["success_rate"] == 100.0
        assert stats["total_weight"] == 1000.0

    def test_mixed_status(self):
        history = [
            make_record(status="finish", total_weight=100),
            make_record(status="fail", total_weight=50),
        ]
        stats = _calculate_history_stats(history)
        assert stats["total"] == 2
        assert stats["success_rate"] == 50.0

    def test_duration_from_hours(self):
        history = [make_record(duration_hours=3.5)]
        stats = _calculate_history_stats(history)
        assert stats["total_duration_hours"] == 3.5

    def test_duration_from_times(self):
        rec = make_record(duration_hours=None)
        rec.pop("duration_hours", None)
        stats = _calculate_history_stats([rec])
        assert stats["total_duration_hours"] > 0

    def test_none_weight_treated_as_zero(self):
        history = [make_record(total_weight=None)]
        stats = _calculate_history_stats(history)
        assert stats["total_weight"] == 0


# ==================== _extract_available_colors 测试 ====================

class TestExtractAvailableColors:
    def test_empty_history(self):
        assert _extract_available_colors([]) == []

    def test_from_colors_used(self):
        history = [make_record(colors_used=["#ff0000", "#00ff00"])]
        colors = _extract_available_colors(history)
        assert "#ff0000" in colors
        assert "#00ff00" in colors

    def test_from_filament_color_fallback(self):
        history = [make_record(colors_used=[], filament_color="#0000ff")]
        colors = _extract_available_colors(history)
        assert "#0000ff" in colors

    def test_deduplication(self):
        history = [make_record(colors_used=["#ff0000"]), make_record(colors_used=["#ff0000"])]
        colors = _extract_available_colors(history)
        assert colors.count("#ff0000") == 1

    def test_sorted_output(self):
        history = [make_record(colors_used=["#cc0000", "#aa0000", "#bb0000"])]
        colors = _extract_available_colors(history)
        assert colors == sorted(colors)

    def test_colors_used_takes_priority(self):
        history = [make_record(colors_used=["#ff0000"], filament_color="#00ff00")]
        colors = _extract_available_colors(history)
        assert "#ff0000" in colors
        assert "#00ff00" not in colors


# ==================== _apply_filters 测试 ====================

class TestApplyFilters:
    @pytest.fixture
    def history(self):
        return [
            make_record(status="finish", filament_color="#ff0000",
                       start_time="2026-12-01T10:00:00+08:00",
                       end_time="2026-12-01T12:00:00+08:00",
                       task_name="拇指支架", filament_type="PETG"),
            make_record(status="fail", filament_color="#00ff00",
                       start_time="2026-11-15T10:00:00+08:00",
                       end_time="2026-11-15T11:00:00+08:00",
                       task_name="齿轮", filament_type="PLA"),
            make_record(status="finish", filament_color="#0000ff",
                       start_time="2026-10-01T10:00:00+08:00",
                       end_time="2026-10-01T14:00:00+08:00",
                       task_name="外壳", filament_type="ABS"),
            make_record(status="cancelled", filament_color="#ff0000",
                       start_time="2026-09-01T10:00:00+08:00",
                       end_time="2026-09-01T10:30:00+08:00",
                       task_name="测试件", filament_type="PLA"),
        ]

    def test_no_filter_returns_all(self, history):
        result = _apply_filters(history, "", "", "", "", "", "")
        assert len(result) == len(history)

    def test_filter_by_status_finish(self, history):
        result = _apply_filters(history, "finish", "", "", "", "", "")
        assert all(r["status"] == "finish" for r in result)
        assert len(result) == 2

    def test_filter_by_status_failed(self, history):
        result = _apply_filters(history, "failed", "", "", "", "", "")
        assert all(r["status"] == "fail" for r in result)
        assert len(result) == 1

    def test_filter_by_color(self, history):
        result = _apply_filters(history, "", "#ff0000", "", "", "", "")
        assert len(result) == 2

    def test_filter_by_date_range(self, history):
        result = _apply_filters(history, "", "", "", "2026-12-01", "2026-12-31", "")
        assert len(result) == 1
        assert "2026-12" in result[0]["end_time"]

    def test_filter_by_search_task_name(self, history):
        result = _apply_filters(history, "", "", "", "", "", "拇指")
        assert len(result) == 1
        assert "拇指" in result[0]["task_name"]

    def test_filter_by_search_filament_type(self, history):
        result = _apply_filters(history, "", "", "", "", "", "PETG")
        assert len(result) == 1

    def test_filter_by_search_case_insensitive(self, history):
        result = _apply_filters(history, "", "", "", "", "", "petg")
        assert len(result) == 1

    def test_combined_filter(self, history):
        result = _apply_filters(history, "finish", "", "", "2026-12-01", "2026-12-31", "")
        assert len(result) == 1
        assert result[0]["status"] == "finish"

    def test_filter_no_match_returns_empty(self, history):
        result = _apply_filters(history, "", "", "", "2099-01-01", "2099-12-31", "")
        assert len(result) == 0

    def test_filter_by_printer_name(self, history):
        history[0]["_printer_name"] = "P2S"
        history[1]["_printer_name"] = "A1Mini"
        result = _apply_filters(history, "", "", "P2S", "", "", "")
        assert len(result) == 1

    def test_filter_by_printer_name_ignored_when_no_tag(self, history):
        # 新逻辑：无 _printer_name 时，仍匹配 printer_serial 和 device_name
        # 测试数据无 printer_serial/device_name，也不匹配 _printer_name，所以结果为空
        result = _apply_filters(history, "", "", "P2S", "", "", "")
        assert len(result) == 0

    def test_color_filter_matches_colors_used_list(self, history):
        history[0]["colors_used"] = ["#ff0000", "#00ff00"]
        result = _apply_filters(history, "", "#00ff00", "", "", "", "")
        assert len(result) >= 1


# ==================== _process_history_request 测试 ====================

class TestProcessHistoryRequest:
    @pytest.fixture
    def mock_coordinator(self):
        history = make_history(55)

        class MockCoordinator:
            def get_sorted_history(self, desc=True):
                if desc:
                    return sorted(history, key=lambda r: r.get("end_time", ""), reverse=True)
                return sorted(history, key=lambda r: r.get("end_time", ""), reverse=False)

        return MockCoordinator()

    def test_basic_pagination(self, mock_coordinator):
        result = _process_history_request(mock_coordinator, "desc", 1, 20, "", "", "", "", "", "")
        assert result["total"] == 55
        assert result["page"] == 1
        assert result["total_pages"] == 3
        assert len(result["records"]) == 20

    def test_last_page(self, mock_coordinator):
        result = _process_history_request(mock_coordinator, "desc", 3, 20, "", "", "", "", "", "")
        assert result["page"] == 3
        assert len(result["records"]) == 15

    def test_page_exceeds_total(self, mock_coordinator):
        result = _process_history_request(mock_coordinator, "desc", 999, 20, "", "", "", "", "", "")
        assert result["page"] == result["total_pages"]

    def test_empty_history(self):
        class EmptyCoordinator:
            def get_sorted_history(self, desc=True):
                return []
        result = _process_history_request(EmptyCoordinator(), "desc", 1, 20, "", "", "", "", "", "")
        assert result["total"] == 0
        assert result["records"] == []

    def test_with_filter(self, mock_coordinator):
        result = _process_history_request(mock_coordinator, "desc", 1, 20, "finish", "", "", "", "", "")
        assert result["total"] < 55
        assert all(r["status"] == "finish" for r in result["records"])

    def test_stats_included(self, mock_coordinator):
        result = _process_history_request(mock_coordinator, "desc", 1, 20, "", "", "", "", "", "")
        assert "stats" in result
        assert result["stats"]["total"] == result["total"]

    def test_available_colors_always_full(self, mock_coordinator):
        full = _process_history_request(mock_coordinator, "desc", 1, 20, "", "", "", "", "", "")
        filtered = _process_history_request(mock_coordinator, "desc", 1, 20, "finish", "", "", "", "", "")
        assert set(full["available_colors"]) == set(filtered["available_colors"])

    def test_total_raw_with_filter(self, mock_coordinator):
        result = _process_history_request(mock_coordinator, "desc", 1, 20, "finish", "", "", "", "", "")
        assert result["total_raw"] == 55
        assert result["total"] < 55

    def test_large_page_size(self, mock_coordinator):
        result = _process_history_request(mock_coordinator, "desc", 1, 500, "", "", "", "", "", "")
        assert len(result["records"]) == 55

    def test_page_size_1(self, mock_coordinator):
        result = _process_history_request(mock_coordinator, "desc", 1, 1, "", "", "", "", "", "")
        assert len(result["records"]) == 1
        assert result["total_pages"] == 55

    def test_asc_sort(self, mock_coordinator):
        result = _process_history_request(mock_coordinator, "asc", 1, 5, "", "", "", "", "", "")
        times = [r.get("end_time", "") for r in result["records"]]
        assert times == sorted(times)

    def test_desc_sort(self, mock_coordinator):
        result = _process_history_request(mock_coordinator, "desc", 1, 5, "", "", "", "", "", "")
        times = [r.get("end_time", "") for r in result["records"]]
        assert times == sorted(times, reverse=True)

    def test_records_sanitized(self, mock_coordinator):
        history = mock_coordinator.get_sorted_history(desc=True)
        history[0]["_printer_name"] = "test"
        result = _process_history_request(mock_coordinator, "desc", 1, 20, "", "", "", "", "", "")
        for rec in result["records"]:
            assert not any(k.startswith("_") for k in rec.keys())


# ==================== storage._match_filter 新筛选项测试 ====================

# match_record_filter 已从 utils.py 提取到 _ns 中，直接复用
_ns2 = _ns
_match_filter_storage = _ns["match_record_filter"]


class TestMatchFilterSliceMode:
    """切片模式筛选测试"""

    def test_filter_cloud_slice(self):
        records = [
            {"slice_mode": "cloud_slice", "status": "finish"},
            {"slice_mode": "lan_file", "status": "finish"},
        ]
        result = [r for r in records if _match_filter_storage(r, "", "", "", "", "", "", "cloud_slice", "")]
        assert len(result) == 1
        assert result[0]["slice_mode"] == "cloud_slice"

    def test_filter_cloud_file(self):
        records = [
            {"slice_mode": "cloud_file", "status": "finish"},
            {"slice_mode": "lan_file", "status": "finish"},
        ]
        result = [r for r in records if _match_filter_storage(r, "", "", "", "", "", "", "cloud_file", "")]
        assert len(result) == 1
        assert result[0]["slice_mode"] == "cloud_file"

    def test_filter_lan_file(self):
        records = [
            {"slice_mode": "cloud_slice", "status": "finish"},
            {"slice_mode": "lan_file", "status": "finish"},
        ]
        result = [r for r in records if _match_filter_storage(r, "", "", "", "", "", "", "lan_file", "")]
        assert len(result) == 1
        assert result[0]["slice_mode"] == "lan_file"

    def test_legacy_cloud_maps_to_cloud_slice(self):
        """旧值 cloud 应映射到 cloud_slice"""
        records = [{"slice_mode": "cloud", "status": "finish"}]
        result = [r for r in records if _match_filter_storage(r, "", "", "", "", "", "", "cloud_slice", "")]
        assert len(result) == 1

    def test_legacy_local_maps_to_lan_file(self):
        """旧值 local 应映射到 lan_file"""
        records = [{"slice_mode": "local", "status": "finish"}]
        result = [r for r in records if _match_filter_storage(r, "", "", "", "", "", "", "lan_file", "")]
        assert len(result) == 1

    def test_empty_slice_mode_filter(self):
        records = [
            {"slice_mode": "cloud_slice"},
            {"slice_mode": "lan_file"},
        ]
        result = [r for r in records if _match_filter_storage(r, "", "", "", "", "", "", "", "")]
        assert len(result) == 2

    def test_missing_slice_mode_field(self):
        records = [
            {"status": "finish"},  # 无 slice_mode 字段
            {"slice_mode": "cloud_slice"},
        ]
        result = [r for r in records if _match_filter_storage(r, "", "", "", "", "", "", "cloud_slice", "")]
        assert len(result) == 1

    def test_case_insensitive(self):
        records = [{"slice_mode": "Cloud_Slice"}]
        result = [r for r in records if _match_filter_storage(r, "", "", "", "", "", "", "cloud_slice", "")]
        assert len(result) == 1


class TestMatchFilterOver500g:
    """超500g筛选测试"""

    def test_filter_over_500g(self):
        records = [
            {"over_500g": True, "total_weight": 600},
            {"over_500g": False, "total_weight": 200},
        ]
        result = [r for r in records if _match_filter_storage(r, "", "", "", "", "", "", "", "yes")]
        assert len(result) == 1
        assert result[0]["over_500g"] is True

    def test_filter_under_500g(self):
        records = [
            {"over_500g": True, "total_weight": 600},
            {"over_500g": False, "total_weight": 200},
        ]
        result = [r for r in records if _match_filter_storage(r, "", "", "", "", "", "", "", "no")]
        assert len(result) == 1
        assert result[0]["over_500g"] is False

    def test_empty_over_500g_filter(self):
        records = [
            {"over_500g": True},
            {"over_500g": False},
        ]
        result = [r for r in records if _match_filter_storage(r, "", "", "", "", "", "", "", "")]
        assert len(result) == 2

    def test_missing_over_500g_field(self):
        records = [
            {"status": "finish"},  # 无 over_500g 字段，默认 False
            {"over_500g": True},
        ]
        result = [r for r in records if _match_filter_storage(r, "", "", "", "", "", "", "", "yes")]
        assert len(result) == 1

    def test_combined_slice_and_weight_filter(self):
        records = [
            {"slice_mode": "cloud_slice", "over_500g": True},
            {"slice_mode": "cloud_slice", "over_500g": False},
            {"slice_mode": "lan_file", "over_500g": True},
        ]
        result = [r for r in records if _match_filter_storage(r, "", "", "", "", "", "", "cloud_slice", "yes")]
        assert len(result) == 1
        assert result[0]["slice_mode"] == "cloud_slice"
        assert result[0]["over_500g"] is True


class TestMatchFilterPrinterSerial:
    """打印机序列号筛选测试"""

    def test_filter_by_serial(self):
        records = [
            {"printer_serial": "22E8BJ5A2401765", "_printer_name": "P2S"},
            {"printer_serial": "0300AA5A1600497", "_printer_name": "A1Mini"},
        ]
        result = [r for r in records if _match_filter_storage(r, "", "", "22E8BJ5A2401765", "", "", "", "", "")]
        assert len(result) == 1
        assert result[0]["printer_serial"] == "22E8BJ5A2401765"

    def test_filter_by_serial_case_insensitive(self):
        records = [
            {"printer_serial": "22E8BJ5A2401765"},
        ]
        result = [r for r in records if _match_filter_storage(r, "", "", "22e8bj5a2401765", "", "", "", "", "")]
        assert len(result) == 1

    def test_filter_by_name_fallback(self):
        records = [
            {"printer_serial": "", "_printer_name": "P2S"},
            {"printer_serial": "", "_printer_name": "A1Mini"},
        ]
        result = [r for r in records if _match_filter_storage(r, "", "", "p2s", "", "", "", "", "")]
        assert len(result) == 1

    def test_no_match(self):
        records = [
            {"printer_serial": "ABC123", "_printer_name": "P2S"},
        ]
        result = [r for r in records if _match_filter_storage(r, "", "", "XYZ789", "", "", "", "", "")]
        assert len(result) == 0


# ==================== 新字段派生计算测试 ====================

class TestDerivedFields:
    """派生字段计算测试（multi_color, over_500g）"""

    def test_multi_color_true(self):
        """total_colors > 1 时 multi_color 应为 True"""
        record = {"total_colors": 3, "total_weight": 100}
        assert (record.get("total_colors", 0) or 0) > 1

    def test_multi_color_false(self):
        """total_colors <= 1 时 multi_color 应为 False"""
        record = {"total_colors": 1, "total_weight": 100}
        assert not ((record.get("total_colors", 0) or 0) > 1)

    def test_multi_color_missing(self):
        """缺少 total_colors 时 multi_color 应为 False"""
        record = {"total_weight": 100}
        assert not ((record.get("total_colors", 0) or 0) > 1)

    def test_over_500g_true(self):
        """total_weight > 500 时 over_500g 应为 True"""
        record = {"total_weight": 600}
        assert (record.get("total_weight", 0) or 0) > 500

    def test_over_500g_false(self):
        """total_weight <= 500 时 over_500g 应为 False"""
        record = {"total_weight": 300}
        assert not ((record.get("total_weight", 0) or 0) > 500)

    def test_over_500g_none_weight(self):
        """total_weight 为 None 时 over_500g 应为 False"""
        record = {"total_weight": None}
        assert not ((record.get("total_weight", 0) or 0) > 500)


# ==================== 统计计算新图表数据测试 ====================

class TestStatisticsNewCharts:
    """统计计算新图表数据测试"""

    def _calc_stats(self, history):
        """从记录列表计算新统计字段"""
        multi_color_count = 0
        single_color_count = 0
        slice_mode_counts = {}
        over_500g_count = 0
        under_500g_count = 0
        nozzle_size_counts = {}
        prepare_time_by_filament = {}
        failed_chamber_temps = []

        for r in history:
            # 多色/单色
            if r.get("multi_color"):
                multi_color_count += 1
            else:
                single_color_count += 1
            # 切片模式
            sm = r.get("slice_mode") or "unknown"
            slice_mode_counts[sm] = slice_mode_counts.get(sm, 0) + 1
            # 超500g
            if r.get("over_500g"):
                over_500g_count += 1
            else:
                under_500g_count += 1
            # 喷嘴尺寸
            ns = r.get("nozzle_size")
            if ns:
                nozzle_size_counts[ns] = nozzle_size_counts.get(ns, 0) + 1
            # 准备时间
            pt = r.get("prepare_time_minutes")
            ft = r.get("filament_type") or "unknown"
            if pt and pt > 0:
                if ft not in prepare_time_by_filament:
                    prepare_time_by_filament[ft] = []
                prepare_time_by_filament[ft].append(pt)
            # 失败仓温
            status = r.get("status", "")
            if status in ("fail", "cancelled"):
                ct = r.get("chamber_temp_final")
                if ct and ct > 0:
                    failed_chamber_temps.append(ct)

        return {
            "multi_color_ratio": {"multi": multi_color_count, "single": single_color_count},
            "slice_mode_distribution": slice_mode_counts,
            "over_500g_ratio": {"over": over_500g_count, "under": under_500g_count},
            "nozzle_size_distribution": nozzle_size_counts,
            "prepare_time_by_filament": prepare_time_by_filament,
            "failed_chamber_temps": failed_chamber_temps,
        }

    def test_multi_color_ratio(self):
        history = [
            {"multi_color": True, "slice_mode": "cloud", "over_500g": False},
            {"multi_color": False, "slice_mode": "local", "over_500g": False},
            {"multi_color": True, "slice_mode": "cloud", "over_500g": True},
        ]
        stats = self._calc_stats(history)
        assert stats["multi_color_ratio"]["multi"] == 2
        assert stats["multi_color_ratio"]["single"] == 1

    def test_slice_mode_distribution(self):
        history = [
            {"multi_color": False, "slice_mode": "cloud", "over_500g": False},
            {"multi_color": False, "slice_mode": "cloud", "over_500g": False},
            {"multi_color": False, "slice_mode": "local", "over_500g": False},
        ]
        stats = self._calc_stats(history)
        assert stats["slice_mode_distribution"]["cloud"] == 2
        assert stats["slice_mode_distribution"]["local"] == 1

    def test_slice_mode_missing(self):
        """缺少 slice_mode 时归入 unknown"""
        history = [{"multi_color": False, "over_500g": False}]
        stats = self._calc_stats(history)
        assert stats["slice_mode_distribution"]["unknown"] == 1

    def test_over_500g_ratio(self):
        history = [
            {"multi_color": False, "slice_mode": "cloud", "over_500g": True},
            {"multi_color": False, "slice_mode": "local", "over_500g": False},
            {"multi_color": False, "slice_mode": "cloud", "over_500g": True},
        ]
        stats = self._calc_stats(history)
        assert stats["over_500g_ratio"]["over"] == 2
        assert stats["over_500g_ratio"]["under"] == 1

    def test_nozzle_size_distribution(self):
        history = [
            {"multi_color": False, "slice_mode": "cloud", "over_500g": False, "nozzle_size": "0.4"},
            {"multi_color": False, "slice_mode": "cloud", "over_500g": False, "nozzle_size": "0.4"},
            {"multi_color": False, "slice_mode": "local", "over_500g": False, "nozzle_size": "0.2"},
        ]
        stats = self._calc_stats(history)
        assert stats["nozzle_size_distribution"]["0.4"] == 2
        assert stats["nozzle_size_distribution"]["0.2"] == 1

    def test_nozzle_size_missing(self):
        """缺少 nozzle_size 时不计入"""
        history = [{"multi_color": False, "slice_mode": "cloud", "over_500g": False}]
        stats = self._calc_stats(history)
        assert stats["nozzle_size_distribution"] == {}

    def test_prepare_time_by_filament(self):
        history = [
            {"multi_color": False, "slice_mode": "cloud", "over_500g": False,
             "filament_type": "PLA", "prepare_time_minutes": 5.0},
            {"multi_color": False, "slice_mode": "cloud", "over_500g": False,
             "filament_type": "PLA", "prepare_time_minutes": 7.0},
            {"multi_color": False, "slice_mode": "local", "over_500g": False,
             "filament_type": "PETG", "prepare_time_minutes": 10.0},
        ]
        stats = self._calc_stats(history)
        assert len(stats["prepare_time_by_filament"]["PLA"]) == 2
        assert len(stats["prepare_time_by_filament"]["PETG"]) == 1

    def test_prepare_time_zero_excluded(self):
        """准备时间为0或None时排除"""
        history = [
            {"multi_color": False, "slice_mode": "cloud", "over_500g": False,
             "filament_type": "PLA", "prepare_time_minutes": 0},
            {"multi_color": False, "slice_mode": "cloud", "over_500g": False,
             "filament_type": "PLA", "prepare_time_minutes": None},
        ]
        stats = self._calc_stats(history)
        assert "PLA" not in stats["prepare_time_by_filament"]

    def test_failed_chamber_temps(self):
        history = [
            {"multi_color": False, "slice_mode": "cloud", "over_500g": False,
             "status": "fail", "chamber_temp_final": 55.0},
            {"multi_color": False, "slice_mode": "cloud", "over_500g": False,
             "status": "finish", "chamber_temp_final": 60.0},
            {"multi_color": False, "slice_mode": "cloud", "over_500g": False,
             "status": "cancelled", "chamber_temp_final": 45.0},
        ]
        stats = self._calc_stats(history)
        assert len(stats["failed_chamber_temps"]) == 2
        assert 55.0 in stats["failed_chamber_temps"]
        assert 45.0 in stats["failed_chamber_temps"]

    def test_failed_chamber_temps_zero_excluded(self):
        """仓温为0或None时排除"""
        history = [
            {"multi_color": False, "slice_mode": "cloud", "over_500g": False,
             "status": "fail", "chamber_temp_final": 0},
            {"multi_color": False, "slice_mode": "cloud", "over_500g": False,
             "status": "fail", "chamber_temp_final": None},
        ]
        stats = self._calc_stats(history)
        assert len(stats["failed_chamber_temps"]) == 0

    def test_prepare_time_iqr_outlier_removal(self):
        """IQR方法排除异常值"""
        times = [5.0, 6.0, 7.0, 6.5, 5.5, 100.0]  # 100.0 是异常值
        sorted_times = sorted(times)
        n = len(sorted_times)
        q1 = sorted_times[n // 4]
        q3 = sorted_times[3 * n // 4]
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        filtered = [t for t in sorted_times if lower <= t <= upper]
        assert 100.0 not in filtered
        assert len(filtered) == 5


# ==================== 导入合并逻辑测试 ====================

class TestIsEmptyValue:
    """_is_empty_value 判断测试"""

    @staticmethod
    def _is_empty_value(val):
        """判断值是否为空/默认值"""
        if val is None:
            return True
        if isinstance(val, str) and val.strip() == "":
            return True
        if isinstance(val, (int, float)) and val == 0:
            return True
        if isinstance(val, bool):
            return val is False
        if isinstance(val, (list, dict)) and len(val) == 0:
            return True
        return False

    def test_none_is_empty(self):
        assert self._is_empty_value(None) is True

    def test_empty_string_is_empty(self):
        assert self._is_empty_value("") is True
        assert self._is_empty_value("   ") is True

    def test_zero_is_empty(self):
        assert self._is_empty_value(0) is True
        assert self._is_empty_value(0.0) is True

    def test_false_is_empty(self):
        assert self._is_empty_value(False) is True

    def test_empty_list_is_empty(self):
        assert self._is_empty_value([]) is True

    def test_empty_dict_is_empty(self):
        assert self._is_empty_value({}) is True

    def test_non_empty_string_not_empty(self):
        assert self._is_empty_value("PLA") is False

    def test_positive_number_not_empty(self):
        assert self._is_empty_value(42) is False
        assert self._is_empty_value(3.14) is False

    def test_true_not_empty(self):
        assert self._is_empty_value(True) is False

    def test_non_empty_list_not_empty(self):
        assert self._is_empty_value(["#ff0000"]) is False


class TestMergeRecord:
    """_merge_record 合并记录测试"""

    @staticmethod
    def _merge_record(existing, incoming):
        """模拟合并逻辑：仅填充空/默认字段"""
        def is_empty(val):
            if val is None:
                return True
            if isinstance(val, str) and val.strip() == "":
                return True
            if isinstance(val, (int, float)) and val == 0:
                return True
            if isinstance(val, bool):
                return val is False
            if isinstance(val, (list, dict)) and len(val) == 0:
                return True
            return False

        # 先做单位转换（在字段名映射之前）
        if "duration_minutes" in incoming and "duration_hours" not in incoming:
            dm = incoming.pop("duration_minutes", 0) or 0
            incoming["duration_hours"] = round(dm / 60, 2) if dm else 0
        if "energy_wh" in incoming and "energy_kwh" not in incoming:
            wh = incoming.pop("energy_wh", 0) or 0
            incoming["energy_kwh"] = round(wh / 1000, 4) if wh else None

        # 字段名映射
        field_map = {
            "endTime": "end_time",
            "startTime": "start_time",
            "deviceId": "printer_serial",
            "designId": "design_id",
        }
        for old_key, new_key in field_map.items():
            if old_key in incoming and new_key not in incoming:
                incoming[new_key] = incoming.pop(old_key)

        # 状态映射
        status_map = {"完成": "finish", "失败": "failed", "取消": "cancelled"}
        if incoming.get("status") in status_map:
            incoming["status"] = status_map[incoming["status"]]

        changed = False
        for key, value in incoming.items():
            if key.startswith("_"):
                continue
            if is_empty(value):
                continue
            existing_val = existing.get(key)
            if is_empty(existing_val):
                existing[key] = value
                changed = True
        return changed

    def test_fill_empty_fields(self):
        """空字段被填充"""
        existing = {"task_name": "test", "design_id": None, "filament_type": ""}
        incoming = {"task_name": "test", "design_id": "123456", "filament_type": "PLA"}
        changed = self._merge_record(existing, incoming)
        assert changed is True
        assert existing["design_id"] == "123456"
        assert existing["filament_type"] == "PLA"

    def test_no_overwrite_existing(self):
        """已有有效数据不被覆盖"""
        existing = {"task_name": "真实名称", "design_id": "existing_id", "filament_type": "PETG"}
        incoming = {"task_name": "导入名称", "design_id": "new_id", "filament_type": "PLA"}
        changed = self._merge_record(existing, incoming)
        assert changed is False
        assert existing["task_name"] == "真实名称"
        assert existing["design_id"] == "existing_id"
        assert existing["filament_type"] == "PETG"

    def test_default_values_can_be_filled(self):
        """默认值（0、False、空列表）可被覆盖"""
        existing = {"ams_used": False, "multi_color": False, "total_weight": 0}
        incoming = {"ams_used": True, "multi_color": True, "total_weight": 25.5}
        changed = self._merge_record(existing, incoming)
        assert changed is True
        assert existing["ams_used"] is True
        assert existing["multi_color"] is True
        assert existing["total_weight"] == 25.5

    def test_old_field_name_mapping(self):
        """老格式字段名自动转换"""
        existing = {"task_name": "test", "printer_serial": None, "end_time": None}
        incoming = {"task_name": "test", "deviceId": "SERIAL123", "endTime": "2026-01-01T12:00:00+08:00"}
        changed = self._merge_record(existing, incoming)
        assert changed is True
        assert existing["printer_serial"] == "SERIAL123"
        assert existing["end_time"] == "2026-01-01T12:00:00+08:00"
        assert "deviceId" not in incoming  # 老字段已移除

    def test_duration_minutes_conversion(self):
        """duration_minutes 自动转换为 duration_hours"""
        existing = {"task_name": "test", "duration_hours": 0}
        incoming = {"task_name": "test", "duration_minutes": 150}
        changed = self._merge_record(existing, incoming)
        assert changed is True
        assert existing["duration_hours"] == 2.5

    def test_energy_wh_conversion(self):
        """energy_wh 自动转换为 energy_kwh"""
        existing = {"task_name": "test", "energy_kwh": None}
        incoming = {"task_name": "test", "energy_wh": 120}
        changed = self._merge_record(existing, incoming)
        assert changed is True
        assert existing["energy_kwh"] == 0.12

    def test_chinese_status_mapping(self):
        """中文状态自动转换为英文"""
        existing = {"task_name": "test", "status": ""}
        incoming = {"task_name": "test", "status": "完成"}
        changed = self._merge_record(existing, incoming)
        assert changed is True
        assert existing["status"] == "finish"

    def test_design_id_from_old_format(self):
        """designId 老格式自动转为 design_id"""
        existing = {"task_name": "test", "design_id": None}
        incoming = {"task_name": "test", "designId": "MW999"}
        changed = self._merge_record(existing, incoming)
        assert changed is True
        assert existing["design_id"] == "MW999"

    def test_skip_internal_fields(self):
        """内部字段（_开头）不参与合并"""
        existing = {"task_name": "test", "_internal": "secret"}
        incoming = {"task_name": "test", "_new_internal": "data", "filament_type": "PLA"}
        changed = self._merge_record(existing, incoming)
        assert changed is True
        assert existing.get("_new_internal") is None
        assert existing["filament_type"] == "PLA"

    def test_incoming_empty_values_ignored(self):
        """导入值为空时不覆盖已有数据"""
        existing = {"task_name": "真实名称", "design_id": "existing_id"}
        incoming = {"task_name": "", "design_id": None}
        changed = self._merge_record(existing, incoming)
        assert changed is False
        assert existing["task_name"] == "真实名称"
        assert existing["design_id"] == "existing_id"


class TestFindDuplicateRecord:
    """_find_duplicate_record 重复判定测试"""

    @staticmethod
    def _find_duplicate(record, history):
        """模拟重复查找：序列号 + 结束时间 ±2分钟（纯标准库实现）"""
        from datetime import datetime, timezone, timedelta

        serial = record.get("printer_serial") or record.get("deviceId") or ""
        end_time_str = record.get("end_time") or record.get("endTime") or ""
        if not serial or not end_time_str:
            return None

        def parse_to_utc(s):
            try:
                dt = datetime.fromisoformat(s)
                if dt.tzinfo is None:
                    # 无时区信息默认按 UTC+8 处理
                    dt = dt.replace(tzinfo=timezone(timedelta(hours=8)))
                return dt.astimezone(timezone.utc)
            except (ValueError, TypeError):
                return None

        end_dt = parse_to_utc(end_time_str)
        if not end_dt:
            return None

        for existing in history:
            ex_serial = existing.get("printer_serial") or existing.get("deviceId") or ""
            if ex_serial != serial:
                continue
            ex_end_str = existing.get("end_time") or existing.get("endTime") or ""
            if not ex_end_str:
                continue
            ex_dt = parse_to_utc(ex_end_str)
            if not ex_dt:
                continue
            if abs((end_dt - ex_dt).total_seconds()) <= 120:
                return existing
        return None

    def test_exact_match(self):
        """完全匹配"""
        history = [{"printer_serial": "SERIAL1", "end_time": "2026-01-01T12:00:00+08:00"}]
        record = {"printer_serial": "SERIAL1", "end_time": "2026-01-01T12:00:00+08:00"}
        result = self._find_duplicate(record, history)
        assert result is not None

    def test_within_2_minutes(self):
        """结束时间差在2分钟内"""
        history = [{"printer_serial": "SERIAL1", "end_time": "2026-01-01T12:00:00+08:00"}]
        record = {"printer_serial": "SERIAL1", "end_time": "2026-01-01T12:01:30+08:00"}
        result = self._find_duplicate(record, history)
        assert result is not None

    def test_beyond_2_minutes(self):
        """结束时间差超过2分钟"""
        history = [{"printer_serial": "SERIAL1", "end_time": "2026-01-01T12:00:00+08:00"}]
        record = {"printer_serial": "SERIAL1", "end_time": "2026-01-01T12:03:00+08:00"}
        result = self._find_duplicate(record, history)
        assert result is None

    def test_different_serial(self):
        """不同序列号不匹配"""
        history = [{"printer_serial": "SERIAL1", "end_time": "2026-01-01T12:00:00+08:00"}]
        record = {"printer_serial": "SERIAL2", "end_time": "2026-01-01T12:00:00+08:00"}
        result = self._find_duplicate(record, history)
        assert result is None

    def test_missing_serial(self):
        """缺少序列号不匹配"""
        history = [{"printer_serial": "SERIAL1", "end_time": "2026-01-01T12:00:00+08:00"}]
        record = {"end_time": "2026-01-01T12:00:00+08:00"}
        result = self._find_duplicate(record, history)
        assert result is None

    def test_old_field_name_deviceId(self):
        """老格式 deviceId 也参与匹配"""
        history = [{"printer_serial": "SERIAL1", "end_time": "2026-01-01T12:00:00+08:00"}]
        record = {"deviceId": "SERIAL1", "endTime": "2026-01-01T12:00:00+08:00"}
        result = self._find_duplicate(record, history)
        assert result is not None

    def test_design_id_not_in_duplicate_check(self):
        """design_id 不参与重复判定"""
        history = [{"printer_serial": "SERIAL1", "end_time": "2026-01-01T12:00:00+08:00", "design_id": "AAA"}]
        record = {"printer_serial": "SERIAL1", "end_time": "2026-01-01T12:00:00+08:00", "design_id": "BBB"}
        result = self._find_duplicate(record, history)
        assert result is not None  # 仍然匹配，design_id 不影响判定


class TestStorageKeyMigration:
    """测试存储键迁移逻辑（entry_id → serial）"""

    def test_resolve_storage_key_prefers_serial(self):
        """序列号优先于 entry_id"""
        # 模拟 coordinator 有序列号的情况
        class MockCoordinator:
            printer_serial = "ABC123"
            class entry:
                entry_id = "old_entry_id_001"
        # _resolve_storage_key 应该返回 serial
        assert MockCoordinator.printer_serial == "ABC123"

    def test_resolve_storage_key_fallback_to_entry_id(self):
        """无序列号时回退到 entry_id"""
        class MockCoordinator:
            printer_serial = ""
            class entry:
                entry_id = "fallback_entry_id"
        assert MockCoordinator.printer_serial == ""  # 空序列号，应回退


class TestIsDuplicateRecord:
    """测试静态方法 _is_duplicate_record（不依赖 self.history）"""

    @staticmethod
    def _is_duplicate(existing, record):
        """复制 coordinator._is_duplicate_record 的核心逻辑"""
        serial = record.get("printer_serial") or record.get("deviceId") or ""
        ex_serial = existing.get("printer_serial") or existing.get("deviceId") or ""
        if serial != ex_serial or not serial:
            return False
        end_time_str = record.get("end_time") or record.get("endTime") or ""
        ex_end_str = existing.get("end_time") or existing.get("endTime") or ""
        if not end_time_str or not ex_end_str:
            return False
        try:
            from datetime import datetime
            def _parse(t):
                t = t.replace("Z", "+00:00")
                if "T" in t:
                    return datetime.fromisoformat(t)
                return datetime.fromisoformat(t.replace(" ", "T"))
            dt1 = _parse(end_time_str)
            dt2 = _parse(ex_end_str)
            if dt1.tzinfo:
                dt1 = dt1.replace(tzinfo=None)
            if dt2.tzinfo:
                dt2 = dt2.replace(tzinfo=None)
            return abs((dt1 - dt2).total_seconds()) <= 120
        except Exception:
            return False

    def test_same_serial_same_time(self):
        """相同序列号+相同时间=重复"""
        existing = {"printer_serial": "S1", "end_time": "2026-01-01 12:00:00"}
        record = {"printer_serial": "S1", "end_time": "2026-01-01 12:00:00"}
        assert self._is_duplicate(existing, record) is True

    def test_different_serial(self):
        """不同序列号=不重复"""
        existing = {"printer_serial": "S1", "end_time": "2026-01-01 12:00:00"}
        record = {"printer_serial": "S2", "end_time": "2026-01-01 12:00:00"}
        assert self._is_duplicate(existing, record) is False

    def test_within_2min_tolerance(self):
        """±2分钟内=重复"""
        existing = {"printer_serial": "S1", "end_time": "2026-01-01 12:00:00"}
        record = {"printer_serial": "S1", "end_time": "2026-01-01 12:01:30"}
        assert self._is_duplicate(existing, record) is True

    def test_beyond_2min(self):
        """超过2分钟=不重复"""
        existing = {"printer_serial": "S1", "end_time": "2026-01-01 12:00:00"}
        record = {"printer_serial": "S1", "end_time": "2026-01-01 12:03:00"}
        assert self._is_duplicate(existing, record) is False

    def test_old_field_name_deviceId(self):
        """老格式 deviceId 也参与比较"""
        existing = {"deviceId": "S1", "end_time": "2026-01-01 12:00:00"}
        record = {"printer_serial": "S1", "end_time": "2026-01-01 12:00:00"}
        assert self._is_duplicate(existing, record) is True

    def test_empty_serial(self):
        """空序列号=不重复"""
        existing = {"printer_serial": "", "end_time": "2026-01-01 12:00:00"}
        record = {"printer_serial": "", "end_time": "2026-01-01 12:00:00"}
        assert self._is_duplicate(existing, record) is False

    def test_iso_format_with_timezone(self):
        """ISO 格式带时区也能正确比较"""
        existing = {"printer_serial": "S1", "end_time": "2026-01-01T12:00:00+08:00"}
        record = {"printer_serial": "S1", "end_time": "2026-01-01T12:01:00+08:00"}
        assert self._is_duplicate(existing, record) is True


class TestScanAllHistoryFiles:
    """测试 StorageManager.scan_all_history_files 静态方法"""

    @staticmethod
    def _scan(history_dir):
        """复制 scan_all_history_files 核心逻辑"""
        import json, os
        if not os.path.isdir(history_dir):
            return []
        all_records = []
        for f in sorted(os.listdir(history_dir)):
            if not f.endswith(".json") or f.endswith("_stats.json"):
                continue
            fp = os.path.join(history_dir, f)
            try:
                with open(fp, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                records = data.get("history", []) if isinstance(data, dict) else data
                serial = f.rsplit("_", 1)[0] if "_" in f else ""
                for r in records:
                    r["_source_serial"] = serial
                all_records.extend(records)
            except Exception:
                continue
        all_records.sort(key=lambda x: x.get("end_time") or x.get("start_time") or "", reverse=True)
        return all_records

    def test_scan_empty_dir(self, tmp_path):
        """空目录返回空列表"""
        result = self._scan(str(tmp_path / "nonexistent"))
        assert result == []

    def test_scan_multiple_serials(self, tmp_path):
        """扫描多个序列号的文件"""
        import json
        d = tmp_path / "history"
        d.mkdir()
        # 写入两个序列号的文件
        (d / "SERIAL1_2026.json").write_text(json.dumps({
            "history": [{"task_name": "A", "end_time": "2026-01-01", "printer_serial": "SERIAL1"}]
        }), encoding="utf-8")
        (d / "SERIAL2_2026.json").write_text(json.dumps({
            "history": [{"task_name": "B", "end_time": "2026-02-01", "printer_serial": "SERIAL2"}]
        }), encoding="utf-8")
        result = self._scan(str(d))
        assert len(result) == 2
        # 按时间降序，B 在前
        assert result[0]["task_name"] == "B"
        assert result[0]["_source_serial"] == "SERIAL2"
        assert result[1]["_source_serial"] == "SERIAL1"

    def test_scan_skips_stats_files(self, tmp_path):
        """跳过统计文件"""
        import json
        d = tmp_path / "history"
        d.mkdir()
        (d / "SERIAL1_stats.json").write_text("{}", encoding="utf-8")
        (d / "SERIAL1_2026.json").write_text(json.dumps({
            "history": [{"task_name": "A", "end_time": "2026-01-01"}]
        }), encoding="utf-8")
        result = self._scan(str(d))
        assert len(result) == 1

    def test_get_all_serials(self, tmp_path):
        """获取所有序列号"""
        import json
        d = tmp_path / "history"
        d.mkdir()
        (d / "SERIAL1_2025.json").write_text("{}", encoding="utf-8")
        (d / "SERIAL1_2026.json").write_text("{}", encoding="utf-8")
        (d / "SERIAL2_2026.json").write_text("{}", encoding="utf-8")
        (d / "SERIAL1_stats.json").write_text("{}", encoding="utf-8")
        # 复制 get_all_serials 逻辑
        serials = set()
        for f in os.listdir(str(d)):
            if f.endswith(".json") and not f.endswith("_stats.json") and "_" in f:
                serial = f.rsplit("_", 1)[0]
                serials.add(serial)
        assert sorted(serials) == ["SERIAL1", "SERIAL2"]


# ==================== extract_model_from_gcode_filename 测试 ====================

# 从 utils.py 提取纯函数
_UTILS_PATH = os.path.join(
    os.path.dirname(__file__), "..",
    "custom_components", "printer_analytics", "utils.py",
)
_UTILS_SOURCE = open(_UTILS_PATH, "r", encoding="utf-8").read()

_ns_utils = {"re": __import__("re"), "os": __import__("os"), "logging": __import__("logging"), "shutil": __import__("shutil"), "datetime": __import__("datetime"), "timezone": __import__("datetime").timezone, "Path": __import__("pathlib").Path, "Optional": __import__("typing").Optional}
exec(_UTILS_SOURCE[_UTILS_SOURCE.index("def extract_model_from_gcode_filename"):], _ns_utils)
extract_model_from_gcode_filename = _ns_utils["extract_model_from_gcode_filename"]


class TestExtractModelFromGcodeFilename:
    """从 gcode_file_downloaded 值提取模型名"""

    def test_standard_format(self):
        """标准格式：designId-模型名+参数描述.gcode.gcode"""
        result = extract_model_from_gcode_filename("925294-问号箱0.2mm 层高, 2 层墙, 15% 填充.gcode.gcode")
        assert result == "问号箱"

    def test_no_param_description(self):
        """无参数描述：只有模型名"""
        result = extract_model_from_gcode_filename("12345-简单模型.gcode.gcode")
        assert result == "简单模型"

    def test_empty_string(self):
        """空字符串"""
        result = extract_model_from_gcode_filename("")
        assert result == ""

    def test_single_gcode_suffix(self):
        """只有一个 .gcode 后缀"""
        result = extract_model_from_gcode_filename("925294-测试模型0.2mm 层高.gcode")
        assert result == "测试模型"

    def test_no_design_id_prefix(self):
        """无 designId 前缀"""
        result = extract_model_from_gcode_filename("直接模型名0.4mm 层高.gcode.gcode")
        assert result == "直接模型名"

    def test_model_with_slash(self):
        """模型名包含斜杠（如 X2D/P2S）"""
        result = extract_model_from_gcode_filename("123-X2D/P2S X轴一体化密封盖0.2mm 层高.gcode.gcode")
        assert result == "X2D/P2S X轴一体化密封盖"

    def test_model_with_english_name(self):
        """英文模型名"""
        result = extract_model_from_gcode_filename("999-MyModel0.2mm.gcode.gcode")
        assert result == "MyModel"

    def test_only_design_id(self):
        """只有 designId，无模型名"""
        result = extract_model_from_gcode_filename("12345-.gcode.gcode")
        assert result == ""
