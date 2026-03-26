import json, requests
from pathlib import Path
text = Path('.ha_connection_info.json').read_text(encoding='utf-8-sig').lstrip('\ufeff')
cfg = json.loads(text)
base = cfg['ha_api']['url'].rstrip('/')
headers = {'Authorization': f"Bearer {cfg['ha_api']['token']}"}
entity_ids = [
  'sensor.a1mini_0300aa5a1600497_print_status',
  'sensor.a1mini_0300aa5a1600497_current_stage',
  'automation.bambu_lab_chao_mian_jian_ce_mi_jia_tong_zhi_ban',
  'input_number.bambu_lab_p1_spaghetti_detection_current_frame_number',
  'input_number.bambu_lab_p1_spaghetti_detection_p_sum',
  'input_number.bambu_lab_p1_spaghetti_detection_ewm_mean',
  'input_number.bambu_lab_p1_spaghetti_detection_normalized_p',
]
rows=[]
for eid in entity_ids:
    r = requests.get(f'{base}/api/states/{eid}', headers=headers, timeout=10)
    rows.append({'entity_id': eid, 'status_code': r.status_code, 'state': (r.json().get('state') if r.status_code==200 else None), 'last_updated': (r.json().get('last_updated') if r.status_code==200 else None)})
print(json.dumps(rows, ensure_ascii=False, indent=2))
