﻿﻿﻿﻿﻿---
name: "ha-backup"
description: "备份HA服务器文件后再修改，支持恢复到任意历史版本。每次修改服务器文件前必须调用此技能。"
---

# Home Assistant 文件备份技能

## 何时使用

**必须在以下操作前调用：**
- 修改服务器上的 configuration.yaml
- 修改服务器上的 automations.yaml
- 修改服务器上的 ui-lovelace.yaml
- 修改服务器上的任何配置文件

## 备份策略

1. **时间戳备份**：每次修改前自动创建带时间戳的备份
2. **永久保存**：备份文件保存在本地，不会自动删除
3. **快速恢复**：可以随时恢复到任意历史版本

## 使用方法

### 1. 备份文件

在修改服务器文件前，先执行备份：

```powershell
# 创建备份目录
$backupDir = "g:\dev\ha\ha\backups\$(Get-Date -Format 'yyyyMMdd_HHmmss')"
New-Item -ItemType Directory -Path $backupDir -Force

# 备份关键文件
copy \\192.168.0.130\config\configuration.yaml $backupDir\configuration.yaml
copy \\192.168.0.130\config\automations.yaml $backupDir\automations.yaml
copy \\192.168.0.130\config\ui-lovelace.yaml $backupDir\ui-lovelace.yaml
```

### 2. 修改文件

备份完成后，再进行修改操作。

### 3. 恢复文件

如果需要恢复到某个版本：

```powershell
# 列出所有备份
Get-ChildItem g:\dev\ha\ha\backups\ | Sort-Object Name -Descending

# 恢复到指定版本
copy g:\dev\ha\ha\backups\20260322_120000\configuration.yaml \\192.168.0.130\config\configuration.yaml
```

## 备份文件命名规范

- 目录：`backups/YYYYMMDD_HHMMSS/`
- 文件：保持原文件名

## 注意事项

1. 每次修改前必须先备份
2. 备份完成后确认文件已保存到本地
3. 修改失败时可以立即恢复
4. 定期清理旧备份（可选）
