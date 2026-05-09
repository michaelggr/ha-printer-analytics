﻿import os
import json

# 搜索目录
search_dir = r"g:\dev\ha\ha"
target_string = "dian_nao_dian_yuan_ri_yong_dian_liang"

print(f"正在搜索 {target_string}...\n")

for filename in os.listdir(search_dir):
    filepath = os.path.join(search_dir, filename)
    if os.path.isfile(filepath) and filename.endswith(('.yaml', '.yml', '.json')):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                if target_string in content:
                    print(f"✓ 找到在: {filename}")
                    lines = content.split('\n')
                    for i, line in enumerate(lines):
                        if target_string in line:
                            print(f"  行 {i+1}: {line.strip()}")
                    print()
        except Exception as e:
            print(f"✗ 读取 {filename} 错误: {e}")

print("搜索完成！")
