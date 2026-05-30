import urllib.request, json

token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiI3Y2EyNjc2MzdmZGU0YzliOWQ3Y2Y3ODM3N2YwMzA5ZSIsImlhdCI6MTc3ODk2OTYzNCwiZXhwIjoyMDk0MzI5NjM0fQ.iFan1gdP67hAY5jn0ilFABv98DbA79TFTHg76PyNhJY'
hdr = {'Authorization': 'Bearer ' + token}
base = 'http://192.168.0.130:8123/api/states/'

def get_state(entity_id):
    try:
        req = urllib.request.Request(base + entity_id, headers=hdr)
        data = json.loads(urllib.request.urlopen(req, timeout=10).read())
        return data.get('state', 'unknown')
    except Exception as e:
        return 'ERR:' + str(e)[:50]

print('=' * 70)
print('【1】新 v2 utility_meter 实体检查（电脑/NAS/取暖器）')
print('=' * 70)

new_v2 = [
    'sensor.computer_daily_energy_v2',
    'sensor.computer_weekly_energy_v2',
    'sensor.computer_monthly_energy_v2',
    'sensor.computer_yearly_energy_v2',
    'sensor.nas_daily_energy_v2',
    'sensor.nas_weekly_energy_v2',
    'sensor.nas_monthly_energy_v2',
    'sensor.nas_yearly_energy_v2',
    'sensor.heater_daily_energy_v2',
    'sensor.heater_weekly_energy_v2',
    'sensor.heater_monthly_energy_v2',
    'sensor.heater_yearly_energy_v2',
]
for s in new_v2:
    val = get_state(s)
    status = 'OK' if not val.startswith('ERR') else 'FAIL'
    print(f'  {status} {s}: {val}')

print()
print('=' * 70)
print('【2】空调 yearly 实体检查')
print('=' * 70)
ac_sensors = [
    'sensor.bedroom_ac_yearly_energy',
    'sensor.living_ac_yearly_energy',
    'sensor.bedroom_ac_weekly_energy',
    'sensor.living_ac_weekly_energy',
    'sensor.bedroom_ac_monthly_energy',
    'sensor.living_ac_monthly_energy',
]
for s in ac_sensors:
    val = get_state(s)
    status = 'OK' if not val.startswith('ERR') else 'FAIL'
    print(f'  {status} {s}: {val}')

print()
print('=' * 70)
print('【3】home_*_total_v2 核心统计（用电统计页面）')
print('=' * 70)

totals = {
    'home_daily_total_v2': get_state('sensor.home_daily_total_v2'),
    'home_weekly_total_v2': get_state('sensor.home_weekly_total_v2'),
    'home_monthly_total_v2': get_state('sensor.home_monthly_total_v2'),
    'home_yearly_total_v2': get_state('sensor.home_yearly_total_v2'),
}

for name, val in totals.items():
    print(f'  {name}: {val} kWh')

# 逻辑校验
d = float(totals['home_daily_total_v2'])
w = float(totals['home_weekly_total_v2'])
m = float(totals['home_monthly_total_v2'])
y = float(totals['home_yearly_total_v2'])

print()
print('【逻辑校验】')
checks = []
checks.append(('本周 >= 今日?', w >= d))
checks.append(('本月 >= 本周?', m >= w))
checks.append(('本年 >= 本月?', y >= m))
checks.append(('本年 >= 本周?', y >= w))

all_ok = True
for desc, ok in checks:
    mark = 'PASS' if ok else 'FAIL'
    if not ok: all_ok = False
    print(f'  [{mark}] {desc} ({m:.2f}>={w:.2f})' if '本月' in desc else f'  [{mark}] {desc}')

if all_ok:
    print('\n  所有逻辑校验通过!')
else:
    print('\n  存在逻辑异常!')

print()
print('=' * 70)
print('【4】各设备 weekly 子值明细（用于排查）')
print('=' * 70)
weekly_subs = [
    ('豆浆机', 'sensor.doujiangji_weekly_energy_v2'),
    ('烤箱', 'sensor.oven_weekly_energy_v2'),
    ('小打印机', 'sensor.xiaoheinu_weekly_energy_v2'),
    ('大打印机', 'sensor.daheinu_weekly_energy_v2'),
    ('洗衣机', 'sensor.washer_weekly_energy_v2'),
    ('电脑电源', 'sensor.computer_weekly_energy_v2'),
    ('NAS', 'sensor.nas_weekly_energy_v2'),
    ('取暖器', 'sensor.heater_weekly_energy_v2'),
]
for label, sid in weekly_subs:
    val = get_state(sid)
    print(f'  {label}: {val}')
