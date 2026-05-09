﻿import yaml

with open(r'\\192.168.0.130\config\templates.yaml', 'r', encoding='utf-8') as f:
    content = f.read()

# Parse and check for errors
try:
    data = yaml.safe_load(content)
    print(f'YAML parsed OK, {len(data)} top-level entries')
    
    # Check the last 50 entries for issues
    for i, entry in enumerate(data[-50:]):
        if not isinstance(entry, dict):
            print(f'Entry {len(data)-50+i}: Not a dict - {type(entry)}')
            continue
        if 'sensor' in entry:
            sensor = entry['sensor']
            if not isinstance(sensor, dict):
                print(f'Entry {len(data)-50+i}: sensor not a dict - {type(sensor)}')
                continue
            name = sensor.get('name', 'NO NAME')
            uid = sensor.get('unique_id', 'NO UID')
            state = sensor.get('state', 'NO STATE')
            dc = sensor.get('device_class', '')
            if dc == 'duration':
                print(f'  OK: {name} | uid={uid} | has_state={bool(state)}')
except yaml.YAMLError as e:
    print(f'YAML error: {e}')
except Exception as e:
    print(f'Error: {e}')
