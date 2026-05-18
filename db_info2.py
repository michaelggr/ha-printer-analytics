import sqlite3

db_path = r"\\192.168.0.130\config\home-assistant_v2.db"

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("=== 检查 states 表结构 ===\n")

cursor.execute("PRAGMA table_info(states)")
columns = cursor.fetchall()
for col in columns:
    print(f"  {col}")

print("\n\n=== states 表最新记录（含 entity_id） ===\n")
cursor.execute("""
    SELECT s.entity_id, s.state, s.last_changed 
    FROM states s
    WHERE s.entity_id IS NOT NULL
    ORDER BY s.last_changed DESC 
    LIMIT 20
""")

results = cursor.fetchall()
for row in results:
    print(f"  {row[0]}: {row[1]} ({row[2]})")

print("\n\n=== 搜索 P2S 相关实体（不区分大小写）===\n")
cursor.execute("""
    SELECT DISTINCT entity_id FROM states 
    WHERE LOWER(entity_id) LIKE '%p2s%'
    ORDER BY entity_id
    LIMIT 50
""")

results = cursor.fetchall()
print(f"找到 {len(results)} 个 P2S 相关实体:")
for row in results:
    print(f"  {row[0]}")

print("\n\n=== 搜索最近的实体更新 ===\n")
cursor.execute("""
    SELECT DISTINCT entity_id FROM states 
    WHERE last_changed > '2026-05-18'
    ORDER BY last_changed DESC
    LIMIT 20
""")

results = cursor.fetchall()
print(f"5月18日之后更新的实体 ({len(results)} 个):")
for row in results:
    print(f"  {row[0]}")

conn.close()
