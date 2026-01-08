# 在 knowledge-hub 目錄下執行
import sqlite3
conn = sqlite3.connect('data/knowledge.db')

# 查看失敗的文件
print("=== 失敗的文件 ===")
for row in conn.execute("SELECT id, filename, status FROM documents WHERE status = 'failed'"):
    print(row)

# 查看任務錯誤
print("\n=== 任務紀錄 ===")
for row in conn.execute("SELECT id, status, error_log FROM index_jobs"):
    print(row)

conn.close()