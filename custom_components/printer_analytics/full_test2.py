"""等待HA重启后测试WebSocket，检查调试文件"""
import urllib.request
import json
import time
import asyncio
import os

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

time.sleep(30)

# 2. 检查传感器
try:
    req = urllib.request.Request(
        "http://192.168.0.130:8123/api/states/sensor.p2s_total_prints",
        headers={"Authorization": f"Bearer {TOKEN}"}
    )
    data = json.loads(urllib.request.urlopen(req, timeout=10).read())
    print(f"传感器: total_prints = {data['state']}")
except Exception as e:
    print(f"传感器错误: {e}")

# 3. 测试WebSocket - 每个命令用新连接
import websockets

async def test_single_command(cmd_type, payload, timeout=15):
    """用新连接测试单个命令"""
    async with websockets.connect(HA_URL, close_timeout=5, max_size=10*1024*1024) as ws:
        init = json.loads(await ws.recv())
        await ws.send(json.dumps({"type": "auth", "access_token": TOKEN}))
        auth = json.loads(await ws.recv())

        t0 = time.time()
        await ws.send(json.dumps(payload))
        try:
            resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout))
            elapsed = (time.time() - t0) * 1000
            return resp, elapsed
        except asyncio.TimeoutError:
            return None, (time.time() - t0) * 1000

# 测试1: history_detail（已知能工作的命令）
print("\n测试1: history_detail...")
resp, elapsed = asyncio.run(test_single_command("printer_analytics/history_detail", {
    "id": 1, "type": "printer_analytics/history_detail",
    "entry_id": ENTRY_ID, "record_id": "nonexistent",
}))
if resp:
    print(f"  OK ({elapsed:.0f}ms): {json.dumps(resp, ensure_ascii=False)[:200]}")
else:
    print(f"  超时 ({elapsed:.0f}ms)")

# 测试2: history
print("\n测试2: history...")
resp, elapsed = asyncio.run(test_single_command("printer_analytics/history", {
    "id": 1, "type": "printer_analytics/history",
    "entry_id": ENTRY_ID, "page": 1, "page_size": 5, "sort": "desc",
}))
if resp:
    print(f"  OK ({elapsed:.0f}ms): {json.dumps(resp, ensure_ascii=False)[:300]}")
else:
    print(f"  超时 ({elapsed:.0f}ms)")

# 4. 检查调试文件
print("\n检查调试文件...")
debug_path = r"\\192.168.0.130\config\.printer_analytics\ws_debug.txt"
if os.path.exists(debug_path):
    with open(debug_path, "r", encoding="utf-8") as f:
        content = f.read()
    print(f"  内容:\n{content}")
else:
    print("  调试文件不存在! handler可能没被调用")
