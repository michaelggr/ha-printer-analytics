﻿import urllib.request, json

token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiI3Y2EyNjc2MzdmZGU0YzliOWQ3Y2Y3ODM3N2YwMzA5ZSIsImlhdCI6MTc3ODk2OTYzNCwiZXhwIjoyMDk0MzI5NjM0fQ.iFan1gdP67hAY5jn0ilFABv98DbA79TFTHg76PyNhJY'
hdr = {'Authorization': f'Bearer {token}'}
base = 'http://192.168.0.130:8123/api/states/'

def get(eid):
    try:
        req = urllib.request.Request(base + eid, headers=hdr)
        return float(json.loads(urllib.request.urlopen(req, timeout=10).read())['state'])
    except:
        return None

print('=' * 85)
print(f'{"设备":^6s} | {"当前累计实体":30s} | {"当前值":>8s} | {"推荐替换为":35s} | {"推荐值":>8s}')
print('-' * 85)

# 每个设备的分析结果
analysis = [
    ('豆浆机',   'sensor.doujiangji_total_kwh_v2',       None,
     'sensor.dou_jiang_ji_ben_nian_yong_dian_kwh',      None,  '⚠️ 需查找年度模板'),
    ('烤箱',     'sensor.oven_total_kwh_v2',              None,
     None,                                              None,  '✅ 用量极小，无需改'),
    ('卧室空调', 'sensor.208907222021213_total_...',     285.50,
     None,                                              None,  '✅ 已正确(原生传感器)'),
    ('客厅空调', 'sensor.210006733703670_total_...',     639.60,
     None,                                              None,  '✅ 已正确(原生传感器)'),
    ('取暖器',   'sensor.heater_total_kwh_v2',            None,
     None,                                              None,  '✅ 用量极小，无需改'),
    ('电脑电源', 'sensor.computer_total_kwh_v2',          0.0023,
     'sensor.computer_yearly_energy_v2',                 114.88, '❌ 改用yearly(114.9)'),
    ('NAS',      'sensor.nas_total_kwh_v2',               0.0007,
     'sensor.naslei_ji_yong_dian',                       58.91,  '❌ 改用累计模板(58.9)'),
    ('小打印机', 'sensor.xiaoheinu_total_kwh_v2',         None,
     None,                                              None,  '✅ 用量极小，无需改'),
    ('大打印机', 'sensor.daheinu_total_kwh_v2',           None,
     'sensor.daheinu_yearly_energy_v2',                  30.12,  '❌ 改用yearly(30.1)'),
    ('洗衣机',   'sensor.washer_total_kwh_v2',            None,
     None,                                              None,  '✅ 用量极小，无需改'),
]

for device, cur_eid, cur_val, rec_eid, rec_val, note in analysis:
    cur_s = f'{cur_val:.4f}' if cur_val is not None else 'N/A'
    rec_s = f'{rec_val:.2f}' if rec_val is not None else 'N/A'
    cur_name = (cur_eid or '').replace('sensor.', '')[:28]
    rec_name = (rec_eid or '').replace('sensor.', '')[:33]
    print(f'{device:^6s} | {cur_name:30s} | {cur_s:>8s} | {rec_name:35s} | {rec_s:>8s}  {note}')

print()
print('结论:')
print('  _v2_total_kwh 是 utility_meter 的短期计数器（已被重置），不能代表真正的累计')
print('  替代方案：使用 yearly_energy_v2（本年累计）或 lei_ji_yong_dian 模板传感器')
