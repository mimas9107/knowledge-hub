"""
Knowledge Hub 資料庫模組
"""
import sqlite3
import json
from datetime import datetime
from contextlib import contextmanager
from config import Config

# 資料庫初始化 SQL
INIT_SQL = """
-- 文件主表
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    filepath TEXT UNIQUE NOT NULL,
    folder TEXT,
    type TEXT NOT NULL,
    size_kb INTEGER,
    status TEXT DEFAULT 'pending',
    chunks_count INTEGER DEFAULT 0,
    metadata JSON,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    indexed_at DATETIME
);

CREATE INDEX IF NOT EXISTS idx_documents_folder ON documents(folder);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
CREATE INDEX IF NOT EXISTS idx_documents_type ON documents(type);

-- 標籤表
CREATE TABLE IF NOT EXISTS tags (
    document_id TEXT NOT NULL,
    tag TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (document_id, tag),
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_tags_tag ON tags(tag);

-- 索引任務表
CREATE TABLE IF NOT EXISTS index_jobs (
    id TEXT PRIMARY KEY,
    status TEXT DEFAULT 'pending',
    total_files INTEGER DEFAULT 0,
    processed_files INTEGER DEFAULT 0,
    failed_files INTEGER DEFAULT 0,
    started_at DATETIME,
    finished_at DATETIME,
    error_log JSON
);

-- 系統設定表
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

class Database:
    """SQLite 資料庫操作類別"""
    
    def __init__(self, db_path=None):
        self.db_path = db_path or Config.DB_PATH
        self._init_db()
    
    def _init_db(self):
        """初始化資料庫結構"""
        with self.get_connection() as conn:
            conn.executescript(INIT_SQL)
    
    @contextmanager
    def get_connection(self):
        """取得資料庫連線（使用 context manager）"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    # ===== 文件操作 =====
    
    def get_documents(self, folder=None, status=None, doc_type=None, page=1, limit=20):
        """取得文件列表"""
        query = "SELECT * FROM documents WHERE 1=1"
        params = []
        
        if folder:
            query += " AND folder = ?"
            params.append(folder)
        if status:
            query += " AND status = ?"
            params.append(status)
        if doc_type:
            query += " AND type = ?"
            params.append(doc_type)
        
        # 計算總數
        count_query = query.replace("SELECT *", "SELECT COUNT(*)")
        
        # 加入分頁
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, (page - 1) * limit])
        
        with self.get_connection() as conn:
            total = conn.execute(count_query, params[:-2]).fetchone()[0]
            rows = conn.execute(query, params).fetchall()
            
            documents = []
            for row in rows:
                doc = dict(row)
                doc['metadata'] = json.loads(doc['metadata']) if doc['metadata'] else {}
                doc['tags'] = self.get_document_tags(doc['id'])
                documents.append(doc)
            
            return {
                'total': total,
                'page': page,
                'limit': limit,
                'documents': documents
            }
    
    def get_document(self, doc_id):
        """取得單一文件"""
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM documents WHERE id = ?", (doc_id,)
            ).fetchone()
            
            if not row:
                return None
            
            doc = dict(row)
            doc['metadata'] = json.loads(doc['metadata']) if doc['metadata'] else {}
            doc['tags'] = self.get_document_tags(doc_id)
            return doc
    
    def upsert_document(self, doc_data):
        """新增或更新文件"""
        with self.get_connection() as conn:
            conn.execute("""
                INSERT INTO documents (id, filename, filepath, folder, type, size_kb, status, metadata, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(filepath) DO UPDATE SET
                    size_kb = excluded.size_kb,
                    metadata = excluded.metadata
            """, (
                doc_data['id'],
                doc_data['filename'],
                doc_data['filepath'],
                doc_data.get('folder'),
                doc_data['type'],
                doc_data.get('size_kb', 0),
                doc_data.get('status', 'pending'),
                json.dumps(doc_data.get('metadata', {})),
                datetime.now().isoformat()
            ))
    
    def update_document_status(self, doc_id, status, chunks_count=None):
        """更新文件狀態"""
        with self.get_connection() as conn:
            if chunks_count is not None:
                conn.execute("""
                    UPDATE documents 
                    SET status = ?, chunks_count = ?, indexed_at = ?
                    WHERE id = ?
                """, (status, chunks_count, datetime.now().isoformat(), doc_id))
            else:
                conn.execute(
                    "UPDATE documents SET status = ? WHERE id = ?",
                    (status, doc_id)
                )
    
    def delete_document(self, doc_id):
        """刪除文件"""
        with self.get_connection() as conn:
            conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
    
    # ===== 標籤操作 =====
    
    def get_document_tags(self, doc_id):
        """取得文件的標籤"""
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT tag FROM tags WHERE document_id = ?", (doc_id,)
            ).fetchall()
            return [row['tag'] for row in rows]
    
    def set_document_tags(self, doc_id, tags):
        """設定文件標籤（覆蓋）"""
        with self.get_connection() as conn:
            conn.execute("DELETE FROM tags WHERE document_id = ?", (doc_id,))
            for tag in tags:
                conn.execute(
                    "INSERT INTO tags (document_id, tag) VALUES (?, ?)",
                    (doc_id, tag)
                )
    
    def get_all_tags(self):
        """取得所有標籤及數量"""
        with self.get_connection() as conn:
            rows = conn.execute("""
                SELECT tag, COUNT(*) as count 
                FROM tags 
                GROUP BY tag 
                ORDER BY count DESC
            """).fetchall()
            return [dict(row) for row in rows]
    
    # ===== 資料夾操作 =====
    
    def get_folders(self):
        """取得所有資料夾及統計"""
        with self.get_connection() as conn:
            rows = conn.execute("""
                SELECT 
                    folder as name,
                    COUNT(*) as count,
                    SUM(CASE WHEN status = 'indexed' THEN 1 ELSE 0 END) as indexed
                FROM documents
                WHERE folder IS NOT NULL
                GROUP BY folder
                ORDER BY name
            """).fetchall()
            return [dict(row) for row in rows]
    
    # ===== 索引任務操作 =====
    
    def create_job(self, job_id, total_files):
        """建立索引任務"""
        with self.get_connection() as conn:
            conn.execute("""
                INSERT INTO index_jobs (id, status, total_files, started_at)
                VALUES (?, 'processing', ?, ?)
            """, (job_id, total_files, datetime.now().isoformat()))
    
    def update_job(self, job_id, processed=None, failed=None, status=None, error=None):
        """更新任務進度"""
        with self.get_connection() as conn:
            updates = []
            params = []
            
            if processed is not None:
                updates.append("processed_files = ?")
                params.append(processed)
            if failed is not None:
                updates.append("failed_files = ?")
                params.append(failed)
            if status:
                updates.append("status = ?")
                params.append(status)
                if status in ('completed', 'failed'):
                    updates.append("finished_at = ?")
                    params.append(datetime.now().isoformat())
            if error:
                updates.append("error_log = ?")
                params.append(json.dumps(error))
            
            if updates:
                params.append(job_id)
                conn.execute(
                    f"UPDATE index_jobs SET {', '.join(updates)} WHERE id = ?",
                    params
                )
    
    def get_job(self, job_id):
        """取得任務資訊"""
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM index_jobs WHERE id = ?", (job_id,)
            ).fetchone()
            if row:
                job = dict(row)
                job['error_log'] = json.loads(job['error_log']) if job['error_log'] else []
                return job
            return None
    
    # ===== 統計 =====
    
    def get_index_status(self):
        """取得索引狀態統計"""
        with self.get_connection() as conn:
            # 統計文件
            row = conn.execute("""
                SELECT 
                    COUNT(*) as total_documents,
                    SUM(CASE WHEN status = 'indexed' THEN 1 ELSE 0 END) as indexed,
                    SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
                FROM documents
            """).fetchone()
            result = dict(row)
            
            # 取得最近任務
            latest_job = conn.execute("""
                SELECT * FROM index_jobs 
                ORDER BY started_at DESC 
                LIMIT 1
            """).fetchone()
            
            if latest_job:
                result['latest_job'] = dict(latest_job)
                
            return result


# 全域資料庫實例
db = Database()
