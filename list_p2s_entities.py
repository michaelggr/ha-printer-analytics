﻿import json, urllib.request

TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiI3Y2EyNjc2MzdmZGU0YzliOWQ3Y2Y3ODM3N2YwMzA5ZSIsImlhdCI6MTc3ODk2OTYzNCwiZXhwIjoyMDk0MzI5NjM0fQ.iFan1gdP67hAY5jn0ilFABv98DbA79TFTHg76PyNhJY'
BASE = "http://192.168.0.130:8123"

req = urllib.request.Request(f"{BASE}/api/states", headers={'Authorization': f'Bearer {TOKEN}'})
data = json.loads(urllib.request.urlopen(req, timeout=15).read())

for e in data:
    eid = e.get('entity_id', '')
    if eid.startswith('sensor.p2s_'):
        attrs = e.get('attributes', {})
        print(f"{eid}: state={e.get('state')}")
        for k in sorted(attrs.keys()):
            if k != 'icon':
                v = attrs[k]
                if isinstance(v, (list, dict)):
                    print(f"  {k}: [{type(v).__name__} len={len(v)}]")
                elif isinstance(v, str) and len(v) > 80:
                    print(f"  {k}: {v[:80]}...")
                else:
                    print(f"  {k}: {v}")
        print()
