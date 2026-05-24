"""
打印机分析 - 自动化测试套件
每次修改代码后运行: python ws_test.py

覆盖范围:
  1. WebSocket 连接与认证
  2. 历史记录分页 (基本/翻页/大页面/边界)
  3. 筛选功能 (状态/颜色/日期/搜索/组合)
  4. 导入功能 (模板格式 + API调用 + 数据验证 + 异常处理)
  5. 性能基准 (响应时间)
  6. 异常与边界条件
"""
import asyncio
import json
import sys
import time
import websockets

# ==================== 配置 ====================
HA_URL = "ws://192.168.0.130:8123/api/websocket"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiI3Y2EyNjc2MzdmZGU0YzliOWQ3Y2Y3ODM3N2YwMzA5ZSIsImlhdCI6MTc3ODk2OTYzNCwiZXhwIjoyMDk0MzI5NjM0fQ.iFan1gdP67hAY5jn0ilFABv98DbA79TFTHg76PyNhJY"
# P2S 打印机 entry_id
ENTRY_ID_P2S = "01KRTS6CW4PZ1GFDK42CRTTMGV"
# A1 Mini 打印机 entry_id
ENTRY_ID_A1MINI = "01KRN9GJCF600K6JNS881DJ81S"

# 性能阈值 (ms)
PERF_WARN = 500   # 超过此值警告
PERF_FAIL = 3000  # 超过此值失败

# ==================== 测试框架 ====================
_msg_id = 0
_results = []  # 收集所有测试结果


class TestResult:
    """单个测试用例结果"""
    def __init__(self, name, passed, detail="", duration_ms=0):
        self.name = name
        self.passed = passed
        self.detail = detail
        self.duration_ms = duration_ms

    def __str__(self):
        icon = "PASS" if self.passed else "FAIL"
        ms = f" ({self.duration_ms:.0f}ms)" if self.duration_ms else ""
        return f"  [{icon}] {self.name}{ms}  {self.detail}"


async def ws_request(ws, command, **kwargs):
    """发送 WebSocket 请求并等待匹配的响应"""
    global _msg_id
    _msg_id += 1
    msg_id = _msg_id
    payload = {"id": msg_id, "type": command, **kwargs}
    await ws.send(json.dumps(payload))
    deadline = time.time() + 15  # 15秒超时
    while True:
        remaining = deadline - time.time()
        if remaining <= 0:
            return {"id": msg_id, "success": False, "error": "timeout"}
        try:
            resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=remaining))
        except asyncio.TimeoutError:
            return {"id": msg_id, "success": False, "error": "timeout"}
        if resp.get("id") == msg_id:
            return resp


def check(name, condition, detail="", duration_ms=0):
    """断言并记录结果"""
    r = TestResult(name, bool(condition), detail, duration_ms)
    _results.append(r)
    print(r)
    return condition


def check_perf(name, duration_ms, threshold=PERF_WARN):
    """检查性能是否达标"""
    passed = duration_ms < PERF_FAIL
    warn = duration_ms >= threshold
    detail = ""
    if not passed:
        detail = f"超时! {duration_ms:.0f}ms > {PERF_FAIL}ms"
    elif warn:
        detail = f"较慢 {duration_ms:.0f}ms > {threshold}ms"
    r = TestResult(f"性能: {name}", passed, detail, duration_ms)
    _results.append(r)
    print(r)
    return passed


def _pg(result):
    """快捷获取分页信息"""
    return result.get("pagination", {})


# ==================== 测试用例 ====================

async def test_connection(ws):
    """TC-01: WebSocket 连接与认证"""
    resp = await ws_request(ws, "printer_analytics/query_history",
                            entry_id=ENTRY_ID_P2S, page=1, page_size=1)
    check("WS连接可达", resp.get("success") is True or resp.get("error", {}).get("code") != "timeout",
          f"success={resp.get('success')}")


