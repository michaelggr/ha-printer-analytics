﻿﻿﻿﻿﻿import shutil
from datetime import datetime

print("正在恢复原始备份...")

# 备份当前配置
current_backup = r'Y:\ui-lovelace.yaml.backup_current_' + datetime.now().strftime('%Y%m%d_%H%M%S')
shutil.copyfile(r'Y:\ui-lovelace.yaml', current_backup)
print(f"当前配置已备份到: {current_backup}")

# 恢复原始备份
original_backup = r'g:\dev\ha\ha\ui-lovelace.yaml.backup_20260429'
shutil.copyfile(original_backup, r'Y:\ui-lovelace.yaml')
shutil.copyfile(original_backup, r'g:\dev\ha\ha\ui-lovelace.yaml')

print("\n✅ 已恢复原始备份！请刷新浏览器检查是否还有配置错误...")
