from pathlib import Path
path = Path('remote_spaghetti.yaml')
text = path.read_text(encoding='utf-8')
text = text.replace('entity_id: input_input_number.', 'entity_id: input_number.')
text = text.replace('target:\n                entity_id:\n                - input_input_number.', 'target:\n                entity_id:\n                - input_number.')
path.write_text(text, encoding='utf-8')
