import urllib.request, json

TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiI3Y2EyNjc2MzdmZGU0YzliOWQ3Y2Y3ODM3N2YwMzA5ZSIsImlhdCI6MTc3ODk2OTYzNCwiZXhwIjoyMDk0MzI5NjM0fQ.iFan1gdP67hAY5jn0ilFABv98DbA79TFTHg76PyNhJY'
req = urllib.request.Request('http://192.168.0.130:8123/api/states', headers={'Authorization': f'Bearer {TOKEN}'})
data = json.loads(urllib.request.urlopen(req, timeout=15).read())

# 查找所有 weekly 相关传感器
weekly = [(e['entity_id'], e.get('state', 'N/A')) for e in data if 'weekly' in e['entity_id'].lower()]
weekly.sort(key=lambda x: x[0])

print("=== Weekly 能源传感器 ===")
for eid, state in weekly:
    print(f"  {eid} = {state}")

# 查找空调的 weekly 传感器
ac = [(e['entity_id'], e.get('state', 'N/A')) for e in data if 'weekly' in e['entity_id'].lower() and ('kong' in e['entity_id'].lower() or 'air' in e['entity_id'].lower() or '2089' in e['entity_id'] or '2100' in e['entity_id'])]
print("\n=== 空调 weekly 传感器 ===")
for eid, state in ac:
    print(f"  {eid} = {state}")

# 查找所有 _weekly_kwh 传感器
kwh_weekly = [(e['entity_id'], e.get('state', 'N/A')) for e in data if '_weekly_kwh' in e['entity_id'].lower()]
kwh_weekly.sort(key=lambda x: x[0])
print("\n=== _weekly_kwh 传感器 ===")
for eid, state in kwh_weekly:
    print(f"  {eid} = {state}")

# 查找 corrected weekly
corrected = [(e['entity_id'], e.get('state', 'N/A')) for e in data if 'weekly' in e['entity_id'].lower() and 'corrected' in e['entity_id'].lower()]
corrected.sort(key=lambda x: x[0])
print("\n=== corrected weekly 传感器 ===")
for eid, state in corrected:
    print(f"  {eid} = {state}")
