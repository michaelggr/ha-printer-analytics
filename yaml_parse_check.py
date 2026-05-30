import yaml, codecs, json

path = r'\\192.168.0.130\config\ui-lovelace.yaml'
with codecs.open(path, 'r', 'utf-8-sig') as f:
    content = f.read()

data = yaml.safe_load(content)

# 遍历所有 view 和卡片，找出 entities 不是数组的
errors = []

def check_cards(cards, view_path, parent=''):
    for i, card in enumerate(cards):
        key = f"{view_path}[{i}]"
        if 'entities' in card and not isinstance(card['entities'], list):
            errors.append({
                'path': key,
                'view': view_path,
                'parent': parent,
                'title': card.get('title', '(none)'),
                'type': card.get('type', '?'),
                'entities_type': type(card['entities']).__name__,
                'entities_preview': str(card['entities'])[:150]
            })
        if 'cards' in card and isinstance(card['cards'], list):
            check_cards(card['cards'], key, card.get('title', parent))

for view in data.get('views', []):
    view_path = view.get('path', view.get('title', '?'))
    check_cards(view.get('cards', []), view_path)

print(f'找到 {len(errors)} 个 entities 不是数组的卡片:')
for e in errors:
    print(f"\n  View: {e['view']}")
    print(f"  Title: {e['title']}")
    print(f"  Type: {e['type']}")
    print(f"  Entities type: {e['entities_type']}")
    print(f"  Preview: {e['entities_preview']}")
