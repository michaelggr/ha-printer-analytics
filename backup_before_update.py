﻿﻿﻿
import smbclient
import json
from datetime import datetime

# 读取连接信息
with open('.ha_connection_info.json', 'r', encoding='utf-8') as f:
    conn = json.load(f)

smb_host = conn['samba']['host']
smb_share = conn['samba']['share']
smb_user = conn['samba']['username']
smb_pass = conn['samba']['password']

# 注册SMB会话
smbclient.register_session(smb_host, username=smb_user, password=smb_pass)

# 读取服务器文件
remote_path = f'\\\\{smb_host}\\{smb_share}\\ui-lovelace.yaml'
with smbclient.open_file(remote_path, 'rb') as remote_file:
    data = remote_file.read()

# 创建备份
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup_path = rf'g:\dev\ha\ha\ui-lovelace.yaml.backup_{timestamp}'
with open(backup_path, 'wb') as backup_file:
    backup_file.write(data)

print(f"✅ 已从服务器备份！")
print(f"   备份文件: ui-lovelace.yaml.backup_{timestamp}")

