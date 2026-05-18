import os

log_path = r"\\192.168.0.130\config\home-assistant.log"

print("=== 读取 HA 日志（最后 200 行）===\n")

try:
    with open(log_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # 只显示最后 200 行
    for line in lines[-200:]:
        print(line.rstrip())
        
except Exception as e:
    print(f"读取失败: {e}")
