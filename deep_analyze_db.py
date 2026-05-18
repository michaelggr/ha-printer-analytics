import sqlite3

db_path = r"\\192.168.0.130\config\home-assistant_v2.db"
backup_path = r"\\192.168.0.130\config\home-assistant_v2.db.backup"

print("=== 深度分析数据库问题 ===\n")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 1. 检查 schema 版本
print("1. 检查 schema 版本...")
cursor.execute("SELECT * FROM schema_changes")
row = cursor.fetchone()
if row:
    print(f"   schema_version: {row}")
else:
    print("   无 schema_changes 记录")

# 2. 检查 states_meta 表
print("\n2. 检查 states_meta 表（实体注册表）...")
cursor.execute("SELECT COUNT(*) FROM states_meta")
count = cursor.fetchone()[0]
print(f"   总实体数: {count}")

cursor.execute("SELECT * FROM states_meta ORDER BY entity_id LIMIT 10")
rows = cursor.fetchall()
print("   前10个实体:")
for row in rows:
    print(f"     {row}")

# 3. 检查是否有 entity_id 存储在其他地方
print("\n3. 检查 attributes 表...")
cursor.execute("SELECT COUNT(*) FROM state_attributes")
count = cursor.fetchone()[0]
print(f"   state_attributes 表记录数: {count}")

# 4. 检查 metadata_id
print("\n4. 检查 states 表的 metadata_id...")
cursor.execute("SELECT metadata_id, COUNT(*) FROM states GROUP BY metadata_id LIMIT 10")
rows = cursor.fetchall()
print("   metadata_id 分布:")
for row in rows:
    print(f"     metadata_id={row[0]}: {row[1]} 条记录")

# 5. 如果有 metadata_id，检查 states_meta
if rows and rows[0][0]:
    print("\n5. 通过 metadata_id 关联查询实体...")
    cursor.execute("""
        SELECT sm.entity_id, s.state, s.metadata_id
        FROM states s
        JOIN states_meta sm ON s.metadata_id = sm.metadata_id
        WHERE sm.entity_id LIKE '%p2s%' OR sm.entity_id LIKE '%a1mini%'
        ORDER BY s.state_id DESC
        LIMIT 10
    """)
    rows = cursor.fetchall()
    print(f"   找到 {len(rows)} 条记录:")
    for row in rows:
        print(f"     {row}")

conn.close()

print("\n\n=== 结论 ===")
print("如果 states_meta 有数据但 states 表的 entity_id 为 NULL：")
print("→ 这可能是 HA 数据库 schema 不兼容问题")
print("→ 需要重建数据库才能解决")
