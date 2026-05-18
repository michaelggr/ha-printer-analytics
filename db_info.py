import sqlite3

db_path = r"\\192.168.0.130\config\home-assistant_v2.db"

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("=== 数据库基本信息 ===\n")

# 表统计
cursor.execute("""
    SELECT name FROM sqlite_master WHERE type='table'
""")
tables = cursor.fetchall()
print("数据库表:")
for t in tables:
    cursor.execute(f"SELECT COUNT(*) FROM {t[0]}")
    count = cursor.fetchone()[0]
    print(f"  {t[0]}: {count} 条记录")

print("\n\n=== states 表最新记录 ===\n")
cursor.execute("""
    SELECT entity_id, state, last_changed FROM states 
    ORDER BY last_changed DESC 
    LIMIT 10
""")

results = cursor.fetchall()
for row in results:
    print(f"  {row[0]}: {row[1]} ({row[2]})")

print("\n\n=== states_meta 表 ===\n")
cursor.execute("SELECT * FROM states_meta LIMIT 10")
results = cursor.fetchall()
for row in results:
    print(f"  {row}")

print("\n\n=== 检查是否有 BambuLab 相关实体 ===\n")
cursor.execute("""
    SELECT DISTINCT entity_id FROM states 
    WHERE entity_id LIKE '%bambu%' OR entity_id LIKE '%blt%'
    LIMIT 20
""")
results = cursor.fetchall()
print(f"找到 {len(results)} 个 BambuLab 相关实体:")
for row in results:
    print(f"  {row[0]}")

conn.close()
