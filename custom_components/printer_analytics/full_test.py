"""等待HA重启，检查日志，测试WebSocket"""
import urllib.request
import json
import time
import asyncio

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
        print(f"  HA已启动! ({(i+1)*10}s)")
        break
    except Exception:
        print(f"  等待中... ({(i+1)*10}s)")
else:
    print("HA启动超时!")
    exit(1)

# 额外等待集成加载
time.sleep(30)

# 2. 检查传感器
print("\n检查传感器...")
try:
    req = urllib.request.Request(
        "http://192.168.0.130:8123/api/states/sensor.p2s_total_prints",
        headers={"Authorization": f"Bearer {TOKEN}"}
    )
    data = json.loads(urllib.request.urlopen(req, timeout=10).read())
    print(f"  total_prints = {data['state']}")
except Exception as e:
    print(f"  错误: {e}")

# 3. 检查HA日志中的WS注册信息
print("\n检查HA日志...")
try:
    req = urllib.request.Request(
        "http://192.168.0.130:8123/api/error_log",
        headers={"Authorization": f"Bearer {TOKEN}"}
    )
    log = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", errors="replace")
    lines = log.strip().split("\n")
    for l in lines[-100:]:
        if any(kw in l for kw in ["WS", "websocket", "printer_analytics", "Printer Analytics"]):
            print(f"  {l[:300]}")
except Exception as e:
    print(f"  日志获取失败: {e}")

# 4. 测试WebSocket
print("\n测试WebSocket...")
import websockets

async def test():
    async with websockets.connect(HA_URL, close_timeout=5, max_size=10*1024*1024) as ws:
        init = json.loads(await ws.recv())
        await ws.send(json.dumps({"type": "auth", "access_token": TOKEN}))
        auth = json.loads(await ws.recv())
        print(f"  认证: {auth.get('type')}")

        # 先测试一个HA内置命令
        await ws.send(json.dumps({"id": 1, "type": "ping"}))
        resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
        print(f"  ping: {resp}")

        # 测试我们的命令
        print("  发送 printer_analytics/history...")
        t0 = time.time()
        await ws.send(json.dumps({
            "id": 2, "type": "printer_analytics/history",
            "entry_id": ENTRY_ID, "page": 1, "page_size": 5, "sort": "desc",
        }))
        try:
            resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
            elapsed = (time.time() - t0) * 1000
            print(f"  结果 ({elapsed:.0f}ms): {json.dumps(resp, ensure_ascii=False)[:500]}")
        except asyncio.TimeoutError:
            print("  超时! 30秒无响应")

asyncio.run(test())
