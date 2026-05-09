﻿﻿﻿﻿﻿import shutil

with open(r'g:\dev\ha\ha\ui-lovelace.yaml', 'r', encoding='utf-8') as f:
    config = f.read()

old_air = """      # ==================== 空气质量监测 ====================

      # PM2.5 和甲醛趋势曲线（双Y轴）
      - type: custom:apexcharts-card
        header:
          show: true
          title: 🌫️ 空气质量趋势
          show_states: true
        graph_span: 24h
        apex_config:
          chart:
            type: line
          legend:
            show: true
          yaxis:
            - title:
                text: PM2.5 (μg/m³)
              min: 0
              max: 150
              decimals: 0
            - title:
                text: 甲醛 (mg/m³)
              opposite: true
              min: 0
              max: 0.5
              decimals: 3
          stroke:
            curve: smooth
        series:
          - entity: sensor.zm1_b0f8931ee681_pm25
            name: PM2.5
            color: "#f44336"
            type: line
          - entity: sensor.zm1_b0f8931ee681_hcho
            name: 甲醛
            color: "#2196f3"
            type: line
            yaxis_id: 1

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

new_air = """      # ==================== 空气质量监测 ====================

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

new_config = config.replace(old_air, new_air)

with open(r'g:\dev\ha\ha\ui-lovelace.yaml', 'w', encoding='utf-8') as f:
    f.write(new_config)

print("本地配置更新成功！")

src_file = r'g:\dev\ha\ha\ui-lovelace.yaml'
dst_file = r'Y:\ui-lovelace.yaml'

try:
    shutil.copyfile(src_file, dst_file)
    print("配置文件上传到服务器成功！")
except Exception as e:
    print(f"上传失败: {e}")