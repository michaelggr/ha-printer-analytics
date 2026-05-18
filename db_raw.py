import sqlite3

db_path = r"\\192.168.0.130\config\home-assistant_v2.db"

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("=== 检查 states 表原始数据 ===\n")

# 直接查询前10条
cursor.execute("SELECT * FROM states LIMIT 10")
rows = cursor.fetchall()

print(f"列名: {[desc[0] for desc in cursor.description]}\n")

for i, row in enumerate(rows):
    print(f"记录 {i+1}:")
    print(f"  state_id: {row[0]}")
    print(f"  entity_id: '{row[1]}' (type: {type(row[1])}, len: {len(str(row[1])) if row[1] else 0})")
    print(f"  state: '{row[2]}'")
    print(f"  last_changed: '{row[5]}'")
    print()

# 检查 entity_id 列的实际值
print("\n=== entity_id 列统计 ===")
cursor.execute("SELECT COUNT(*), COUNT(entity_id), COUNT(CASE WHEN entity_id IS NULL THEN 1 END) FROM states")
result = cursor.fetchone()
print(f"总行数: {result[0]}")
print(f"非NULL的entity_id数: {result[1]}")
print(f"NULL的entity_id数: {result[2]}")

# 检查是否有任何记录有非空 entity_id
cursor.execute("SELECT state_id, entity_id FROM states WHERE length(entity_id) > 0 LIMIT 5")
results = cursor.fetchall()
print(f"\n有非空entity_id的记录数: {len(results)}")
for r in results:
    print(f"  {r}")

conn.close()
