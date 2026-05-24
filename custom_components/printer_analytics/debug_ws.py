"""获取HA日志并搜索printer_analytics相关信息"""
import urllib.request
import json

TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiI3Y2EyNjc2MzdmZGU0YzliOWQ3Y2Y3ODM3N2YwMzA5ZSIsImlhdCI6MTc3ODk2OTYzNCwiZXhwIjoyMDk0MzI5NjM0fQ.iFan1gdP67hAY5jn0ilFABv98DbA79TFTHg76PyNhJY"

# 方法1: 通过API获取日志
try:
    req = urllib.request.Request(
        "http://192.168.0.130:8123/api/error_log",
        headers={"Authorization": f"Bearer {TOKEN}"}
    )
    log = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", errors="replace")
    lines = log.strip().split("\n")
    print(f"API日志共 {len(lines)} 行")
    # 搜索相关行
    for l in lines[-50:]:
        if any(kw in l.lower() for kw in ["printer_analytics", "websocket", "ws_handle", "traceback", "error"]):
            print(l[:300])
except Exception as e:
    print(f"API日志获取失败: {e}")

# 方法2: 检查集成是否正常加载
print("\n检查集成配置...")
try:
    req = urllib.request.Request(
        "http://192.168.0.130:8123/api/config/config_entries/entry/01KRTS6CW4PZ1GFDK42CRTTMGV",
        headers={"Authorization": f"Bearer {TOKEN}"}
    )
    data = json.loads(urllib.request.urlopen(req, timeout=10).read())
    print(f"  集成状态: {data.get('state')}")
    print(f"  集成标题: {data.get('title')}")
    print(f"  域: {data.get('domain')}")
except Exception as e:
    print(f"  获取失败: {e}")

# 方法3: 检查WebSocket命令是否注册 - 尝试发送一个不存在的命令看报错
print("\n测试WebSocket命令注册...")
import asyncio
import websockets

async def test():
    async with websockets.connect("ws://192.168.0.130:8123/api/websocket", close_timeout=5) as ws:
        init = json.loads(await ws.recv())
        await ws.send(json.dumps({"type": "auth", "access_token": TOKEN}))
        auth = json.loads(await ws.recv())
        print(f"  认证: {auth.get('type')}")

        # 测试一个已知存在的命令
        await ws.send(json.dumps({"id": 1, "type": "get_states"}))
        resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
        print(f"  get_states: success={resp.get('success')}")

        # 测试我们的命令 - 用极简参数
        print("  发送 printer_analytics/history...")
        await ws.send(json.dumps({
            "id": 2, "type": "printer_analytics/history",
            "entry_id": "01KRTS6CW4PZ1GFDK42CRTTMGV",
            "page": 1, "page_size": 5, "sort": "desc",
        }))
        try:
            resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
            print(f"  结果: {json.dumps(resp, ensure_ascii=False)[:500]}")
        except asyncio.TimeoutError:
            print("  超时! 10秒无响应")

asyncio.run(test())
