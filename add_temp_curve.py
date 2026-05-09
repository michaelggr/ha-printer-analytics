﻿﻿﻿﻿﻿import shutil
from datetime import datetime

with open(r'Y:\ui-lovelace.yaml', 'r', encoding='utf-8') as f:
    config = f.read()

backup_file = r'Y:\ui-lovelace.yaml.backup_' + datetime.now().strftime('%Y%m%d_%H%M%S')
shutil.copyfile(r'Y:\ui-lovelace.yaml', backup_file)
print(f"已备份到: {backup_file}")

# 在湿度曲线前面插入温度曲线
old_humidity = '''      # 9区域湿度曲线
      - type: custom:mini-graph-card
        title: 💧 各区域湿度监测'''

new_temp_and_humidity = '''      # 9区域温度曲线
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
        group: false

      # 9区域湿度曲线
      - type: custom:mini-graph-card
        title: 💧 各区域湿度监测'''

new_config = config.replace(old_humidity, new_temp_and_humidity)

if new_config == config:
    print("⚠️ 未找到匹配内容")
else:
    print("✅ 替换成功！")
    with open(r'g:\dev\ha\ha\ui-lovelace.yaml', 'w', encoding='utf-8') as f:
        f.write(new_config)
    shutil.copyfile(r'g:\dev\ha\ha\ui-lovelace.yaml', r'Y:\ui-lovelace.yaml')
    print("服务器配置已更新 🎉")
