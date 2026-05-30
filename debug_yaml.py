import os

server_path = r'\\192.168.0.130\config\configuration.yaml'
with open(server_path, 'rb') as f:
    raw = f.read()

print(f"File size: {len(raw)} bytes")
print(f"First 3 bytes (BOM check): {raw[:3].hex()}")

# 逐字节检查位置 490-510
print(f"\nBytes around position 496-497:")
for i in range(485, min(510, len(raw))):
    b = raw[i]
    ch = chr(b) if 32 <= b < 127 else f'\\x{b:02x}'
    marker = " <<<" if i in (496, 497) else ""
    print(f"  [{i}] 0x{b:02x} = {ch}{marker}")

# 尝试解码，找到所有错误位置
print("\nScanning for invalid UTF-8 sequences:")
i = 0
errors = []
while i < len(raw):
    b = raw[i]
    if b < 0x80:
        i += 1
    elif b < 0xC0:
        errors.append(i)
        i += 1
    elif b < 0xE0:
        if i + 1 < len(raw) and 0x80 <= raw[i+1] < 0xC0:
            i += 2
        else:
            errors.append(i)
            i += 1
    elif b < 0xF0:
        if i + 2 < len(raw) and 0x80 <= raw[i+1] < 0xC0 and 0x80 <= raw[i+2] < 0xC0:
            i += 3
        else:
            errors.append(i)
            i += 1
    elif b < 0xF8:
        if i + 3 < len(raw) and 0x80 <= raw[i+1] < 0xC0 and 0x80 <= raw[i+2] < 0xC0 and 0x80 <= raw[i+3] < 0xC0:
            i += 4
        else:
            errors.append(i)
            i += 1
    else:
        errors.append(i)
        i += 1

if errors:
    print(f"Found {len(errors)} invalid UTF-8 positions:")
    for pos in errors:
        context_start = max(0, pos - 5)
        context_end = min(len(raw), pos + 5)
        print(f"  Position {pos}: bytes={raw[context_start:context_end].hex()}")
        print(f"    Context: {raw[context_start:context_end]}")
else:
    print("No invalid UTF-8 sequences found!")

# 检查 BOM 在文件中的所有位置
bom = b'\xef\xbb\xbf'
pos = 0
bom_positions = []
while True:
    pos = raw.find(bom, pos)
    if pos == -1:
        break
    bom_positions.append(pos)
    pos += 3

if bom_positions:
    print(f"\nBOM positions: {bom_positions}")
else:
    print("\nNo BOM found in file")
