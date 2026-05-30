import urllib.request, json

token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiI3Y2EyNjc2MzdmZGU0YzliOWQ3Y2Y3ODM3N2YwMzA5ZSIsImlhdCI6MTc3ODk2OTYzNCwiZXhwIjoyMDk0MzI5NjM0fQ.iFan1gdP67hAY5jn0ilFABv98DbA79TFTHg76PyNhJY'
hdr = {'Authorization': 'Bearer ' + token}
base = 'http://192.168.0.130:8123/api/states/'

def get_full(entity):
    try:
        req = urllib.request.Request(base + entity, headers=hdr)
        return json.loads(urllib.request.urlopen(req, timeout=10).read())
    except:
        return None

print('=' * 70)
print('【Riemann 差值=0 的根因分析】')
print('=' * 70)

# 检查电脑电源的 Riemann 累计源
sources = [
    ('电脑Riemann累计', 'sensor.dian_nao_dian_yuan_lei_ji_yong_dian_total'),
    ('NAS Riemann累计', 'sensor.naslei_ji_yong_dian_total'),
    ('取暖器原始Wh', 'sensor.giot_cn_1162898415_v8icm_power_consumption_p_4_1'),
]

for label, sid in sources:
    d = get_full(sid)
    if d:
        print(f'  {label}: state={d.get("state")}')
        attrs = d.get('attributes', {})
        print(f'    unit={attrs.get("unit_of_measurement")}, device_class={attrs.get("device_class")}')
        print(f'    last_updated={d.get("last_updated")}')
    else:
        print(f'  {label}: NOT FOUND')

print()
print('--- 关键问题：HA模板中 states(entity, datetime) 是否支持？ ---')
print()

# 用 API 测试历史数据查询
import datetime
now = datetime.datetime.now()
week_start = (now - datetime.timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0)
t0_str = week_start.strftime('%Y-%m-%dT00:00:00+08:00')

print(f'当前时间: {now.isoformat()}')
print(f'周一零点:  {t0_str}')

# 尝试历史状态API
try:
    req = urllib.request.Request(
        f'http://192.168.0.130:8123/api/history/period/{t0_str}?filter_entity_id=sensor.dian_nao_dian_yuan_lei_ji_yong_dian_total',
        headers=hdr
    )
    data = json.loads(urllib.request.urlopen(req, timeout=15).read())
    if data and len(data[0]) > 0:
        first = data[0][0]
        last = data[0][-1]
        print(f'\n  电脑Riemann历史记录数: {len(data[0])}')
        print(f'  周一最早值: {first.get("state")} @ {first.get("last_updated")}')
        print(f'  最新值:     {last.get("state")} @ {last.get("last_updated")}')
        
        cur = float(last.get('state', 0))
        first_val = float(first.get('state', 0))
        diff = cur - first_val
        print(f'  本周差值应为: {cur} - {first_val} = {diff:.4f} kWh')
    else:
        print('  无历史记录!')
except Exception as e:
    print(f'  历史查询失败: {e}')

# 也检查 NAS
try:
    req2 = urllib.request.Request(
        f'http://192.168.0.130:8123/api/history/period/{t0_str}?filter_entity_id=sensor.naslei_ji_yong_dian_total',
        headers=hdr
    )
    data2 = json.loads(urllib.request.urlopen(req2, timeout=15).read())
    if data2 and len(data2[0]) > 0:
        first2 = data2[0][0]
        last2 = data2[0][-1]
        cur2 = float(last2.get('state', 0))
        first2_val = float(first2.get('state', 0))
        print(f'\n  NAS历史记录数: {len(data2[0])}')
        print(f'  NAS本周差值应为: {cur2} - {first2_val} = {cur2 - first2_val:.4f} kWh')
except Exception as e2:
    print(f'  NAS历史查询失败: {e2}')