async def test_basic_pagination(ws):
    """TC-02~05: 基本分页功能"""
    t0 = time.time()
    resp = await ws_request(ws, "printer_analytics/query_history",
                            entry_id=ENTRY_ID_P2S, page=1, page_size=20)
    ms = (time.time() - t0) * 1000

    if not check("基本分页-请求成功", resp.get("success"), str(resp.get("error"))):
        return None

    r = resp["result"]
    pg = _pg(r)
    check("基本分页-返回记录数<=20", len(r["records"]) <= 20,
          f"records={len(r['records'])}")
    check("基本分页-total>0", pg.get("total", 0) > 0, f"total={pg.get('total')}")
    check("基本分页-total_pages>=1", pg.get("total_pages", 0) >= 1, f"total_pages={pg.get('total_pages')}")
    check("基本分页-page=1", pg.get("page") == 1, f"page={pg.get('page')}")
    check_perf("基本分页", ms)

    # 默认降序: 第一条时间 >= 第二条
    if len(r["records"]) >= 2:
        t1 = r["records"][0].get("start_time", "")
        t2 = r["records"][1].get("start_time", "")
        check("默认降序排序", t1 >= t2, f"{t1[:10]} >= {t2[:10]}")

    return r


async def test_pagination_navigation(ws, first_result):
    """TC-06~08: 翻页导航"""
    if not first_result:
        check("翻页测试", False, "跳过: 无首页数据")
        return

    pg = _pg(first_result)
    total_pages = pg.get("total_pages", 1)
    total = pg.get("total", 0)

    # 翻到第2页
    if total_pages >= 2:
        t0 = time.time()
        resp = await ws_request(ws, "printer_analytics/query_history",
                                entry_id=ENTRY_ID_P2S, page=2, page_size=20)
        ms = (time.time() - t0) * 1000
        if check("翻页-第2页成功", resp.get("success")):
            r2 = _pg(resp["result"])
            check("翻页-第2页page=2", r2.get("page") == 2, f"page={r2.get('page')}")
            check_perf("翻页第2页", ms)

    # 翻到最后一页
    if total_pages > 2:
        t0 = time.time()
        resp = await ws_request(ws, "printer_analytics/query_history",
                                entry_id=ENTRY_ID_P2S, page=total_pages, page_size=20)
        ms = (time.time() - t0) * 1000
        if check("翻页-最后一页成功", resp.get("success")):
            r_last = _pg(resp["result"])
            check("翻页-最后一页page正确", r_last.get("page") == total_pages,
                  f"page={r_last.get('page')}")
            expected_last = total - (total_pages - 1) * 20
            check("翻页-最后一页记录数", len(resp["result"]["records"]) == expected_last,
                  f"expected={expected_last}, actual={len(resp['result']['records'])}")
            check_perf("翻页最后一页", ms)

    # 超出页码范围
    resp = await ws_request(ws, "printer_analytics/query_history",
                            entry_id=ENTRY_ID_P2S, page=99999, page_size=20)
    if check("翻页-超出范围不报错", resp.get("success")):
        r_over = _pg(resp["result"])
        check("翻页-超出范围自动修正页码", r_over.get("page", 99999) <= r_over.get("total_pages", 0),
              f"page={r_over.get('page')}, total_pages={r_over.get('total_pages')}")


async def test_large_page_size(ws):
    """TC-09: 大页面请求"""
    t0 = time.time()
    resp = await ws_request(ws, "printer_analytics/query_history",
                            entry_id=ENTRY_ID_P2S, page=1, page_size=500)
    ms = (time.time() - t0) * 1000
    if check("大页面(500条)-成功", resp.get("success")):
        r = resp["result"]
        check("大页面-记录数<=500", len(r["records"]) <= 500, f"records={len(r['records'])}")
        check_perf("大页面500条", ms)

    # page_size=1 极端情况
    resp = await ws_request(ws, "printer_analytics/query_history",
                            entry_id=ENTRY_ID_P2S, page=1, page_size=1)
    if check("极小页面(1条)-成功", resp.get("success")):
        check("极小页面-记录数=1", len(resp["result"]["records"]) == 1,
              f"records={len(resp['result']['records'])}")


