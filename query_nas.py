import urllib.request, json

req = urllib.request.Request('http://192.168.0.130:8123/api/states',
  headers={'Authorization': 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiI3Y2EyNjc2MzdmZGU0YzliOWQ3Y2Y3ODM3N2YwMzA5ZSIsImlhdCI6MTc3ODk2OTYzNCwiZXhwIjoyMDk0MzI5NjM0fQ.iFan1gdP67hAY5jn0ilFABv98DbA79TFTHg76PyNhJY'})
data = json.loads(urllib.request.urlopen(req, timeout=15).read())

# 查找所有 NAS 相关传感器
targets = [e for e in data if 'nas' in e['entity_id'].lower() and 'sensor.' in e['entity_id']]
for t in sorted(targets, key=lambda x: x['entity_id']):
    val = t.get('state', '?')
    attrs = t.get('attributes', {})
    name = attrs.get('friendly_name', '')
    unit = attrs.get('unit_of_measurement', '')
    dev_cla = attrs.get('device_class', '')
    print(f"{t['entity_id']:55s} | {val:>12s} | {unit:6s} | {name}")
