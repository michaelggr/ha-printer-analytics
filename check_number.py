import json, requests
from pathlib import Path
text=Path('.ha_connection_info.json').read_text(encoding='utf-8-sig').lstrip('\ufeff')
cfg=json.loads(text)
base=cfg['ha_api']['url'].rstrip('/')
headers={'Authorization': f"Bearer {cfg['ha_api']['token']}"}
entity_ids=['number.bambu_lab_p1_spaghetti_detection_current_frame_number','number.bambu_lab_p1_spaghetti_detection_p_sum']
for eid in entity_ids:
    r=requests.get(f'{base}/api/states/{eid}', headers=headers, timeout=15)
    print(eid, r.status_code)
    if r.status_code==200:
        print(json.dumps(r.json(), ensure_ascii=False, indent=2))
    else:
        print(r.text)
