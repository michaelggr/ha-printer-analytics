﻿﻿﻿﻿﻿import requests, json

with open('.ha_connection_info.json', 'r', encoding='utf-8') as f:
    conn_info = json.load(f)

HA_URL = conn_info['ha_api']['url'].rstrip('/')
TOKEN = conn_info['ha_api']['token']
headers = {'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json'}

# 用HA API获取系统日志
r = requests.get(f'{HA_URL}/api/system_log', headers=headers)
if r.status_code == 200:
    logs = r.json()
    # 过滤出最近的错误
    for entry in logs[:30]:
        level = entry.get('level', '')
        message = entry.get('message', '')[:200]
        source = entry.get('source', [''])[0] if entry.get('source') else ''
        if 'error' in level.lower() or 'lovelace' in message.lower() or 'ui-lovelace' in message.lower():
            print(f"[{level}] {source}: {message}")
    print(f"\n共 {len(logs)} 条日志")
else:
    print(f"无法获取系统日志: {r.status_code}")
    # 尝试获取所有日志
    r2 = requests.get(f'{HA_URL}/api/system_log/fetch', headers=headers)
    print(f"Fetch API: {r2.status_code}, {r2.text[:300] if r2.status_code != 404 else 'not found'}")
