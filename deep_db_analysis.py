import sqlite3

db_path = r"\\192.168.0.130\config\home-assistant_v2.db"

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("=== 深入分析数据库结构 ===\n")

# 1. 检查 states 表的精确 schema
print("1. states 表结构：")
cursor.execute("PRAGMA table_info(states)")
for col in cursor.fetchall():
    print(f"   {col}")

# 2. 检查实际数据
print("\n2. 检查实际数据样本（前5条）：")
cursor.execute("SELECT state_id, entity_id, state, metadata_id FROM states LIMIT 5")
for row in cursor.fetchall():
    print(f"   {row}")

# 3. 检查 states_meta 表
print("\n3. states_meta 表样本：")
cursor.execute("SELECT * FROM states_meta LIMIT 5")
for row in cursor.fetchall():
    print(f"   {row}")

# 4. 检查是否有 metadata_id 但没有 entity_id
print("\n4. 检查 metadata_id 分布：")
cursor.execute("""
    SELECT metadata_id, COUNT(*) as cnt 
    FROM states 
    GROUP BY metadata_id 
    HAVING cnt > 0
    LIMIT 10
""")
for row in cursor.fetchall():
    print(f"   metadata_id={row[0]}: {row[1]} 条")

# 5. 检查 states_meta 和 states 的关联
print("\n5. 通过 metadata_id 关联查询：")
cursor.execute("""
    SELECT sm.entity_id, s.state, sm.metadata_id
    FROM states s
    JOIN states_meta sm ON s.metadata_id = sm.metadata_id
    LIMIT 5
""")
rows = cursor.fetchall()
if rows:
    for row in rows:
        print(f"   {row}")
else:
    print("   无关联数据")

# 6. 检查是否有任何有效记录
print("\n6. 检查有效记录：")
cursor.execute("""
    SELECT COUNT(*) FROM states 
    WHERE entity_id IS NOT NULL AND entity_id != ''
""")
count = cursor.fetchone()[0]
print(f"   有 entity_id 的记录数: {count}")

cursor.execute("""
    SELECT COUNT(*) FROM states 
    WHERE metadata_id IS NOT NULL
""")
count = cursor.fetchone()[0]
print(f"   有 metadata_id 的记录数: {count}")

# 7. 检查是否有 p2s 相关的 metadata
print("\n7. 检查 p2s 相关实体：")
cursor.execute("SELECT * FROM states_meta WHERE entity_id LIKE '%p2s%' LIMIT 10")
for row in cursor.fetchall():
    print(f"   {row}")

conn.close()
