# Knowledge Hub - 本地端 RAG 知識庫系統

**Knowledge Hub** 是一個模組化的本地端檢索增強生成 (RAG) 系統，旨在索引本地文件（PDF、Markdown），將其儲存於混合式資料庫架構（SQLite + ChromaDB），並透過 **Model Context Protocol (MCP)** 提供語意搜尋功能。本系統作為後端服務，讓 AI Agent 能夠從本地檔案中檢索有根據的上下文資訊。

## 🏗️ 系統架構

本系統採用 **Clean Architecture (整潔架構)**，強制分離核心領域邏輯、資料持久層與外部介面。

### 資料流管道 (Data Pipeline)
1.  **攝取 (Ingestion)**：`Scanner` 偵測檔案 -> `Parser` 提取文字 -> `Chunker` 切分語意片段 -> `Embedder` 向量化。
2.  **儲存 (Storage)**：Metadata 存於 ACID 相容的 SQLite；向量存於優化過 ANN 搜尋的 ChromaDB。
3.  **檢索 (Retrieval)**：MCP/API 請求 -> Embedding 轉換 -> 向量搜尋 -> Metadata 豐富化 -> 回傳結果。

### 目錄結構映射
| 路徑 | 層級 | 職責 |
| :--- | :--- | :--- |
| `core/` | Domain (領域層) | 純 Python 邏輯 (向量/Embedding 抽象層、切分策略)。 |
| `models/` | Persistence (持久層) | SQLite 的資料存取物件 (DAO)。 |
| `api/` | Interface (介面層) | REST 端點 (Flask/FastAPI)。 |
| `mcp_server.py` | Interface (介面層) | **MCP 入口點**，供 LLM Agent 連接使用。 |
| `data/` | Storage (儲存層) | SQLite 檔案 (`knowledge.db`) 與 ChromaDB 持久化數據。 |
| `tests/` | Testing | 系統測試、偵錯工具與單元測試。 |
| `scripts/` | Utilities | 資料庫維護、重設與非同步任務管理腳本。 |

---

## 🛠️ 測試與工具

系統提供多種工具與測試腳本，執行時請確保位於專案根目錄：

### 測試腳本 (`tests/`)
*   **搜尋測試**: `python tests/test_search.py` - 測試向量檢索功能。
*   **切分測試**: `python tests/test_chunker.py` - 驗證智慧章節切分邏輯。
*   **資料庫檢查**: `python tests/dbcheck.py` - 查看 SQLite 中的文件狀態與錯誤紀錄。

### 維護腳本 (`scripts/`)
*   **重置系統**: `python scripts/dbterminate.py` - 清除所有索引紀錄並重設文件狀態。
*   **重新索引**: `python scripts/reindex_failed.py` - 重新處理失敗的文件。


## 💾 資料庫綱要與模型

### 關聯式儲存 (SQLite)
*路徑：`data/knowledge.db`*
用於狀態追蹤、檔案 Metadata 管理以及確保操作的等冪性 (Idempotency)。

```sql
CREATE TABLE documents (
    id TEXT PRIMARY KEY,            -- UUID
    filename TEXT NOT NULL,
    filepath TEXT UNIQUE NOT NULL,  -- 實體路徑
    folder TEXT,                    -- 邏輯分組
    status TEXT DEFAULT 'pending',  -- 狀態機：pending -> processing -> indexed
    chunks_count INTEGER,
    metadata JSON,                  -- 可擴充欄位
    created_at DATETIME
);

CREATE TABLE index_jobs (           -- 非同步任務追蹤
    id TEXT PRIMARY KEY,
    status TEXT,
    processed_files INTEGER,
    failed_files INTEGER,
    error_log JSON
);
```

### 向量儲存 (ChromaDB)
*路徑：`data/chroma/`*
*   **Collection 名稱**：`knowledge_chunks`
*   **Embedding 模型**：`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
*   **Metadata 欄位**：`document_id` (關聯 ID), `chunk_index` (順序), `page` (頁碼), `folder` (過濾用)。

---

## 🔌 MCP 介面規格 (Interface Specification)

`mcp_server.py` 向 LLM Context 暴露了以下工具 (Tools)。

### 工具：`search_knowledge`
對向量資料庫執行語意相似度搜尋。
*   **參數 (Args)**：
    *   `query` (str)：自然語言查詢語句。
    *   `top_k` (int, 預設=5)：檢索的區塊數量。
    *   `threshold` (float, 預設=0.0)：相似度門檻值。
*   **回傳 (Returns)**：包含 `text`、`score` (相似度) 與 `source` 的 JSON 列表。

### 工具：`ask_knowledge_base`
檢索上下文並模擬 RAG 回應（目前執行檢索並格式化上下文）。
*   **參數 (Args)**：
    *   `question` (str)：使用者的問題。
    *   `top_k` (int, 預設=5)：上下文視窗大小。
*   **回傳 (Returns)**：包含合成回答與引用來源的字串。

### 工具：`get_document_content`
檢索特定文件的完整內容（將所有區塊重新組裝）。
*   **參數 (Args)**：
    *   `doc_id` (str)：文件的 UUID。
*   **回傳 (Returns)**：包含完整 Metadata 與排序後所有文字區塊的 JSON 物件。

### 工具：`get_index_status`
回傳索引引擎目前的健康狀況與狀態。
*   **回傳 (Returns)**：包含計數 (`indexed`, `pending`, `failed`) 與最新背景任務詳情的 JSON 物件。

---

## 🚀 安裝與設定

###先決條件
*   Python 3.10+
*   `pip install -r requirements.txt`

### MCP 設定 (Claude Desktop/Cursor)
請將以下內容新增至您的 MCP 設定檔：

```json
{
  "mcpServers": {
    "knowledge-hub": {
      "command": "python",
      "args": ["/absolute/path/to/knowledge-hub/mcp_server.py"],
      "env": {
        "PYTHONIOENCODING": "utf-8"
      }
    }
  }
}
```
