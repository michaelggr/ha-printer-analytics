﻿import urllib.request, json

token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiI3Y2EyNjc2MzdmZGU0YzliOWQ3Y2Y3ODM3N2YwMzA5ZSIsImlhdCI6MTc3ODk2OTYzNCwiZXhwIjoyMDk0MzI5NjM0fQ.iFan1gdP67hAY5jn0ilFABv98DbA79TFTHg76PyNhJY'
hdr = {'Authorization': f'Bearer {token}'}
base = 'http://192.168.0.130:8123/api/states/'

# 神秘传感器：值大但不在 templates.yaml 中定义
mystery = [
    'sensor.dian_nao_dian_yuan_lei_ji_yong_dian',      # 75.35 kWh
    'sensor.dian_nao_dian_yuan_lei_ji_yong_dian_kwh',   # ? (utility_meter source)
    'sensor.naslei_ji_yong_dian',                        # 58.93 kWh
    'sensor.xiao_da_yin_ji_lei_ji_yong_dian',            # 1.0036 kWh
]

print('深度检查神秘传感器的完整属性:')
print('=' * 120)

for eid in mystery:
    try:
        req = urllib.request.Request(base + eid, headers=hdr)
        data = json.loads(urllib.request.urlopen(req, timeout=10).read())
        attrs = data.get('attributes', {})
        
        print(f'\n【{eid.replace("sensor.", "")}】')
        print(f'  state = {data["state"]}')
        for k, v in sorted(attrs.items()):
            if k not in ('icon',):
                print(f'  {k} = {v}')
    except Exception as e:
        print(f'\n【{eid.replace("sensor.", "")}】ERROR: {e}')

# 同时查 counter.yaml 看看有没有定义
print('\n' + '=' * 120)
print('\n检查 counter.yaml:')
