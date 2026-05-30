import json, os

history_dir = r'\\192.168.0.130\config\.printer_analytics\history_by_year'
serial = '22E8BJ5A2401765'

year_files = sorted([f for f in os.listdir(history_dir) if f.startswith(serial) and f.endswith('.json') and '_stats' not in f])
print(f"Year files (sorted): {year_files}")

cache_limit = 50
recent_records = []

# 模拟 load_history 的 reversed(year_files) 循环
for year_file in reversed(year_files):
    if len(recent_records) >= cache_limit:
        break
    fp = os.path.join(history_dir, year_file)
    with open(fp, 'r', encoding='utf-8') as f:
        data = json.load(f)
    records = data.get('history', []) if isinstance(data, dict) else data
    remaining = cache_limit - len(recent_records)

    print(f"\n{year_file}: {len(records)} records, remaining={remaining}")
    print(f"  File order: first={records[0].get('end_time')}, last={records[-1].get('end_time')}")
    print(f"  File is DESCENDING (newest first): {records[0].get('end_time') > records[-1].get('end_time')}")

    # records[:remaining] 取的是文件开头（最新的记录）
    taken = records[:remaining]
    print(f"  Taken first {remaining}: {taken[0].get('end_time')} to {taken[-1].get('end_time')}")

    # 拼接：records[:remaining] + recent_records
    # recent_records 初始为空，所以第一次循环后 recent_records = taken
    recent_records = taken + recent_records
    print(f"  After concat: first={recent_records[0].get('end_time')}, last={recent_records[-1].get('end_time')}")

print(f"\nBefore sort: {len(recent_records)} records")
print(f"  first={recent_records[0].get('end_time')}, last={recent_records[-1].get('end_time')}")

# sort by end_time ascending
recent_records.sort(key=lambda x: x.get("end_time", ""))
print(f"\nAfter sort (ascending): {len(recent_records)} records")
print(f"  first={recent_records[0].get('end_time')}, last={recent_records[-1].get('end_time')}")

# stats.history = coordinator.history[-50:]
last50 = recent_records[-50:]
print(f"\nLast 50 (for stats.history):")
print(f"  first={last50[0].get('end_time')}, last={last50[-1].get('end_time')}")
print(f"  This is ASCENDING (oldest first, newest last)")

# Now simulate _truncate_history_attrs
# slim_history = [精简后的记录]
# If still too large, slim_history = slim_history[len(slim_history) // 3:]
# In ascending order, this removes the OLDEST 1/3, keeping the NEWEST 2/3
# This is CORRECT behavior

# But what if the history was actually DESCENDING?
# Let's check what the API returns
print("\n--- Checking what API would return ---")
# If history is descending (newest first), slim_history[len // 3:] would
# remove the NEWEST records and keep the OLDEST records - WRONG!

# Let's verify: the API returned records from March first, February last
# This means the history is in DESCENDING order in the sensor
# But our analysis shows it should be ASCENDING after sort

# The issue might be that the sort is NOT actually happening
# or the __pycache__ was caching old code
