import requests
import json
import time

with open('.ha_connection_info.json', 'r', encoding='utf-8') as f:
    conn_info = json.load(f)

HA_URL = conn_info['ha_api']['url'].rstrip('/')
TOKEN = conn_info['ha_api']['token']

headers = {'Authorization': f'Bearer {TOKEN}'}

print("=" * 80)
print("最终验证 - 检查打印机分析页面所有关键组件")
print("=" * 80)

# 1. 验证 JS 文件无 BOM
print("\n--- 1. 验证 JS 文件 ---")
r = requests.get(f'{HA_URL}/local/pa-v346-final.js', headers=headers, timeout=10)
if r.status_code == 200:
    content = r.content
    has_bom = content[:3] == b'\xef\xbb\xbf'
    print(f"  文件大小: {len(content)} bytes")
    print(f"  BOM 标记: {'⚠️ 有' if has_bom else '✓ 无'}")
    print(f"  开头字符: {content[:20].decode('utf-8', errors='replace')}")
    
    # 检查关键内容
    text = content.decode('utf-8', errors='replace')
    checks = [
        ('class PrinterAnalyticsCard', '类定义'),
        ("customElements.define('printer-analytics-card'", '元素注册'),
        ('window.customCards', '卡片注册'),
        ('_renderHistoryPage', '历史页面方法'),
        ('_renderFilamentUsage', '耗材使用方法'),
        ('_renderRealtimeMonitor', '实时监控方法'),
    ]
    for keyword, desc in checks:
        if keyword in text:
            print(f"  ✓ {desc}")
        else:
            print(f"  ✗ {desc} 缺失")
else:
    print(f"  ✗ HTTP {r.status_code}")

# 2. 验证所有传感器实体
print("\n--- 2. 验证传感器实体 ---")
r = requests.get(f'{HA_URL}/api/states', headers=headers, timeout=10)
if r.status_code == 200:
    entities = r.json()
    entity_map = {e['entity_id']: e for e in entities}
    
    # P2S 关键实体
    p2s_entities = [
        ('sensor.p2s_p2s_da_yin_li_shi', '打印历史'),
        ('sensor.p2s_p2s_zong_da_yin_ci_shu', '总打印次数'),
        ('sensor.p2s_p2s_cheng_gong_lu', '成功率'),
        ('sensor.p2s_p2s_da_yin_zhuang_tai', '打印状态'),
        ('sensor.p2s_22e8bj5a2401765_task_name', '当前任务'),
        ('sensor.p2s_22e8bj5a2401765_print_progress', '打印进度'),
        ('sensor.p2s_22e8bj5a2401765_ams_1_tray_1', 'AMS托盘1'),
    ]
    
    print("  P2S 传感器:")
    for eid, name in p2s_entities:
        if eid in entity_map:
            state = entity_map[eid].get('state', 'N/A')
            print(f"    ✓ {name}: {state}")
        else:
            print(f"    ✗ {name}: 不存在")
    
    # a1mini 关键实体
    a1mini_entities = [
        ('sensor.a1mini_a1mini_da_yin_li_shi', '打印历史'),
        ('sensor.a1mini_a1mini_zong_da_yin_ci_shu', '总打印次数'),
        ('sensor.a1mini_a1mini_cheng_gong_lu', '成功率'),
        ('sensor.a1mini_a1mini_da_yin_zhuang_tai', '打印状态'),
        ('sensor.a1mini_0300aa5a1600497_task_name', '当前任务'),
    ]
    
    print("  a1mini 传感器:")
    for eid, name in a1mini_entities:
        if eid in entity_map:
            state = entity_map[eid].get('state', 'N/A')
            print(f"    ✓ {name}: {state}")
        else:
            print(f"    ✗ {name}: 不存在")

# 3. 验证配置文件
print("\n--- 3. 验证配置文件 ---")
import os
samba_config = conn_info['samba']
unc_path = f'\\\\{samba_config["host"]}\\config'

config_path = os.path.join(unc_path, 'config', 'configuration.yaml')
if os.path.exists(config_path):
    with open(config_path, 'r', encoding='utf-8') as f:
        content = f.read()
    has_bom = content[:1] == '\ufeff'
    print(f"  configuration.yaml: BOM={'有' if has_bom else '无'}, 包含 pa-v346-final.js={'是' if 'pa-v346-final.js' in content else '否'}")
else:
    print(f"  ✗ configuration.yaml 不存在")

yaml_path = os.path.join(unc_path, 'config', 'ui-printer-analytics.yaml')
if os.path.exists(yaml_path):
    with open(yaml_path, 'r', encoding='utf-8') as f:
        content = f.read()
    has_bom = content[:1] == '\ufeff'
    has_correct_a1mini = 'a1mini_a1mini_da_yin_li_shi' in content
    print(f"  ui-printer-analytics.yaml: BOM={'有' if has_bom else '无'}, a1mini正确实体={'是' if has_correct_a1mini else '否'}")
else:
    print(f"  ✗ ui-printer-analytics.yaml 不存在")

# 4. 验证 JS 文件可被浏览器正确解析
print("\n--- 4. 验证 JS 文件解析 ---")
try:
    import subprocess
    result = subprocess.run(['node', '-e', f'''
const fs = require('fs');
const https = require('http');
const options = {{
    hostname: '192.168.0.130',
    port: 8123,
    path: '/local/pa-v346-final.js',
    method: 'GET',
    headers: {{ 'Authorization': 'Bearer {TOKEN}' }}
}};
const req = https.request(options, (res) => {{
    let data = '';
    res.on('data', (chunk) => {{ data += chunk; }});
    res.on('end', () => {{
        try {{
            new Function(data);
            console.log('✓ JS 文件可以被正确解析为函数');
        }} catch(e) {{
            console.log('✗ JS 解析错误: ' + e.message);
        }}
    }});
}});
req.end();
'''], capture_output=True, text=True, timeout=15)
    print(f"  {result.stdout.strip()}")
    if result.stderr:
        print(f"  stderr: {result.stderr[:200]}")
except Exception as e:
    print(f"  验证异常: {e}")

print("\n" + "=" * 80)
print("验证完成！")
print("=" * 80)
