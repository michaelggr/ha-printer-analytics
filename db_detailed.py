import sqlite3
from datetime import datetime

db_path = r"\\192.168.0.130\config\home-assistant_v2.db"

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("=== 数据库记录统计 ===\n")

# states 表记录数
cursor.execute("SELECT COUNT(*) as cnt FROM states")
cnt = cursor.fetchone()['cnt']
print(f"states 表总记录数: {cnt}")

# 有 entity_id 的记录数
cursor.execute("SELECT COUNT(*) as cnt FROM states WHERE entity_id IS NOT NULL AND entity_id != ''")
cnt = cursor.fetchone()['cnt']
print(f"有 entity_id 的记录数: {cnt}")

# 检查最早的记录
cursor.execute("""
    SELECT entity_id, state, last_changed 
    FROM states 
    WHERE entity_id IS NOT NULL AND entity_id != ''
    ORDER BY last_changed ASC 
    LIMIT 5
""")
print("\n最早的记录:")
for row in cursor.fetchall():
    print(f"  {row['entity_id']}: {row['state']} ({row['last_changed']})")

# 检查最新的记录
cursor.execute("""
    SELECT entity_id, state, last_changed 
    FROM states 
    WHERE entity_id IS NOT NULL AND entity_id != ''
    ORDER BY last_changed DESC 
    LIMIT 10
""")
print("\n最新的记录:")
for row in cursor.fetchall():
    print(f"  {row['entity_id']}: {row['state']} ({row['last_changed']})")

# 检查是否有 P2S 相关实体
cursor.execute("""
    SELECT DISTINCT entity_id FROM states 
    WHERE entity_id LIKE '%p2s%' OR entity_id LIKE '%P2S%'
    LIMIT 20
""")
print("\n包含 'p2s' 的实体:")
p2s_entities = cursor.fetchall()
for row in p2s_entities:
    print(f"  {row['entity_id']}")
if not p2s_entities:
    print("  (无)")

# 检查是否 BambuLab 相关
cursor.execute("""
    SELECT DISTINCT entity_id FROM states 
    WHERE entity_id LIKE '%bambu%' OR entity_id LIKE '%Bambu%'
    LIMIT 20
""")
print("\n包含 'bambu' 的实体:")
bambu_entities = cursor.fetchall()
for row in bambu_entities:
    print(f"  {row['entity_id']}")
if not bambu_entities:
    print("  (无)")

conn.close()
