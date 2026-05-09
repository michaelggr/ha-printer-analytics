﻿#!/usr/bin/env python3
import json

with open('entities_by_area.json', 'r', encoding='utf-8') as f:
    entities_by_area = json.load(f)

with open('ui-lovelace.yaml', 'r', encoding='utf-8') as f:
    lines = f.readlines()

area_info = {
    '客厅': {
        'path': 'living-room',
        'icon': 'mdi:sofa',
        'entity': 'sensor.linp_cn_blt_3_1n20sdaek4k01_es4b_occupancy_status_p_2_1078'
    },
    '主卧': {
        'path': 'master-bedroom',
        'icon': 'mdi:bed-king',
        'entity': 'sensor.vchon_cn_blt_3_1o931kgud0400_mbs17_temperature_p_2_1001'
    },
    '卧室': {
        'path': 'bedroom',
        'icon': 'mdi:bed',
        'entity': 'sensor.linp_cn_blt_3_1ocv0fv7l0o00_es5b_occupancy_status_p_2_1078'
    },
    '厨房': {
        'path': 'kitchen',
        'icon': 'mdi:stove',
        'entity': 'sensor.linp_cn_1137697716_lp1bc_occupancy_status_p_5_1'
    },
    '餐厅': {
        'path': 'dining',
        'icon': 'mdi:silverware-fork-knife',
        'entity': 'sensor.linp_cn_blt_3_1n49ffqescc00_es2_occupancy_status_p_2_1078'
    },
    '大阳台': {
        'path': 'large-balcony',
        'icon': 'mdi:balcony',
        'entity': 'sensor.vchon_cn_blt_3_1lgrvovgoc400_mbs17_temperature_p_2_1001'
    },
    '卫生间': {
        'path': 'bathroom',
        'icon': 'mdi:toilet',
        'entity': 'sensor.linp_cn_1137691863_lp1bc_occupancy_status_p_5_1'
    },
    '洗衣机阳台': {
        'path': 'washer-balcony',
        'icon': 'mdi:washing-machine',
        'entity': 'sensor.ym001_cn_blt_3_1o90bni4h0g00_ymwsdj_temperature_p_2_1001'
    },
    '门口': {
        'path': 'doorway',
        'icon': 'mdi:door-open',
        'entity': 'sensor.linp_cn_2079761645_ld6bcw_has_someone_duration_p_5_3'
    },
    '走廊玄关': {
        'path': 'hallway',
        'icon': 'mdi:door',
        'entity': 'sensor.linp_cn_1161876236_hb01_occupancy_status_p_2_1'
    },
    '室外': {
        'path': 'outdoor',
        'icon': 'mdi:outdoor-lamp',
        'entity': 'sensor.ym001_cn_blt_3_1o9vhlvug4403_ymwsdj_temperature_p_2_1001'
    }
}

area_order = [
    '客厅', '主卧', '卧室',
    '厨房', '餐厅', '大阳台',
    '卫生间', '洗衣机阳台', '门口',
    '走廊玄关', '室外'
]

# ========== 1. 更新区域导航 ==========
nav_start = -1
nav_end = -1
for i, line in enumerate(lines):
    if "      # 区域导航网格" in line:
        nav_start = i
    if "      # 快速统计" in line and nav_start != -1 and nav_end == -1:
        nav_end = i
        break

new_nav = []
new_nav.append("      # 区域导航网格\n")
new_nav.append("\n")
new_nav.append("      - type: grid\n")
new_nav.append("\n")
new_nav.append("        title: 区域导航\n")
new_nav.append("\n")
new_nav.append("        columns: 3\n")
new_nav.append("\n")
new_nav.append("        cards:\n")

for area_name in area_order:
    info = area_info[area_name]
    new_nav.append("\n")
    new_nav.append(f"          # {area_name}\n")
    new_nav.append("\n")
    new_nav.append("          - type: button\n")
    new_nav.append("\n")
    new_nav.append(f"            name: {area_name}\n")
    new_nav.append("\n")
    new_nav.append(f"            icon: {info['icon']}\n")
    new_nav.append("\n")
    new_nav.append("            tap_action:\n")
    new_nav.append("\n")
    new_nav.append("              action: navigate\n")
    new_nav.append("\n")
    new_nav.append(f"              navigation_path: /lovelace/{info['path']}\n")
    new_nav.append("\n")
    new_nav.append(f"            entity: {info['entity']}\n")
    new_nav.append("\n")
    new_nav.append("            show_state: true\n")

new_nav.append("\n")
new_nav.append("\n")

new_lines = lines[:nav_start] + new_nav + lines[nav_end:]
lines = new_lines