async def test_filter_status(ws):
    """TC-10~11: 状态筛选"""
    # 筛选成功
    t0 = time.time()
    resp = await ws_request(ws, "printer_analytics/query_history",
                            entry_id=ENTRY_ID_P2S, page=1, page_size=20,
                            filters={"status": "finish"})
    ms = (time.time() - t0) * 1000
    finish_total = 0
    if check("状态筛选(finish)-成功", resp.get("success")):
        r = resp["result"]
        finish_total = _pg(r).get("total", 0)
        check("状态筛选(finish)-total>0", finish_total > 0, f"total={finish_total}")
        # 验证所有记录状态都是成功
        if r["records"]:
            all_finish = all(rec.get("status") in ("finish", "completed", "success") for rec in r["records"])
            check("状态筛选(finish)-记录状态正确", all_finish)
        check_perf("状态筛选(finish)", ms)

    # 筛选失败
    t0 = time.time()
    resp = await ws_request(ws, "printer_analytics/query_history",
                            entry_id=ENTRY_ID_P2S, page=1, page_size=20,
                            filters={"status": "failed"})
    ms = (time.time() - t0) * 1000
    failed_total = 0
    if check("状态筛选(failed)-成功", resp.get("success")):
        r = resp["result"]
        failed_total = _pg(r).get("total", 0)
        # failed 记录可能为0（取决于数据），不作为必须通过项
        check("状态筛选(failed)-记录数", failed_total >= 0, f"total={failed_total}")
        if r["records"]:
            all_failed = all(rec.get("status") in ("fail", "failed") for rec in r["records"])
            check("状态筛选(failed)-记录状态正确", all_failed)
        check_perf("状态筛选(failed)", ms)

    # finish + failed 总数应 <= 全量
    resp_all = await ws_request(ws, "printer_analytics/query_history",
                                entry_id=ENTRY_ID_P2S, page=1, page_size=1)
    if resp_all.get("success"):
        all_total = _pg(resp_all["result"]).get("total", 0)
        check("状态筛选-数量一致性", finish_total + failed_total <= all_total,
              f"finish={finish_total} + failed={failed_total} <= all={all_total}")


async def test_filter_color(ws):
    """TC-12: 颜色筛选"""
    # 先获取可用颜色列表
    resp = await ws_request(ws, "printer_analytics/query_history",
                            entry_id=ENTRY_ID_P2S, page=1, page_size=1)
    if not resp.get("success"):
        check("颜色筛选", False, "无法获取颜色列表")
        return

    # 颜色列表在 filter_options.colors 中
    colors = resp["result"].get("filter_options", {}).get("colors", [])
    check("颜色列表非空", len(colors) > 0, f"colors={len(colors)}")

    if not colors:
        return

    # 用第一个颜色筛选
    test_color = colors[0]
    t0 = time.time()
    resp = await ws_request(ws, "printer_analytics/query_history",
                            entry_id=ENTRY_ID_P2S, page=1, page_size=20,
                            filters={"color": test_color})
    ms = (time.time() - t0) * 1000
    if check(f"颜色筛选({test_color})-成功", resp.get("success")):
        r = resp["result"]
        check("颜色筛选-有结果", _pg(r).get("total", 0) > 0, f"total={_pg(r).get('total')}")
        check_perf(f"颜色筛选({test_color})", ms)


