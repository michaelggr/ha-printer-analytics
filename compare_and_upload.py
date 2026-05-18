#!/usr/bin/env python3
"""
对比本地和服务器上的集成文件，如有差异则上传
"""

import os
import shutil
import filecmp

LOCAL_PATH = r"g:\dev\ha\ha\custom_components\printer_analytics"
SERVER_PATH = r"\\192.168.0.130\config\custom_components\printer_analytics"

def compare_files():
    """对比文件并返回差异列表"""
    diff_files = []
    
    if not os.path.exists(LOCAL_PATH):
        print(f"❌ 本地路径不存在: {LOCAL_PATH}")
        return []
    
    if not os.path.exists(SERVER_PATH):
        print(f"❌ 服务器路径不存在: {SERVER_PATH}")
        return []
    
    # 获取本地所有文件
    for root, dirs, files in os.walk(LOCAL_PATH):
        # 跳过 __pycache__
        if '__pycache__' in root:
            continue
            
        for file in files:
            # 跳过备份文件
            if file.endswith('.backup') or file.endswith('.temp') or file.endswith('.pyc'):
                continue
                
            local_file = os.path.join(root, file)
            rel_path = os.path.relpath(local_file, LOCAL_PATH)
            server_file = os.path.join(SERVER_PATH, rel_path)
            
            if not os.path.exists(server_file):
                print(f"⚠️  服务器缺少文件: {rel_path}")
                diff_files.append(rel_path)
            else:
                # 对比文件内容
                if not filecmp.cmp(local_file, server_file, shallow=False):
                    print(f"⚠️  文件有差异: {rel_path}")
                    diff_files.append(rel_path)
                else:
                    print(f"✅ 文件一致: {rel_path}")
    
    return diff_files

def upload_files(diff_files):
    """上传差异文件"""
    if not diff_files:
        print("\n✅ 所有文件都一致，无需上传")
        return
    
    print(f"\n⚠️  需要上传 {len(diff_files)} 个文件\n")
    
    for rel_path in diff_files:
        local_file = os.path.join(LOCAL_PATH, rel_path)
        server_file = os.path.join(SERVER_PATH, rel_path)
        
        # 确保目标目录存在
        server_dir = os.path.dirname(server_file)
        os.makedirs(server_dir, exist_ok=True)
        
        try:
            shutil.copy2(local_file, server_file)
            print(f"✅ 已上传: {rel_path}")
        except Exception as e:
            print(f"❌ 上传失败 {rel_path}: {e}")

def main():
    print("对比 printer_analytics 集成文件")
    print("=" * 80)
    
    diff_files = compare_files()
    upload_files(diff_files)
    
    print("\n" + "=" * 80)
    print("完成")

if __name__ == "__main__":
    main()
