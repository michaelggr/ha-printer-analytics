﻿import urllib.request, json

# 先清理 templates.yaml 中的测试条目
with open(r'\\192.168.0.130\config\templates.yaml', 'r', encoding='utf-8') as f:
    content = f.read()

marker = '# 测试亮灯时长 template sensor'
idx = content.find(marker)
if idx != -1:
    content = content[:idx].rstrip()

# 添加一个与现有格式完全一致的 template sensor
# 现有格式：name 不带引号，unit_of_measurement 不带引号，state 用单引号
new_entry = '''

- sensor:
    name: 厨房灯周亮灯时长h
    unique_id: chu_fang_deng_zhou_liang_deng_shi_chang_h
    unit_of_measurement: 小时
    device_class: duration
    icon: mdi:clock-outline
    state: >
      {{ (states('sensor.chu_fang_deng_zhou_liang_deng_shi_chang') | float(0) / 3600) | round(1) }}
'''

with open(r'\\192.168.0.130\config\templates.yaml', 'w', encoding='utf-8') as f:
    f.write(content + new_entry)

print('已添加测试传感器（匹配现有格式）')
