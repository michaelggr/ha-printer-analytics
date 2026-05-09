﻿﻿﻿
#!/usr/bin/env python3
import json
import shutil
from pathlib import Path

# 读取实体数据
with open('entities_by_area.json', 'r', encoding='utf-8') as f:
    entities_by_area = json.load(f)

# 读取ui-lovelace.yaml
with open('ui-lovelace.yaml', 'r', encoding='utf-8') as f:
    ui_content = f.read()

# 区域信息
area_info = {
    '客厅': {
        'path': 'living-room',
        'icon': 'mdi:sofa',
        'occupancy': 'sensor.linp_cn_blt_3_1n20sdaek4k01_es4b_occupancy_status_p_2_1078'
    },
    '卧室': {
        'path': 'bedroom',
        'icon': 'mdi:bed',
        'occupancy': 'sensor.linp_cn_blt_3_1ocv0fv7l0o00_es5b_occupancy_status_p_2_1078'
    },
    '主卧': {
        'path': 'master-bedroom',
        'icon': 'mdi:bed-king',
        'occupancy': 'sensor.vchon_cn_blt_3_1o931kgud0400_mbs17_occupancy_status_p_2_1078'
    },
    '厨房': {
        'path': 'kitchen',
        'icon': 'mdi:stove',
        'occupancy': 'sensor.linp_cn_1137697716_lp1bc_occupancy_status_p_5_1'
    },
    '餐厅': {
        'path': 'dining',
        'icon': 'mdi:silverware-fork-knife',
        'occupancy': 'sensor.linp_cn_blt_3_1n49ffqescc00_es2_occupancy_status_p_2_1078'
    },
    '卫生间': {
        'path': 'bathroom',
        'icon': 'mdi:toilet',
        'occupancy': 'sensor.linp_cn_1137691863_lp1bc_occupancy_status_p_5_1'
    },
    '走廊玄关': {
        'path': 'hallway',
        'icon': 'mdi:door',
        'occupancy': 'sensor.linp_cn_1161876236_hb01_occupancy_status_p_2_1'
    },
    '门口': {
        'path': 'doorway',
        'icon': 'mdi:door-open',
        'occupancy': 'sensor.linp_cn_2079761645_ld6bcw_has_someone_duration_p_5_3'
    },
    '大阳台': {
        'path': 'large-balcony',
        'icon': 'mdi:balcony',
        'occupancy': 'sensor.vchon_cn_blt_3_1lgrvovgoc400_mbs17_occupancy_status_p_2_1078'
    },
    '洗衣机阳台': {
        'path': 'washer-balcony',
        'icon': 'mdi:washing-machine',
        'occupancy': 'sensor.ym001_cn_blt_3_1o90bni4h0g00_ymwsdj_occupancy_status_p_2_1078'
    },
    '室外': {
        'path': 'outdoor',
        'icon': 'mdi:outdoor-lamp',
        'occupancy': 'sensor.ym001_cn_blt_3_1o9vhlvug4403_ymwsdj_occupancy_status_p_2_1078'
    }
}

# ========== 1. 更新区域导航 ==========
# 找到旧的区域导航部分
old_nav_start = "      # 区域导航网格\n\n      - type: grid\n\n        title: 区域导航\n\n        columns: 2\n\n        cards:"
old_nav_end = "      # 快速统计"

# 构建新的区域导航
new_nav = "      # 区域导航网格\n\n      - type: grid\n\n        title: 区域导航\n\n        columns: 3\n\n        cards:"

area_order = [
    '客厅', '主卧', '卧室',
    '厨房', '餐厅', '大阳台',
    '卫生间', '洗衣机阳台', '门口',
    '走廊玄关', '室外'
]

for area_name in area_order:
    info = area_info[area_name]
    new_nav += f"\n\n          # {area_name}\n\n          - type: button\n\n            name: {area_name}\n\n            icon: {info['icon']}\n\n            tap_action:\n\n              action: navigate\n\n              navigation_path: /lovelace/{info['path']}\n\n            entity: {info['occupancy']}\n\n            show_state: true"

new_nav += "\n\n\n      # 快速统计"

# 替换区域导航
ui_content = ui_content.replace(
    ui_content[ui_content.find(old_nav_start):ui_content.find(old_nav_end, ui_content.find(old_nav_start)) + len(old_nav_end)],
    new_nav
)

# ========== 2. 构建所有区域页面 ==========
# 找到旧页面结束的位置
old_pages_end = "  # ==================== 功耗统计面板 ===================="
old_pages_start = "  # ==================== 客厅区域详情 ===================="

# 构建新的区域页面
new_pages = ""

for area_name in area_order:
    info = area_info[area_name]
    entities = entities_by_area.get(area_name, [])
    
    new_pages += f"\n  # ==================== {area_name}区域详情 ====================\n\n  - title: {area_name}\n\n    icon: {info['icon']}\n\n    path: {info['path']}\n\n    cards:"
    
    # 添加实体列表
    new_pages += "\n\n      - type: entities\n\n        title: {area_name}状态\n\n        entities:"
    
    # 筛选有用的实体（跳过button、number、select、text、event等，优先显示light、switch、sensor、climate等）
    useful_entities = []
    for entity in entities:
        entity_id = entity['entity_id']
        if entity_id.startswith(('button.', 'number.', 'select.', 'text.', 'event.', 'input_', 'counter.', 'automation.')):
            continue
        useful_entities.append(entity)
    
    # 添加实体
    for entity in useful_entities[:30]:  # 限制最多30个
        new_pages += f"\n\n          - entity: {entity['entity_id']}\n\n            name: {entity['name']}"
    
    # 添加返回按钮
    new_pages += "\n\n      - type: button\n\n        name: 返回首页\n\n        icon: mdi:arrow-left\n\n        tap_action:\n\n          action: navigate\n\n          navigation_path: /lovelace/home"

# 替换旧页面
ui_content = ui_content.replace(
    ui_content[ui_content.find(old_pages_start):ui_content.find(old_pages_end, ui_content.find(old_pages_start)) + len(old_pages_end)],
    new_pages + old_pages_end
)

# ========== 3. 保存文件 ==========
with open('ui-lovelace.yaml', 'w', encoding='utf-8') as f:
    f.write(ui_content)

print(f"✅ 完成！更新了{len(area_order)}个区域")

