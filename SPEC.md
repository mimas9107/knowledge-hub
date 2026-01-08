# Knowledge Hub API 規格

> 個人 RAG 知識平台 API 設計文件
> 版本：v0.2.0
> 日期：2026-01-07

---

## 專案概述

Knowledge Hub 是一個自用的 RAG（Retrieval-Augmented Generation）知識管理平台，用於：
- 整理分類上課講義（.pdf/.pptx/.md/.docx）
- 建立向量索引供語意搜尋
- 提供問答介面，結合 LLM 生成回答
- 透過 MCP 讓 Claude 等 AI 助理直接存取個人知識庫

---

## 基礎資訊

```
Base URL: http://localhost:5002/api
Content-Type: application/json
```

---

## API 端點

### 📁 文件管理

#### `GET /documents`

列出所有文件

**Query Params:**

| 參數 | 類型 | 必填 | 說明 |
|------|------|------|------|
| folder | string | 否 | 篩選特定資料夾 |
| status | string | 否 | `pending` / `indexed` / `failed` |
| type | string | 否 | `pdf` / `pptx` / `md` / `docx` |
| page | int | 否 | 分頁，預設 1 |
| limit | int | 否 | 每頁數量，預設 20 |

**Response:**

```json
{
  "total": 42,
  "page": 1,
  "limit": 20,
  "documents": [
    {
      "id": "a1b2c3",
      "filename": "01-變數與型別.pdf",
      "folder": "Python基礎",
      "type": "pdf",
      "size_kb": 1240,
      "status": "indexed",
      "chunks_count": 23,
      "tags": ["重要"],
      "created_at": "2025-12-20T10:30:00",
      "indexed_at": "2025-12-21T08:15:00"
    }
  ]
}
```

---

#### `GET /documents/{id}`

取得單一文件詳情

**Path Params:**

| 參數 | 類型 | 說明 |
|------|------|------|
| id | string | 文件唯一識別碼 |

**Response:**

```json
{
  "id": "a1b2c3",
  "filename": "01-變數與型別.pdf",
  "filepath": "/講義/Python基礎/01-變數與型別.pdf",
  "folder": "Python基礎",
  "type": "pdf",
  "size_kb": 1240,
  "status": "indexed",
  "chunks_count": 23,
  "tags": ["重要"],
  "chunks_preview": [
    { "index": 0, "text": "Python 是一種直譯式語言..." },
    { "index": 1, "text": "變數不需要事先宣告型別..." }
  ],
  "metadata": {
    "pages": 15,
    "title": "Python 基礎教學",
    "author": "Unknown"
  },
  "created_at": "2025-12-20T10:30:00",
  "indexed_at": "2025-12-21T08:15:00"
}
```

---

#### `POST /documents/scan`

觸發目錄掃描，探索新文件

**Request:**

```json
{
  "path": "/Users/你的路徑/講義",
  "recursive": true
}
```

**Response:**

```json
{
  "status": "success",
  "new_files": 12,
  "updated_files": 3,
  "total_files": 42
}
```

---

#### `DELETE /documents/{id}`

從索引中移除文件（不刪除原始檔案）

**Response:**

```json
{
  "status": "success",
  "message": "Document removed from index"
}
```

---

### ⚙️ 索引處理

#### `POST /index/process`

處理文件建立向量索引

**Request:**

```json
{
  "document_ids": ["a1b2c3", "d4e5f6"],
  "force": false
}
```

| 欄位 | 類型 | 說明 |
|------|------|------|
| document_ids | array | 要處理的文件 ID，空陣列 = 處理所有 pending |
| force | bool | `true` = 重新處理已索引的文件 |

**Response:**

```json
{
  "status": "processing",
  "job_id": "job-xyz-123",
  "queued": 2
}
```

---

#### `GET /index/status`

查詢索引處理狀態

**Response:**

```json
{
  "total_documents": 42,
  "indexed": 38,
  "pending": 3,
  "failed": 1,
  "processing": {
    "job_id": "job-xyz-123",
    "current_file": "03-函數.pdf",
    "progress_percent": 65
  }
}
```

