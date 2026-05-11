import yaml

# Test 1: Does YAML single-quoted string handle '''' correctly?
test1 = yaml.safe_load("message: \"[''unknown'', ''unavailable'', '''']\"")
print(f'Test double-quoted: {test1}')

test2 = yaml.safe_load("message: '[''unknown'', ''unavailable'', '''']'")
print(f'Test single-quoted: {test2}')

# Test current file
try:
    with open(r'\\192.168.0.130\config\automations\10_printer.yaml', 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    print('CURRENT YAML: OK')
except Exception as e:
    print(f'CURRENT YAML ERROR: {e}')
