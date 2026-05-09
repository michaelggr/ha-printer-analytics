﻿import urllib.request, json

TOKEN = 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiI1M2Q4NzBkOGY4M2U0YWY3ODIzNTJlNjVkNmVkYzY5YSIsImlhdCI6MTc3NDE5NTM2MCwiZXhwIjoyMDg5NTU1MzYwfQ.7VKORHi3sWJfROnc7HKzDyY1uwapDC8WXdLIj4sAITs'
BASE_URL = 'http://192.168.0.130:8123/api/config/config_entries/flow'

def create_template_sensor(name, state_template, unit, device_class='duration'):
    # Step 1: Init flow
    init_data = json.dumps({'handler': 'template', 'show_advanced_options': True}).encode()
    req = urllib.request.Request(BASE_URL, method='POST', headers={
        'Authorization': TOKEN, 'Content-Type': 'application/json'
    }, data=init_data)
    resp = urllib.request.urlopen(req, timeout=10)
    flow = json.loads(resp.read())
    flow_id = flow['flow_id']

    # Step 2: Select sensor type
    step2_data = json.dumps({'next_step_id': 'sensor'}).encode()
    req2 = urllib.request.Request(f'{BASE_URL}/{flow_id}', method='POST', headers={
        'Authorization': TOKEN, 'Content-Type': 'application/json'
    }, data=step2_data)
    resp2 = urllib.request.urlopen(req2, timeout=10)
    flow2 = json.loads(resp2.read())

    # Step 3: Fill sensor details (no unique_id)
    step3_data = json.dumps({
        'name': name,
        'state': state_template,
        'unit_of_measurement': unit,
        'device_class': device_class,
    }).encode()
    req3 = urllib.request.Request(f'{BASE_URL}/{flow_id}', method='POST', headers={
        'Authorization': TOKEN, 'Content-Type': 'application/json'
    }, data=step3_data)
    try:
        resp3 = urllib.request.urlopen(req3, timeout=10)
        result = json.loads(resp3.read())
        print(f'  Created: {name}')
        return True
    except urllib.error.HTTPError as e:
        error = e.read().decode()
        print(f'  Error: {name} - {error[:200]}')
        return False

# 测试一个
result = create_template_sensor(
    name='厨房灯周亮灯时长h',
    state_template="{{ (states('sensor.chu_fang_deng_zhou_liang_deng_shi_chang') | float(0) / 3600) | round(1) }}",
    unit='小时'
)
print(f'Result: {result}')

# 验证
import urllib.request
url = 'http://192.168.0.130:8123/api/states'
req = urllib.request.Request(url, headers={'Authorization': TOKEN})
data = json.loads(urllib.request.urlopen(req, timeout=10).read())
for e in data:
    if 'chu_fang_deng_zhou_liang_deng_shi_chang' in e['entity_id'] and e['entity_id'].endswith('_h'):
        print(f'  Found: {e["entity_id"]} | state={e["state"]} | unit={e.get("attributes",{}).get("unit_of_measurement","")}')
