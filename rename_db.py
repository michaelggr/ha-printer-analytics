import os
import shutil
from datetime import datetime

# 文件路径
db_path = r"\\192.168.0.130\config\home-assistant_v2.db"
backup_suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
new_db_path = rf"\\192.168.0.130\config\home-assistant_v2.db.broken_{backup_suffix}"

print("=== 重建 HA 数据库 ===\n")

# 检查文件是否存在
if os.path.exists(db_path):
    print(f"1. 找到数据库文件: {db_path}")
    size = os.path.getsize(db_path)
    print(f"   文件大小: {size:,} bytes")
    
    # 重命名
    print(f"\n2. 重命名数据库文件...")
    try:
        shutil.move(db_path, new_db_path)
        print(f"   ✅ 已重命名为: {new_db_path}")
        
        # 检查重命名是否成功
        if not os.path.exists(db_path) and os.path.exists(new_db_path):
            print(f"\n3. ✅ 操作成功！")
            print(f"\n=== 下一步 ===")
            print("请执行以下操作：")
            print("1. 重启 Home Assistant")
            print("2. 等待 2-3 分钟让 HA 完全启动")
            print("3. 新数据库会自动创建")
            print("4. 之后通知我检查数据库状态")
        else:
            print(f"\n❌ 操作失败 - 请手动检查文件状态")
            
    except Exception as e:
        print(f"   ❌ 重命名失败: {e}")
else:
    print(f"❌ 数据库文件不存在: {db_path}")
    print("检查是否已经被重命名了...")
    
    # 查找是否有备份文件
    config_dir = r"\\192.168.0.130\config"
    for f in os.listdir(config_dir):
        if f.startswith('home-assistant_v2.db') and f != 'home-assistant_v2.db':
            print(f"   找到备份文件: {f}")
