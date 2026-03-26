import json, requests
from pathlib import Path
text=Path('.ha_connection_info.json').read_text(encoding='utf-8-sig').lstrip('\ufeff')
cfg=json.loads(text)
base=cfg['ha_api']['url'].rstrip('/')
headers={'Authorization': f"Bearer {cfg['ha_api']['token']}"}
resp=requests.post(f'{base}/api/services/automation/reload', headers=headers, timeout=15)
print(resp.status_code, resp.text)
