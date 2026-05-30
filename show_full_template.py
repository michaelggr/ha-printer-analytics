﻿import re

tpl_path = r'\\192.168.0.130\config\templates.yaml'

with open(tpl_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 找到 li_shi_zong_gong_hao 的完整定义（行1502附近）
print('=== li_shi_zong_gong_hao 完整模板定义 ===')
in_target = False
block = []
for i, line in enumerate(lines):
    if 'name: li_shi_zong_gong_hao' in line or 'unique_id: li_shi_zong_gong_hao' in line:
        # 往回找到 - sensor: 行
        start = i
        while start > 0 and '- sensor:' not in lines[start]:
            start -= 1
        in_target = True
    
    if in_target:
        block.append((i+1, line.rstrip()))
        # 到下一个顶级缩进结束
        if i > 0 and line.strip() and not line[0].isspace() and line.strip().startswith('-') and 'sensor:' not in line and 'name:' not in line and len(block) > 5:
            break
        if len(block) > 30:
            break

for ln, bl in block:
    print('  %d: %s' % (ln, bl))

# 也检查"历史总功耗"(第一个定义，行491附近)
print('\n\n=== 历史总功耗(第一个定义) 完整模板 ===')
in_target2 = False
block2 = []
for i, line in enumerate(lines):
    if 'name: 历史总功耗' in line and i < 1000:
        start = i
        while start > 0 and '- sensor:' not in lines[start]:
            start -= 1
        in_target2 = True
    
    if in_target2:
        block2.append((i+1, line.rstrip()))
        if i > 0 and line.strip() and not line[0].isspace() and line.strip().startswith('-') and len(block2) > 5:
            break
        if len(block2) > 30:
            break

for ln, bl in block2:
    print('  %d: %s' % (ln, bl))
