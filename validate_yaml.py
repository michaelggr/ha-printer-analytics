﻿﻿﻿﻿﻿import requests, json, yaml

with open('.ha_connection_info.json', 'r', encoding='utf-8') as f:
    conn_info = json.load(f)

HA_URL = conn_info['ha_api']['url'].rstrip('/')
TOKEN = conn_info['ha_api']['token']
headers = {'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json'}

# 读取当前配置文件
with open(r'Y:\ui-lovelace.yaml', 'r', encoding='utf-8') as f:
    content = f.read()

# 尝试解析YAML
try:
    data = yaml.safe_load(content)
    print("✅ YAML语法正确")
    
    # 检查首页卡片
    for view in data.get('views', []):
        if view.get('path') == 'home':
            cards = view.get('cards', [])
            print(f"\n首页共有 {len(cards)} 个卡片:")
            for i, card in enumerate(cards):
                card_type = card.get('type', 'unknown')
                title = card.get('title', '无标题')
                entity = card.get('entity', card.get('entities', ''))
                print(f"  [{i}] type={card_type}, title={title}")
                if card_type == 'custom:mini-graph-card':
                    # 检查是否有不兼容的参数组合
                    has_entity = 'entity' in card
                    has_entities = 'entities' in card
                    has_group = 'group' in card
                    if has_entity and has_group:
                        print(f"      ⚠️ 使用entity时不应有group参数!")
                    if has_entities:
                        ents = card['entities']
                        print(f"      entities数量: {len(ents)}")
                    if has_entity:
                        print(f"      entity: {entity}")
except yaml.YAMLError as e:
    print(f"❌ YAML语法错误: {e}")
