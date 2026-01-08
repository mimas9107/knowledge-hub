import sqlite3
conn = sqlite3.connect('data/knowledge.db')
conn.execute("DELETE FROM index_jobs")
conn.execute("UPDATE documents SET status = 'pending', chunks_count = 0")
conn.commit()
conn.close()
print("已重置")