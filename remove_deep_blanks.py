import codecs

path = r'\\192.168.0.130\config\ui-lovelace.yaml'
with codecs.open(path, 'r', 'utf-8-sig') as f:
    lines = f.readlines()

new_lines = []
removed = 0

for i, line in enumerate(lines):
    stripped = line.strip()
    
    # 如果是空行，检查上下文
    if stripped == '':
        # 检查上一行和下一行的缩进
        if i > 0 and i < len(lines) - 1:
            prev = lines[i-1]
            next_line = lines[i+1]
            prev_sp = len(prev) - len(prev.lstrip()) if prev.strip() else 0
            next_sp = len(next_line) - len(next_line.lstrip()) if next_line.strip() else 0
            
            # 如果上下行缩进 >= 10sp（深层属性），移除空行
            if prev_sp >= 10 or next_sp >= 10:
                removed += 1
                continue
            
            # 如果上一行是 entities: 或下一行是 entities:，也移除
            if prev.strip() == 'entities:' or next_line.strip() == 'entities:':
                removed += 1
                continue
            
            # 如果下一行是 - entity: 或 - type:，也移除（列表项前的空行）
            if next_line.strip().startswith('- entity:') or next_line.strip().startswith('- type:'):
                if next_sp >= 10:
                    removed += 1
                    continue
    
    new_lines.append(line)

result = ''.join(new_lines)
with codecs.open(path, 'w', 'utf-8') as f:
    f.write(result)

print(f'✅ 移除了 {removed} 个深层空行')
print(f'原行数: {len(lines)}, 新行数: {len(new_lines)}')
