import json, requests
from pathlib import Path
text = Path('.ha_connection_info.json').read_text(encoding='utf-8-sig').lstrip('\ufeff')
cfg = json.loads(text)
base = cfg['ha_api']['url'].rstrip('/')
print('base', base)
headers = {'Authorization': f"Bearer {cfg['ha_api']['token']}"}
resp = requests.get(f'{base}/api/config/logs', headers=headers, timeout=15)
print(resp.status_code)
print(resp.text[:1000])
