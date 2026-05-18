import shutil
import re

src = r"g:\dev\ha\ha\www\pa-v5.9.js"
dst1 = r"\\192.168.0.130\config\www\pa-v5.9.js"
dst2 = r"\\192.168.0.130\config\custom_components\printer_analytics\www\pa-v5.9.js"

with open(src, 'r', encoding='utf-8') as f:
    content = f.read()

# 提取当前版本并递增
match = re.search(r'v(\d+)\.(\d+)\.(\d+)', content)
if match:
    major, minor, patch = int(match.group(1)), int(match.group(2)), int(match.group(3))
    patch += 1
    new_version = f"v{major}.{minor}.{patch}"
    old_match = re.search(r'v\d+\.\d+\.\d+', content)
    if old_match:
        content = content.replace(old_match.group(0), new_version)
        print(f"Version: {old_match.group(0)} -> {new_version}")

with open(src, 'w', encoding='utf-8') as f:
    f.write(content)

try:
    shutil.copy(src, dst1)
    print(f"Uploaded to {dst1}")
except Exception as e:
    print(f"Error: {e}")

try:
    shutil.copy(src, dst2)
    print(f"Uploaded to {dst2}")
except Exception as e:
    print(f"Error: {e}")

print(f"\n✅ Done! Version: {new_version}")
