﻿﻿﻿﻿﻿import shutil
from datetime import datetime

# 从服务器读取当前配置
with open(r'Y:\ui-lovelace.yaml', 'r', encoding='utf-8') as f:
    config = f.read()

# 备份
backup_file = r'Y:\ui-lovelace.yaml.backup_' + datetime.now().strftime('%Y%m%d_%H%M%S')
shutil.copyfile(r'Y:\ui-lovelace.yaml', backup_file)
print(f"已备份到: {backup_file}")

# 1. 替换小黑奴：湿度→温度
old_xhn = '''      # 小黑奴湿度曲线
      - type: custom:mini-graph-card
        title: 🖨️ 小黑奴环境湿度
        icon: mdi:printer-3d
        entities:
          - entity: sensor.qjiang_cn_blt_3_1n7f0sntk4s01_002_relative_humidity_p_2_1002
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
        group: false'''

new_xhn = '''      # 小黑奴温度曲线
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
        group: false'''

# 2. 替换密封箱：单个→全部3个密封箱湿度
old_mifeng = '''      # 耗材湿度曲线
      - type: custom:mini-graph-card
        title: 📦 耗材密封箱湿度
        icon: mdi:package-variant
        entities:
          - entity: sensor.vchon_cn_blt_3_1nf9gjb3k4000_mbs17_relative_humidity_p_2_1002
            name: 耗材密封箱
            color: "#795548"
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

new_mifeng = '''      # 密封箱湿度曲线（全部密封箱）
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
        group: false'''

# 执行替换
new_config = config.replace(old_xhn, new_xhn)
new_config = new_config.replace(old_mifeng, new_mifeng)

# 验证替换是否成功
if new_config == config:
    print("⚠️ 未找到匹配的旧配置，尝试查找...")
    # 查找小黑奴相关内容
    if "小黑奴" in config:
        idx = config.find("小黑奴")
        print(f"找到小黑奴在位置 {idx}")
        print(f"上下文: ...{config[max(0,idx-100):idx+200]}...")
    if "密封箱" in config:
        idx = config.find("密封箱")
        print(f"找到密封箱在位置 {idx}")
        print(f"上下文: ...{config[max(0,idx-100):idx+200]}...")
else:
    print("✅ 替换成功！")

    # 保存到本地
    with open(r'g:\dev\ha\ha\ui-lovelace.yaml', 'w', encoding='utf-8') as f:
        f.write(new_config)
    print("本地配置已更新")

    # 保存到服务器
    shutil.copyfile(r'g:\dev\ha\ha\ui-lovelace.yaml', r'Y:\ui-lovelace.yaml')
    print("服务器配置已更新 🎉")
