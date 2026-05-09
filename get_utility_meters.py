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

print("=" * 80)
print("正在获取所有 Utility Meter 实体...")
print("=" * 80)

response = requests.get(f'{HA_URL}/api/states', headers=headers)
all_states = response.json()

# 分类收集
daily_sensors = []
weekly_sensors = []
monthly_sensors = []
yearly_sensors = []

for state in all_states:
    entity_id = state['entity_id']
    if 'energy' in entity_id:
        if 'daily' in entity_id or 'ri_yong' in entity_id:
            daily_sensors.append(entity_id)
        elif 'weekly' in entity_id or 'zhou_yong' in entity_id:
            weekly_sensors.append(entity_id)
        elif 'monthly' in entity_id or 'yue_yong' in entity_id:
            monthly_sensors.append(entity_id)
        elif 'yearly' in entity_id or 'nian_yong' in entity_id:
            yearly_sensors.append(entity_id)

# 输出结果
print("\n【每日】 - Daily")
for s in sorted(daily_sensors):
    print(f"  - {s}")

print("\n【每周】 - Weekly")
for s in sorted(weekly_sensors):
    print(f"  - {s}")

print("\n【每月】 - Monthly")
for s in sorted(monthly_sensors):
    print(f"  - {s}")

print("\n【每年】 - Yearly")
for s in sorted(yearly_sensors):
    print(f"  - {s}")

print("=" * 80)

# 保存为JSON文件备用
data = {
    'daily': sorted(daily_sensors),
    'weekly': sorted(weekly_sensors),
    'monthly': sorted(monthly_sensors),
    'yearly': sorted(yearly_sensors)
}

with open('utility_meters_list.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print(f"\n✓ 已保存到 utility_meters_list.json")
print(f"  每日: {len(daily_sensors)} 个")
print(f"  每周: {len(weekly_sensors)} 个")
print(f"  每月: {len(monthly_sensors)} 个")
print(f"  每年: {len(yearly_sensors)} 个")
