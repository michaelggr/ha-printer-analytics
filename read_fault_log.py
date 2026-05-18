#!/usr/bin/env python3
"""
读取 home-assistant.log.fault
"""

import os

CONFIG_PATH = r"\\192.168.0.130\config"

def main():
    filepath = os.path.join(CONFIG_PATH, "home-assistant.log.fault")
    
    if not os.path.exists(filepath):
        print(f"❌ 文件不存在: {filepath}")
        return
    
    print(f"读取文件: {filepath}")
    print("=" * 80)
    
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
            print(content)
    except Exception as e:
        print(f"❌ 读取失败: {e}")
        # 尝试用二进制读取
        try:
            with open(filepath, 'rb') as f:
                raw = f.read()
                print(f"二进制内容 (前2000字节): {repr(raw[:2000])}")
        except Exception as e2:
            print(f"❌ 二进制读取也失败: {e2}")

if __name__ == "__main__":
    main()
