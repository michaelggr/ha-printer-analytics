import requests
import json

with open('.ha_connection_info.json', 'r', encoding='utf-8') as f:
    conn_info = json.load(f)

HA_URL = conn_info['ha_api']['url'].rstrip('/')
TOKEN = conn_info['ha_api']['token']

headers = {'Authorization': f'Bearer {TOKEN}'}

r = requests.get(f'{HA_URL}/api/states', headers=headers, timeout=10)
entities = r.json()

# 查找 a1mini 相关的 printer_analytics 传感器
a1mini_entities = [e for e in entities if 'a1mini' in e['entity_id'].lower() and 'printer' not in e['entity_id'].lower()]

print("a1mini 相关传感器实体:")
for e in sorted(a1mini_entities, key=lambda x: x['entity_id']):
    state = e.get('state', 'N/A')
    attrs = e.get('attributes', {})
    friendly_name = attrs.get('friendly_name', '')
    print(f"  {e['entity_id']}: {state} ({friendly_name})")

# 特别查找打印历史
print("\n--- 查找打印历史实体 ---")
history_entities = [e for e in entities if 'history' in e['entity_id'].lower() or 'li_shi' in e['entity_id'].lower()]
for e in sorted(history_entities, key=lambda x: x['entity_id']):
    state = e.get('state', 'N/A')
    attrs = e.get('attributes', {})
    friendly_name = attrs.get('friendly_name', '')
    print(f"  {e['entity_id']}: {state} ({friendly_name})")
