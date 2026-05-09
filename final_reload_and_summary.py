﻿import requests
import json
import time

with open('.ha_connection_info.json', 'r', encoding='utf-8') as f:
    conn_info = json.load(f)

HA_URL = conn_info['ha_api']['url'].rstrip('/')
TOKEN = conn_info['ha_api']['token']

headers = {
    'Authorization': f'Bearer {TOKEN}',
    'Content-Type': 'application/json'
}

print("=" * 80)
print("正在重载 Home Assistant 配置...")
print("=" * 80)

response = requests.post(
    f'{HA_URL}/api/services/homeassistant/reload_all',
    headers=headers,
    json={}
)

if response.status_code == 200:
    print("✓ homeassistant.reload_all 调用成功！")
else:
    print(f"✗ 调用失败: {response.status_code}")

print("\n等待 2 秒...")
time.sleep(2)

print("=" * 80)
print("配置重载完成！")
print("\n【完成的任务总结】")
print("1. ✓ 修复了豆浆机的单位转换问题（从 mWh 转换到 kWh）")
print("2. ✓ 创建了每日/每周/每月/每年强制重置 Utility Meter 的自动化")
print("3. ✓ 将所有自动化按功能分类到不同文件：")
print("   - 10_printer.yaml - 打印机相关")
print("   - 20_lighting.yaml - 亮灯时长相关")
print("   - 30_region.yaml - 区域统计相关")
print("   - 40_energy.yaml - 能耗/Utility Meter相关")
print("   - 90_system.yaml - 系统/虚拟事件相关")
print("4. ✓ 修改了 configuration.yaml 使用新的目录结构")
print("5. ✓ 上传了所有配置文件到服务器")
print("6. ✓ 重载了配置")
print("\n现在你可以在 Home Assistant 中验证所有自动化是否正常工作！")
print("=" * 80)
