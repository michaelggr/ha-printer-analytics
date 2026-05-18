import shutil
import re

src = r"g:\dev\ha\ha\www\pa-v5.9.js"
dst1 = r"\\192.168.0.130\config\www\pa-v5.9.js"
dst2 = r"\\192.168.0.130\config\custom_components\printer_analytics\www\pa-v5.9.js"

with open(src, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. 先替换变量名 etaTime -> endTime，etaDate -> endDate
content = content.replace('const etaTime =', 'const endTime =')
content = content.replace('if (etaTime', 'if (endTime')
content = content.replace('const etaDate =', 'const endDate =')
content = content.replace('if (!isNaN(etaDate', 'if (!isNaN(endDate')

# 2. 找到实时监控函数并替换
old_start = '  _renderRealtimeMonitor() {\n    const printers = this._getPrintersConfig();\n    let html = `<div class="section-header"><div class="section-title"><span class="section-icon">📡</span><span>实时监控面板</span></div></div>`;\n\n    for (const printer of printers) {'
new_start = '  _renderRealtimeMonitor() {\n    const printers = this._getPrintersConfig();\n    let html = `<div class="section-header"><div class="section-title"><span class="section-icon">📡</span><span>实时监控面板</span></div></div>`;\n\n    // 只显示当前选择的打印机\n    const selectedPrinterName = this._selectedPrinter;\n    let printerToDisplay = null;\n    \n    if (selectedPrinterName !== \'全部\') {\n      printerToDisplay = printers.find(p => p.printer_name === selectedPrinterName);\n    } else if (printers.length > 0) {\n      // 如果选择"全部"，只显示第一台打印机\n      printerToDisplay = printers[0];\n    }\n    \n    if (printerToDisplay) {'

# 替换循环开始部分
content = content.replace(old_start, new_start)

# 替换中间的 printer.printer_name -> printerToDisplay.printer_name
content = content.replace('${this._escapeHtml(printer.printer_name)}', '${this._escapeHtml(printerToDisplay.printer_name)}')

# 替换最后 for 循环结束的部分
old_end = '    }\n    return html;\n  }'
new_end = '    }\n    return html;\n  }'

content = content.replace(old_end, new_end)

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

print("Modified realtime monitor")

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
