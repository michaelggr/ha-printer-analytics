﻿﻿﻿﻿﻿import shutil

with open(r'Y:\ui-lovelace.yaml', 'r', encoding='utf-8') as f:
    config = f.read()

# 精确匹配的旧配置
old_part = """      # ==================== 空气质量监测 ====================

      # PM2.5 和甲醛趋势曲线（合并）
      - type: custom:mini-graph-card
        title: 🌫️ 空气质量趋势
        icon: mdi:blur
        entities:
          - entity: sensor.zm1_b0f8931ee681_pm25
            name: PM2.5
            color: "#f44336"
          - entity: sensor.zm1_b0f8931ee681_hcho
            name: 甲醛
            color: "#2196f3"
        line_width: 2
        hours_to_show: 24
        points_per_hour: 2
        show:
          graph: line
          legend: true
          fill: false
          points: false
        align_header: default
        align_icon: right
        group: false

      # 空气质量实时数值（保留）
      - type: glance
        title: 📊 空气质量实时
        entities:
          - entity: sensor.zm1_b0f8931ee681_pm25
            name: PM2.5
          - entity: sensor.zm1_b0f8931ee681_hcho
            name: 甲醛
        show_state: true
        show_icon: true"""

new_part = """      # ==================== 空气质量监测 ====================

      # PM2.5 趋势曲线（带Y轴）
      - type: custom:mini-graph-card
        title: 🌫️ PM2.5 趋势
        icon: mdi:blur
        entity: sensor.zm1_b0f8931ee681_pm25
        line_width: 2
        hours_to_show: 24
        points_per_hour: 2
        color_thresholds:
          - value: 0
            color: "#4caf50"
          - value: 35
            color: "#ffeb3b"
          - value: 75
            color: "#ff9800"
          - value: 115
            color: "#f44336"
        show:
          graph: line
          legend: false
          fill: true
          points: false
          labels: true
          extrema: true
        align_header: default
        align_icon: right

      # 甲醛趋势曲线（带Y轴）
      - type: custom:mini-graph-card
        title: 🌫️ 甲醛(HCHO) 趋势
        icon: mdi:chemical-weapon
        entity: sensor.zm1_b0f8931ee681_hcho
        line_width: 2
        hours_to_show: 24
        points_per_hour: 2
        color_thresholds:
          - value: 0
            color: "#4caf50"
          - value: 0.08
            color: "#ffeb3b"
          - value: 0.1
            color: "#ff9800"
          - value: 0.3
            color: "#f44336"
        show:
          graph: line
          legend: false
          fill: true
          points: false
          labels: true
          extrema: true
        align_header: default
        align_icon: right

      # 空气质量实时数值（保留）
      - type: glance
        title: 📊 空气质量实时
        entities:
          - entity: sensor.zm1_b0f8931ee681_pm25
            name: PM2.5
          - entity: sensor.zm1_b0f8931ee681_hcho
            name: 甲醛
        show_state: true
        show_icon: true"""

# 检查是否匹配成功
if old_part in config:
    print("找到匹配的配置，正在替换...")
    new_config = config.replace(old_part, new_part)
    with open(r'Y:\ui-lovelace.yaml', 'w', encoding='utf-8') as f:
        f.write(new_config)
    print("配置文件更新成功！")
    
    # 同时更新本地文件
    with open(r'g:\dev\ha\ha\ui-lovelace.yaml', 'w', encoding='utf-8') as f:
        f.write(new_config)
    print("本地配置文件也已更新。")
else:
    print("没有找到匹配的配置内容！")
    print("请检查配置格式。")

print("\n配置更新完成，请刷新Home Assistant页面查看！")