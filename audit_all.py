import json, urllib.request, time
from collections import Counter

token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiI1M2Q4NzBkOGY4M2U0YWY3ODIzNTJlNjVkNmVkYzY5YSIsImlhdCI6MTc3NDE5NTM2MCwiZXhwIjoyMDg5NTU1MzYwfQ.7VKORHi3sWJfROnc7HKzDyY1uwapDC8WXdLIj4sAITs'
base = 'http://192.168.0.130:8123'
hdr = {'Authorization': f'Bearer {token}'}

req = urllib.request.Request(f'{base}/api/states', headers=hdr)
resp = urllib.request.urlopen(req)
data = json.loads(resp.read())

# 获取entity_registry（从本地文件）
with open(r'g:\dev\ha\ha\.storage\core.entity_registry', 'r', encoding='utf-8-sig') as f:
    reg_data = json.load(f)
registry = reg_data.get('data', {}).get('entities', [])

# 构建entity_id -> platform的映射
platform_map = {}
for r in registry:
    platform_map[r['entity_id']] = r.get('platform', 'unknown')

# 筛选所有restored不可用实体
unavail_restored = [e for e in data if e['state'] == 'unavailable' and e.get('attributes', {}).get('restored')]

print(f'=== 总计 restored 不可用实体: {len(unavail_restored)} ===')
print()

# 按域名(domain)统计
domain_counter = Counter()
for e in unavail_restored:
    domain = e['entity_id'].split('.')[0]
    domain_counter[domain] += 1

print('--- 按域名分布 ---')
for domain, count in domain_counter.most_common():
    print(f'  {domain}: {count}个')

print()

# 按平台(platform)统计（从registry获取）
plat_counter = Counter()
for e in unavail_restored:
    eid = e['entity_id']
    plat = platform_map.get(eid, 'unknown')
    plat_counter[plat] += 1

print('--- 按平台分布 ---')
for plat, count in plat_counter.most_common():
    print(f'  {plat}: {count}个')

print()

# 按关键字分类
categories = {
    'duration_hours': [],
    'duration': [],       # 不含hours的duration
    '_energy_v2': [],
    'daily_kwh': [],
    'weekly_kwh': [],
    'monthly_kwh': [],
    'total_kwh': [],
    'liang_deng_shi_chang': [],
    'yong_dian_liang': [],
    'zm1_': [],
    'other': []
}

for e in unavail_restored:
    eid = e['entity_id']
    if 'duration_hours' in eid:
        categories['duration_hours'].append(eid)
    elif 'duration' in eid:
        categories['duration'].append(eid)
    elif '_energy_v2' in eid or '_daily_energy_v2' in eid or '_weekly_energy_v2' in eid or '_monthly_energy_v2' in eid or '_yearly_energy_v2' in eid:
        categories['_energy_v2'].append(eid)
    elif 'daily_kwh' in eid:
        categories['daily_kwh'].append(eid)
    elif 'weekly_kwh' in eid:
        categories['weekly_kwh'].append(eid)
    elif 'monthly_kwh' in eid:
        categories['monthly_kwh'].append(eid)
    elif 'total_kwh' in eid:
        categories['total_kwh'].append(eid)
    elif 'liang_deng_shi_chang' in eid:
        categories['liang_deng_shi_chang'].append(eid)
    elif 'yong_dian_liang' in eid:
        categories['yong_dian_liang'].append(eid)
    elif 'zm1_' in eid:
        categories['zm1_'].append(eid)
    else:
        categories['other'].append(eid)

print('--- 按功能分类 ---')
for cat, entities in sorted(categories.items(), key=lambda x: -len(x[1])):
    if entities:
        print(f'\n  [{cat}] ({len(entities)}个)')
        for eid in sorted(entities)[:15]:
            plat = platform_map.get(eid, '?')
            print(f'    {eid:65s} | platform={plat}')
        if len(entities) > 15:
            print(f'    ... 还有 {len(entities)-15} 个')

# 特别检查：utility_meter相关
print()
print('=== utility_meter 平台实体详情 ===')
um_entities = [e for e in unavail_restored if platform_map.get(e['entity_id']) == 'utility_meter']
print(f'  总数: {len(um_entities)}')
if um_entities:
    for e in sorted(um_entities, key=lambda x: x['entity_id'])[:20]:
        attrs = e.get('attributes', {})
        print(f"    {e['entity_id']:60s} | last_reset={attrs.get('last_reset','?')}")
