import json, os

history_dir = r'\\192.168.0.130\config\.printer_analytics\history_by_year'
serial = '22E8BJ5A2401765'

fp = os.path.join(history_dir, f'{serial}_2026.json')
with open(fp, 'r', encoding='utf-8') as f:
    data = json.load(f)
records = data.get('history', []) if isinstance(data, dict) else data

print(f'File has {len(records)} records')
print(f'Before sort: first={records[0].get("end_time")}, last={records[-1].get("end_time")}')

# 新逻辑：先排序，再取最后 N 条
records.sort(key=lambda x: x.get("end_time", ""))
print(f'After sort: first={records[0].get("end_time")}, last={records[-1].get("end_time")}')

cache_limit = 50
remaining = cache_limit
# records[-remaining:] 取最后 50 条（最新的）
taken = records[-remaining:]
print(f'records[-{remaining}:]: first={taken[0].get("end_time")}, last={taken[-1].get("end_time")}')
print(f'Top 5 (should be May):')
for i, r in enumerate(taken[:5]):
    print(f'  [{i}] {r.get("end_time")} - {r.get("task_name", "?")[:40]} [{r.get("status")}]')
