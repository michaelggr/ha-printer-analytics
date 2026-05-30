import urllib.request, json

token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiI3Y2EyNjc2MzdmZGU0YzliOWQ3Y2Y3ODM3N2YwMzA5ZSIsImlhdCI6MTc3ODk2OTYzNCwiZXhwIjoyMDk0MzI5NjM0fQ.iFan1gdP67hAY5jn0ilFABv98DbA79TFTHg76PyNhJY'
hdr = {'Authorization': 'Bearer ' + token}
base = 'http://192.168.0.130:8123/api/states/'

# 当前 UI 所有设备的累计实体
cumulative_entities = [
    ('总功耗',   'sensor.li_shi_zong_gong_hao'),
    ('豆浆机',   'sensor.dou_jiang_ji_lei_ji_yong_dian_kwh'),
    ('烤箱',     'sensor.kao_xiang_lei_ji_yong_dian_kwh'),
    ('卧室空调', 'sensor.208907222021213_total_energy_consumption'),
    ('客厅空调', 'sensor.210006733703670_total_energy_consumption'),
    ('取暖器',   'sensor.qu_nuan_qi_lei_ji_yong_dian_kwh'),
    ('电脑电源', 'sensor.dian_nao_dian_yuan_lei_ji_yong_dian'),
    ('NAS',      'sensor.naslei_ji_yong_dian'),
    ('小打印机', 'sensor.xiao_da_yin_ji_lei_ji_yong_dian'),
    ('大打印机', 'sensor.da_da_yin_ji_lei_ji_yong_dian'),
    ('洗衣机',   'sensor.xi_yi_ji_lei_ji_yong_dian_kwh'),
]

# 需要额外检查的中间实体（模板引用链中可能存在的周期传感器）
chain_entities = [
    'sensor.xiaoheinu_yearly_energy_v2_corrected',
    'sensor.xiaoheinu_yearly_energy_v2',
    'sensor.daheinu_yearly_energy_v2_corrected',
    'sensor.daheinu_yearly_energy_v2',
    'sensor.doujiangji_yearly_energy_v2',
    'sensor.oven_yearly_energy_v2',
    'sensor.heater_yearly_energy_v2',
    'sensor.computer_yearly_energy_v2',
    'sensor.nas_yearly_energy_v2',
    'sensor.washer_yearly_energy_v2',
    'sensor.xiao_da_yin_ji_lei_ji_yong_dian_kwh',
    'sensor.da_da_yin_ji_lei_ji_yong_dian_kwh',
]

all_eids = [(n, e) for n, e in cumulative_entities] + [('链路检查', e) for e in chain_entities]

# 去重
seen = set()
unique = []
for n, e in all_eids:
    if e not in seen:
        seen.add(e)
        unique.append((n, e))

print('=' * 120)
print(f'{"设备":^8s} | {"实体ID":55s} | {"值":>10s} | {"unit":4s} | {"state_class":18s} | {"next_reset":22s} | {"source":45s}')
print('-' * 120)

for name, eid in unique:
    try:
        req = urllib.request.Request(base + eid, headers=hdr)
        data = json.loads(urllib.request.urlopen(req, timeout=10).read())
        attrs = data.get('attributes', {})
        state = data['state']
        unit = attrs.get('unit_of_measurement', '')
        sc = attrs.get('state_class', '-')
        nr = attrs.get('next_reset', '-') or '-'
        source = attrs.get('source', '-')
        
        # 标记风险
        risk = ''
        lower = eid.lower()
        if nr != '-':
            risk = '⚠️ 有next_reset!'
        elif any(x in lower for x in ['yearly', 'weekly', 'monthly', 'daily']):
            risk = '⚠️ 周期实体名'
        elif any(x in lower for x in ['_v2_corrected']):
            risk = '⚠️ corrected包装'
        
        short = eid.replace('sensor.', '')[:50]
        nr_s = str(nr)[:19] if nr != '-' else '-'
        src_s = source.replace('sensor.', '')[:42] if source != '-' else '-'
        
        print(f'{name:^8s} | {short:55s} | {state:>10s} {unit:3s} | {sc:18s} | {nr_s:22s} | {src_s:45s} {risk}')
    except Exception as e:
        short = eid.replace('sensor.', '')[:50]
        print(f'{name:^8s} | {short:55s} | {"不存在":>10s}     | {"-":18s} | {"-":22s} | {"-":45s}')

print()
print('=' * 120)
print('\n关键判断:')
print('  • next_reset 存在 → 该实体会在指定时间重置')
print('  • _yearly_ / _weekly_ / _monthly_ / _daily_ → utility_meter 周期传感器')
print('  • _v2_corrected → 对 utility_meter 的修正包装，同样会随底层重置')
