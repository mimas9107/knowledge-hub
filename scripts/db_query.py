#!/usr/bin/env python3
"""
Knowledge Hub 資料庫查詢工具

用法:
    python scripts/db_query.py          # 顯示統計
    python scripts/db_query.py failed   # 列出失敗文件
    python scripts/db_query.py recent   # 最近新增的文件
    python scripts/db_query.py sql "SELECT * FROM documents LIMIT 5"
"""
import sqlite3
import sys
import json
from pathlib import Path

# 資料庫路徑
DB_PATH = Path(__file__).parent.parent / 'data' / 'knowledge.db'


def connect():
    """建立資料庫連線"""
    if not DB_PATH.exists():
        print(f"❌ 資料庫不存在: {DB_PATH}")
        print("請先執行 python app.py 啟動服務")
        sys.exit(1)
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def show_stats():
    """顯示統計資訊"""
    conn = connect()
    cursor = conn.cursor()
    
    # 總數統計
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN status='indexed' THEN 1 ELSE 0 END) as indexed,
            SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) as pending,
            SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) as failed,
            SUM(chunks_count) as total_chunks
        FROM documents
    """)
    row = cursor.fetchone()
    
    print()
    print("=" * 55)
    print("📊 Knowledge Hub 資料庫統計")
    print("=" * 55)
    print(f"  總文件數:     {row['total'] or 0}")
    print(f"  已索引:       {row['indexed'] or 0} ✅")
    print(f"  待處理:       {row['pending'] or 0} ⏳")
    print(f"  失敗:         {row['failed'] or 0} ❌")
    print(f"  總 Chunks:    {row['total_chunks'] or 0}")
    print("-" * 55)
    
    # 各資料夾統計
    cursor.execute("""
        SELECT folder, COUNT(*) as count,
               SUM(CASE WHEN status='indexed' THEN 1 ELSE 0 END) as indexed
        FROM documents 
        WHERE folder IS NOT NULL
        GROUP BY folder 
        ORDER BY count DESC
        LIMIT 10
    """)
    folders = cursor.fetchall()
    
    if folders:
        print("\n📁 資料夾統計 (前 10):")
        for f in folders:
            status = f"[{f['indexed']}/{f['count']}]"
            print(f"  {f['folder']:<30} {status:>10}")
    
    # 各類型統計
    cursor.execute("""
        SELECT type, COUNT(*) as count 
        FROM documents 
        GROUP BY type 
        ORDER BY count DESC
    """)
    types = cursor.fetchall()
    
    if types:
        print("\n📄 檔案類型:")
        for t in types:
            print(f"  .{t['type']:<6} {t['count']:>5} 個")
    
    # 標籤統計
    cursor.execute("""
        SELECT tag, COUNT(*) as count 
        FROM tags 
        GROUP BY tag 
        ORDER BY count DESC
        LIMIT 5
    """)
    tags = cursor.fetchall()
    
    if tags:
        print("\n🏷️  常用標籤:")
        for t in tags:
            print(f"  #{t['tag']:<15} {t['count']:>3} 個文件")
    
    print()
    conn.close()


def list_failed():
    """列出失敗的文件"""
    conn = connect()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT filename, folder, filepath 
        FROM documents 
        WHERE status = 'failed'
        ORDER BY folder, filename
    """)
    rows = cursor.fetchall()
    
    if not rows:
        print("\n✅ 沒有失敗的文件\n")
        return
    
    print(f"\n❌ 失敗的文件 ({len(rows)} 個):\n")
    for row in rows:
        folder = row['folder'] or '根目錄'
        print(f"  [{folder}] {row['filename']}")
        print(f"    路徑: {row['filepath']}")
    print()
    
    conn.close()


def list_recent(limit=10):
    """列出最近新增的文件"""
    conn = connect()
    cursor = conn.cursor()
    
    cursor.execute(f"""
        SELECT filename, folder, status, created_at
        FROM documents 
        ORDER BY created_at DESC
        LIMIT {limit}
    """)
    rows = cursor.fetchall()
    
    if not rows:
        print("\n資料庫是空的\n")
        return
    
    print(f"\n🕐 最近新增的文件 ({len(rows)} 個):\n")
    for row in rows:
        status_icon = {'indexed': '✅', 'pending': '⏳', 'failed': '❌'}.get(row['status'], '?')
        folder = row['folder'] or '根目錄'
        print(f"  {status_icon} [{folder}] {row['filename']}")
        print(f"     {row['created_at']}")
    print()
    
    conn.close()


def run_sql(query):
    """執行自訂 SQL"""
    conn = connect()
    cursor = conn.cursor()
    
    try:
        cursor.execute(query)
        rows = cursor.fetchall()
        
        if not rows:
            print("\n查詢結果為空\n")
            return
        
        # 取得欄位名稱
        columns = [desc[0] for desc in cursor.description]
        
        # 計算欄位寬度
        widths = [len(col) for col in columns]
        for row in rows:
            for i, val in enumerate(row):
                widths[i] = max(widths[i], len(str(val) if val else ''))
        
        # 輸出表頭
        print()
        header = " | ".join(col.ljust(widths[i]) for i, col in enumerate(columns))
        print(header)
        print("-" * len(header))
        
        # 輸出資料
        for row in rows:
            line = " | ".join(
                str(val if val is not None else '').ljust(widths[i]) 
                for i, val in enumerate(row)
            )
            print(line)
        
        print(f"\n共 {len(rows)} 筆結果\n")
        
    except Exception as e:
        print(f"\n❌ SQL 錯誤: {e}\n")
    
    conn.close()


def show_help():
    """顯示說明"""
    print("""
Knowledge Hub 資料庫查詢工具

用法:
    python scripts/db_query.py              顯示統計資訊
    python scripts/db_query.py stats        同上
    python scripts/db_query.py failed       列出處理失敗的文件
    python scripts/db_query.py recent       列出最近新增的文件
    python scripts/db_query.py recent 20    列出最近 20 個文件
    python scripts/db_query.py sql "..."    執行自訂 SQL 查詢

範例 SQL:
    python scripts/db_query.py sql "SELECT * FROM documents LIMIT 5"
    python scripts/db_query.py sql "SELECT folder, COUNT(*) FROM documents GROUP BY folder"
    python scripts/db_query.py sql "SELECT * FROM tags"
""")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        show_stats()
    elif sys.argv[1] in ('stats', 'stat'):
        show_stats()
    elif sys.argv[1] == 'failed':
        list_failed()
    elif sys.argv[1] == 'recent':
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        list_recent(limit)
    elif sys.argv[1] == 'sql' and len(sys.argv) > 2:
        run_sql(sys.argv[2])
    elif sys.argv[1] in ('help', '-h', '--help'):
        show_help()
    else:
        show_help()
