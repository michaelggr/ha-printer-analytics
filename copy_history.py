﻿import shutil
from pathlib import Path

src = Path("g:/dev/ha/ha/01KRN9GJCF600K6JNS881DJ81S_2026.final.json")
dst = Path("\\\\192.168.0.130\\config\\.printer_analytics\\history_by_year\\01KRN9GJCF600K6JNS881DJ81S_2026.json")
dst_backup = dst.parent / (dst.name + ".backup.manual")

print(f"源文件: {src}")
print(f"目标: {dst}")
print(f"备份: {dst_backup}")

print("\n备份原文件...")
if dst.exists():
    shutil.copy2(dst, dst_backup)
    print(f"✓ 已备份到: {dst_backup}")

print("\n复制新文件...")
shutil.copy2(src, dst)
print(f"✓ 已复制到: {dst}")

print("\n✓ 完成!")
