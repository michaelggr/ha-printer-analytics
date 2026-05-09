﻿import urllib.request, json

# 清理 templates.yaml 中的测试条目
with open(r'\\192.168.0.130\config\templates.yaml', 'r', encoding='utf-8') as f:
    content = f.read()

# 删除测试条目
marker = '# 测试亮灯时长 template sensor'
idx = content.find(marker)
if idx != -1:
    content = content[:idx].rstrip()
    print(f'已删除测试条目')

# 也删除之前添加的亮灯时长 template sensors（如果有的话）
marker2 = '# 亮灯时长 template sensors'
idx2 = content.find(marker2)
if idx2 != -1:
    content = content[:idx2].rstrip()
    print(f'已删除旧亮灯时长条目')

with open(r'\\192.168.0.130\config\templates.yaml', 'w', encoding='utf-8') as f:
    f.write(content)

print('templates.yaml 已清理')

# 删除之前创建的 state=0 的测试传感器
TOKEN = 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiI1M2Q4NzBkOGY4M2U0YWY3ODIzNTJlNjVkNmVkYzY5YSIsImlhdCI6MTc3NDE5NTM2MCwiZXhwIjoyMDg5NTU1MzYwfQ.7VKORHi3sWJfROnc7HKzDyY1uwapDC8WXdLIj4sAITs'

# 获取所有 config entries
url = 'http://192.168.0.130:8123/api/config/config_entries/entry'
req = urllib.request.Request(url, headers={'Authorization': TOKEN})
data = json.loads(urllib.request.urlopen(req, timeout=10).read())

# 找到 state=0 的测试传感器（entry_id 01KQG7BW4E552DAY99B8WRRT7）
test_entry_id = '01KQG7BW4E552DAY99B8WRRT7'
for entry in data:
    if entry.get('entry_id') == test_entry_id:
        # 删除它
        del_url = f'http://192.168.0.130:8123/api/config/config_entries/entry/{test_entry_id}'
        del_req = urllib.request.Request(del_url, method='DELETE', headers={'Authorization': TOKEN})
        try:
            urllib.request.urlopen(del_req, timeout=10)
            print(f'已删除测试传感器: {entry.get("title")}')
        except Exception as e:
            print(f'删除失败: {e}')
        break
