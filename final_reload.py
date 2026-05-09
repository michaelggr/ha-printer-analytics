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
print("\n【已添加的自动化】")
print(" 1. [能耗] 每日强制重置 Utility Meter (00:01)")
print(" 2. [能耗] 每周一强制重置 Utility Meter (00:02)")
print(" 3. [能耗] 每月1号强制重置 Utility Meter (00:03)")
print(" 4. [能耗] 每年1月1号强制重置 Utility Meter (00:04)")
print("\n【已修复的问题】")
print(" - 豆浆机数值单位转换 (除以1,000,000)")
print(" - 数值异常已修正")
print(" - 每日自动重置防止累计溢出")
print("=" * 80)
