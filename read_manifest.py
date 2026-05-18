#!/usr/bin/env python3
"""读取集成manifest.json文件"""
import os
import json

SERVER_CONFIG_DIR = r"\\192.168.0.130\config"
MANIFEST_PATH = os.path.join(SERVER_CONFIG_DIR, "custom_components", "printer_analytics", "manifest.json")

def main():
    print("=" * 80)
    print("检查manifest.json")
    print("=" * 80)
    
    if os.path.exists(MANIFEST_PATH):
        print(f"\n✅ 文件存在: {MANIFEST_PATH}")
        try:
            with open(MANIFEST_PATH, 'r', encoding='utf-8') as f:
                content = json.load(f)
            print(f"\n内容:")
            print(json.dumps(content, indent=2, ensure_ascii=False))
        except Exception as e:
            print(f"\n❌ 读取失败: {e}")
    else:
        print(f"\n❌ 文件不存在: {MANIFEST_PATH}")

if __name__ == "__main__":
    main()
