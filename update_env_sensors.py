﻿﻿﻿﻿﻿
import shutil

# 读取当前配置
with open(r'Y:\ui-lovelace.yaml', 'r', encoding='utf-8') as f:
    config = f.read()

# 要替换的旧温湿度+空气质量部分
old_part = '''      # ==================== 温湿度监测 ====================

      # 温度曲线（多环境对比）
      - type: custom:mini-graph-card
        title: 🌡️ 温度监测
        icon: mdi:thermometer
        entities:
          - entity: sensor.zm1_b0f8931ee681_temperature
            name: 室内
            color: "#f44336"
          - entity: sensor.miaomiaoc_cn_blt_3_14n419k7k5k01_t2_temperature_p_2_1
            name: 客厅
            color: "#2196f3"
          - entity: sensor.vchon_cn_blt_3_1lgrvovgoc400_mbs17_temperature_p_2_1001
            name: 书房
            color: "#4caf50"
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

      # 湿度曲线（多环境对比）
      - type: custom:mini-graph-card
        title: 💧 湿度监测
        icon: mdi:water-percent
        entities:
          - entity: sensor.zm1_b0f8931ee681_humidity
            name: 室内
            color: "#00bcd4"
          - entity: sensor.miaomiaoc_cn_blt_3_14n419k7k5k01_t2_relative_humidity_p_2_2
            name: 客厅
            color: "#9c27b0"
          - entity: sensor.vchon_cn_blt_3_1lgrvovgoc400_mbs17_relative_humidity_p_2_1002
            name: 书房
            color: "#ff9800"
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

      # ==================== 空气质量监测 ====================

      # PM2.5 和甲醛实时数值
      - type: glance
        title: 🌫️ 空气质量
        entities:
          - entity: sensor.zm1_b0f8931ee681_pm25
            name: PM2.5
          - entity: sensor.zm1_b0f8931ee681_hcho
            name: 甲醛
        show_state: true
        show_icon: true

      # PM2.5 趋势曲线
      - type: custom:mini-graph-card
        title: PM2.5 趋势
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
        align_header: default
        align_icon: right

      # 甲醛趋势曲线
      - type: custom:mini-graph-card
        title: 甲醛(HCHO) 趋势
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
        align_header: default
        align_icon: right'''

