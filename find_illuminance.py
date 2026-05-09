﻿import urllib.request, json

TOKEN = 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiI1M2Q4NzBkOGY4M2U0YWY3ODIzNTJlNjVkNmVkYzY5YSIsImlhdCI6MTc3NDE5NTM2MCwiZXhwIjoyMDg5NTU1MzYwfQ.7VKORHi3sWJfROnc7HKzDyY1uwapDC8WXdLIj4sAITs'
url = 'http://192.168.0.130:8123/api/states'
req = urllib.request.Request(url, headers={'Authorization': TOKEN})
data = json.loads(urllib.request.urlopen(req, timeout=10).read())

# 查找所有光照度传感器
for e in data:
    eid = e['entity_id']
    fname = e.get('attributes', {}).get('friendly_name', '')
    unit = e.get('attributes', {}).get('unit_of_measurement', '')
    dc = e.get('attributes', {}).get('device_class', '')
    # 光照度通常是 lux 或 illuminance
    if dc == 'illuminance' or unit == 'lx' or unit == 'lux' or '光照' in fname or 'guang_zhao' in eid.lower() or 'illuminance' in eid.lower():
        state = e['state']
        print(f'{eid} | {fname} | {state} {unit} | dc={dc}')
