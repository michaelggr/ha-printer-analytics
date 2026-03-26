from pathlib import Path
path = Path('ha_export/blueprints/automation/spaghetti_detection_xiaomi.yaml')
text = path.read_text(encoding='utf-8')
target = 'below: 30'
if target not in text:
    raise SystemExit('target not found')
text = text.replace(target, 'below: 15', 1)
path.write_text(text, encoding='utf-8')
