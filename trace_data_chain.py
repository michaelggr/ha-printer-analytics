﻿import urllib.request, json

token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiI3Y2EyNjc2MzdmZGU0YzliOWQ3Y2Y3ODM3N2YwMzA5ZSIsImlhdCI6MTc3ODk2OTYzNCwiZXhwIjoyMDk0MzI5NjM0fQ.iFan1gdP67hAY5jn0ilFABv98DbA79TFTHg76PyNhJY'
hdr = {'Authorization': f'Bearer {token}'}
base = 'http://192.168.0.130:8123/api/states/'

# 这些是 lei_ji 模板引用的"底层源传感器"，需要查清它们的来源
mystery_sensors = [
    ('电脑电源底层',  'sensor.dian_nao_dian_yuan_lei_ji_yong_dian'),
    ('NAS底层',       'sensor.naslei_ji_yong_dian'),
    ('豆浆机累计',   'sensor.dou_jiang_ji_lei_ji_yong_dian_kwh'),
    ('烤箱累计',     'sensor.kao_xiang_lei_ji_yong_dian_kwh'),
    ('取暖器累计',   'sensor.qu_nuan_qi_lei_ji_yong_dian_kwh'),
    ('小打印机累计', 'sensor.xiao_da_yin_ji_lei_ji_yong_dian'),
    ('大打印机累计', 'sensor.da_da_yin_ji_lei_ji_yong_dian_kwh'),
    ('洗衣机累计',   'sensor.xi_yi_ji_lei_ji_yong_dian_kwh'),
]

# 同时查它们引用的 yearly 源
yearly_sources = [
    ('小打印机yearly源', 'sensor.xiaoheinu_yearly_energy_v2_corrected'),
    ('大打印机yearly源', 'sensor.daheinu_yearly_energy_v2_corrected'),
]

print('=' * 110)
print('追踪 "累计" 模板传感器的数据链:')
print('=' * 110)

all_checks = mystery_sensors + yearly_sources

for name, eid in all_checks:
    try:
        req = urllib.request.Request(base + eid, headers=hdr)
        data = json.loads(urllib.request.urlopen(req, timeout=10).read())
        attrs = data.get('attributes', {})
        
        state = data['state']
        unit = attrs.get('unit_of_measurement', '')
        sc = attrs.get('state_class', '-')
        source = attrs.get('source', '')
        lr = attrs.get('last_reset', '') or '-'
        nr = attrs.get('next_reset', '') or '-'
        integration = attrs.get('integration', '')
        
        print(f'\n【{name}】{eid.replace("sensor.", "")}')
        print(f'  值={state} {unit} | state_class={sc}')
        if source: print(f'  source={source}')
        if lr != '-': print(f'  last_reset={str(lr)[:19]}')
        if nr != '-': print(f'  next_reset={str(nr)[:19]}')
        if integration: print(f'  integration={integration}')
        
        # 判断类型
        if '_corrected' in eid or '_v2_corrected' in eid:
            stype = 'utility_meter corrected (可能年重置)'
        elif 'yearly' in eid:
            stype = '⚠️ utility_meter yearly (每年1月1日重置!)'
        elif 'lei_ji' in eid or 'li_shi' in eid:
            stype = '模板传感器(需追溯来源)'
        else:
            stype = '?'
        print(f'  → 类型判断: {stype}')
        
    except Exception as e:
        print(f'\n【{name}】{eid.replace("sensor.", "")}: 不存在 ({e})')

# 最终结论
print('\n' + '=' * 110)
print('\n数据链追踪总结:')
print('=' * 110)
