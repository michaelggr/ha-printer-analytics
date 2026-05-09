﻿import urllib.request, json, time

TOKEN = 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiI1M2Q4NzBkOGY4M2U0YWY3ODIzNTJlNjVkNmVkYzY5YSIsImlhdCI6MTc3NDE5NTM2MCwiZXhwIjoyMDg5NTU1MzYwfQ.7VKORHi3sWJfROnc7HKzDyY1uwapDC8WXdLIj4sAITs'
BASE_URL = 'http://192.168.0.130:8123/api/config/config_entries/flow'

# 先删除刚才创建的测试传感器（state=0 的那个）
# 然后用正确的 state template 重新创建

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

created = 0
errors = 0

for light in LIGHTS:
    for period in PERIODS:
        um_entity = f'sensor.{light["prefix"]}{period["um_suffix"]}'
        name = f'{light["name"]}{period["label"]}亮灯时长h'
        state_template = f"{{{{ (states('{um_entity}') | float(0) / 3600) | round(1) }}}}"

        try:
            # Step 1: Init flow
            init_data = json.dumps({'handler': 'template', 'show_advanced_options': True}).encode()
            req = urllib.request.Request(BASE_URL, method='POST', headers={
                'Authorization': TOKEN, 'Content-Type': 'application/json'
            }, data=init_data)
            resp = urllib.request.urlopen(req, timeout=10)
            flow = json.loads(resp.read())
            flow_id = flow['flow_id']

            # Step 2: Select sensor type
            step2_data = json.dumps({'next_step_id': 'sensor'}).encode()
            req2 = urllib.request.Request(f'{BASE_URL}/{flow_id}', method='POST', headers={
                'Authorization': TOKEN, 'Content-Type': 'application/json'
            }, data=step2_data)
            urllib.request.urlopen(req2, timeout=10)

            # Step 3: Fill sensor details
            step3_data = json.dumps({
                'name': name,
                'state': state_template,
                'unit_of_measurement': '小时',
            }).encode()
            req3 = urllib.request.Request(f'{BASE_URL}/{flow_id}', method='POST', headers={
                'Authorization': TOKEN, 'Content-Type': 'application/json'
            }, data=step3_data)
            resp3 = urllib.request.urlopen(req3, timeout=10)
            result = json.loads(resp3.read())
            created += 1
            print(f'OK: {name}')
            time.sleep(0.3)

        except urllib.error.HTTPError as e:
            error = e.read().decode()[:100]
            errors += 1
            print(f'ERROR: {name} - {error}')
        except Exception as e:
            errors += 1
            print(f'ERROR: {name} - {str(e)[:100]}')

print(f'\nCreated: {created}, Errors: {errors}')
