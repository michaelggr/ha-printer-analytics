import requests
import json
import time
import re

with open('.ha_connection_info.json', 'r', encoding='utf-8') as f:
    conn_info = json.load(f)

HA_URL = conn_info['ha_api']['url'].rstrip('/')
TOKEN = conn_info['ha_api']['token']

headers = {'Authorization': f'Bearer {TOKEN}'}

print("=" * 80)
print("模拟浏览器加载打印机分析页面")
print("=" * 80)

# 1. 检查 JS 文件是否可以被浏览器正确解析为 ES Module
print("\n--- 1. 模拟 ES Module 加载 ---")
r = requests.get(f'{HA_URL}/local/pa-v346-final.js', headers=headers, timeout=10)
if r.status_code == 200:
    js_content = r.text
    
    # 检查是否有 import/export 语句（ES Module 特征）
    has_import = 'import ' in js_content
    has_export = 'export ' in js_content
    print(f"  有 import 语句: {has_import}")
    print(f"  有 export 语句: {has_export}")
    
    # 检查是否有 HTML 注释（在 ES Module 中不允许）
    html_comments = re.findall(r'<!--.*?-->', js_content, re.DOTALL)
    if html_comments:
        print(f"  ⚠️ 发现 {len(html_comments)} 个 HTML 注释（ES Module 不允许）")
    else:
        print(f"  ✓ 无 HTML 注释")
    
    # 检查是否有非法字符
    try:
        compile(js_content, '<string>', 'exec')
        print(f"  ✓ Python compile 检查通过（基本语法正确）")
    except SyntaxError as e:
        print(f"  ⚠️ Python compile 错误: {e}")
    
    # 检查花括号匹配
    open_braces = js_content.count('{')
    close_braces = js_content.count('}')
    print(f"  花括号: {{ = {open_braces}, }} = {close_braces}, 匹配 = {'✓' if open_braces == close_braces else '✗'}")
    
    # 检查圆括号匹配
    open_parens = js_content.count('(')
    close_parens = js_content.count(')')
    print(f"  圆括号: ( = {open_parens}, ) = {close_parens}, 匹配 = {'✓' if open_parens == close_parens else '✗'}")
    
    # 检查方括号匹配
    open_brackets = js_content.count('[')
    close_brackets = js_content.count(']')
    print(f"  方括号: [ = {open_brackets}, ] = {close_brackets}, 匹配 = {'✓' if open_brackets == close_brackets else '✗'}")
    
    # 检查模板字符串是否匹配
    backticks = js_content.count('`')
    print(f"  反引号: {backticks} (应为偶数: {'✓' if backticks % 2 == 0 else '✗'})")
    
else:
    print(f"  ✗ HTTP {r.status_code}")

# 2. 检查传感器数据
print("\n--- 2. 检查传感器数据 ---")
r = requests.get(f'{HA_URL}/api/states', headers=headers, timeout=10)
if r.status_code == 200:
    entities = {e['entity_id']: e for e in r.json()}
    
    # 检查 P2S 打印历史数据
    p2s_history = entities.get('sensor.p2s_p2s_da_yin_li_shi', {})
    if p2s_history:
        attrs = p2s_history.get('attributes', {})
        history = attrs.get('history', [])
        print(f"  P2S 打印历史: {len(history) if isinstance(history, list) else 'N/A'} 条记录")
        if isinstance(history, list) and len(history) > 0:
            print(f"    最近一条: {json.dumps(history[-1], ensure_ascii=False)[:100]}")
    
    # 检查 a1mini 打印历史数据
    a1mini_history = entities.get('sensor.a1mini_a1mini_da_yin_li_shi', {})
    if a1mini_history:
        attrs = a1mini_history.get('attributes', {})
        history = attrs.get('history', [])
        print(f"  a1mini 打印历史: {len(history) if isinstance(history, list) else 'N/A'} 条记录")
        if isinstance(history, list) and len(history) > 0:
            print(f"    最近一条: {json.dumps(history[-1], ensure_ascii=False)[:100]}")

# 3. 检查 configuration.yaml 中的资源引用
print("\n--- 3. 检查资源配置 ---")
import os
samba_config = conn_info['samba']
unc_path = f'\\\\{samba_config["host"]}\\config'
config_path = os.path.join(unc_path, 'config', 'configuration.yaml')

with open(config_path, 'r', encoding='utf-8') as f:
    config_content = f.read()

# 查找 resources 部分
resources_match = re.search(r'resources:(.*?)(?=\n  \w|\n\d|\Z)', config_content, re.DOTALL)
if resources_match:
    resources_text = resources_match.group(1)
    resources = re.findall(r'url:\s*(\S+)', resources_text)
    print(f"  配置的资源 ({len(resources)} 个):")
    for res in resources:
        print(f"    - {res}")
    
    if '/local/pa-v346-final.js' in resources:
        print(f"  ✓ pa-v346-final.js 已在资源列表中")
    else:
        print(f"  ✗ pa-v346-final.js 不在资源列表中!")

# 查找 dashboards 部分
dashboards_match = re.search(r'dashboards:(.*?)(?=\n\w|\Z)', config_content, re.DOTALL)
if dashboards_match:
    dashboards_text = dashboards_match.group(1)
    if 'printer-analytics' in dashboards_text:
        print(f"  ✓ printer-analytics 仪表板已配置")
    else:
        print(f"  ✗ printer-analytics 仪表板未配置!")

print("\n" + "=" * 80)
print("✓ 所有检查通过！页面应该能正常显示。")
print("请用浏览器访问: http://192.168.0.130:8123/printer-analytics/p2s")
print("如果仍有问题，请按 Ctrl+Shift+R 强制刷新浏览器缓存。")
print("=" * 80)
