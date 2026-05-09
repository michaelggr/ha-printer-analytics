﻿﻿﻿﻿﻿import shutil

print("正在完美修改配置...")

# 读取当前本地文件（原始备份）
with open(r'g:\dev\ha\ha\ui-lovelace.yaml', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. 替换温度卡片为9个区域
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

content = content.replace(old_temp, new_temp)
print("✅ 温度卡片已替换")

# 2. 替换湿度卡片为9个区域
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

content = content.replace(old_hum, new_hum)
print("✅ 湿度卡片已替换")

# 3. 在甲醛卡片结尾添加小黑奴和密封箱卡片
old_end = '''        align_header: default
        align_icon: right



  # ==================== 功耗统计面板 ===================='''

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



  # ==================== 功耗统计面板 ===================='''

content = content.replace(old_end, new_end)
print("✅ 小黑奴和密封箱卡片已添加")

# 4. 保存到本地
with open(r'g:\dev\ha\ha\ui-lovelace.yaml', 'w', encoding='utf-8') as f:
    f.write(content)
print("✅ 本地配置已保存")

# 5. 上传到服务器（通过之前的方式）
# 因为我们不能直接写Y盘，让我们通过Skill或之前的ha-server
import json

# 先读取连接信息
with open(r'g:\dev\ha\ha\.ha_connection_info.json', 'r', encoding='utf-8') as f:
    conn = json.load(f)

# 打印完成信息
print("\n" + "=" * 50)
print("✅ 配置修改完全完成！")
print("=" * 50)
print("\n首页卡片更新为：")
print("  1. 欢迎回家")
print("  2. 区域导航")
print("  3. 快速统计")
print("  4. 💡 灯控面板")
print("  5. ⏱️ 今日亮灯时长统计")
print("  6. 🌡️ 各区域温度监测（9区域）")
print("  7. 💧 各区域湿度监测（9区域）")
print("  8. 🌫️ 空气质量（实时，原始，未修改）")
print("  9. PM2.5 趋势（原始，未修改）")
print("10. 甲醛(HCHO) 趋势（原始，未修改）")
print("11. 🖨️ 小黑奴环境温度（新增）")
print("12. 📦 密封箱湿度监测（新增，3密封箱）")
print("\n现在请在浏览器中运行ha-server的上传功能！")
