﻿import urllib.request, json

# 通过 HA UI API 创建 template helper
# 每个灯的日/周/月/年亮灯时长

LIGHTS = [
    {'name': '客厅吸顶灯', 'prefix': 'ke_ting_xi_ding_deng'},
    {'name': '客厅沙发灯', 'prefix': 'ke_ting_sha_fa_deng'},
    {'name': '卧室灯', 'prefix': 'wo_shi_deng'},
    {'name': '卧室灯带', 'prefix': 'wo_shi_deng_dai'},
    {'name': '厨房灯', 'prefix': 'chu_fang_deng'},
    {'name': '餐厅灯', 'prefix': 'can_ting_deng'},
    {'name': '卫生间灯', 'prefix': 'wei_sheng_jian_deng'},
    {'name': '浴霸灯', 'prefix': 'yu_ba_deng'},
    {'name': '走廊走道灯', 'prefix': 'zou_lang_zou_dao_deng'},
    {'name': '走廊卫生间灯', 'prefix': 'zou_lang_wei_sheng_jian_deng'},
    {'name': '门口筒灯', 'prefix': 'men_kou_tong_deng'},
]

PERIODS = [
    {'label': '日', 'suffix': 'ri', 'um_suffix': '_ri_liang_deng_shi_chang'},
    {'label': '周', 'suffix': 'zhou', 'um_suffix': '_zhou_liang_deng_shi_chang'},
    {'label': '月', 'suffix': 'yue', 'um_suffix': '_yue_liang_deng_shi_chang'},
    {'label': '年', 'suffix': 'nian', 'um_suffix': '_nian_liang_deng_shi_chang'},
]

TOKEN = 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiI1M2Q4NzBkOGY4M2U0YWY3ODIzNTJlNjVkNmVkYzY5YSIsImlhdCI6MTc3NDE5NTM2MCwiZXhwIjoyMDg5NTU1MzYwfQ.7VKORHi3sWJfROnc7HKzDyY1uwapDC8WXdLIj4sAITs'
BASE_URL = 'http://192.168.0.130:8123/api/config/config_entries/flow'

created = 0
errors = 0

for light in LIGHTS:
    for period in PERIODS:
        um_entity = f'sensor.{light["prefix"]}{period["um_suffix"]}'
        name = f'{light["name"]}{period["label"]}亮灯时长h'
        unique_id = f'{light["prefix"]}_{period["suffix"]}_liang_deng_shi_chang_h'
        template = f'{{{{ (states(\'{um_entity}\') | float(0) / 3600) | round(1) }}}}'

        # Step 1: Init flow
        init_data = json.dumps({
            'handler': 'template',
            'show_advanced_options': False
        }).encode()

        req = urllib.request.Request(
            f'{BASE_URL}',
            data=init_data,
            headers={
                'Authorization': TOKEN,
                'Content-Type': 'application/json'
            },
            method='POST'
        )

        try:
            resp = urllib.request.urlopen(req, timeout=10)
            flow = json.loads(resp.read())
            flow_id = flow.get('flow_id')

            # Step 2: Configure the sensor
            config_data = json.dumps({
                'name': name,
                'template_type': 'sensor',
                'unit_of_measurement': '小时',
                'device_class': 'duration',
                'state': template,
                'unique_id': unique_id,
                'icon': 'mdi:clock-outline'
            }).encode()

            req2 = urllib.request.Request(
                f'{BASE_URL}/{flow_id}',
                data=config_data,
                headers={
                    'Authorization': TOKEN,
                    'Content-Type': 'application/json'
                },
                method='POST'
            )

            resp2 = urllib.request.urlopen(req2, timeout=10)
            result = json.loads(resp2.read())
            created += 1
            print(f'OK: {name}')

        except urllib.error.HTTPError as e:
            error_body = e.read().decode()
            errors += 1
            print(f'ERROR: {name} - {e.code} - {error_body[:100]}')
        except Exception as e:
            errors += 1
            print(f'ERROR: {name} - {str(e)[:100]}')

print(f'\nCreated: {created}, Errors: {errors}')
