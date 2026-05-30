import json, os

history_dir = r'\\192.168.0.130\config\.printer_analytics\history_by_year'
serial = '22E8BJ5A2401765'

fp = os.path.join(history_dir, f'{serial}_2026.json')
with open(fp, 'r', encoding='utf-8') as f:
    data = json.load(f)

records = data.get('history', []) if isinstance(data, dict) else data
print(f'Total records in file: {len(records)}')
print(f'First record end_time: {records[0].get("end_time")}')
print(f'Last record end_time: {records[-1].get("end_time")}')
print(f'File is DESCENDING: {records[0].get("end_time") > records[-1].get("end_time")}')

# Simulate load_history: records[:50]
recent = records[:50]
print(f'\nrecords[:50] (first 50 from file):')
print(f'  First: {recent[0].get("end_time")}')
print(f'  Last: {recent[-1].get("end_time")}')

# After sort ascending
recent.sort(key=lambda x: x.get("end_time", ""))
print(f'\nAfter sort ascending:')
print(f'  First: {recent[0].get("end_time")}')
print(f'  Last: {recent[-1].get("end_time")}')

# Now check: what if load_history was using records[-50:] (OLD CODE)?
old_code = records[-50:]
print(f'\nOLD CODE records[-50:] (last 50 from file):')
print(f'  First: {old_code[0].get("end_time")}')
print(f'  Last: {old_code[-1].get("end_time")}')
old_code.sort(key=lambda x: x.get("end_time", ""))
print(f'  After sort: First: {old_code[0].get("end_time")}, Last: {old_code[-1].get("end_time")}')

# Check the actual server storage.py
with open(r'\\192.168.0.130\config\custom_components\printer_analytics\storage.py', 'r', encoding='utf-8') as f:
    content = f.read()

if 'records[:remaining]' in content:
    print('\nServer storage.py uses records[:remaining] (CORRECT)')
elif 'records[-remaining:]' in content:
    print('\nServer storage.py uses records[-remaining:] (OLD BUG)')
else:
    print('\nCannot determine which version is on server')