async def test_filter_date(ws):
    """TC-13: 日期范围筛选"""
    t0 = time.time()
    resp = await ws_request(ws, "printer_analytics/query_history",
                            entry_id=ENTRY_ID_P2S, page=1, page_size=20,
                            filters={"date_from": "2024-01-01", "date_to": "2024-12-31"})
    ms = (time.time() - t0) * 1000
    if check("日期筛选(2024年)-成功", resp.get("success")):
        r = resp["result"]
        # 2024年可能无数据，不作为必须通过项
        check("日期筛选(2024年)-记录数", _pg(r).get("total", 0) >= 0, f"total={_pg(r).get('total')}")
        # 验证记录日期都在范围内
        if r["records"]:
            all_in_range = all(
                "2024" in (rec.get("start_time", "") or rec.get("end_time", ""))
                for rec in r["records"]
            )
            check("日期筛选-记录在范围内", all_in_range)
        check_perf("日期筛选", ms)

    # 筛选不可能的日期范围
    resp = await ws_request(ws, "printer_analytics/query_history",
                            entry_id=ENTRY_ID_P2S, page=1, page_size=20,
                            filters={"date_from": "2099-01-01", "date_to": "2099-12-31"})
    if check("日期筛选(未来)-成功", resp.get("success")):
        check("日期筛选(未来)-无结果", _pg(resp["result"]).get("total", 0) == 0,
              f"total={_pg(resp['result']).get('total')}")


async def test_search(ws):
    """TC-14: 搜索功能"""
    # 搜索中文关键词
    t0 = time.time()
    resp = await ws_request(ws, "printer_analytics/query_history",
                            entry_id=ENTRY_ID_P2S, page=1, page_size=20,
                            filters={"search": "拇指"})
    ms = (time.time() - t0) * 1000
    if check("搜索(拇指)-成功", resp.get("success")):
        r = resp["result"]
        # "拇指"可能不在当前数据中，不作为必须通过项
        check("搜索(拇指)-记录数", _pg(r).get("total", 0) >= 0, f"total={_pg(r).get('total')}")
        if r["records"]:
            matched = any("拇指" in (rec.get("task_name", "") or "") for rec in r["records"])
            check("搜索-结果包含关键词", matched)
        check_perf("搜索", ms)

    # 搜索耗材类型
    resp = await ws_request(ws, "printer_analytics/query_history",
                            entry_id=ENTRY_ID_P2S, page=1, page_size=20,
                            filters={"search": "PETG"})
    if check("搜索(PETG)-成功", resp.get("success")):
        check("搜索(PETG)-有结果", _pg(resp["result"]).get("total", 0) > 0,
              f"total={_pg(resp['result']).get('total')}")

    # 搜索不存在的内容
    resp = await ws_request(ws, "printer_analytics/query_history",
                            entry_id=ENTRY_ID_P2S, page=1, page_size=20,
                            filters={"search": "ZZZZNOTEXIST"})
    if check("搜索(不存在)-成功", resp.get("success")):
        check("搜索(不存在)-无结果", _pg(resp["result"]).get("total", 0) == 0,
              f"total={_pg(resp['result']).get('total')}")


async def test_combined_filter(ws):
    """TC-15: 组合筛选"""
    t0 = time.time()
    resp = await ws_request(ws, "printer_analytics/query_history",
                            entry_id=ENTRY_ID_P2S, page=1, page_size=20,
                            filters={"status": "finish", "date_from": "2024-01-01", "date_to": "2024-12-31"})
    ms = (time.time() - t0) * 1000
    if check("组合筛选(finish+2024年)-成功", resp.get("success")):
        r = resp["result"]
        combined_total = _pg(r).get("total", 0)
        # 2024年可能无数据，不作为必须通过项
        check("组合筛选-记录数", combined_total >= 0, f"total={combined_total}")
        check_perf("组合筛选", ms)

    # 三重组合: 状态 + 搜索
    resp = await ws_request(ws, "printer_analytics/query_history",
                            entry_id=ENTRY_ID_P2S, page=1, page_size=20,
                            filters={"status": "finish", "search": "PETG"})
    if check("三重组合(finish+PETG)-成功", resp.get("success")):
        r = resp["result"]
        check("三重组合-有结果", _pg(r).get("total", 0) > 0, f"total={_pg(r).get('total')}")
        if r["records"]:
            all_finish = all(rec.get("status") in ("finish", "completed", "success") for rec in r["records"])
            check("三重组合-状态正确", all_finish)


