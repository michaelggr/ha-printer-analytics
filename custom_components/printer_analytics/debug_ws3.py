"""检查HA版本和WebSocket调试"""
import asyncio
import json
import time
import websockets

TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiI3Y2EyNjc2MzdmZGU0YzliOWQ3Y2Y3ODM3N2YwMzA5ZSIsImlhdCI6MTc3ODk2OTYzNCwiZXhwIjoyMDk0MzI5NjM0fQ.iFan1gdP67hAY5jn0ilFABv98DbA79TFTHg76PyNhJY"
HA_URL = "ws://192.168.0.130:8123/api/websocket"
ENTRY_ID = "01KRTS6CW4PZ1GFDK42CRTTMGV"

async def test():
    async with websockets.connect(HA_URL, close_timeout=5, max_size=10*1024*1024) as ws:
        # 认证
        init = json.loads(await ws.recv())
        print(f"HA版本: {init.get('ha_version')}")
        await ws.send(json.dumps({"type": "auth", "access_token": TOKEN}))
        auth = json.loads(await ws.recv())
        print(f"认证: {auth.get('type')}")

        # 测试1: 获取config（已知HA内置命令）
        print("\n测试1: get_config...")
        await ws.send(json.dumps({"id": 1, "type": "get_config"}))
        resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
        print(f"  success={resp.get('success')}, 版本={resp.get('result', {}).get('version')}")

        # 测试2: 我们的命令 - 极简参数
        print("\n测试2: printer_analytics/history...")
        t0 = time.time()
        await ws.send(json.dumps({
            "id": 2, "type": "printer_analytics/history",
            "entry_id": ENTRY_ID, "page": 1, "page_size": 5, "sort": "desc",
        }))

        # 等待响应，同时检查连接状态
        try:
            resp = await asyncio.wait_for(ws.recv(), timeout=15)
            elapsed = (time.time() - t0) * 1000
            print(f"  收到响应 ({elapsed:.0f}ms): {resp[:500]}")
        except asyncio.TimeoutError:
            print(f"  超时! 15秒无响应")
            # 检查连接是否还活着
            try:
                await ws.send(json.dumps({"id": 99, "type": "ping"}))
                pong = await asyncio.wait_for(ws.recv(), timeout=3)
                print(f"  连接仍活跃: {pong}")
            except Exception as e:
                print(f"  连接已断开: {e}")

        # 测试3: history_detail
        print("\n测试3: printer_analytics/history_detail...")
        await ws.send(json.dumps({
            "id": 3, "type": "printer_analytics/history_detail",
            "entry_id": ENTRY_ID, "record_id": "test",
        }))
        try:
            resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
            print(f"  结果: {json.dumps(resp, ensure_ascii=False)[:300]}")
        except asyncio.TimeoutError:
            print("  超时!")

asyncio.run(test())
