"""测试 WebSocket 命令是否注册 - 发送无效 sort 值看是否返回验证错误"""
import asyncio, json, websockets

HA_URL = "ws://192.168.0.130:8123/api/websocket"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiI3Y2EyNjc2MzdmZGU0YzliOWQ3Y2Y3ODM3N2YwMzA5ZSIsImlhdCI6MTc3ODk2OTYzNCwiZXhwIjoyMDk0MzI5NjM0fQ.iFan1gdP67hAY5jn0ilFABv98DbA79TFTHg76PyNhJY"
ENTRY_ID = "01KRTS6CW4PZ1GFDK42CRTTMGV"

async def main():
    async with websockets.connect(HA_URL, close_timeout=5) as ws:
        init = json.loads(await ws.recv())
        await ws.send(json.dumps({"type": "auth", "access_token": TOKEN}))
        auth = json.loads(await ws.recv())
        print(f"认证: {auth.get('type')}")

        # 测试1: 发送无效 sort 值
        print("\n测试1: sort=invalid (应返回验证错误)")
        await ws.send(json.dumps({
            "id": 1, "type": "printer_analytics/history",
            "entry_id": ENTRY_ID, "page": 1, "page_size": 5, "sort": "invalid",
        }))
        resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
        print(f"  success={resp.get('success')}, error={resp.get('error')}")

        # 测试2: 发送 sort=desc (应通过验证)
        print("\n测试2: sort=desc (应通过验证)")
        await ws.send(json.dumps({
            "id": 2, "type": "printer_analytics/history",
            "entry_id": ENTRY_ID, "page": 1, "page_size": 5, "sort": "desc",
        }))
        try:
            resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
            print(f"  success={resp.get('success')}, error={resp.get('error')}")
            if resp.get("success"):
                r = resp["result"]
                print(f"  total: {r.get('total')}, records: {len(r.get('records', []))}")
        except asyncio.TimeoutError:
            print("  超时! 10秒无响应")

        # 测试3: 不存在的命令
        print("\n测试3: 不存在的命令 (应返回 unknown_command)")
        await ws.send(json.dumps({
            "id": 3, "type": "nonexistent_command",
        }))
        resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
        print(f"  success={resp.get('success')}, error={resp.get('error')}")

asyncio.run(main())
