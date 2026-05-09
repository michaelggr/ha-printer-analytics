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

response = requests.get(f'{HA_URL}/api/states', headers=headers)
all_states = response.json()

print("=" * 80)
print("正在查找所有的 Utility Meter...")
print("=" * 80)

utility_meters = []
for state in all_states:
    entity_id = state['entity_id']
    if (entity_id.startswith('sensor.') and 
        ('daily' in entity_id or 
         'weekly' in entity_id or 
         'monthly' in entity_id or 
         'yearly' in entity_id) and
        'energy' in entity_id):
        utility_meters.append(entity_id)
        print(f"✓ 找到: {entity_id}")

print(f"\n共找到 {len(utility_meters)} 个 Utility Meter!")

print("\n" + "=" * 80)
print("正在重置所有 Utility Meter...")
print("=" * 80)

success_count = 0
for meter in utility_meters:
    print(f"\n正在重置: {meter}")
    
    response = requests.post(
        f'{HA_URL}/api/services/utility_meter/reset',
        headers=headers,
        json={
            'entity_id': meter
        }
    )
    
    if response.status_code == 200:
        print(f"✓ 重置成功: {meter}")
        success_count += 1
    else:
        print(f"✗ 重置失败: {meter}")
        print(f"  错误: {response.status_code}")
        print(f"  内容: {response.text}")

print("\n" + "=" * 80)
print(f"重置完成！成功重置 {success_count}/{len(utility_meters)} 个 Utility Meter!")
print("=" * 80)
