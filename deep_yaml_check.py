import yaml, codecs, json

path = r'\\192.168.0.130\config\ui-lovelace.yaml'
with codecs.open(path, 'r', 'utf-8-sig') as f:
    content = f.read()

data = yaml.safe_load(content)

# 深度检查所有卡片
errors = []

def deep_check(obj, path, view_path):
    if not obj or not isinstance(obj, dict):
        return
    
    if 'entities' in obj and not isinstance(obj['entities'], list):
        errors.append({
            'path': path,
            'view': view_path,
            'title': obj.get('title', '(none)'),
            'type': obj.get('type', '?'),
            'entities_type': type(obj['entities']).__name__,
            'preview': str(obj['entities'])[:150]
        })
    
    if 'cards' in obj and isinstance(obj['cards'], list):
        for i, card in enumerate(obj['cards']):
            deep_check(card, f'{path}.cards[{i}]', view_path)
    
    # 检查 entities 列表项中的嵌套 entities
    if 'entities' in obj and isinstance(obj['entities'], list):
        for i, entity in enumerate(obj['entities']):
            if isinstance(entity, dict):
                if 'entities' in entity and not isinstance(entity['entities'], list):
                    errors.append({
                        'path': f'{path}.entities[{i}]',
                        'view': view_path,
                        'title': entity.get('name', entity.get('entity', '(none)')),
                        'type': 'sub-entity',
                        'entities_type': type(entity['entities']).__name__,
                        'preview': str(entity['entities'])[:150]
                    })

for view in data.get('views', []):
    vp = view.get('path', view.get('title', '?'))
    for i, card in enumerate(view.get('cards', [])):
        deep_check(card, f'{vp}[{i}]', vp)

print(f'找到 {len(errors)} 个 entities 不是数组的卡片:')
for e in errors:
    print(f"\n  View: {e['view']}")
    print(f"  Path: {e['path']}")
    print(f"  Title: {e['title']}")
    print(f"  Type: {e['type']}")
    print(f"  Entities type: {e['entities_type']}")
    print(f"  Preview: {e['preview']}")
