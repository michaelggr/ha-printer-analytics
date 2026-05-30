import codecs
path = r'\\192.168.0.130\config\ui-lovelace.yaml'
with codecs.open(path, 'r', 'utf-8-sig') as f:
    lines = f.readlines()
for start, end, title in [(704, 1180, 'power-stats section')]:
    print(f'=== {title} L{start}-{end} ===')
    for i in range(start-1, min(end, len(lines))):
        print(f'{i+1:4d}: {lines[i]}', end='')