---

#### `GET /index/jobs/{job_id}`

查詢特定任務狀態

**Response:**

```json
{
  "job_id": "job-xyz-123",
  "status": "completed",
  "started_at": "2026-01-07T10:00:00",
  "finished_at": "2026-01-07T10:05:30",
  "processed": 5,
  "failed": 0,
  "errors": []
}
```

---

### 🔍 搜尋與問答

#### `POST /search`

語意搜尋（找出最相關的文件段落）

**Request:**

```json
{
  "query": "Python for 迴圈怎麼寫",
  "top_k": 5,
  "threshold": 0.5,
  "filter": {
    "folders": ["Python基礎"],
    "types": ["pdf", "md"],
    "tags": ["重要"]
  }
}
```

| 欄位 | 類型 | 說明 |
|------|------|------|
| query | string | 搜尋問句 |
| top_k | int | 回傳前 K 筆結果，預設 5 |
| threshold | float | 相似度門檻 0-1，預設 0.5 |
| filter | object | 篩選條件（可選） |

**Response:**

```json
{
  "query": "Python for 迴圈怎麼寫",
  "results": [
    {
      "document_id": "a1b2c3",
      "filename": "02-流程控制.pdf",
      "folder": "Python基礎",
      "chunk_index": 7,
      "text": "for 迴圈的基本語法是 for item in iterable...",
      "score": 0.89,
      "page": 12
    }
  ],
  "search_time_ms": 45
}
```

---

#### `POST /chat`

問答模式（語意搜尋 + LLM 生成回答）

**Request:**

```json
{
  "question": "Python 的 list comprehension 是什麼？",
  "top_k": 5,
  "include_sources": true,
  "model": "auto"
}
```

| 欄位 | 類型 | 說明 |
|------|------|------|
| question | string | 問題 |
| top_k | int | 參考前 K 筆相關段落 |
| include_sources | bool | 是否回傳引用來源 |
| model | string | `auto` / `ollama` / `claude` / `openai` |

**Response:**

```json
{
  "answer": "List comprehension 是 Python 中一種簡潔的語法，可以用一行程式碼建立清單。基本格式是 [expression for item in iterable if condition]...",
  "sources": [
    {
      "document_id": "a1b2c3",
      "filename": "03-資料結構.pdf",
      "folder": "Python基礎",
      "text": "List comprehension 提供一種優雅的方式...",
      "page": 8,
      "score": 0.92
    }
  ],
  "model_used": "ollama/llama3",
  "response_time_ms": 1250
}
```

---

### 🏷️ 分類與標籤

#### `GET /folders`

列出所有資料夾分類

**Response:**

```json
{
  "folders": [
    { "name": "Python基礎", "count": 15, "indexed": 15 },
    { "name": "FastAPI教學", "count": 8, "indexed": 6 },
    { "name": "LangChain", "count": 6, "indexed": 0 }
  ]
}
```

---

#### `GET /tags`

列出所有標籤

**Response:**

```json
{
  "tags": [
    { "name": "重要", "count": 12 },
    { "name": "複習", "count": 8 },
    { "name": "待整理", "count": 3 }
  ]
}
```

---

#### `POST /documents/{id}/tags`

新增/更新文件標籤

**Request:**

```json
{
  "tags": ["重要", "複習"]
}
```

**Response:**

```json
{
  "status": "success",
  "document_id": "a1b2c3",
  "tags": ["重要", "複習"]
}
```

---

#### `DELETE /documents/{id}/tags/{tag}`

移除單一標籤

---

### ⚙️ 系統設定

#### `GET /settings`

取得系統設定

**Response:**

```json
{
  "scan_path": "/Users/xxx/講義",
  "embedding_model": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
  "chunk_size": 500,
  "chunk_overlap": 50,
  "llm_provider": "ollama",
  "llm_model": "llama3"
}
```

---

#### `PUT /settings`

更新系統設定

**Request:**

