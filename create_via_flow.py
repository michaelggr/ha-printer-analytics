﻿import urllib.request, json

TOKEN = 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiI1M2Q4NzBkOGY4M2U0YWY3ODIzNTJlNjVkNmVkYzY5YSIsImlhdCI6MTc3NDE5NTM2MCwiZXhwIjoyMDg5NTU1MzYwfQ.7VKORHi3sWJfROnc7HKzDyY1uwapDC8WXdLIj4sAITs'

# 使用 HA config entry flow 创建 template sensor
# Step 1: Init flow - 选择 sensor 类型
url = 'http://192.168.0.130:8123/api/config/config_entries/flow'
init_data = json.dumps({
    'handler': 'template',
    'show_advanced_options': True,
    'type': 'sensor'
}).encode()

req = urllib.request.Request(url, method='POST', headers={
    'Authorization': TOKEN,
    'Content-Type': 'application/json'
}, data=init_data)

try:
    resp = urllib.request.urlopen(req, timeout=10)
    flow = json.loads(resp.read())
    flow_id = flow.get('flow_id')
    step_id = flow.get('step_id')
    print(f'Step 1: flow_id={flow_id}, step_id={step_id}')
    print(f'Schema: {json.dumps(flow.get("data_schema", []), ensure_ascii=False)[:500]}')
    
    # Step 2: 填写 sensor 详情
    config_data = json.dumps({
        'name': '厨房灯周亮灯时长h',
        'state': "{{ (states('sensor.chu_fang_deng_zhou_liang_deng_shi_chang') | float(0) / 3600) | round(1) }}",
        'unit_of_measurement': '小时',
        'device_class': 'duration',
        'unique_id': 'chu_fang_deng_zhou_liang_deng_shi_chang_h',
        'icon': 'mdi:clock-outline'
    }).encode()
    
    req2 = urllib.request.Request(
        f'{url}/{flow_id}',
        method='POST',
        headers={
            'Authorization': TOKEN,
            'Content-Type': 'application/json'
        },
        data=config_data
    )
    
    resp2 = urllib.request.urlopen(req2, timeout=10)
    result = json.loads(resp2.read())
    print(f'\nStep 2 result: {json.dumps(result, indent=2, ensure_ascii=False)[:500]}')
    
except urllib.error.HTTPError as e:
    body = e.read().decode()
    print(f'HTTP Error {e.code}: {body[:500]}')
except Exception as e:
    print(f'Error: {e}')