# 新的完整温湿度+空气质量部分
new_part = '''      # ==================== 温湿度监测 ====================

      # 温度曲线（9个区域）
      - type: custom:mini-graph-card
        title: 🌡️ 温度监测
        icon: mdi:thermometer
        entities:
          - entity: sensor.zm1_b0f8931ee681_temperature
            name: 客厅
            color: "#f44336"
          - entity: sensor.miaomiaoc_cn_blt_3_14n419k7k5k01_t2_temperature_p_2_1
            name: 厨房
            color: "#2196f3"
          - entity: sensor.miaomiaoc_cn_blt_3_1lip7b874ck01_t2_temperature_p_2_1
            name: 卧室
            color: "#4caf50"
          - entity: sensor.vchon_cn_blt_3_1lgrvovgoc400_mbs17_temperature_p_2_1001
            name: 大阳台
            color: "#ff9800"
          - entity: sensor.linp_cn_blt_3_1ll1gt2c10c00_ks2bb_temperature_p_2_1001
            name: 卫生间
            color: "#9c27b0"
          - entity: sensor.linp_cn_blt_3_1nb2mr6n44s00_ks2bb_temperature_p_2_1001
            name: 门口
            color: "#00bcd4"
          - entity: sensor.ym001_cn_blt_3_1o90bni4h0g00_ymwsdj_temperature_p_2_1001
            name: 洗衣机阳台
            color: "#795548"
          - entity: sensor.vchon_cn_blt_3_1o931kgud0400_mbs17_temperature_p_2_1001
            name: 主卧
            color: "#607d8b"
          - entity: sensor.ym001_cn_blt_3_1o9vhlvug4403_ymwsdj_temperature_p_2_1001
            name: 室外
            color: "#e91e63"
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

      # 湿度曲线（9个区域）
      - type: custom:mini-graph-card
        title: 💧 湿度监测
        icon: mdi:water-percent
        entities:
          - entity: sensor.zm1_b0f8931ee681_humidity
            name: 客厅
            color: "#f44336"
          - entity: sensor.miaomiaoc_cn_blt_3_14n419k7k5k01_t2_relative_humidity_p_2_2
            name: 厨房
            color: "#2196f3"
          - entity: sensor.miaomiaoc_cn_blt_3_1lip7b874ck01_t2_relative_humidity_p_2_2
            name: 卧室
            color: "#4caf50"
          - entity: sensor.vchon_cn_blt_3_1lgrvovgoc400_mbs17_relative_humidity_p_2_1002
            name: 大阳台
            color: "#ff9800"
          - entity: sensor.linp_cn_blt_3_1ll1gt2c10c00_ks2bb_relative_humidity_p_2_1002
            name: 卫生间
            color: "#9c27b0"
          - entity: sensor.linp_cn_blt_3_1nb2mr6n44s00_ks2bb_relative_humidity_p_2_1002
            name: 门口
            color: "#00bcd4"
          - entity: sensor.ym001_cn_blt_3_1o90bni4h0g00_ymwsdj_relative_humidity_p_2_1002
            name: 洗衣机阳台
            color: "#795548"
          - entity: sensor.vchon_cn_blt_3_1o931kgud0400_mbs17_relative_humidity_p_2_1002
            name: 主卧
            color: "#607d8b"
          - entity: sensor.ym001_cn_blt_3_1o9vhlvug4403_ymwsdj_relative_humidity_p_2_1002
            name: 室外
            color: "#e91e63"
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

      # ==================== 小黑奴 & 耗材 ====================

      # 小黑奴温度
      - type: custom:mini-graph-card
        title: 🖨️ 小黑奴温度
        icon: mdi:printer-3d
        entities:
          - entity: sensor.qjiang_cn_blt_3_1n7f0sntk4s01_002_temperature_p_2_1001
            name: 耗材密封箱
            color: "#ff9800"
          - entity: sensor.p2s_22e8bj5a2401765_ams_1_temperature
            name: 打印机
            color: "#4caf50"
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

      # 耗材区域湿度
      - type: custom:mini-graph-card
        title: 📦 耗材区域湿度
        icon: mdi:drop
        entities:
          - entity: sensor.qjiang_cn_blt_3_1n7f0sntk4s01_002_relative_humidity_p_2_1002
            name: 耗材密封箱
            color: "#4caf50"
          - entity: sensor.p2s_22e8bj5a2401765_ams_1_humidity
            name: 大密封箱
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

      # ==================== 空气质量监测 ====================

      # PM2.5 趋势曲线
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
        align_header: default
        align_icon: right
        group: false

      # 甲醛趋势曲线
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
        align_header: default
        align_icon: right
        group: false

      # 空气质量实时数值
      - type: glance
        title: 📊 空气质量实时
        entities:
          - entity: sensor.zm1_b0f8931ee681_pm25
            name: PM2.5
          - entity: sensor.zm1_b0f8931ee681_hcho
            name: 甲醛
        show_state: true
        show_icon: true'''

# 替换配置
new_config = config.replace(old_part, new_part)

# 保存到本地
local_file = r'g:\dev\ha\ha\ui-lovelace.yaml'
with open(local_file, 'w', encoding='utf-8') as f:
    f.write(new_config)
print("本地配置更新成功！")

# 保存到服务器
server_file = r'Y:\ui-lovelace.yaml'
shutil.copyfile(local_file, server_file)
print("服务器配置更新成功！🎉")

print("\n✅ 完成！请刷新浏览器查看！")
