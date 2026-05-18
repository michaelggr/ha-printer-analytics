﻿#!/usr/bin/env python3
"""直接交换两个历史文件的内容"""

import os
import json
import shutil

# 服务器路径
server_path = r"\\192.168.0.130\config"
history_dir = os.path.join(server_path, ".printer_analytics", "history_by_year")

# 当前配置条目 ID
ENTRY_IDS = {
    "a1mini": "01KRTS51PW4BEKAC3AFJZ7TYF3",
    "p2s": "01KRTS6CW4PZ1GFDK42CRTTMGV",
}

def main():
    print("=" * 80)
    print("直接交换两个历史文件的内容")
    print("=" * 80)
    
    a1mini_file = os.path.join(history_dir, f"{ENTRY_IDS['a1mini']}_2026.json")
    p2s_file = os.path.join(history_dir, f"{ENTRY_IDS['p2s']}_2026.json")
    
    # 先备份
    print("\n备份当前文件...")
    shutil.copy2(a1mini_file, a1mini_file + ".backup_swap")
    shutil.copy2(p2s_file, p2s_file + ".backup_swap")
    print("✅ 备份完成")
    
    # 读取两个文件的内容
    print("\n读取文件内容...")
    with open(a1mini_file, 'r', encoding='utf-8') as f:
        a1mini_data = json.load(f)
    
    with open(p2s_file, 'r', encoding='utf-8') as f:
        p2s_data = json.load(f)
    
    print(f"   a1mini 当前记录数: {len(a1mini_data.get('history', []))}")
    print(f"   p2s 当前记录数: {len(p2s_data.get('history', []))}")
    
    # 交换内容
    print("\n交换内容...")
    with open(a1mini_file, 'w', encoding='utf-8') as f:
        json.dump(p2s_data, f, ensure_ascii=False, indent=2)
    
    with open(p2s_file, 'w', encoding='utf-8') as f:
        json.dump(a1mini_data, f, ensure_ascii=False, indent=2)
    
    print("✅ 交换完成")
    
    # 验证
    print("\n验证结果...")
    with open(a1mini_file, 'r', encoding='utf-8') as f:
        a1mini_data = json.load(f)
    
    with open(p2s_file, 'r', encoding='utf-8') as f:
        p2s_data = json.load(f)
    
    print(f"\n📊 a1mini: {len(a1mini_data.get('history', []))} 条记录")
    print(f"📊 p2s: {len(p2s_data.get('history', []))} 条记录")
    
    print("\n" + "=" * 80)
    print("操作完成，请重新加载组件或重启 HA")
    print("=" * 80)

if __name__ == "__main__":
    main()