import codecs

f = codecs.open(r'\\192.168.0.130\config\ui-lovelace.yaml', 'r', 'utf-8-sig')
lines = f.readlines()

print('=== PM2.5 apexcharts-card (L655-L740) ===')
for i in range(654, min(740, len(lines))):
    print(f'{i+1:4d}: {lines[i]}', end='')

print('\n\n=== 能源 apexcharts-card (L1090-1175) ===')
for i in range(1089, min(1175, len(lines))):
    print(f'{i+1:4d}: {lines[i]}', end='')

f.close()
