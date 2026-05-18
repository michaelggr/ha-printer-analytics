#!/usr/bin/env python3
"""
读取配置文件
"""

import os

CONFIG_PATH = r"\\192.168.0.130\config\config"

def main():
    filepath = os.path.join(CONFIG_PATH, "configuration.yaml")
    
    if not os.path.exists(filepath):
        print(f"❌ 文件不存在: {filepath}")
        print(f"目录内容: {os.listdir(CONFIG_PATH)}")
        return
    
    print(f"读取文件: {filepath}")
    print("=" * 80)
    
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
            print(content)
    except Exception as e:
        print(f"❌ 读取失败: {e}")

if __name__ == "__main__":
    main()