```json
{
  "scan_path": "/new/path",
  "chunk_size": 800
}
```

---

## 🔌 MCP Tools

供 Claude Desktop 或其他 MCP 客戶端使用

| Tool | 參數 | 說明 |
|------|------|------|
| `list_knowledge_folders()` | 無 | 列出所有知識分類 |
| `list_documents(folder?, status?)` | folder, status | 列出文件清單 |
| `search_knowledge(query, top_k?)` | query, top_k | 語意搜尋知識庫 |
| `get_document_content(id)` | document_id | 取得文件完整內容 |
| `ask_knowledge_base(question)` | question | 問答模式 |
| `get_index_status()` | 無 | 查詢索引狀態 |

---

## 資料庫結構（SQLite）

### documents 表

```sql
CREATE TABLE documents (
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

CREATE INDEX idx_documents_folder ON documents(folder);
CREATE INDEX idx_documents_status ON documents(status);
CREATE INDEX idx_documents_type ON documents(type);
```

### tags 表

```sql
CREATE TABLE tags (
  document_id TEXT NOT NULL,
  tag TEXT NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (document_id, tag),
  FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
);

CREATE INDEX idx_tags_tag ON tags(tag);
```

### index_jobs 表

```sql
CREATE TABLE index_jobs (
  id TEXT PRIMARY KEY,
  status TEXT DEFAULT 'pending',
  total_files INTEGER DEFAULT 0,
  processed_files INTEGER DEFAULT 0,
  failed_files INTEGER DEFAULT 0,
  started_at DATETIME,
  finished_at DATETIME,
  error_log JSON
);
```

### settings 表

```sql
CREATE TABLE settings (
  key TEXT PRIMARY KEY,
  value TEXT,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

---

## 向量資料庫（ChromaDB）

Collection 結構：

```python
{
  "name": "knowledge_chunks",
  "metadata": {
    "embedding_model": "paraphrase-multilingual-MiniLM-L12-v2"
  }
}

# 每個 chunk 的結構
{
  "id": "a1b2c3_chunk_0",
  "document": "Python 是一種直譯式語言...",
  "metadata": {
    "document_id": "a1b2c3",
    "filename": "01-變數與型別.pdf",
    "folder": "Python基礎",
    "chunk_index": 0,
    "page": 1
  },
  "embedding": [0.123, -0.456, ...]
}
```

---

## 技術選型

| 層面 | 選擇 | 備註 |
|------|------|------|
| Web 框架 | Flask | 與 project-dashboard 一致 |
| 資料庫 | SQLite | 輕量、單機使用 |
| 向量資料庫 | ChromaDB | 純 Python、易整合 |
| Embedding | sentence-transformers | 本地執行、支援中文 |
| PDF 解析 | pdfplumber | 支援表格抽取 |
| PPTX 解析 | python-pptx | 官方套件 |
| DOCX 解析 | python-docx | 官方套件 |
| MD 解析 | 原生讀取 | 純文字處理 |
| LLM | Ollama / Claude API | 可切換 |

---

## 錯誤回應格式

所有 API 錯誤統一格式：

```json
{
  "error": {
    "code": "DOCUMENT_NOT_FOUND",
    "message": "Document with id 'xyz' not found"
  }
}
```

常見錯誤碼：

| Code | HTTP Status | 說明 |
|------|-------------|------|
| DOCUMENT_NOT_FOUND | 404 | 文件不存在 |
| INVALID_REQUEST | 400 | 請求格式錯誤 |
| INDEX_IN_PROGRESS | 409 | 索引處理中，無法重複觸發 |
| EMBEDDING_FAILED | 500 | Embedding 處理失敗 |
| LLM_UNAVAILABLE | 503 | LLM 服務不可用 |

---

## 版本紀錄

| 版本 | 日期 | 說明 |
|------|------|------|
| v0.2.0 | 2026-01-07 | 智慧章節切分：根據標題結構切分，保留上下文 |
| v0.1.0 | 2026-01-07 | 初版 API 規格 |
