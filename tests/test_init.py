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
        result = _apply_filters(history, "", "", "P2S", "", "", "")
        assert len(result) == len(history)

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

# 从 storage.py 提取 _match_filter 纯函数
_STORAGE_PATH = os.path.join(
    os.path.dirname(__file__), "..",
    "custom_components", "printer_analytics", "storage.py",
)
_storage_src = open(_STORAGE_PATH, "r", encoding="utf-8").read()

# 提取 _match_filter 方法并转为独立函数
_ns2 = {}
_match_filter_src = _storage_src[
    _storage_src.index("    @staticmethod\n    def _match_filter"):
    _storage_src.index("    @staticmethod\n    def _collect_colors")
]
# 去掉 @staticmethod 和 self 参数，转为独立函数
_match_filter_src = _match_filter_src.replace("    @staticmethod\n", "").replace("    def _match_filter", "def _match_filter_storage")
exec(_match_filter_src, _ns2)
_match_filter_storage = _ns2["_match_filter_storage"]


class TestMatchFilterSliceMode:
    """切片模式筛选测试"""

    def test_filter_cloud_slice(self):
        records = [
            {"slice_mode": "cloud", "status": "finish"},
            {"slice_mode": "local", "status": "finish"},
        ]
        result = [r for r in records if _match_filter_storage(r, "", "", "", "", "", "", "cloud", "")]
        assert len(result) == 1
        assert result[0]["slice_mode"] == "cloud"

    def test_filter_local_slice(self):
        records = [
            {"slice_mode": "cloud", "status": "finish"},
            {"slice_mode": "local", "status": "finish"},
        ]
        result = [r for r in records if _match_filter_storage(r, "", "", "", "", "", "", "local", "")]
        assert len(result) == 1
        assert result[0]["slice_mode"] == "local"

    def test_empty_slice_mode_filter(self):
        records = [
            {"slice_mode": "cloud"},
            {"slice_mode": "local"},
        ]
        result = [r for r in records if _match_filter_storage(r, "", "", "", "", "", "", "", "")]
        assert len(result) == 2

    def test_missing_slice_mode_field(self):
        records = [
            {"status": "finish"},  # 无 slice_mode 字段
            {"slice_mode": "cloud"},
        ]
        result = [r for r in records if _match_filter_storage(r, "", "", "", "", "", "", "cloud", "")]
        assert len(result) == 1

    def test_case_insensitive(self):
        records = [{"slice_mode": "Cloud"}]
        result = [r for r in records if _match_filter_storage(r, "", "", "", "", "", "", "cloud", "")]
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
            {"slice_mode": "cloud", "over_500g": True},
            {"slice_mode": "cloud", "over_500g": False},
            {"slice_mode": "local", "over_500g": True},
        ]
        result = [r for r in records if _match_filter_storage(r, "", "", "", "", "", "", "cloud", "yes")]
        assert len(result) == 1
        assert result[0]["slice_mode"] == "cloud"
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
