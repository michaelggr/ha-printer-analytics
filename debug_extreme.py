import urllib.request, json

token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiI3Y2EyNjc2MzdmZGU0YzliOWQ3Y2Y3ODM3N2YwMzA5ZSIsImlhdCI6MTc3ODk2OTYzNCwiZXhwIjoyMDk0MzI5NjM0fQ.iFan1gdP67hAY5jn0ilFABv98DbA79TFTHg76PyNhJY'

# 检查 extreme_stats 实体的属性结构
req = urllib.request.Request(
    'http://192.168.0.130:8123/api/states/sensor.p2s_p2s_zhi_zui_da_yin',
    headers={'Authorization': 'Bearer ' + token}
)
resp = urllib.request.urlopen(req, timeout=10)
data = json.loads(resp.read())

attrs = data.get('attributes', {})
print(f'Entity: sensor.p2s_p2s_zhi_zui_da_yin')
print(f'State: {data.get("state")}')
print(f'Attribute keys: {list(attrs.keys())}')
for k, v in attrs.items():
    if k in ('icon', 'friendly_name'):
        continue
    if isinstance(v, dict):
        print(f'  {k}: keys={list(v.keys())[:5]}')
        for kk, vv in v.items():
            if isinstance(vv, dict):
                print(f'    {kk}: {list(vv.keys())[:5]}')
    else:
        print(f'  {k}: {v}')

# 检查 print_history 实体 ID（用于提取前缀）
req2 = urllib.request.Request(
    'http://192.168.0.130:8123/api/states',
    headers={'Authorization': 'Bearer ' + token}
)
resp2 = urllib.request.urlopen(req2, timeout=15)
states = json.loads(resp2.read())
for s in states:
    eid = s.get('entity_id', '')
    if 'da_yin_li_shi' in eid:
        print(f'\nprint_history entity: {eid}')
