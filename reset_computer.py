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
print("正在单独重置电脑电源的 Utility Meter！")
print("=" * 80)

computer_sensors = [
    'sensor.dian_nao_dian_yuan_ri_yong_dian_liang',
    'sensor.dian_nao_dian_yuan_zhou_yong_dian_liang',
    'sensor.dian_nao_dian_yuan_yue_yong_dian_liang'
]

for sensor in computer_sensors:
    print(f"\n正在重置: {sensor}")
    
    response = requests.post(
        f'{HA_URL}/api/services/utility_meter/reset',
        headers=headers,
        json={
            'entity_id': sensor
        }
    )
    
    if response.status_code == 200:
        print(f"✓ 重置成功: {sensor}")
    else:
        print(f"✗ 重置失败: {sensor}")
        print(f"  错误: {response.status_code}")
        print(f"  内容: {response.text}")

print("\n" + "=" * 80)
print("等待 2 秒...")
print("=" * 80)
import time
time.sleep(2)

print("\n正在检查数值...")

response = requests.get(f'{HA_URL}/api/states', headers=headers)
all_states = response.json()
states_dict = {}
for state in all_states:
    states_dict[state['entity_id']] = state

for sensor in computer_sensors:
    if sensor in states_dict:
        value = float(states_dict[sensor]['state'])
        print(f"\n{sensor}: {value} kWh")

print("\n" + "=" * 80)
print("检查最终的 home_daily_total_v2...")
print("=" * 80)
final_sensor = 'sensor.home_daily_total_v2'
if final_sensor in states_dict:
    value = float(states_dict[final_sensor]['state'])
    print(f"\n{final_sensor}: {value} kWh")
    print("✅ 现在这个数值应该非常合理了！")
