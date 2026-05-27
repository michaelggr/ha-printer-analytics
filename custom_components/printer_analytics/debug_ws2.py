"""调试WebSocket命令注册 - 对比已知命令和自定义命令"""
import asyncio
import json
import websockets

TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiI3Y2EyNjc2MzdmZGU0YzliOWQ3Y2Y3ODM3N2YwMzA5ZSIsImlhdCI6MTc3ODk2OTYzNCwiZXhwIjoyMDk0MzI5NjM0fQ.iFan1gdP67hAY5jn0ilFABv98DbA79TFTHg76PyNhJY"
HA_URL = "ws://192.168.0.130:8123/api/websocket"
ENTRY_ID = "01KRTS6CW4PZ1GFDK42CRTTMGV"

async def test():
    async with websockets.connect(HA_URL, close_timeout=5, max_size=10*1024*1024) as ws:
        init = json.loads(await ws.recv())
        await ws.send(json.dumps({"type": "auth", "access_token": TOKEN}))
        auth = json.loads(await ws.recv())
        print(f"认证: {auth.get('type')}")

        # 测试1: 发送一个不存在的命令
        print("\n测试1: 不存在的命令...")
        await ws.send(json.dumps({"id": 1, "type": "nonexistent_command"}))
        resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
        print(f"  结果: {json.dumps(resp, ensure_ascii=False)[:300]}")

        # 测试2: 发送我们的命令（缺少必填参数）
        print("\n测试2: printer_analytics/history (缺少entry_id)...")
        await ws.send(json.dumps({"id": 2, "type": "printer_analytics/history"}))
        try:
            resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            print(f"  结果: {json.dumps(resp, ensure_ascii=False)[:300]}")
        except asyncio.TimeoutError:
            print("  超时!")

        # 测试3: 完整参数
        print("\n测试3: printer_analytics/history (完整参数)...")
        await ws.send(json.dumps({
            "id": 3, "type": "printer_analytics/history",
            "entry_id": ENTRY_ID, "page": 1, "page_size": 5, "sort": "desc",
        }))
        try:
            resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
            print(f"  结果: {json.dumps(resp, ensure_ascii=False)[:500]}")
        except asyncio.TimeoutError:
            print("  超时!")

        # 测试4: history_detail
        print("\n测试4: printer_analytics/history_detail...")
        await ws.send(json.dumps({
            "id": 4, "type": "printer_analytics/history_detail",
            "entry_id": ENTRY_ID, "record_id": "test",
        }))
        try:
            resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
            print(f"  结果: {json.dumps(resp, ensure_ascii=False)[:500]}")
        except asyncio.TimeoutError:
            print("  超时!")

asyncio.run(test())
