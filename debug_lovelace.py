﻿﻿﻿﻿﻿import requests, json, time

with open('.ha_connection_info.json', 'r', encoding='utf-8') as f:
    conn_info = json.load(f)

HA_URL = conn_info['ha_api']['url'].rstrip('/')
TOKEN = conn_info['ha_api']['token']
headers = {'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json'}

# 直接用HA的websocket API获取前端渲染错误
# 先尝试获取lovelace配置
ws_url = HA_URL.replace('http', 'ws') + '/api/websocket'
print(f"WebSocket URL: {ws_url}")

# 用REST API模拟前端请求，获取dashboard配置
# 尝试不同的API端点
endpoints = [
    '/api/lovelace/config',
    '/api/lovelace/config/lovelace', 
    '/api/lovelace/dashboards/lovelace/views/home',
    '/api/lovelace/dashboards/lovelace',
]

for ep in endpoints:
    r = requests.get(f'{HA_URL}{ep}', headers=headers)
    print(f"{ep}: {r.status_code}")
    if r.status_code == 200:
        try:
            data = r.json()
            print(f"  数据: {json.dumps(data, indent=2, ensure_ascii=False)[:500]}")
        except:
            print(f"  响应: {r.text[:300]}")

# 检查是否有websocket API可用
r = requests.get(f'{HA_URL}/api/websocket', headers=headers)
print(f"\nWebSocket endpoint: {r.status_code}")

# 尝试直接验证YAML配置是否能被HA正确解析
# 通过创建一个临时的API调用
print("\n尝试通过HA验证配置...")
r = requests.post(
    f'{HA_URL}/api/services/homeassistant/reload_config_entry',
    headers=headers,
    json={"entry_id": "lovelace"}
)
print(f"Reload config entry: {r.status_code}, {r.text[:200] if r.text else 'no response'}")
