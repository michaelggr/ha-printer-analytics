﻿import requests
import json

with open('.ha_connection_info.json', 'r', encoding='utf-8') as f:
    conn_info = json.load(f)

HA_URL = conn_info['ha_api']['url'].rstrip('/')
TOKEN = conn_info['ha_api']['token']

headers = {
    'Authorization': f'Bearer {TOKEN}',
    'Content-Type': 'application/json'
}

print("正在获取所有实体状态...\n")
response = requests.get(f'{HA_URL}/api/states', headers=headers)
all_states = response.json()

print("搜索所有相关传感器...\n")
for state in all_states:
    entity_id = state['entity_id']
    if 'doujiangji' in entity_id or 'oven' in entity_id or 'heater' in entity_id or 'computer' in entity_id or 'nas' in entity_id or 'xiaoheinu' in entity_id or 'daheinu' in entity_id or 'washer' in entity_id or 'daily' in entity_id:
        print(f"{entity_id:<60} state={state['state']}")
