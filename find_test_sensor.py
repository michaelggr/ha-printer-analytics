﻿import urllib.request, json

url = 'http://192.168.0.130:8123/api/states'
req = urllib.request.Request(url, headers={
    'Authorization': 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiI1M2Q4NzBkOGY4M2U0YWY3ODIzNTJlNjVkNmVkYzY5YSIsImlhdCI6MTc3NDE5NTM2MCwiZXhwIjoyMDg5NTU1MzYwfQ.7VKORHi3sWJfROnc7HKzDyY1uwapDC8WXdLIj4sAITs'
})
data = json.loads(urllib.request.urlopen(req, timeout=10).read())

# 查找所有可能是 templates.yaml 定义的传感器
# 通过匹配 templates.yaml 中定义的名称
yaml_names = [
    'yutai_cn_1169887446_fsov8m_power_consumption_kwh',
    'printer_daily_energy',
    'printer_weekly_energy',
    'printer_monthly_energy',
    'Total Prints',
    'Success Rate',
    'Average Print Duration',
    'Total Online Duration',
    'test_kitchen_weekly_hours',
]

for e in data:
    fname = e.get('attributes', {}).get('friendly_name', '')
    eid = e['entity_id']
    for name in yaml_names:
        if name.lower().replace(' ', '_') in eid.lower() or name == fname:
            print(f'{eid} | {fname} | state={e["state"]}')

# 搜索所有包含 "test" 的传感器
print('\n--- All test sensors ---')
for e in data:
    if 'test' in e['entity_id'].lower():
        print(f'{e["entity_id"]} | {e["state"]}')

# 搜索所有包含 "kitchen_weekly" 的传感器
print('\n--- All kitchen_weekly sensors ---')
for e in data:
    if 'kitchen_weekly' in e['entity_id'].lower() or 'kitchen' in e['entity_id'].lower() and 'weekly' in e['entity_id'].lower():
        print(f'{e["entity_id"]} | {e["state"]}')
