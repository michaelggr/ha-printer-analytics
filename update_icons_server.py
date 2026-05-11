import re

# ===== 服务器文件 =====

# 1. configuration.yaml - sidebar icons
path = r'\\192.168.0.130\config\configuration.yaml'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("icon: mdi:printer-3d", "icon: mdi:chart-timeline-variant")
content = content.replace("icon: mdi:chart-line", "icon: mdi:chart-timeline-variant")

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print(f'[OK] configuration.yaml - 已更新')

# 2. ui-all-printers.yaml - view icons (printer-3d-nozzle-outline and printer-3d)
path = r'\\192.168.0.130\config\ui-all-printers.yaml'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("icon: mdi:printer-3d-nozzle-outline", "icon: mdi:chart-timeline-variant")
content = content.replace("icon: mdi:printer-3d", "icon: mdi:chart-timeline-variant")

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print(f'[OK] ui-all-printers.yaml - 已更新')

# 3. ui-printer-analysis.yaml - view icon
path = r'\\192.168.0.130\config\ui-printer-analysis.yaml'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("icon: mdi:chart-line", "icon: mdi:chart-timeline-variant")

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print(f'[OK] ui-printer-analysis.yaml - 已更新')

print('\n服务器文件更新完成！')
