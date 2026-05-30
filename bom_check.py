import os
files = [r'G:\dev\ha\ha\templates.yaml', r'G:\dev\ha\ha\ui-lovelace.yaml']
for fp in files:
    with open(fp, 'rb') as f:
        raw = f.read()
    has_bom = raw[:3] == b'\xef\xbb\xbf'
    name = os.path.basename(fp)
    if has_bom:
        print('BOM! ' + name + ' - removing...')
        raw = raw[3:]
        with open(fp, 'wb') as f:
            f.write(raw)
        print('  BOM removed')
    else:
        print('OK  ' + name + ' (' + str(len(raw)) + ' bytes)')
