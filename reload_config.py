﻿import requests
import json

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

# 重载全部配置
print("\n1. 调用 homeassistant.reload_all...")
response = requests.post(
    f'{HA_URL}/api/services/homeassistant/reload_all',
    headers=headers,
    json={}
)

if response.status_code == 200:
    print("✓ homeassistant.reload_all 调用成功！")
else:
    print(f"✗ 调用失败: {response.status_code}")
    print(response.text)

print("\n2. 调用 homeassistant.reload_config_entries...")
response = requests.post(
    f'{HA_URL}/api/services/homeassistant/reload_config_entries',
    headers=headers,
    json={}
)

if response.status_code == 200:
    print("✓ homeassistant.reload_config_entries 调用成功！")
else:
    print(f"✗ 调用失败: {response.status_code}")
    print(response.text)

print("\n" + "=" * 80)
print("重载配置完成！")
print("现在等几秒钟，我们检查一下数值！")
print("=" * 80)