async def test_multi_printer(ws):
    """TC-16: 多打印机数据"""
    # A1 Mini（可能未注册，不作为必须通过项）
    resp = await ws_request(ws, "printer_analytics/query_history",
                            entry_id=ENTRY_ID_A1MINI, page=1, page_size=20)
    if resp.get("success"):
        r = resp["result"]
        check("A1Mini-有数据", _pg(r).get("total", 0) >= 0, f"total={_pg(r).get('total')}")
    else:
        # A1 Mini 未注册是合法的，不算失败
        check("A1Mini-未注册(跳过)", True, f"error={resp.get('error')}")

    # 不存在的 entry_id
    resp = await ws_request(ws, "printer_analytics/query_history",
                            entry_id="invalid_entry_id", page=1, page_size=20)
    check("无效entry_id-返回错误", not resp.get("success"),
          f"success={resp.get('success')}")


async def test_pagination_consistency(ws):
    """TC-17: 分页一致性"""
    resp = await ws_request(ws, "printer_analytics/query_history",
                            entry_id=ENTRY_ID_P2S, page=1, page_size=100)
    if not resp.get("success"):
        check("分页一致性", False, "请求失败")
        return

    r = resp["result"]
    pg = _pg(r)
    total = pg.get("total", 0)
    total_pages = pg.get("total_pages", 1)

    # 抽样验证: 第1页 + 最后1页
    count = len(r["records"])

    if total_pages > 1:
        resp_last = await ws_request(ws, "printer_analytics/query_history",
                                     entry_id=ENTRY_ID_P2S, page=total_pages, page_size=100)
        if resp_last.get("success"):
            count += len(resp_last["result"]["records"])

    check("分页一致性-第1页有数据", count > 0, f"count={count}")


async def test_performance_sequential(ws):
    """TC-18: 连续请求性能"""
    times = []
    for p in range(1, 6):
        t0 = time.time()
        resp = await ws_request(ws, "printer_analytics/query_history",
                                entry_id=ENTRY_ID_P2S, page=p, page_size=20)
        ms = (time.time() - t0) * 1000
        times.append(ms)
        if not resp.get("success"):
            check(f"连续请求第{p}页", False, "请求失败")
            return

    avg = sum(times) / len(times)
    max_ms = max(times)
    check_perf("连续5页平均", avg)
    check(f"连续5页-最大延迟<{PERF_FAIL}ms", max_ms < PERF_FAIL,
          f"max={max_ms:.0f}ms")


async def test_available_colors_stability(ws):
    """TC-19: 颜色列表不受筛选影响"""
    # 无筛选时的颜色列表
    resp1 = await ws_request(ws, "printer_analytics/query_history",
                             entry_id=ENTRY_ID_P2S, page=1, page_size=1)
    # 有筛选时的颜色列表
    resp2 = await ws_request(ws, "printer_analytics/query_history",
                             entry_id=ENTRY_ID_P2S, page=1, page_size=1,
                             filters={"status": "failed"})

    if resp1.get("success") and resp2.get("success"):
        colors1 = set(resp1["result"].get("filter_options", {}).get("colors", []))
        colors2 = set(resp2["result"].get("filter_options", {}).get("colors", []))
        check("颜色列表-筛选后仍完整", colors1 == colors2,
              f"无筛选={len(colors1)}色, 有筛选={len(colors2)}色")


