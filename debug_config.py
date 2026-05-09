import json, urllib.request, time

token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiI1M2Q4NzBkOGY4M2U0YWY3ODIzNTJlNjVkNmVkYzY5YSIsImlhdCI6MTc3NDE5NTM2MCwiZXhwIjoyMDg5NTU1MzYwfQ.7VKORHi3sWJfROnc7HKzDyY1uwapDC8WXdLIj4sAITs'
base = 'http://192.168.0.130:8123'
hdr = {'Authorization': f'Bearer {token}'}

# 检查HA日志中的配置错误
print('=== 检查配置错误 ===')
try:
    req = urllib.request.Request(f'{base}/api/error_log', headers=hdr)
    resp = urllib.request.urlopen(req)
    log_text = resp.read().decode('utf-8', errors='replace')
    
    lines = log_text.split('\n')
    # 查找最近的错误
    error_lines = [l for l in lines if any(kw in l.lower() for kw in ['error', 'invalid', 'failed', 'utility_meter', 'input_number', 'command_line'])]
    
    print(f"  日志总行数: {len(lines)}")
    print(f"  错误相关行: {len(error_lines)}")
    
    # 显示最后20行错误
    for line in error_lines[-20:]:
        clean = line.strip()[:200]
        if clean:
            print(f"  {clean}")
            
except Exception as e:
    print(f"  Error: {e}")

# 检查config是否正确加载了新内容
print()
print('=== 验证服务器上的configuration.yaml内容 ===')
with open(r'g:\dev\ha\ha\configuration.yaml', 'r', encoding='utf-8') as f:
    content = f.read()

checks = ['utility_meter:', 'input_number:', 'command_line:', 'counter:', 'template:', 'input_datetime:']
for c in checks:
    found = c in content
    print(f"  {c:20s} {'✅' if found else '❌ MISSING'}")

# 检查input_number实体（精确ID）
print()
print('=== 精确检查input_number实体 ===')
req2 = urllib.request.Request(f'{base}/api/states', headers=hdr)
resp2 = urllib.request.urlopen(req2)
data = json.loads(resp2.read())

inp_nums = [e for e in data if e['entity_id'].startswith('input_number.light_')]
print(f"  light_开头的input_number实体: {len(inp_nums)}个")
for e in sorted(inp_nums, key=lambda x: x['entity_id']):
    restored = e.get('attributes', {}).get('restored', False)
    print(f"    {e['entity_id']:55s} | state={e['state']:12s} | restored={restored}")
