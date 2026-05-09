﻿import urllib.request, json

with open(r'\\192.168.0.130\config\templates.yaml', 'r', encoding='utf-8') as f:
    content = f.read()

marker = '# 测试亮灯时长 template sensor'
idx = content.find(marker)
if idx != -1:
    content = content[:idx].rstrip()

# 不用 device_class，测试基本功能
test_sensor = '''

# 测试亮灯时长 template sensor
- sensor:
    name: "test_kitchen_weekly_hours"
    unique_id: test_kitchen_weekly_hours
    unit_of_measurement: "h"
    icon: mdi:clock-outline
    state: >
      {{ (states("sensor.chu_fang_deng_zhou_liang_deng_shi_chang") | float(0) / 3600) | round(1) }}
'''

with open(r'\\192.168.0.130\config\templates.yaml', 'w', encoding='utf-8') as f:
    f.write(content + test_sensor)

print('已添加测试传感器（无 device_class）')
