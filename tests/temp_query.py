import sqlite3
import os

db_path = os.path.join('data', 'knowledge.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT id, filename, chunks_count FROM documents WHERE type='pdf'")
rows = cursor.fetchall()
for row in rows:
    print(row)
conn.close()
