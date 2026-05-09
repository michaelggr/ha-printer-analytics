﻿﻿﻿
#!/usr/bin/env python3
import json

# 读取实体数据
with open('entities_by_area.json', 'r', encoding='utf-8') as f:
    entities_by_area = json.load(f)

# 读取ui-lovelace.yaml
with open('ui-lovelace.yaml', 'r', encoding='utf-8') as f:
    lines = f.readlines()

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

area_order = [
    '客厅', '主卧', '卧室',
    '厨房', '餐厅', '大阳台',
    '卫生间', '洗衣机阳台', '门口',
    '走廊玄关', '室外'
]

# ========== 1. 更新区域导航 ==========
# 找到区域导航的开始和结束位置
nav_start = -1
nav_end = -1
for i, line in enumerate(lines):
    if "      # 区域导航网格" in line:
        nav_start = i
    if "      # 快速统计" in line and nav_start != -1 and nav_end == -1:
        nav_end = i
        break

# 构建新的导航
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
    new_nav.append(f"            entity: {info['occupancy']}\n")
    new_nav.append("\n")
    new_nav.append("            show_state: true\n")

new_nav.append("\n")
new_nav.append("\n")

# 替换旧导航
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
    
    # 添加实体列表
    new_area_pages.append("\n")
    new_area_pages.append("      - type: entities\n")
    new_area_pages.append("\n")
    new_area_pages.append(f"        title: {area_name}状态\n")
    new_area_pages.append("\n")
    new_area_pages.append("        entities:\n")
    
    # 筛选有用的实体
    useful_entities = []
    for entity in entities:
        entity_id = entity['entity_id']
        # 跳过不需要的实体类型
        if entity_id.startswith(('button.', 'number.', 'select.', 'text.', 'event.', 
                              'input_', 'counter.', 'automation.', 'notify.')):
            continue
        # 优先显示light、switch、sensor、climate等
        useful_entities.append(entity)
    
    # 添加实体
    for entity in useful_entities[:35]:
        new_area_pages.append("\n")
        new_area_pages.append(f"          - entity: {entity['entity_id']}\n")
        new_area_pages.append("\n")
        new_area_pages.append(f"            name: {entity['name']}\n")
    
    # 添加返回按钮
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

# 替换旧区域详情页
final_lines = lines[:area_pages_start] + new_area_pages + lines[area_pages_end:]

# ========== 4. 保存文件 ==========
with open('ui-lovelace.yaml', 'w', encoding='utf-8') as f:
    f.writelines(final_lines)

print(f"✅ 完成！更新了{len(area_order)}个区域")
print(f" - 区域导航已更新为3列布局")
print(f" - 添加了新区域页面")
print(f" - 每个区域页面包含该区域的所有设备")

