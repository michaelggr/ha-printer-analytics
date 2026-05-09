﻿﻿﻿﻿﻿import shutil
from datetime import datetime

print("正在正确修改温湿度卡片为9个区域...")

# 从原始备份开始
with open(r'g:\dev\ha\ha\ui-lovelace.yaml.backup_20260429', 'r', encoding='utf-8') as f:
    config = f.read()

# 备份当前状态
backup_file = r'Y:\ui-lovelace.yaml.backup_' + datetime.now().strftime('%Y%m%d_%H%M%S')
shutil.copyfile(r'Y:\ui-lovelace.yaml', backup_file)
print(f"已备份当前状态到: {backup_file}")

# ================== 1. 修改原始温度卡片为9区域 ==================
old_temp_card = '''      # 温度曲线（多环境对比）
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

new_temp_card = '''      # 温度曲线（9区域对比）
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

config = config.replace(old_temp_card, new_temp_card)

# ================== 2. 修改原始湿度卡片为9区域 ==================
old_humidity_card = '''      # 湿度曲线（多环境对比）
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

new_humidity_card = '''      # 湿度曲线（9区域对比）
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

config = config.replace(old_humidity_card, new_humidity_card)

# ================== 3. 在空气质量后面添加小黑奴和密封箱卡片 ==================
old_after_air = '''      # 甲醛趋势曲线
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
        align_icon: right

  # ==================== 功耗统计面板 ===================='''

new_after_air = '''      # 甲醛趋势曲线
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

  # ==================== 功耗统计面板 ===================='''

config = config.replace(old_after_air, new_after_air)

# 保存配置
with open(r'g:\dev\ha\ha\ui-lovelace.yaml', 'w', encoding='utf-8') as f:
    f.write(config)
shutil.copyfile(r'g:\dev\ha\ha\ui-lovelace.yaml', r'Y:\ui-lovelace.yaml')

print("\n✅ 配置更新完成！")
print("首页卡片数量：10个原始 → 12个（2个新增）")
print("\n修改内容：")
print("  1. 温度监测：3个区域 → 9个区域（客厅、厨房、卧室、大阳台、卫生间、门口、洗衣机阳台、主卧、室外）")
print("  2. 湿度监测：3个区域 → 9个区域（同上）")
print("  3. 新增：🖨️ 小黑奴环境温度")
print("  4. 新增：📦 密封箱湿度监测（3个密封箱）")
print("\n空气质量卡片保持原样，没有修改！")
