﻿import urllib.request, json

token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiI3Y2EyNjc2MzdmZGU0YzliOWQ3Y2Y3ODM3N2YwMzA5ZSIsImlhdCI6MTc3ODk2OTYzNCwiZXhwIjoyMDk0MzI5NjM0fQ.iFan1gdP67hAY5jn0ilFABv98DbA79TFTHg76PyNhJY'
hdr = {'Authorization': f'Bearer {token}'}
base = 'http://192.168.0.130:8123/api/states/'

# 详细查看 NAS 相关传感器的完整属性
nas_sensors = [
    'sensor.naszhou_yong_dian_liang',
    'sensor.naslei_ji_yong_dian',
    'sensor.nas_yearly_energy_v2',
    'sensor.nasben_zhou_yong_dian_kwh',
]

print('NAS 传感器详细信息:')
print('=' * 80)
for eid in nas_sensors:
    try:
        req = urllib.request.Request(base + eid, headers=hdr)
        data = json.loads(urllib.request.urlopen(req, timeout=10).read())
        attrs = data.get('attributes', {})
        print(f'实体: {eid}')
        print(f'  state     = {data["state"]}')
        print(f'  unit      = {attrs.get("unit_of_measurement", "无")}')
        print(f'  device_class = {attrs.get("device_class", "无")}')
        print(f'  friendly_name = {attrs.get("friendly_name", "无")}')
        # 检查是否有其他关键属性
        for k, v in attrs.items():
            if k not in ('unit_of_measurement', 'device_class', 'friendly_name', 'icon'):
                print(f'  {k} = {v}')
        print()
    except Exception as e:
        print(f'{eid}: 不存在 ({e})')
        print()
