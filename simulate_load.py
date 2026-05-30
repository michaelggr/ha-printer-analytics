import json, os

history_dir = r'\\192.168.0.130\config\.printer_analytics\history_by_year'
serial = '22E8BJ5A2401765'

year_files = sorted([f for f in os.listdir(history_dir) if f.startswith(serial) and f.endswith('.json') and '_stats' not in f])
print(f"Year files: {year_files}")

cache_limit = 50
recent_records = []

for year_file in reversed(year_files):
    if len(recent_records) >= cache_limit:
        break
    fp = os.path.join(history_dir, year_file)
    with open(fp, 'r', encoding='utf-8') as f:
        data = json.load(f)
    records = data.get('history', []) if isinstance(data, dict) else data
    remaining = cache_limit - len(recent_records)
    print(f"\n{year_file}: {len(records)} records, remaining={remaining}")
    print(f"  File first end_time: {records[0].get('end_time', '?')}")
    print(f"  File last end_time: {records[-1].get('end_time', '?')}")
    taken = records[:remaining]
    print(f"  Taking first {remaining}: end_time range {taken[0].get('end_time')} to {taken[-1].get('end_time')}")
    recent_records = taken + recent_records

print(f"\nBefore sort: {len(recent_records)} records")
print(f"  First end_time: {recent_records[0].get('end_time')}")
print(f"  Last end_time: {recent_records[-1].get('end_time')}")

recent_records.sort(key=lambda x: x.get("end_time", ""))
print(f"\nAfter sort (ascending): {len(recent_records)} records")
print(f"  First end_time: {recent_records[0].get('end_time')}")
print(f"  Last end_time: {recent_records[-1].get('end_time')}")

last50 = recent_records[-50:]
print(f"\nLast 50 (for stats.history):")
print(f"  First end_time: {last50[0].get('end_time')}")
print(f"  Last end_time: {last50[-1].get('end_time')}")
