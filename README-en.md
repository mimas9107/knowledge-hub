# Knowledge Hub - Local RAG System

**Knowledge Hub** is a modular, local Retrieval-Augmented Generation (RAG) system designed to index documents (PDF, Markdown), store them in a hybrid database architecture (SQLite + ChromaDB), and expose semantic search capabilities via the **Model Context Protocol (MCP)**. This system serves as a backend for AI agents to retrieve grounded context from local files.

## 🏗️ System Architecture

The system implements **Clean Architecture**, enforcing separation of concerns between the core domain, data persistence, and external interfaces.

### Data Flow Pipeline
1.  **Ingestion**: `Scanner` detects files -> `Parser` extracts text -> `Chunker` splits text -> `Embedder` vectorizes text.
2.  **Storage**: Metadata is ACID-compliant (SQLite); Vectors are optimized for ANN search (ChromaDB).
3.  **Retrieval**: MCP/API Request -> Embedding -> Vector Search -> Metadata Enrichment -> Result.

### Directory Structure Map
| Path | Layer | Responsibility |
| :--- | :--- | :--- |
| `core/` | Domain | Pure Python logic (Vector/Embedding abstractions, Chunking strategies). |
| `models/` | Persistence | Data Access Objects (DAO) for SQLite. |
| `api/` | Interface | REST endpoints (Flask/FastAPI). |
| `mcp_server.py` | Interface | **MCP Entry Point** for LLM Agents. |
| `data/` | Storage | SQLite file (`knowledge.db`) and ChromaDB persistence. |
| `tests/` | Testing | System tests, debugging tools, and unit tests. |
| `scripts/` | Utilities | Database maintenance, reset, and async task management scripts. |

---

## 🛠️ Testing & Utilities

The system provides various tools and testing scripts. Ensure you run these from the project root:

### Test Scripts (`tests/`)
*   **Search Test**: `python tests/test_search.py` - Test vector retrieval functionality.
*   **Chunker Test**: `python tests/test_chunker.py` - Validate semantic chunking logic.
*   **DB Check**: `python tests/dbcheck.py` - Inspect document status and error logs in SQLite.

### Maintenance Scripts (`scripts/`)
*   **Reset System**: `python scripts/dbterminate.py` - Clear all indexing records and reset document status.
*   **Re-index**: `python scripts/reindex_failed.py` - Retry processing failed documents.


## 💾 Database Schema & Models

### Relational Store (SQLite)
*Path: `data/knowledge.db`*
Used for state tracking, file metadata, and ensuring idempotency.

```sql
CREATE TABLE documents (
    id TEXT PRIMARY KEY,            -- UUID
    filename TEXT NOT NULL,
    filepath TEXT UNIQUE NOT NULL,  -- Physical path
    folder TEXT,                    -- Logical grouping
    status TEXT DEFAULT 'pending',  -- State machine: pending -> processing -> indexed
    chunks_count INTEGER,
    metadata JSON,                  -- Extensible fields
    created_at DATETIME
);

CREATE TABLE index_jobs (           -- Async job tracking
    id TEXT PRIMARY KEY,
    status TEXT,
    processed_files INTEGER,
    failed_files INTEGER,
    error_log JSON
);
```

### Vector Store (ChromaDB)
*Path: `data/chroma/`*
*   **Collection**: `knowledge_chunks`
*   **Embedding Model**: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
*   **Metadata Fields**: `document_id`, `chunk_index`, `page`, `folder`.

---

## 🔌 MCP Interface Specification

The `mcp_server.py` exposes the following tools to the LLM context.

### Tool: `search_knowledge`
Performs semantic similarity search on the vector database.
*   **Args**:
    *   `query` (str): The natural language query.
    *   `top_k` (int, default=5): Number of chunks to retrieve.
    *   `threshold` (float, default=0.0): Similarity cutoff.
*   **Returns**: JSON list of chunks with `text`, `score` (similarity), and `source`.

### Tool: `ask_knowledge_base`
Retrieves context and simulates a RAG response (currently retrieves and formats context).
*   **Args**:
    *   `question` (str): The user's question.
    *   `top_k` (int, default=5): Context window size.
*   **Returns**: String containing a synthesized answer and cited sources.

### Tool: `get_document_content`
Retrieves the full content of a specific document, reassembled from its chunks.
*   **Args**:
    *   `doc_id` (str): The UUID of the document.
*   **Returns**: JSON object containing full metadata and ordered list of all text chunks.

### Tool: `get_index_status`
Returns the current health and status of the indexing engine.
*   **Returns**: JSON object with counts (`indexed`, `pending`, `failed`) and details of the latest background job.

---

## 🚀 Setup & Configuration

### Prerequisites
*   Python 3.10+
*   `pip install -r requirements.txt`

### MCP Configuration (Claude Desktop/Cursor)
Add to your MCP settings file:

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