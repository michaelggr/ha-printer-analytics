import shutil
import os

src = r"g:\dev\ha\ha\www\pa-v5.9.js"
dst1 = r"\\192.168.0.130\config\www\pa-v5.9.js"
dst2 = r"\\192.168.0.130\config\custom_components\printer_analytics\www\pa-v5.9.js"

# 读取文件
with open(src, 'r', encoding='utf-8') as f:
    content = f.read()

# 将 eta_time 替换为 end_time
content = content.replace('e.eta_time', 'e.end_time')
content = content.replace('const etaTime', 'const endTime')
content = content.replace('if (etaTime', 'if (endTime')
content = content.replace('const etaDate', 'const endDate')
content = content.replace('etaDisplay', 'endDisplay')

print("Modified eta_time -> end_time")

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
