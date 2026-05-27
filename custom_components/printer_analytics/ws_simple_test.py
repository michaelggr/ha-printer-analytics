"""检查 HA 是否正常 + 测试 WebSocket"""
import urllib.request, json, asyncio, time, websockets

TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiI3Y2EyNjc2MzdmZGU0YzliOWQ3Y2Y3ODM3N2YwMzA5ZSIsImlhdCI6MTc3ODk2OTYzNCwiZXhwIjoyMDk0MzI5NjM0fQ.iFan1gdP67hAY5jn0ilFABv98DbA79TFTHg76PyNhJY"

# 1. 检查 HA API
print("=== 检查 HA API ===")
try:
    req = urllib.request.Request(
        "http://192.168.0.130:8123/api/states/sensor.p2s_total_prints",
        headers={"Authorization": f"Bearer {TOKEN}"}
    )
    data = json.loads(urllib.request.urlopen(req, timeout=10).read())
    print(f"  p2s_total_prints: {data['state']}")
except Exception as e:
    print(f"  API 错误: {e}")

# 2. 测试 WebSocket 基本命令
async def test_ws():
    HA_URL = "ws://192.168.0.130:8123/api/websocket"
    ENTRY_ID = "01KRTS6CW4PZ1GFDK42CRTTMGV"

    async with websockets.connect(HA_URL, close_timeout=5) as ws:
        init = json.loads(await ws.recv())
        await ws.send(json.dumps({"type": "auth", "access_token": TOKEN}))
        auth = json.loads(await ws.recv())
        print(f"\n=== WebSocket 认证: {auth.get('type')} ===")

        # 测试一个简单的 HA 命令
        print("\n测试基本 WS 命令 (get_config)...")
        t0 = time.time()
        await ws.send(json.dumps({"id": 1, "type": "get_config"}))
        resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
        t1 = time.time()
        print(f"  success={resp.get('success')}, 耗时={(t1-t0)*1000:.0f}ms")

        # 测试 printer_analytics/history
        print("\n测试 printer_analytics/history...")
        t0 = time.time()
        await ws.send(json.dumps({
            "id": 2, "type": "printer_analytics/history",
            "entry_id": ENTRY_ID, "page": 1, "page_size": 5, "sort": "desc",
        }))
        try:
            resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
            t1 = time.time()
            print(f"  success={resp.get('success')}, 耗时={(t1-t0)*1000:.0f}ms")
            if resp.get("success"):
                r = resp["result"]
                print(f"  total: {r.get('total')}, records: {len(r.get('records', []))}")
            else:
                print(f"  error: {resp.get('error')}")
        except asyncio.TimeoutError:
            print(f"  超时! 30秒无响应")

asyncio.run(test_ws())
