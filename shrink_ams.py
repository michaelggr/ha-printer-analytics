import shutil
import re

src = r"g:\dev\ha\ha\www\pa-v5.9.js"
dst1 = r"\\192.168.0.130\config\www\pa-v5.9.js"
dst2 = r"\\192.168.0.130\config\custom_components\printer_analytics\www\pa-v5.9.js"

with open(src, 'r', encoding='utf-8') as f:
    content = f.read()

# 缩小AMS尺寸
content = content.replace('minmax(130px, 1fr)', 'minmax(90px, 1fr)')
content = content.replace('gap: 14px;', 'gap: 8px;')
content = content.replace('margin-top: 16px;', 'margin-top: 10px;')
content = content.replace('padding: 16px;', 'padding: 10px;')
content = content.replace('font-size: 11px;', 'font-size: 10px;', 1)
content = content.replace('margin-bottom: 8px;', 'margin-bottom: 6px;')
content = content.replace('width: 48px;', 'width: 36px;')
content = content.replace('height: 48px;', 'height: 36px;')
content = content.replace('margin: 0 auto 10px;', 'margin: 0 auto 6px;')
content = content.replace('font-size: 13px;', 'font-size: 11px;', 1)

# 递增版本号
match = re.search(r'v(\d+)\.(\d+)\.(\d+)', content)
if match:
    major, minor, patch = int(match.group(1)), int(match.group(2)), int(match.group(3))
    patch += 1
    new_version = f"v{major}.{minor}.{patch}"
    content = re.sub(r'v\d+\.\d+\.\d+', new_version, content, 1)
    print(f"Version: {match.group(0)} -> {new_version}")

with open(src, 'w', encoding='utf-8') as f:
    f.write(content)

print("Shrunk AMS tray display")

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
