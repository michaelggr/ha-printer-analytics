import urllib.request, json

token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiI3Y2EyNjc2MzdmZGU0YzliOWQ3Y2Y3ODM3N2YwMzA5ZSIsImlhdCI6MTc3ODk2OTYzNCwiZXhwIjoyMDk0MzI5NjM0fQ.iFan1gdP67hAY5jn0ilFABv98DbA79TFTHg76PyNhJY'
hdr = {'Authorization': 'Bearer ' + token}
base = 'http://192.168.0.130:8123/api/states/'
storage_base = 'http://192.168.0.130:8123/api/storage/'

def get(entity):
    try:
        req = urllib.request.Request(base + entity, headers=hdr)
        return json.loads(urllib.request.urlopen(req, timeout=10).read())
    except:
        return None

def get_storage(path):
    try:
        req = urllib.request.Request(storage_base + path, headers=hdr)
        return json.loads(urllib.request.urlopen(req, timeout=10).read())
    except:
        return None

print('=' * 70)
print('【A】电脑电源数据链追踪：周 vs 月 差异根因')
print('=' * 70)

# 获取电脑相关所有实体
targets = [
    'sensor.dian_nao_dian_yuan_zhou_yong_dian_liang',
    'sensor.dian_nao_dian_yuan_yue_yong_dian_liang',
    'sensor.dian_nao_dian_yuan_ri_yong_dian_liang',
    'sensor.computer_weekly_energy',
    'sensor.computer_monthly_energy',
    'sensor.computer_daily_energy',
    'sensor.dian_nao_dian_yuan_lei_ji_yong_dian_kwh',
    'sensor.dian_nao_dian_yuan_lei_ji_yong_dian_2',
]
for t in targets:
    d = get(t)
    if d:
        attrs = d.get('attributes', {})
        src = attrs.get('source_sensor', attrs.get('unit_of_measurement', ''))
        print(f'  {t}')
        print(f'    state = {d.get("state")}')
        if src:
            print(f'    attr  = source:{src}' if isinstance(src, str) else f'    attr  = {list(attrs.keys())[:5]}')
    else:
        print(f'  {t}: NOT FOUND')

print()
print('=' * 70)
print('【B】查找旧模板传感器的定义来源')
print('=' * 70)

# 从 storage 中查找模板传感器定义
storage = get_storage('core.config_entries')
if storage:
    entries = storage.get('data', {}).get('entries', [])
    for e in entries:
        domain = e.get('domain', '')
        if domain == 'template':
            title = e.get('title', '')
            eid = e.get('entry_id', '')
            print(f'  Found template entry: {title} (id={eid})')

print()
print('=' * 70)
print('【C】NAS 数据链追踪')
print('=' * 70)

nas_targets = [
    ('NAS周(旧模板)', 'sensor.naszhou_yong_dian_liang'),
    ('NAS月(旧模板)', 'sensor.nasyue_yong_dian_liang'),
    ('NAS日(旧模板)', 'sensor.nasri_yong_dian_liang'),
    ('NAS周(v2)', 'sensor.nas_weekly_energy_v2'),
    ('NAS月(v2)', 'sensor.nas_monthly_energy_v2'),
    ('NAS原始Wh', 'sensor.giot_cn_1163256502_v8icm_power_consumption_p_4_1'),
]
for label, sid in nas_targets:
    d = get(sid)
    if d:
        print(f'  {label:20s}: {d.get("state")}')
    else:
        print(f'  {label:20s}: NOT FOUND')
