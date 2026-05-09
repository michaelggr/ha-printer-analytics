﻿﻿﻿﻿﻿import shutil
from datetime import datetime

with open(r'Y:\ui-lovelace.yaml', 'r', encoding='utf-8') as f:
    config = f.read()

backup_file = r'Y:\ui-lovelace.yaml.backup_' + datetime.now().strftime('%Y%m%d_%H%M%S')
shutil.copyfile(r'Y:\ui-lovelace.yaml', backup_file)
print(f"已备份到: {backup_file}")

old_air = '''      # ==================== 空气质量监测 ====================

      # PM2.5 趋势曲线'''

new_air = '''      # ==================== 空气质量监测 ====================

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

      # PM2.5 趋势曲线'''

new_config = config.replace(old_air, new_air)

if new_config == config:
    print("⚠️ 未找到匹配内容")
else:
    print("✅ 替换成功！")
    with open(r'g:\dev\ha\ha\ui-lovelace.yaml', 'w', encoding='utf-8') as f:
        f.write(new_config)
    shutil.copyfile(r'g:\dev\ha\ha\ui-lovelace.yaml', r'Y:\ui-lovelace.yaml')
    print("服务器配置已更新 🎉")
