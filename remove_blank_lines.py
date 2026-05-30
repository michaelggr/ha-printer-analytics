import codecs, re

path = r'\\192.168.0.130\config\ui-lovelace.yaml'
with codecs.open(path, 'r', 'utf-8-sig') as f:
    content = f.read()

lines = content.split('\n')
new_lines = []
removed = 0

i = 0
while i < len(lines):
    line = lines[i]
    stripped = line.strip()
    
    # 如果当前行是空行，检查下一行是否比当前行缩进更深
    # 且上一行是非空行（说明这是属性之间的空行）
    if stripped == '' and i > 0 and i < len(lines) - 1:
        prev_stripped = lines[i-1].strip()
        next_stripped = lines[i+1].strip()
        
        if prev_stripped and next_stripped:
            prev_spaces = len(lines[i-1]) - len(lines[i-1].lstrip())
            next_spaces = len(lines[i+1]) - len(lines[i+1].lstrip())
            
            # 如果上下行缩进相同（同级属性之间），保留空行
            # 如果下一行缩进更深（子属性），移除空行
            # 如果下一行缩进更浅（父级），保留空行
            if next_spaces > prev_spaces:
                # 子属性前的空行，移除
                removed += 1
                i += 1
                continue
            # 如果上下行缩进相同，但都在 entities 列表项内部
            # 例如 "- entity:" 和 "name:" 之间的空行
            if next_spaces == prev_spaces and prev_spaces >= 10:
                # 在深层缩进中，属性间的空行移除
                removed += 1
                i += 1
                continue
    
    new_lines.append(line)
    i += 1

result = '\n'.join(new_lines)

with codecs.open(path, 'w', 'utf-8') as f:
    f.write(result)

print(f'✅ 移除了 {removed} 个多余空行')
print(f'原行数: {len(lines)}, 新行数: {len(new_lines)}')
