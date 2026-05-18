#!/usr/bin/env python3
"""
列出服务器配置目录
"""

import os

SERVER_PATH = r"\\192.168.0.130\config"

def main():
    print("服务器配置目录内容:")
    print("=" * 80)
    
    if os.path.exists(SERVER_PATH):
        files = os.listdir(SERVER_PATH)
        for f in sorted(files):
            fp = os.path.join(SERVER_PATH, f)
            if os.path.isdir(fp):
                print(f"  [DIR] {f}")
            else:
                size_mb = os.path.getsize(fp) / 1024 / 1024
                print(f"  [FILE] {f} ({size_mb:.2f} MB)")
    
    print("\n配置子目录:")
    config_subdir = os.path.join(SERVER_PATH, "config")
    if os.path.exists(config_subdir):
        for f in sorted(os.listdir(config_subdir)):
            fp = os.path.join(config_subdir, f)
            if os.path.isdir(fp):
                print(f"  [DIR] {f}")
            else:
                size_mb = os.path.getsize(fp) / 1024 / 1024
                print(f"  [FILE] {f} ({size_mb:.2f} MB)")

if __name__ == "__main__":
    main()