# ========== 2. 找到区域详情页的位置 ==========
area_pages_start = -1
area_pages_end = -1

for i, line in enumerate(lines):
    if "  # ==================== 客厅区域详情 ====================" in line:
        area_pages_start = i
    if "  # ==================== 监控页面 ====================" in line and area_pages_start != -1 and area_pages_end == -1:
        area_pages_end = i
        break

# ========== 3. 构建新的区域详情页 ==========
SKIP_PREFIXES = ('button.', 'number.', 'select.', 'text.', 'event.',
                 'input_', 'counter.', 'automation.', 'notify.')
SKIP_NAME_KEYWORDS = ('累计', '计数', '计时', '时长累计', '访问计数', '亮灯时长累计')

new_area_pages = []
for area_name in area_order:
    info = area_info[area_name]
    entities = entities_by_area.get(area_name, [])

    new_area_pages.append(f"\n  # ==================== {area_name}区域详情 ====================\n")
    new_area_pages.append("\n")
    new_area_pages.append(f"  - title: {area_name}\n")
    new_area_pages.append("\n")
    new_area_pages.append(f"    icon: {info['icon']}\n")
    new_area_pages.append("\n")
    new_area_pages.append(f"    path: {info['path']}\n")
    new_area_pages.append("\n")
    new_area_pages.append("    cards:\n")

    useful_entities = []
    for entity in entities:
        eid = entity['entity_id']
        ename = entity['name']
        if eid.startswith(SKIP_PREFIXES):
            continue
        if any(kw in ename for kw in SKIP_NAME_KEYWORDS):
            continue
        useful_entities.append(entity)

    # 按类型分组：light/climate/cover/fan/media_player → 控制类，sensor/switch/binary_sensor → 状态类
    control_types = {'light', 'climate', 'cover', 'fan', 'media_player'}
    control_entities = []
    status_entities = []
    for e in useful_entities:
        domain = e['entity_id'].split('.')[0]
        if domain in control_types:
            control_entities.append(e)
        else:
            status_entities.append(e)

    # 控制类卡片
    if control_entities:
        new_area_pages.append("\n")
        new_area_pages.append("      - type: entities\n")
        new_area_pages.append("\n")
        new_area_pages.append(f"        title: {area_name}控制\n")
        new_area_pages.append("\n")
        new_area_pages.append("        entities:\n")
        for e in control_entities:
            new_area_pages.append("\n")
            new_area_pages.append(f"          - entity: {e['entity_id']}\n")
            new_area_pages.append("\n")
            new_area_pages.append(f"            name: {e['name']}\n")

    # 状态类卡片
    if status_entities:
        new_area_pages.append("\n")
        new_area_pages.append("\n")
        new_area_pages.append("      - type: entities\n")
        new_area_pages.append("\n")
        new_area_pages.append(f"        title: {area_name}状态\n")
        new_area_pages.append("\n")
        new_area_pages.append("        entities:\n")
        for e in status_entities[:30]:
            new_area_pages.append("\n")
            new_area_pages.append(f"          - entity: {e['entity_id']}\n")
            new_area_pages.append("\n")
            new_area_pages.append(f"            name: {e['name']}\n")

    # 返回按钮
    new_area_pages.append("\n")
    new_area_pages.append("\n")
    new_area_pages.append("      - type: button\n")
    new_area_pages.append("\n")
    new_area_pages.append("        name: 返回首页\n")
    new_area_pages.append("\n")
    new_area_pages.append("        icon: mdi:arrow-left\n")
    new_area_pages.append("\n")
    new_area_pages.append("        tap_action:\n")
    new_area_pages.append("\n")
    new_area_pages.append("          action: navigate\n")
    new_area_pages.append("\n")
    new_area_pages.append("          navigation_path: /lovelace/home\n")

final_lines = lines[:area_pages_start] + new_area_pages + lines[area_pages_end:]

with open('ui-lovelace.yaml', 'w', encoding='utf-8') as f:
    f.writelines(final_lines)

print(f"完成！更新了{len(area_order)}个区域")
for a in area_order:
    ents = entities_by_area.get(a, [])
    ctrl = [e for e in ents if e['entity_id'].split('.')[0] in control_types and not e['entity_id'].startswith(SKIP_PREFIXES)]
    stat = [e for e in ents if e['entity_id'].split('.')[0] not in control_types and not e['entity_id'].startswith(SKIP_PREFIXES) and not any(kw in e['name'] for kw in SKIP_NAME_KEYWORDS)]
    print(f"  {a}: 控制{len(ctrl)}个, 状态{len(stat)}个")
