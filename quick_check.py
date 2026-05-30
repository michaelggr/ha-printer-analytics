import urllib.request, json

token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiI3Y2EyNjc2MzdmZGU0YzliOWQ3Y2Y3ODM3N2YwMzA5ZSIsImlhdCI6MTc3ODk2OTYzNCwiZXhwIjoyMDk0MzI5NjM0fQ.iFan1gdP67hAY5jn0ilFABv98DbA79TFTHg76PyNhJY'

req = urllib.request.Request(
    'http://192.168.0.130:8123/api/states/sensor.p2s_p2s_da_yin_li_shi',
    headers={'Authorization': 'Bearer ' + token}
)
resp = urllib.request.urlopen(req, timeout=10)
data = json.loads(resp.read())
attrs = data.get('attributes', {})
history = attrs.get('history', [])
total_count = attrs.get('total_count', 0)
truncated = attrs.get('truncated', False)

print(f'records: {len(history)}, total_count: {total_count}, truncated: {truncated}')
if history:
    for i, r in enumerate(history[:5]):
        et = r.get('end_time', '?')
        name = r.get('task_name', '?')[:40]
        status = r.get('status', '?')
        print(f'  [{i}] {et} - {name} [{status}]')
