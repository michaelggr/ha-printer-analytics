import urllib.request, json
token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiI3Y2EyNjc2MzdmZGU0YzliOWQ3Y2Y3ODM3N2YwMzA5ZSIsImlhdCI6MTc3ODk2OTYzNCwiZXhwIjoyMDk0MzI5NjM0fQ.iFan1gdP67hAY5jn0ilFABv98DbA79TFTHg76PyNhJY'
req = urllib.request.Request('http://192.168.0.130:8123/api/states', headers={'Authorization': f'Bearer {token}'})
data = json.loads(urllib.request.urlopen(req, timeout=15).read())

for e in data:
    eid = e['entity_id']
    if 'p2s' in eid or 'a1mini' in eid:
        print(f"{eid}")
