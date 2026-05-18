#!/usr/bin/env python3
"""
等待并检查Home Assistant日志
"""

import os
import time

SERVER_PATH = r"\\192.168.0.130\config"

def check_logs():
    print("检查日志文件...")
    log_path = os.path.join(SERVER_PATH, "home-assistant.log")
    
    if os.path.exists(log_path):
        size_mb = os.path.getsize(log_path) / 1024 / 1024
        print(f"✓ 找到 home-assistant.log ({size_mb:.2f} MB)")
        
        try:
            with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()
                print(f"✓ 文件有 {len(lines)} 行")
                
                # 搜索printer_analytics相关
                print("\n搜索 printer_analytics 相关日志:")
                pa_lines = []
                for i, line in enumerate(lines[-100:], 1):  # 最后100行
                    if 'printer_analytics' in line.lower():
                        pa_lines.append(line)
                
                if pa_lines:
                    for line in pa_lines[-20:]:  # 最后20条
                        print(f"  {line.strip()}")
                else:
                    print("  未找到 printer_analytics 相关日志")
                
                # 检查最后几行看是否启动完成
                print("\n最后20行日志:")
                for line in lines[-20:]:
                    print(f"  {line.strip()}")
                    
        except Exception as e:
            print(f"❌ 读取日志失败: {e}")
    else:
        print("❌ 未找到 home-assistant.log")

def main():
    print("等待Home Assistant启动...")
    print("=" * 80)
    
    # 检查几次
    for i in range(3):
        print(f"\n[{i+1}/3] 检查...")
        check_logs()
        if i < 2:
            print(f"\n等待30秒...")
            time.sleep(30)

if __name__ == "__main__":
    main()
