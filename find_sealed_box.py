﻿﻿﻿﻿﻿import requests
import json

with open('.ha_connection_info.json', 'r', encoding='utf-8') as f:
    conn_info = json.load(f)

HA_URL = conn_info['ha_api']['url'].rstrip('/')
TOKEN = conn_info['ha_api']['token']
headers = {'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json'}

response = requests.get(f'{HA_URL}/api/states', headers=headers)
all_states = response.json()

print("=== 密封箱相关传感器 ===")
for state in all_states:
    eid = state['entity_id']
    name = state.get('attributes', {}).get('friendly_name', '')
    sv = state['state']
    if '密封箱' in name or '密封箱' in eid:
        print(f"{eid:<70} name={name:<40} state={sv}")

print()
print("=== 小黑奴相关传感器 ===")
for state in all_states:
    eid = state['entity_id']
    name = state.get('attributes', {}).get('friendly_name', '')
    sv = state['state']
    if '小黑奴' in name or 'qjiang' in eid:
        print(f"{eid:<70} name={name:<40} state={sv}")

print()
print("=== 耗材相关传感器 ===")
for state in all_states:
    eid = state['entity_id']
    name = state.get('attributes', {}).get('friendly_name', '')
    sv = state['state']
    if '耗材' in name or '耗材' in eid:
        print(f"{eid:<70} name={name:<40} state={sv}")
