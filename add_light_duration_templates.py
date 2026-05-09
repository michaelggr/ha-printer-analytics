﻿LIGHTS = [
    {
        'name': '客厅吸顶灯',
        'um_sensor': 'sensor.ke_ting_xi_ding_deng_ri_liang_deng_shi_chang',
        'prefix': 'ke_ting_xi_ding_deng',
    },
    {
        'name': '客厅沙发灯',
        'um_sensor': 'sensor.ke_ting_sha_fa_deng_ri_liang_deng_shi_chang',
        'prefix': 'ke_ting_sha_fa_deng',
    },
    {
        'name': '卧室灯',
        'um_sensor': 'sensor.wo_shi_deng_ri_liang_deng_shi_chang',
        'prefix': 'wo_shi_deng',
    },
    {
        'name': '卧室灯带',
        'um_sensor': 'sensor.wo_shi_deng_dai_ri_liang_deng_shi_chang',
        'prefix': 'wo_shi_deng_dai',
    },
    {
        'name': '厨房灯',
        'um_sensor': 'sensor.chu_fang_deng_ri_liang_deng_shi_chang',
        'prefix': 'chu_fang_deng',
    },
    {
        'name': '餐厅灯',
        'um_sensor': 'sensor.can_ting_deng_ri_liang_deng_shi_chang',
        'prefix': 'can_ting_deng',
    },
    {
        'name': '卫生间灯',
        'um_sensor': 'sensor.wei_sheng_jian_deng_ri_liang_deng_shi_chang',
        'prefix': 'wei_sheng_jian_deng',
    },
    {
        'name': '浴霸灯',
        'um_sensor': 'sensor.yu_ba_deng_ri_liang_deng_shi_chang',
        'prefix': 'yu_ba_deng',
    },
    {
        'name': '走廊走道灯',
        'um_sensor': 'sensor.zou_lang_zou_dao_deng_ri_liang_deng_shi_chang',
        'prefix': 'zou_lang_zou_dao_deng',
    },
    {
        'name': '走廊卫生间灯',
        'um_sensor': 'sensor.zou_lang_wei_sheng_jian_deng_ri_liang_deng_shi_chang',
        'prefix': 'zou_lang_wei_sheng_jian_deng',
    },
    {
        'name': '门口筒灯',
        'um_sensor': 'sensor.men_kou_tong_deng_ri_liang_deng_shi_chang',
        'prefix': 'men_kou_tong_deng',
    },
]

PERIODS = [
    {'label': '日', 'suffix': 'ri', 'um_suffix': '_ri_liang_deng_shi_chang'},
    {'label': '周', 'suffix': 'zhou', 'um_suffix': '_zhou_liang_deng_shi_chang'},
    {'label': '月', 'suffix': 'yue', 'um_suffix': '_yue_liang_deng_shi_chang'},
    {'label': '年', 'suffix': 'nian', 'um_suffix': '_nian_liang_deng_shi_chang'},
]

lines = []
lines.append('')
lines.append('# 亮灯时长 template sensors（秒→小时，修复 utility_meter 的 kWh 单位问题）')

for light in LIGHTS:
    for period in PERIODS:
        um_entity = f'sensor.{light["prefix"]}{period["um_suffix"]}'
        unique_id = f'{light["prefix"]}_{period["suffix"]}_liang_deng_shi_chang_h'
        name = f'{light["name"]}{period["label"]}亮灯时长'

        lines.append('')
        lines.append('- sensor:')
        lines.append(f'    name: "{name}"')
        lines.append(f'    unique_id: {unique_id}')
        lines.append(f'    unit_of_measurement: "小时"')
        lines.append(f'    device_class: duration')
        lines.append(f'    icon: mdi:clock-outline')
        lines.append(f'    state: >')
        lines.append(f'      {{{{ (states(\'{um_entity}\') | float(0) / 3600) | round(1) }}}}')

# 全屋灯光
for period in PERIODS:
    um_entity = f'sensor.quan_wu_deng_guang_{period["suffix"]}liang_deng_zong_shi_chang'
    if period['suffix'] == 'ri':
        um_entity = 'sensor.quan_wu_deng_guang_riliang_deng_zong_shi_chang'
    unique_id = f'quan_wu_deng_guang_{period["suffix"]}_liang_deng_shi_chang_h'
    name = f'全屋灯光{period["label"]}亮灯总时长'

    lines.append('')
    lines.append('- sensor:')
    lines.append(f'    name: "{name}"')
    lines.append(f'    unique_id: {unique_id}')
    lines.append(f'    unit_of_measurement: "小时"')
    lines.append(f'    device_class: duration')
    lines.append(f'    icon: mdi:clock-outline')
    lines.append(f'    state: >')
    lines.append(f'      {{{{ (states(\'{um_entity}\') | float(0) / 3600) | round(1) }}}}')

output = '\n'.join(lines)

with open(r'\\192.168.0.130\config\templates.yaml', 'a', encoding='utf-8') as f:
    f.write(output)

print(f'已添加 {len(LIGHTS) * len(PERIODS) + len(PERIODS)} 个亮灯时长 template sensor')
