﻿﻿﻿﻿﻿import shutil
from datetime import datetime

print("正在用最简单的方式处理...")

# 1. 完全恢复原始备份
shutil.copy(r'g:\dev\ha\ha\ui-lovelace.yaml.backup_20260429', r'Y:\ui-lovelace.yaml')
shutil.copy(r'g:\dev\ha\ha\ui-lovelace.yaml.backup_20260429', r'g:\dev\ha\ha\ui-lovelace.yaml')

# 2. 读取完整原始配置
with open(r'g:\dev\ha\ha\ui-lovelace.yaml', 'r', encoding='utf-8') as f:
    full_config = f.read()

# 3. 替换温度卡片
old_temp = '''      # 温度曲线（多环境对比）
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
        group: false'''

new_temp = '''      # 温度曲线（9区域对比）
      - type: custom:mini-graph-card
        title: 🌡️ 各区域温度监测
        icon: mdi:thermometer
        entities:
          - entity: sensor.miaomiaoc_cn_blt_3_11c1qp540lc00_t2_temperature_p_2_1
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
            color: "#e91e63"
          - entity: sensor.vchon_cn_blt_3_1o931kgud0400_mbs17_temperature_p_2_1001
            name: 主卧
            color: "#673ab7"
          - entity: sensor.ym001_cn_blt_3_1o9vhlvug4403_ymwsdj_temperature_p_2_1001
            name: 室外
            color: "#009688"
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
        group: false'''

full_config = full_config.replace(old_temp, new_temp)

# 4. 替换湿度卡片
old_hum = '''      # 湿度曲线（多环境对比）
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
        group: false'''

new_hum = '''      # 湿度曲线（9区域对比）
      - type: custom:mini-graph-card
        title: 💧 各区域湿度监测
        icon: mdi:water-percent
        entities:
          - entity: sensor.miaomiaoc_cn_blt_3_11c1qp540lc00_t2_relative_humidity_p_2_2
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
            color: "#e91e63"
          - entity: sensor.vchon_cn_blt_3_1o931kgud0400_mbs17_relative_humidity_p_2_1002
            name: 主卧
            color: "#673ab7"
          - entity: sensor.ym001_cn_blt_3_1o9vhlvug4403_ymwsdj_relative_humidity_p_2_1002
            name: 室外
            color: "#009688"
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
        group: false'''

full_config = full_config.replace(old_hum, new_hum)

# 5. 添加小黑奴和密封箱卡片，这次完全用原始甲醛结尾内容
old_end = '''        align_header: default
        align_icon: right

'''

new_end = '''        align_header: default
        align_icon: right

      # ==================== 新增：小黑奴和密封箱 ====================

      # 小黑奴环境温度曲线
      - type: custom:mini-graph-card
        title: 🖨️ 小黑奴环境温度
        icon: mdi:printer-3d
        entities:
          - entity: sensor.qjiang_cn_blt_3_1n7f0sntk4s01_002_temperature_p_2_1001
            name: 小黑奴环境
            color: "#ff5722"
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

      # 密封箱湿度曲线（全部3个）
      - type: custom:mini-graph-card
        title: 📦 密封箱湿度监测
        icon: mdi:package-variant
        entities:
          - entity: sensor.vchon_cn_blt_3_1nf9gjb3k4000_mbs17_relative_humidity_p_2_1002
            name: 耗材密封箱
            color: "#795548"
          - entity: sensor.ym001_cn_blt_3_1ng77ce2p0c00_ymwsdj_relative_humidity_p_2_1002
            name: 大密封箱
            color: "#2196f3"
          - entity: sensor.ym001_cn_blt_3_1o9lb3n2p0o00_ymwsdj_relative_humidity_p_2_1002
            name: 耗材空余智能
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

'''

full_config = full_config.replace(old_end, new_end)

# 6. 保存！
with open(r'g:\dev\ha\ha\ui-lovelace.yaml', 'w', encoding='utf-8') as f:
    f.write(full_config)
shutil.copy(r'g:\dev\ha\ha\ui-lovelace.yaml', r'Y:\ui-lovelace.yaml')

print("\n✅ 完全完成！")
