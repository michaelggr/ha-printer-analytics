import asyncio, json, urllib.request

token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiI3Y2EyNjc2MzdmZGU0YzliOWQ3Y2Y3ODM3N2YwMzA5ZSIsImlhdCI6MTc3ODk2OTYzNCwiZXhwIjoyMDk0MzI5NjM0fQ.iFan1gdP67hAY5jn0ilFABv98DbA79TFTHg76PyNhJY'
hdr = {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'}
base = 'http://192.168.0.130:8123'

# 尝试通过 HA 的内部 API 获取 energy 配置
# HA 前端使用 WebSocket，但 REST API 也可以通过特定端点访问
endpoints = [
    ('GET', '/api/config/energy'),
    ('GET', '/api/energy'),
    ('POST', '/api/config/energy'),
    ('GET', '/api/stores/energy'),
]

for method, ep in endpoints:
    try:
        if method == 'GET':
            req = urllib.request.Request(f'{base}{ep}', headers=hdr)
        else:
            data = json.dumps({}).encode()
            req = urllib.request.Request(f'{base}{ep}', data=data, headers=hdr, method=method)
        resp = urllib.request.urlopen(req, timeout=10)
        result = resp.read().decode()[:500]
        print(f'✅ {method} {ep} → HTTP {resp.status}: {result}')
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:200]
        print(f'❌ {method} {ep} → HTTP {e.code}: {body}')
    except Exception as e:
        print(f'❌ {method} {ep} → {e}')

# 尝试读取 .storage/energy 文件
print('\n尝试通过 SMB 读取 .storage/energy:')
try:
    with open(r'\\192.168.0.130\config\.storage\energy', 'r', encoding='utf-8') as f:
        energy_data = json.load(f)
    print(f'✅ 读取成功! keys={list(energy_data.keys())}')
    if 'data' in energy_data:
        print(f'data keys={list(energy_data["data"].keys())}')
        if 'device_consumption' in energy_data['data']:
            print(f'当前 device_consumption ({len(energy_data["data"]["device_consumption"])} 个):')
            for dc in energy_data['data']['device_consumption']:
                print(f'  - {json.dumps(dc, ensure_ascii=False)[:120]}')
except Exception as e:
    print(f'❌ {e}')
