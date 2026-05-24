"""等待HA重启完成，然后测试WebSocket"""
import urllib.request
import json
import time
import asyncio
import websockets

TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiI3Y2EyNjc2MzdmZGU0YzliOWQ3Y2Y3ODM3N2YwMzA5ZSIsImlhdCI6MTc3ODk2OTYzNCwiZXhwIjoyMDk0MzI5NjM0fQ.iFan1gdP67hAY5jn0ilFABv98DbA79TFTHg76PyNhJY"
HA_URL = "ws://192.168.0.130:8123/api/websocket"
ENTRY_ID = "01KRTS6CW4PZ1GFDK42CRTTMGV"

# 1. 等待HA启动
print("等待HA重启完成...")
for i in range(18):
    time.sleep(10)
    try:
        req = urllib.request.Request(
            "http://192.168.0.130:8123/api/",
            headers={"Authorization": f"Bearer {TOKEN}"}
        )
        urllib.request.urlopen(req, timeout=5)
        print(f"  HA已启动! (等待了 {(i+1)*10}s)")
        break
    except Exception:
        print(f"  等待中... ({(i+1)*10}s)")
else:
    print("HA启动超时!")
    exit(1)

# 额外等待集成加载
time.sleep(15)

# 2. 检查传感器状态
print("\n检查传感器状态...")
try:
    req = urllib.request.Request(
        "http://192.168.0.130:8123/api/states/sensor.p2s_22e8bj5a2401765_total_prints",
        headers={"Authorization": f"Bearer {TOKEN}"}
    )
    data = json.loads(urllib.request.urlopen(req, timeout=10).read())
    print(f"  total_prints = {data['state']}")
except Exception as e:
    print(f"  错误: {e}")

# 3. 测试WebSocket分页
async def test_ws():
    print("\n测试WebSocket分页...")
    try:
        async with websockets.connect(HA_URL, close_timeout=5) as ws:
            # 认证
            init = json.loads(await ws.recv())
            await ws.send(json.dumps({"type": "auth", "access_token": TOKEN}))
            auth = json.loads(await ws.recv())
            print(f"  认证: {auth.get('type')}")

            # 测试1：基本分页
            print("\n  测试1: 基本分页 (page=1, page_size=20)...")
            t0 = time.time()
            await ws.send(json.dumps({
                "id": 1, "type": "printer_analytics/history",
                "entry_id": ENTRY_ID, "page": 1, "page_size": 20, "sort": "desc",
            }))
            resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
            elapsed = (time.time() - t0) * 1000
            if resp.get("success"):
                result = resp.get("result", {})
                print(f"    成功! total={result.get('total')}, page={result.get('page')}, "
                      f"records={len(result.get('records', []))}, 耗时={elapsed:.0f}ms")
            else:
                print(f"    失败: {resp}")

            # 测试2：翻页
            print("\n  测试2: 翻页 (page=50, page_size=20)...")
            t0 = time.time()
            await ws.send(json.dumps({
                "id": 2, "type": "printer_analytics/history",
                "entry_id": ENTRY_ID, "page": 50, "page_size": 20, "sort": "desc",
            }))
            resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
            elapsed = (time.time() - t0) * 1000
            if resp.get("success"):
                result = resp.get("result", {})
                print(f"    成功! total={result.get('total')}, page={result.get('page')}, "
                      f"records={len(result.get('records', []))}, 耗时={elapsed:.0f}ms")
            else:
                print(f"    失败: {resp}")

            # 测试3：状态筛选
            print("\n  测试3: 状态筛选 (filter_status=failed)...")
            t0 = time.time()
            await ws.send(json.dumps({
                "id": 3, "type": "printer_analytics/history",
                "entry_id": ENTRY_ID, "page": 1, "page_size": 20, "sort": "desc",
                "filter_status": "failed",
            }))
            resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
            elapsed = (time.time() - t0) * 1000
            if resp.get("success"):
                result = resp.get("result", {})
                print(f"    成功! total={result.get('total')}, page={result.get('page')}, "
                      f"records={len(result.get('records', []))}, 耗时={elapsed:.0f}ms")
            else:
                print(f"    失败: {resp}")

            # 测试4：日期范围筛选
            print("\n  测试4: 日期范围筛选 (2025-01-01 ~ 2025-06-30)...")
            t0 = time.time()
            await ws.send(json.dumps({
                "id": 4, "type": "printer_analytics/history",
                "entry_id": ENTRY_ID, "page": 1, "page_size": 20, "sort": "desc",
                "date_from": "2025-01-01", "date_to": "2025-06-30",
            }))
            resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
            elapsed = (time.time() - t0) * 1000
            if resp.get("success"):
                result = resp.get("result", {})
                print(f"    成功! total={result.get('total')}, page={result.get('page')}, "
                      f"records={len(result.get('records', []))}, 耗时={elapsed:.0f}ms")
            else:
                print(f"    失败: {resp}")

            # 测试5：搜索
            print("\n  测试5: 搜索 (search=Benchy)...")
            t0 = time.time()
            await ws.send(json.dumps({
                "id": 5, "type": "printer_analytics/history",
                "entry_id": ENTRY_ID, "page": 1, "page_size": 20, "sort": "desc",
                "search": "Benchy",
            }))
            resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
            elapsed = (time.time() - t0) * 1000
            if resp.get("success"):
                result = resp.get("result", {})
                print(f"    成功! total={result.get('total')}, page={result.get('page')}, "
                      f"records={len(result.get('records', []))}, 耗时={elapsed:.0f}ms")
            else:
                print(f"    失败: {resp}")

            # 测试6：大page_size
            print("\n  测试6: 大page_size (page_size=100)...")
            t0 = time.time()
            await ws.send(json.dumps({
                "id": 6, "type": "printer_analytics/history",
                "entry_id": ENTRY_ID, "page": 1, "page_size": 100, "sort": "desc",
            }))
            resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
            elapsed = (time.time() - t0) * 1000
            if resp.get("success"):
                result = resp.get("result", {})
                print(f"    成功! total={result.get('total')}, page={result.get('page')}, "
                      f"records={len(result.get('records', []))}, 耗时={elapsed:.0f}ms")
            else:
                print(f"    失败: {resp}")

            # 测试7：组合筛选
            print("\n  测试7: 组合筛选 (status=finish + date范围)...")
            t0 = time.time()
            await ws.send(json.dumps({
                "id": 7, "type": "printer_analytics/history",
                "entry_id": ENTRY_ID, "page": 1, "page_size": 20, "sort": "desc",
                "filter_status": "finish",
                "date_from": "2025-01-01", "date_to": "2025-12-31",
            }))
            resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
            elapsed = (time.time() - t0) * 1000
            if resp.get("success"):
                result = resp.get("result", {})
                print(f"    成功! total={result.get('total')}, page={result.get('page')}, "
                      f"records={len(result.get('records', []))}, 耗时={elapsed:.0f}ms")
                # 检查available_colors
                colors = result.get("available_colors", [])
                print(f"    available_colors: {len(colors)} 种")
                # 检查stats
                stats = result.get("stats", {})
                if stats:
                    print(f"    stats: success_rate={stats.get('success_rate')}%, "
                          f"total_weight={stats.get('total_weight')}g, "
                          f"total_duration={stats.get('total_duration_hours')}h")
            else:
                print(f"    失败: {resp}")

    except asyncio.TimeoutError:
        print("  超时! 30秒无响应")
    except Exception as e:
        print(f"  错误: {e}")

asyncio.run(test_ws())
