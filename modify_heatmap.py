import shutil
import os

src = r"g:\dev\ha\ha\www\pa-v5.9.js"
dst1 = r"\\192.168.0.130\config\www\pa-v5.9.js"
dst2 = r"\\192.168.0.130\config\custom_components\printer_analytics\www\pa-v5.9.js"

# 读取文件
with open(src, 'r', encoding='utf-8') as f:
    content = f.read()

# 修改热力图格子大小 - 从 min-height: 8px 改为 2px
content = content.replace(
    '.heatmap-cell {\n          aspect-ratio: 1;\n          border-radius: 3px;\n          min-height: 8px;',
    '.heatmap-cell {\n          aspect-ratio: 1;\n          border-radius: 2px;\n          min-height: 2px;'
)

# 写回文件
with open(src, 'w', encoding='utf-8') as f:
    f.write(content)

print("Modified heatmap cell size")

# 上传到服务器
try:
    shutil.copy(src, dst1)
    print(f"Copied to {dst1}")
except Exception as e:
    print(f"Error copying to {dst1}: {e}")

try:
    shutil.copy(src, dst2)
    print(f"Copied to {dst2}")
except Exception as e:
    print(f"Error copying to {dst2}: {e}")

print("Done!")
