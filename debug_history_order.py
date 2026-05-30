import json, os

history_dir = r'\\192.168.0.130\config\.printer_analytics\history_by_year'
serial = '22E8BJ5A2401765'

# 1. 检查数据文件的记录顺序
fp = os.path.join(history_dir, f'{serial}_2026.json')
with open(fp, 'r', encoding='utf-8') as f:
    data = json.load(f)
records = data.get('history', []) if isinstance(data, dict) else data
print(f'Data file: {len(records)} records')
print(f'  first end_time: {records[0].get("end_time")}')
print(f'  last end_time: {records[-1].get("end_time")}')
is_desc = records[0].get('end_time', '') > records[-1].get('end_time', '')
print(f'  Order: {"DESCENDING (newest first)" if is_desc else "ASCENDING (oldest first)"}')

# 2. 检查统计缓存文件
stats_dir = r'\\192.168.0.130\config\.printer_analytics'
stats_files = [f for f in os.listdir(stats_dir) if 'stats' in f.lower() or 'cache' in f.lower()]
print(f'\nStats/cache files: {stats_files}')

for sf in stats_files:
    sfp = os.path.join(stats_dir, sf)
    if sf.endswith('.json'):
        with open(sfp, 'r', encoding='utf-8') as f:
            sdata = json.load(f)
        if isinstance(sdata, dict):
            print(f'  {sf}: keys={list(sdata.keys())[:10]}')
            if 'history' in sdata:
                hist = sdata['history']
                print(f'    history: {len(hist)} records')
                if hist:
                    print(f'    first end_time: {hist[0].get("end_time")}')
                    print(f'    last end_time: {hist[-1].get("end_time")}')
        else:
            print(f'  {sf}: type={type(sdata).__name__}')

# 3. 检查 coordinator 缓存
cache_files = [f for f in os.listdir(stats_dir) if f.endswith('.json')]
print(f'\nAll JSON files in .printer_analytics:')
for f in sorted(cache_files):
    size = os.path.getsize(os.path.join(stats_dir, f))
    print(f'  {f} ({size} bytes)')
