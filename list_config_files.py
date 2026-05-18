import os

config_dir = r"\\192.168.0.130\config"

print("=== config 目录文件列表 ===\n")

files = os.listdir(config_dir)
for f in sorted(files):
    if f.startswith('home-assistant') or f.endswith('.log'):
        full_path = os.path.join(config_dir, f)
        if os.path.isfile(full_path):
            size = os.path.getsize(full_path)
            print(f"  {f}: {size:,} bytes")
        else:
            print(f"  {f}/ (目录)")
