﻿﻿﻿import json

jpath = r'\\192.168.0.130\config\.printer_analytics\history_by_year\01KR0G2VXBQA2RJCF0KHN99W40_2026.json'
with open(jpath, 'r', encoding='utf-8') as f:
    data = json.load(f)

print(f"Type: {type(data)}")
print(f"Keys: {list(data.keys()) if isinstance(data, dict) else 'N/A'}")

if isinstance(data, dict):
    for key in data:
        val = data[key]
        if isinstance(val, list):
            print(f"  {key}: list of {len(val)}")
            if len(val) > 0:
                print(f"    First item keys: {list(val[0].keys()) if isinstance(val[0], dict) else type(val[0])}")
        elif isinstance(val, str) and len(val) > 100:
            print(f"  {key}: str({len(val)})")
        else:
            print(f"  {key}: {val}")
