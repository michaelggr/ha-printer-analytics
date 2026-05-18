﻿#!/usr/bin/env python3
"""重命名历史文件以匹配当前配置条目 ID"""

import os
import shutil
import json

# 服务器路径
server_path = r"\\192.168.0.130\config"
history_dir = os.path.join(server_path, ".printer_analytics", "history_by_year")

# 当前配置条目 ID
ENTRY_IDS = {
    "a1mini": "01KRTS51PW4BEKAC3AFJZ7TYF3",
    "p2s": "01KRTS6CW4PZ1GFDK42CRTTMGV",
}

# 根据之前的检查，确定哪个文件对应哪个打印机
# 01KRN9GJCF600K6JNS881DJ81S_2026.json - 39 条记录 (应该是 a1mini)
# 01KRNAENC2QZY5528QSZ8GYTRD_2026.json - 1 条记录 (应该是 p2s)

FILE_MAPPING = {
    "01KRN9GJCF600K6JNS881DJ81S": "a1mini",
    "01KRNAENC2QZY5528QSZ8GYTRD": "p2s",
}

def main():
    print("=" * 80)
    print("重命名历史文件")
    print("=" * 80)
    
    if not os.path.exists(history_dir):
        print(f"❌ 历史目录不存在: {history_dir}")
        return
    
    files = os.listdir(history_dir)
    json_files = [f for f in files if f.endswith('.json') and '_' in f]
    
    print(f"\n找到 {len(json_files)} 个历史文件")
    print("\n" + "-" * 80)
    
    renamed_count = 0
    
    for filename in json_files:
        # 解析文件名: entryid_year.json
        parts = filename.split('_')
        if len(parts) < 2:
            continue
        
        old_entry_id = parts[0]
        year_part = parts[1]
        
        if old_entry_id not in FILE_MAPPING:
            print(f"⚠️  跳过未知文件: {filename}")
            continue
        
        printer_name = FILE_MAPPING[old_entry_id]
        new_entry_id = ENTRY_IDS[printer_name]
        new_filename = f"{new_entry_id}_{year_part}"
        
        old_path = os.path.join(history_dir, filename)
        new_path = os.path.join(history_dir, new_filename)
        
        print(f"\n📄 {printer_name}:")
        print(f"   旧文件名: {filename}")
        print(f"   新文件名: {new_filename}")
        
        # 先备份旧文件
        backup_path = old_path + ".backup"
        shutil.copy2(old_path, backup_path)
        print(f"   ✅ 已备份到: {filename}.backup")
        
        # 重命名
        os.rename(old_path, new_path)
        print(f"   ✅ 已重命名")
        
        renamed_count += 1
    
    print("\n" + "-" * 80)
    print(f"\n✅ 完成，共重命名 {renamed_count} 个文件")
    
    # 验证结果
    print("\n" + "=" * 80)
    print("验证重命名结果")
    print("=" * 80)
    
    files = os.listdir(history_dir)
    json_files = [f for f in files if f.endswith('.json') and '_' in f and not f.endswith('.backup')]
    
    print(f"\n当前历史文件:")
    for filename in json_files:
        file_path = os.path.join(history_dir, filename)
        size = os.path.getsize(file_path)
        print(f"  - {filename} ({size} 字节)")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as fp:
                data = json.load(fp)
                if isinstance(data, dict) and 'history' in data:
                    print(f"    包含 {len(data['history'])} 条记录")
        except Exception as e:
            print(f"    ❌ 读取失败: {e}")
    
    print("\n" + "=" * 80)
    print("操作完成")
    print("=" * 80)

if __name__ == "__main__":
    main()