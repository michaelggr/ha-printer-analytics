﻿import urllib.request, json

TOKEN = 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiI1M2Q4NzBkOGY4M2U0YWY3ODIzNTJlNjVkNmVkYzY5YSIsImlhdCI6MTc3NDE5NTM2MCwiZXhwIjoyMDg5NTU1MzYwfQ.7VKORHi3sWJfROnc7HKzDyY1uwapDC8WXdLIj4sAITs'
BASE_URL = 'http://192.168.0.130:8123/api/config/config_entries/flow'

# Step 1: Init flow
init_data = json.dumps({'handler': 'template', 'show_advanced_options': True}).encode()
req = urllib.request.Request(BASE_URL, method='POST', headers={
    'Authorization': TOKEN, 'Content-Type': 'application/json'
}, data=init_data)
resp = urllib.request.urlopen(req, timeout=10)
flow = json.loads(resp.read())
flow_id = flow['flow_id']
print(f'Flow ID: {flow_id}')

# Step 2: Select sensor type
step2_data = json.dumps({'next_step_id': 'sensor'}).encode()
req2 = urllib.request.Request(f'{BASE_URL}/{flow_id}', method='POST', headers={
    'Authorization': TOKEN, 'Content-Type': 'application/json'
}, data=step2_data)
resp2 = urllib.request.urlopen(req2, timeout=10)
flow2 = json.loads(resp2.read())
print(f'Step 2: {json.dumps(flow2, indent=2, ensure_ascii=False)[:1000]}')

# Step 3: Try with minimal data
step3_data = json.dumps({
    'name': '厨房灯周亮灯时长h',
    'state': "0",
    'unit_of_measurement': '小时',
}).encode()
req3 = urllib.request.Request(f'{BASE_URL}/{flow_id}', method='POST', headers={
    'Authorization': TOKEN, 'Content-Type': 'application/json'
}, data=step3_data)
try:
    resp3 = urllib.request.urlopen(req3, timeout=10)
    result = json.loads(resp3.read())
    print(f'Step 3 result: {json.dumps(result, indent=2, ensure_ascii=False)[:500]}')
except urllib.error.HTTPError as e:
    error = e.read().decode()
    print(f'Step 3 error: {e.code} - {error}')
