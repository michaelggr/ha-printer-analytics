﻿﻿﻿﻿﻿import shutil

print("添加小黑奴和密封箱卡片...")

# 读取当前文件
with open(r'g:\dev\ha\ha\ui-lovelace.yaml', 'r', encoding='utf-8') as f:
    content = f.read()

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

# 保存并上传
with open(r'g:\dev\ha\ha\ui-lovelace.yaml', 'w', encoding='utf-8') as f:
    f.write(content)
shutil.copy(r'g:\dev\ha\ha\ui-lovelace.yaml', r'Y:\ui-lovelace.yaml')

print("\n✅ 全部完成！")
print("\n首页卡片现在为：")
print("  1. 欢迎回家")
print("  2. 区域导航")
print("  3. 快速统计")
print("  4. 💡 灯控面板")
print("  5. ⏱️ 今日亮灯时长统计")
print("  6. 🌡️ 各区域温度监测（9区域）")
print("  7. 💧 各区域湿度监测（9区域）")
print("  8. 🌫️ 空气质量")
print("  9. PM2.5 趋势")
print("10. 甲醛(HCHO) 趋势")
print("11. 🖨️ 小黑奴环境温度")
print("12. 📦 密封箱湿度监测")
