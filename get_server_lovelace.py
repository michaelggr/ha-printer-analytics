import requests
import json

with open('.ha_connection_info.json', 'r', encoding='utf-8') as f:
    conn_info = json.load(f)

HA_URL = conn_info['ha_api']['url'].rstrip('/')
TOKEN = conn_info['ha_api']['token']
headers = {'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json'}

print("=== 从服务器获取 Lovelace 配置 ===\n")

# 1. 获取所有 dashboard
print("1. 获取所有 dashboards...")
r = requests.get(f'{HA_URL}/api/lovelace/dashboards', headers=headers)
print(f"   状态码: {r.status_code}")
if r.status_code == 200:
    dashboards = r.json()
    print(f"   找到 {len(dashboards)} 个 dashboard")
    for d in dashboards:
        print(f"   - {d.get('id', 'unknown')}: {d.get('title', 'no title')}")

# 2. 获取主配置
print("\n2. 获取 HA 配置...")
r2 = requests.get(f'{HA_URL}/api/config', headers=headers)
if r2.status_code == 200:
    cfg = r2.json()
    lovelace_mode = cfg.get('lovelace', {}).get('mode', 'unknown')
    print(f"   Lovelace 模式: {lovelace_mode}")

# 3. 检查服务器上的 ui-lovelace.yaml（通过 SMB 方式）
print("\n3. 检查是否有 ui-lovelace.yaml...")
try:
    import smbclient
    from smbclient import open_file
    
    smbclient.register_session(
        conn_info['samba']['host'],
        username=conn_info['samba']['username'],
        password=conn_info['samba']['password']
    )
    
    file_path = f"\\\\{conn_info['samba']['host']}\\{conn_info['samba']['share']}\\ui-lovelace.yaml"
    print(f"   尝试读取: {file_path}")
    
    with open_file(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # 搜索 expander-card
    print(f"\n4. 搜索 expander-card 引用...")
    if 'expander-card' in content.lower():
        print("   ❗ 找到 expander-card 引用！")
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if 'expander' in line.lower():
                print(f"   行 {i+1}: {line.strip()}")
        
        # 保存服务器配置到本地用于分析
        with open('server_ui-lovelace.yaml', 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"\n   ✓ 已保存服务器配置到 server_ui-lovelace.yaml")
    else:
        print("   ✓ 未找到 expander-card 引用")
        
except Exception as e:
    print(f"   SMB 读取失败: {e}")
    print("   尝试通过 API 获取 storage 模式的配置...")
    
    # 尝试获取 storage 模式的 dashboard 数据
    for d in dashboards:
        dash_id = d.get('id')
        print(f"\n   尝试获取 dashboard: {dash_id}")
        r_dash = requests.get(f'{HA_URL}/api/lovelace/dashboards/{dash_id}', headers=headers)
        if r_dash.status_code == 200:
            dash_data = r_dash.json()
            dash_json = json.dumps(dash_data, indent=2, ensure_ascii=False)
            if 'expander' in dash_json.lower():
                print(f"   ❗ dashboard {dash_id} 中找到 expander-card！")
                with open(f'server_dashboard_{dash_id}.json', 'w', encoding='utf-8') as f:
                    f.write(dash_json)
                print(f"   ✓ 已保存到 server_dashboard_{dash_id}.json")
