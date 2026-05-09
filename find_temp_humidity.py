﻿﻿﻿﻿﻿import requests
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

print("搜索所有温湿度传感器...\n")
for state in all_states:
    entity_id = state['entity_id']
    attributes = state.get('attributes', {})
    friendly_name = attributes.get('friendly_name', '')
    
    # 查找温湿度相关传感器
    if 'temperature' in entity_id or 'humidity' in entity_id or '温湿度' in friendly_name or '温度' in friendly_name or '湿度' in friendly_name:
        print(f"{entity_id:<60} name={friendly_name} state={state['state']}")