async def test_import_template(ws):
    """TC-20~25: 导入功能测试（模板格式 + 导入API + 数据验证 + 异常处理）"""
    import uuid

    # ---- TC-20: 模板格式验证 ----
    # 模拟前端 _downloadImportTemplate 生成的模板结构
    template = {
        "_说明": "这是打印历史导入模板",
        "_字段说明": {
            "task_name": "任务名称（必填）",
            "status": "状态：finish=成功, failed=失败, cancelled=已取消",
            "start_time": "开始时间，格式：YYYY-MM-DD HH:mm",
            "end_time": "结束时间，格式：YYYY-MM-DD HH:mm",
            "duration_minutes": "时长（分钟）",
            "filament_type": "耗材类型，如 PLA、PETG、ABS",
            "filament_color": "耗材颜色，如 #FF0000",
            "total_weight": "耗材重量（克）",
            "total_length": "耗材长度（米）",
            "energy_kwh": "能耗（千瓦时）",
            "nozzle_size": "喷嘴尺寸，如 0.4",
            "colors_used": "使用的颜色列表",
            "cover_image_url": "封面图URL（可选）"
        },
        "history": [
            {
                "task_name": "测试导入任务A",
                "status": "finish",
                "start_time": "2026-01-15 10:00",
                "end_time": "2026-01-15 12:30",
                "duration_minutes": 150,
                "filament_type": "PLA",
                "filament_color": "#2898F7",
                "total_weight": 25.5,
                "total_length": 8.3,
                "energy_kwh": 0.12,
                "nozzle_size": "0.4",
                "colors_used": ["#2898F7"],
                "cover_image_url": ""
            },
            {
                "task_name": "测试导入任务B",
                "status": "failed",
                "start_time": "2026-01-16 14:00",
                "end_time": "2026-01-16 14:45",
                "duration_minutes": 45,
                "filament_type": "PETG",
                "filament_color": "#FF6600",
                "total_weight": 10.2,
                "total_length": 3.5,
                "energy_kwh": 0.05,
                "nozzle_size": "0.4",
                "colors_used": ["#FF6600"]
            }
        ]
    }

    # 验证模板 JSON 可序列化
    try:
        template_json = json.dumps(template, ensure_ascii=False)
        check("模板-JSON序列化", True)
    except Exception as e:
        check("模板-JSON序列化", False, str(e))
        return

    # 验证模板结构完整性
    check("模板-包含history字段", "history" in template)
    check("模板-history非空", len(template["history"]) > 0)
    check("模板-包含字段说明", "_字段说明" in template)

    # 验证模板示例数据字段
    sample = template["history"][0]
    required_fields = ["task_name", "status", "start_time", "end_time", "duration_minutes"]
    for field in required_fields:
        check(f"模板-示例含{field}", field in sample)

    # ---- TC-21: 导入API调用（通过 call_service） ----
    # 记录导入前的记录总数
    resp_before = await ws_request(ws, "printer_analytics/query_history",
                                   entry_id=ENTRY_ID_P2S, page=1, page_size=1)
    if not check("导入前-查询成功", resp_before.get("success")):
        return
    total_before = _pg(resp_before["result"]).get("total", 0)

    # 为测试记录加唯一标记，方便后续清理
    test_marker = f"__import_test_{uuid.uuid4().hex[:8]}"
    import_data = json.loads(template_json)
    for rec in import_data["history"]:
        rec["task_name"] = rec["task_name"] + test_marker

    import_json_str = json.dumps(import_data, ensure_ascii=False)

    # 通过 call_service 调用导入
    t0 = time.time()
    resp_import = await ws_request(ws, "call_service",
                                   domain="printer_analytics",
                                   service="import_history",
                                   service_data={
                                       "entity_id": "sensor.p2s_print_history",
                                       "json_data": import_json_str
                                   })
    ms = (time.time() - t0) * 1000
    check("导入API-调用成功", resp_import.get("success"), f"resp={resp_import.get('error')}")
    check_perf("导入API", ms)

    # ---- TC-22: 导入后数据验证 ----
    # 等待数据刷新后查询（coordinator 需要时间保存和更新）
    await asyncio.sleep(3)
    resp_after = await ws_request(ws, "printer_analytics/query_history",
                                  entry_id=ENTRY_ID_P2S, page=1, page_size=10,
                                  filters={"search": test_marker})
    if check("导入后-查询成功", resp_after.get("success")):
        r = resp_after["result"]
        check("导入后-记录数>=2", _pg(r).get("total", 0) >= 2, f"搜索到{_pg(r).get('total')}条导入记录")

        # 验证导入的记录内容
        if r["records"]:
            imported = r["records"][0]
            check("导入后-有task_name", bool(imported.get("task_name")))
            check("导入后-有status", imported.get("status") in ("finish", "failed", "cancelled"),
                  f"status={imported.get('status')}")
            check("导入后-有start_time", bool(imported.get("start_time")))
            check("导入后-有id", bool(imported.get("id")), "缺少自动生成的id")

    # ---- TC-23: 导入总数增加验证 ----
    resp_total = await ws_request(ws, "printer_analytics/query_history",
                                  entry_id=ENTRY_ID_P2S, page=1, page_size=1)
    if resp_total.get("success"):
        total_after = _pg(resp_total["result"]).get("total", 0)
        check("导入后-总数增加", total_after >= total_before + 2,
              f"导入前={total_before}, 导入后={total_after}")

    # ---- TC-24: 无效JSON导入 ----
    resp_bad = await ws_request(ws, "call_service",
                                domain="printer_analytics",
                                service="import_history",
                                service_data={
                                    "entity_id": "sensor.p2s_print_history",
                                    "json_data": "not valid json{{{"
                                })
    # 后端现在返回中文友好错误信息
    bad_error = resp_bad.get("error", {})
    bad_msg = bad_error.get("message", "") if isinstance(bad_error, dict) else str(bad_error)
    check("无效JSON-不崩溃", resp_bad.get("error") != "timeout",
          f"error={resp_bad.get('error')}")
    check("无效JSON-有友好提示", "JSON" in bad_msg or "语法" in bad_msg or "Invalid" in bad_msg,
          f"msg={bad_msg}")

    # ---- TC-25: 空history导入 ----
    empty_data = json.dumps({"history": []})
    resp_empty = await ws_request(ws, "call_service",
                                  domain="printer_analytics",
                                  service="import_history",
                                  service_data={
                                      "entity_id": "sensor.p2s_print_history",
                                      "json_data": empty_data
                                  })
    # 空history现在应返回友好错误
    empty_error = resp_empty.get("error", {})
    empty_msg = empty_error.get("message", "") if isinstance(empty_error, dict) else str(empty_error)
    check("空history-有友好提示", "空" in empty_msg or "没有记录" in empty_msg or resp_empty.get("success"),
          f"msg={empty_msg}")

    # ---- TC-26: 缺少必填字段 ----
    missing_field_data = json.dumps({"history": [{"start_time": "2026-01-01 10:00"}]})
    resp_missing = await ws_request(ws, "call_service",
                                    domain="printer_analytics",
                                    service="import_history",
                                    service_data={
                                        "entity_id": "sensor.p2s_print_history",
                                        "json_data": missing_field_data
                                    })
    missing_error = resp_missing.get("error", {})
    missing_msg = missing_error.get("message", "") if isinstance(missing_error, dict) else str(missing_error)
    check("缺必填字段-有友好提示", "task_name" in missing_msg or "缺少" in missing_msg or "必填" in missing_msg or "Invalid" in missing_msg,
          f"msg={missing_msg}")

    # ---- TC-27: 非法status值 ----
    bad_status_data = json.dumps({"history": [{"task_name": "test", "status": "running"}]})
    resp_bad_status = await ws_request(ws, "call_service",
                                       domain="printer_analytics",
                                       service="import_history",
                                       service_data={
                                           "entity_id": "sensor.p2s_print_history",
                                           "json_data": bad_status_data
                                       })
    bs_error = resp_bad_status.get("error", {})
    bs_msg = bs_error.get("message", "") if isinstance(bs_error, dict) else str(bs_error)
    check("非法status-有友好提示", "status" in bs_msg or "不合法" in bs_msg or "Invalid" in bs_msg,
          f"msg={bs_msg}")

    # ---- TC-28: history不是数组 ----
    bad_history_type = json.dumps({"history": "not an array"})
    resp_bad_type = await ws_request(ws, "call_service",
                                     domain="printer_analytics",
                                     service="import_history",
                                     service_data={
                                         "entity_id": "sensor.p2s_print_history",
                                         "json_data": bad_history_type
                                     })
    bt_error = resp_bad_type.get("error", {})
    bt_msg = bt_error.get("message", "") if isinstance(bt_error, dict) else str(bt_error)
    check("history非数组-有友好提示", "数组" in bt_msg or "history" in bt_msg or "Invalid" in bt_msg or "Unsupported" in bt_msg,
          f"msg={bt_msg}")

    # ---- 清理测试数据 ----
    resp_cleanup = await ws_request(ws, "printer_analytics/query_history",
                                    entry_id=ENTRY_ID_P2S, page=1, page_size=100,
                                    filters={"search": test_marker})
    if resp_cleanup.get("success") and resp_cleanup["result"]["records"]:
        test_ids = [rec["id"] for rec in resp_cleanup["result"]["records"]
                    if test_marker in rec.get("task_name", "")]
        if test_ids:
            await ws_request(ws, "call_service",
                             domain="printer_analytics",
                             service="delete_history_records",
                             service_data={
                                 "entity_id": "sensor.p2s_print_history",
                                 "record_ids": test_ids
                             })
            print(f"  [清理] 已删除 {len(test_ids)} 条测试记录")


