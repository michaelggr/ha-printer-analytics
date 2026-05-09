﻿﻿﻿import requests
import json

with open('.ha_connection_info.json', 'r', encoding='utf-8') as f:
    conn = json.load(f)

headers = {'Authorization': f'Bearer {conn["ha_api"]["token"]}'}
HA_URL = conn["ha_api"]["url"].rstrip('/')

# 获取所有实体状态
response = requests.get(f'{HA_URL}/api/states', headers=headers)

if response.status_code == 200:
    states = response.json()
    
    # 收集所有区域信息
    areas = {}
    for state in states:
        # 从 attributes 中获取 area 信息或者从 entity_id 推断
        area = None
        
        # 先看 attributes 中有没有 area 相关
        if 'area_id' in state['attributes']:
            area = state['attributes']['area_id']
        elif 'friendly_name' in state['attributes']:
            # 从 friendly_name 推断
            name = state['attributes']['friendly_name']
            if '客厅' in name: area = '客厅'
            elif '卧室' in name and '主卧' not in name: area = '卧室'
            elif '主卧' in name: area = '主卧'
            elif '厨房' in name: area = '厨房'
            elif '餐厅' in name: area = '餐厅'
            elif '卫生间' in name or '厕所' in name: area = '卫生间'
            elif '走廊' in name or '玄关' in name: area = '走廊玄关'
            elif '门口' in name: area = '门口'
            elif '大阳台' in name: area = '大阳台'
            elif '洗衣机' in name and '阳台' in name: area = '洗衣机阳台'
            elif '阳台' in name and '大' not in name and '洗衣机' not in name: area = '阳台'
            elif '室外' in name: area = '室外'
        
        if area:
            if area not in areas:
                areas[area] = []
            areas[area].append({
                'entity_id': state['entity_id'],
                'name': state['attributes'].get('friendly_name', state['entity_id']),
                'state': state['state']
            })
    
    # 保存结果
    with open('entities_by_area.json', 'w', encoding='utf-8') as f:
        json.dump(areas, f, ensure_ascii=False, indent=2)
    
    print("✅ 已获取所有实体，按区域分类！")
    print("\n发现的区域：")
    for area in sorted(areas.keys()):
        print(f"  - {area} ({len(areas[area])} 个设备)")
else:
    print(f"❌ 获取实体失败，状态码：{response.status_code}")
