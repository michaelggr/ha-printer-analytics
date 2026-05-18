﻿﻿﻿import os
import json

history_dir = r'\\192.168.0.130\config\.printer_analytics\history_by_year'
for jfile in os.listdir(history_dir):
    if not jfile.endswith('.json'):
        continue
    jpath = os.path.join(history_dir, jfile)
    print(f"Reading: {jpath}")
    with open(jpath, 'r', encoding='utf-8') as f:
        content = f.read()
    print(f"  Content length: {len(content)}")
    print(f"  First 100 chars: {content[:100]}")
    
    try:
        records = json.loads(content)
        if isinstance(records, list):
            with_cover = sum(1 for r in records if r.get('cover_image_local'))
            print(f"  Records: {len(records)}, with cover_image_local: {with_cover}")
        else:
            print(f"  Not a list: {type(records)}")
    except json.JSONDecodeError as e:
        print(f"  JSON decode error: {e}")
