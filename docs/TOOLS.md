# Knowledge Hub 開發工具指南

## SQLite 資料庫查詢工具

Knowledge Hub 使用 SQLite 儲存文件索引狀態，以下是幾種查看資料的方式。

資料庫位置：`data/knowledge.db`

---

### 方案 1：DB Browser for SQLite（推薦，GUI）

圖形化介面，適合不熟 SQL 的使用者。

**安裝：**

```bash
# macOS
brew install --cask db-browser-for-sqlite

# Ubuntu/Debian
sudo apt install sqlitebrowser

# Windows
# 到 https://sqlitebrowser.org/dl/ 下載安裝
```

**使用方式：**

1. 開啟 DB Browser for SQLite
2. 點選 `File` → `Open Database`
3. 選擇 `knowledge-hub/data/knowledge.db`
4. 功能說明：
   - **Database Structure**：查看表結構
   - **Browse Data**：瀏覽表格內容
   - **Execute SQL**：執行自訂 SQL 查詢
   - **Export**：匯出為 CSV/JSON

**常用操作：**

- 查看所有文件：Browse Data → 選 `documents` 表
- 篩選狀態：在 Filter 欄輸入 `status = 'pending'`
- 匯出報表：Execute SQL 後點 Export

---

### 方案 2：sqlite3 命令列工具

系統內建，適合快速查詢。

**基本用法：**

```bash
# 進入資料庫
cd knowledge-hub
sqlite3 data/knowledge.db

# 顯示格式設定（建議先執行）
.mode column
.headers on
```

**常用指令：**

```sql
-- 列出所有表
.tables

-- 查看表結構
.schema documents

-- 查看所有文件
SELECT * FROM documents;

-- 統計各狀態數量
SELECT status, COUNT(*) as count 
FROM documents 
GROUP BY status;

-- 查看特定資料夾
SELECT filename, status, chunks_count 
FROM documents 
WHERE folder = 'Python基礎';

-- 查看失敗的文件
SELECT filename, folder 
FROM documents 
WHERE status = 'failed';

-- 查看標籤
SELECT d.filename, t.tag 
FROM documents d 
JOIN tags t ON d.id = t.document_id;

-- 查看最近新增的文件
SELECT filename, created_at 
FROM documents 
ORDER BY created_at DESC 
LIMIT 10;

-- 離開
.quit
```

**匯出資料：**

```bash
# 匯出為 CSV
sqlite3 -header -csv data/knowledge.db \
  "SELECT * FROM documents" > documents.csv

# 匯出特定查詢
sqlite3 -header -csv data/knowledge.db \
  "SELECT filename, status FROM documents WHERE status='indexed'" > indexed.csv
```

---

### 方案 3：VS Code 擴充套件

適合在開發時順手查看。

**安裝擴充套件：**

1. 開啟 VS Code
2. 到 Extensions（Ctrl+Shift+X）
3. 搜尋並安裝其一：
   - **SQLite Viewer**（純檢視，輕量）
   - **SQLite**（可執行 SQL）

**使用方式：**

- 在檔案總管中直接點擊 `data/knowledge.db`
- SQLite Viewer：自動顯示表格
- SQLite 擴充：右鍵選 Open Database，在側邊欄操作

---

### 方案 4：Python 腳本（自訂查詢）

適合整合到自動化流程。

建立 `scripts/db_query.py`：

```python
#!/usr/bin/env python3
"""
Knowledge Hub 資料庫查詢工具
用法: python scripts/db_query.py
"""
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / 'data' / 'knowledge.db'

def get_stats():
    """取得統計資訊"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 總數統計
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN status='indexed' THEN 1 ELSE 0 END) as indexed,
            SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) as pending,
            SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) as failed
        FROM documents
    """)
    row = cursor.fetchone()
    
    print("=" * 50)
    print("📊 Knowledge Hub 資料庫統計")
    print("=" * 50)
    print(f"總文件數:   {row[0]}")
    print(f"已索引:     {row[1]} ✅")
    print(f"待處理:     {row[2]} ⏳")
    print(f"失敗:       {row[3]} ❌")
    
    # 各資料夾統計
    cursor.execute("""
        SELECT folder, COUNT(*) as count 
        FROM documents 
        WHERE folder IS NOT NULL
        GROUP BY folder 
        ORDER BY count DESC
    """)
    folders = cursor.fetchall()
    
    if folders:
        print("\n📁 各資料夾文件數:")
        for folder, count in folders:
            print(f"  {folder}: {count}")
    
    # 各類型統計
    cursor.execute("""
        SELECT type, COUNT(*) as count 
        FROM documents 
        GROUP BY type 
        ORDER BY count DESC
    """)
    types = cursor.fetchall()
    
    print("\n📄 各類型文件數:")
    for t, count in types:
        print(f"  {t}: {count}")
    
    conn.close()

def list_failed():
    """列出失敗的文件"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT filename, folder, filepath 
        FROM documents 
        WHERE status = 'failed'
    """)
    rows = cursor.fetchall()
    
    if not rows:
        print("沒有失敗的文件 ✅")
        return
    
    print(f"❌ 失敗的文件 ({len(rows)} 個):")
    for filename, folder, filepath in rows:
        print(f"  - {folder or '根目錄'}/{filename}")
    
    conn.close()

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'failed':
        list_failed()
    else:
        get_stats()
```

**使用：**

```bash
# 查看統計
python scripts/db_query.py

# 查看失敗文件
python scripts/db_query.py failed
```

---

## ChromaDB 向量資料庫查詢

向量資料庫位置：`data/chroma/`

**Python 查詢：**

```python
import chromadb

client = chromadb.PersistentClient(path="data/chroma")
collection = client.get_collection("knowledge_chunks")

# 查看總數
print(f"總 chunks 數: {collection.count()}")

# 查看前 5 筆
results = collection.peek(5)
for i, doc in enumerate(results['documents']):
    print(f"[{i}] {doc[:100]}...")
```

---

## 資料庫表結構速查

### documents 表
| 欄位 | 類型 | 說明 |
|------|------|------|
| id | TEXT | 主鍵，MD5 hash |
| filename | TEXT | 檔案名稱 |
| filepath | TEXT | 完整路徑 |
| folder | TEXT | 所屬資料夾 |
| type | TEXT | pdf/pptx/md/docx |
| size_kb | INTEGER | 檔案大小 |
| status | TEXT | pending/indexed/failed |
| chunks_count | INTEGER | chunk 數量 |
| metadata | JSON | 額外資訊 |
| created_at | DATETIME | 建立時間 |
| indexed_at | DATETIME | 索引時間 |

### tags 表
| 欄位 | 類型 | 說明 |
|------|------|------|
| document_id | TEXT | 文件 ID |
| tag | TEXT | 標籤名稱 |
| created_at | DATETIME | 建立時間 |

### index_jobs 表
| 欄位 | 類型 | 說明 |
|------|------|------|
| id | TEXT | 任務 ID |
| status | TEXT | pending/processing/completed |
| total_files | INTEGER | 總文件數 |
| processed_files | INTEGER | 已處理數 |
| failed_files | INTEGER | 失敗數 |
| started_at | DATETIME | 開始時間 |
| finished_at | DATETIME | 結束時間 |
| error_log | JSON | 錯誤記錄 |
