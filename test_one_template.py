﻿import urllib.request, json

# 先读取当前 templates.yaml
with open(r'\\192.168.0.130\config\templates.yaml', 'r', encoding='utf-8') as f:
    content = f.read()

# 删除之前添加的亮灯时长 template sensors
marker = '# 亮灯时长 template sensors'
idx = content.find(marker)
if idx != -1:
    content = content[:idx].rstrip()
    print(f'已删除旧条目')

# 只添加一个测试传感器
test_sensor = '''

# 测试亮灯时长 template sensor
- sensor:
    name: "test_light_duration_kitchen_weekly"
    unique_id: test_light_duration_kitchen_weekly
    unit_of_measurement: "h"
    device_class: duration
    icon: mdi:clock-outline
    state: >
      {{ (states("sensor.chu_fang_deng_zhou_liang_deng_shi_chang") | float(0) / 3600) | round(1) }}
'''

with open(r'\\192.168.0.130\config\templates.yaml', 'w', encoding='utf-8') as f:
    f.write(content + test_sensor)

print('已添加测试传感器')
