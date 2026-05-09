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
print("正在删除旧的自动化实体...")
print("=" * 80)

entities_to_delete = [
    'automation.neng_hao_mei_yue_1hao_qiang_zhi_zhong_zhi_utility_meter',
    'automation.neng_hao_mei_nian_1yue_1hao_qiang_zhi_zhong_zhi_utility_meter'
]

for entity_id in entities_to_delete:
    print(f"\n正在删除: {entity_id}")
    response = requests.delete(
        f'{HA_URL}/api/states/{entity_id}',
        headers=headers
    )
    if response.status_code == 200:
        print("✓ 删除成功")
    else:
        print(f"✗ 删除失败: {response.status_code}")
        print(response.text)

print("\n" + "=" * 80)
print("完成！")
print("=" * 80)