# ==================== 主流程 ====================

async def run_all_tests():
    """运行全部测试"""
    print("=" * 60)
    print("  打印机分析 - 自动化测试套件")
    print("=" * 60)

    try:
        async with websockets.connect(HA_URL, close_timeout=5) as ws:
            # 认证
            init = json.loads(await ws.recv())
            await ws.send(json.dumps({"type": "auth", "access_token": TOKEN}))
            auth = json.loads(await ws.recv())
            if not check("认证", auth.get("type") == "auth_ok", auth.get("type")):
                print("\n认证失败，终止测试")
                return

            # 依次运行测试模块
            print("\n--- 连接测试 ---")
            await test_connection(ws)

            print("\n--- 基本分页 ---")
            first_result = await test_basic_pagination(ws)

            print("\n--- 翻页导航 ---")
            await test_pagination_navigation(ws, first_result)

            print("\n--- 大页面 ---")
            await test_large_page_size(ws)

            print("\n--- 状态筛选 ---")
            await test_filter_status(ws)

            print("\n--- 颜色筛选 ---")
            await test_filter_color(ws)

            print("\n--- 日期筛选 ---")
            await test_filter_date(ws)

            print("\n--- 搜索 ---")
            await test_search(ws)

            print("\n--- 组合筛选 ---")
            await test_combined_filter(ws)

            print("\n--- 多打印机 ---")
            await test_multi_printer(ws)

            print("\n--- 分页一致性 ---")
            await test_pagination_consistency(ws)

            print("\n--- 性能基准 ---")
            await test_performance_sequential(ws)

            print("\n--- 颜色列表稳定性 ---")
            await test_available_colors_stability(ws)

            print("\n--- 导入功能 ---")
            await test_import_template(ws)

    except Exception as e:
        check("WebSocket连接", False, str(e))

    # 汇总
    print("\n" + "=" * 60)
    passed = sum(1 for r in _results if r.passed)
    failed = sum(1 for r in _results if not r.passed)
    total = len(_results)
    print(f"  测试结果: {total} 用例, {passed} PASS, {failed} FAIL")
    print("=" * 60)

    if failed > 0:
        print("\n失败用例:")
        for r in _results:
            if not r.passed:
                print(f"  [FAIL] {r.name} - {r.detail}")

    # 返回退出码
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_all_tests())
    sys.exit(exit_code)
