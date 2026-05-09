import requests
import json
import os
import time

with open('.ha_connection_info.json', 'r', encoding='utf-8') as f:
    conn_info = json.load(f)

HA_URL = conn_info['ha_api']['url'].rstrip('/')
TOKEN = conn_info['ha_api']['token']

headers = {
    'Authorization': f'Bearer {TOKEN}',
    'Content-Type': 'application/json'
}

def check_api():
    """检查 HA API 连接"""
    try:
        r = requests.get(f'{HA_URL}/api/', headers=headers, timeout=10)
        print(f"API 状态: {r.status_code} - {r.json().get('message', 'OK')}")
        return True
    except Exception as e:
        print(f"API 连接失败: {e}")
        return False

def list_entities(domain='sensor'):
    """列出指定域的实体"""
    try:
        r = requests.get(f'{HA_URL}/api/states', headers=headers, timeout=10)
        if r.status_code == 200:
            entities = r.json()
            matching = [e['entity_id'] for e in entities if e['entity_id'].startswith(f'{domain}.') and 'p2s' in e['entity_id'].lower()]
            print(f"\n找到 {len(matching)} 个 p2s 相关 {domain} 实体:")
            for eid in sorted(matching)[:20]:
                print(f"  - {eid}")
            if len(matching) > 20:
                print(f"  ... 还有 {len(matching) - 20} 个")
            return matching
        else:
            print(f"获取实体失败: {r.status_code}")
            return []
    except Exception as e:
        print(f"获取实体异常: {e}")
        return []

def check_lovelace_resources():
    """检查 Lovelace 资源配置"""
    try:
        r = requests.get(f'{HA_URL}/api/lovelace/resources', headers=headers, timeout=10)
        if r.status_code == 200:
            resources = r.json()
            print(f"\n当前 Lovelace 资源 ({len(resources)} 个):")
            for res in resources:
                print(f"  - {res.get('url', 'N/A')} ({res.get('type', 'N/A')})")
            return resources
        else:
            print(f"获取资源失败: {r.status_code}")
            return []
    except Exception as e:
        print(f"获取资源异常: {e}")
        return []

def check_file_exists(path):
    """检查服务器上的文件是否存在"""
    try:
        r = requests.get(f'{HA_URL}/local/{path}', headers=headers, timeout=10)
        if r.status_code == 200:
            print(f"  ✓ 文件存在: /local/{path} ({len(r.content)} bytes)")
            return True
        else:
            print(f"  ✗ 文件不存在: /local/{path} (HTTP {r.status_code})")
            return False
    except Exception as e:
        print(f"  ✗ 检查文件异常: {e}")
        return False

def restart_ha():
    """重启 Home Assistant"""
    try:
        r = requests.post(f'{HA_URL}/api/services/homeassistant/restart', headers=headers, json={}, timeout=10)
        if r.status_code == 200:
            print("✓ 重启命令已发送")
            return True
        else:
            print(f"✗ 重启失败: {r.status_code}")
            return False
    except Exception as e:
        print(f"✗ 重启异常: {e}")
        return False

def reload_lovelace():
    """重载 Lovelace 配置"""
    try:
        r = requests.post(f'{HA_URL}/api/services/lovelace/reload_resources', headers=headers, json={}, timeout=10)
        if r.status_code == 200:
            print("✓ Lovelace 资源重载命令已发送")
            return True
        else:
            print(f"✗ 重载失败: {r.status_code}")
            return False
    except Exception as e:
        print(f"✗ 重载异常: {e}")
        return False

print("=" * 80)
print("Home Assistant 诊断工具")
print("=" * 80)

if not check_api():
    print("无法连接到 HA API，退出")
    exit(1)

print("\n--- 检查 JS 文件 ---")
check_file_exists('pa-v346-final.js')
check_file_exists('test-card.js')

print("\n--- 检查传感器实体 ---")
list_entities('sensor')

print("\n--- 检查 Lovelace 资源 ---")
check_lovelace_resources()

print("\n" + "=" * 80)
print("诊断完成")
print("=" * 80)
