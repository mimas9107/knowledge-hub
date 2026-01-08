"""
Knowledge Hub MCP Server
使用 FastMCP 提供知識庫存取功能
版本：v0.3.0
"""
import json
import time
import sys
from fastmcp import FastMCP
from core.vectordb import search as vector_search, get_collection, get_document_chunks
from core.embedder import embed_text, get_model
from models.database import db

# 初始化 MCP Server
VERSION = "v0.3.0"
mcp = FastMCP("KnowledgeHub")

def log(message: str):
    """將日誌輸出至 stderr，避免干擾 MCP 通訊協定"""
    print(f"[*] {message}", file=sys.stderr, flush=True)

def initialize_services():
    """預載服務以避免冷啟動卡頓"""
    log(f"正在初始化核心服務 ({VERSION})...")
    start_time = time.time()
    
    try:
        log(f"載入 Embedding 模型...")
        get_model()
        
        log(f"連接向量資料庫 (ChromaDB)...")
        get_collection()
        
        log(f"檢查資料庫狀態 (SQLite)...")
        db.get_folders()
        
        elapsed = time.time() - start_time
        log(f"✅ 服務初始化完成 (耗時: {elapsed:.2f}s)")
    except Exception as e:
        log(f"❌ 初始化失敗: {str(e)}")

@mcp.tool()
def search_knowledge(query: str, top_k: int = 5, threshold: float = 0.0) -> str:
    """
    搜尋知識庫中的相關內容。
    當使用者詢問具體知識、講義內容或技術問題時使用此工具。
    """
    try:
        log(f"收到搜尋請求: '{query}'")
        overall_start = time.time()
        
        # 1. 將查詢轉為向量
        t0 = time.time()
        query_embedding = embed_text(query)
        t_embed = time.time() - t0
        log(f"- Embedding 完成 (耗時: {t_embed:.4f}s)")
        
        # 2. 進行向量搜尋
        t0 = time.time()
        results = vector_search(
            query_embedding=query_embedding,
            top_k=top_k,
            threshold=threshold
        )
        t_search = time.time() - t0
        log(f"- 向量搜尋完成 (耗時: {t_search:.4f}s, 找到 {len(results)} 筆)")
        
        if not results:
            return "沒有找到相關內容，請嘗試調整關鍵字。"
            
        # 3. 格式化輸出
        formatted_results = []
        for r in results:
            formatted_results.append({
                "source": f"{r.get('folder', 'Unknown')}/{r.get('document_id', '')}",
                "score": r.get('score', 0),
                "text": r.get('text', '').strip(),
                "page": r.get('page')
            })
            
        elapsed = time.time() - overall_start
        log(f"搜尋總計耗時: {elapsed:.2f}s")
        return json.dumps(formatted_results, ensure_ascii=False, indent=2)
        
    except Exception as e:
        log(f"搜尋發生錯誤: {str(e)}")
        return f"搜尋發生錯誤: {str(e)}"

@mcp.tool()
def ask_knowledge_base(question: str, top_k: int = 5) -> str:
    """
    問答模式：基於知識庫回答問題。
    此工具會先搜尋相關文件，然後組合回答（目前僅回傳檢索結果與摘要建議）。
    
    Args:
        question: 問題
        top_k: 參考前 K 筆相關段落
    """
    try:
        log(f"收到問答請求: '{question}'")
        
        # 1. 搜尋
        query_embedding = embed_text(question)
        results = vector_search(query_embedding=query_embedding, top_k=top_k)
        
        if not results:
            return "抱歉，在知識庫中找不到相關資訊。"
            
        # 2. 組合回答 (模擬 RAG)
        answer = f"根據知識庫中的 {len(results)} 筆相關資料：\n\n"
        answer += "最相關的內容來自：\n"
        
        for r in results[:3]:
            source = f"{r.get('folder', '')}/{r.get('document_id', '')}"
            text_preview = r.get('text', '')[:150].replace('\n', ' ')
            answer += f"- [{source}] (Score: {r.get('score', 0):.2f})\n  {text_preview}...\n"
            
        answer += "\n詳細來源資料：\n" + json.dumps(results, ensure_ascii=False, indent=2)
        return answer
        
    except Exception as e:
        log(f"問答發生錯誤: {str(e)}")
        return f"發生錯誤: {str(e)}"

@mcp.tool()
def list_folders() -> str:
    """
    列出知識庫中所有的資料夾分類。
    
    Returns:
        JSON 格式的資料夾列表
    """
    folders = db.get_folders()
    return json.dumps(folders, ensure_ascii=False, indent=2)

@mcp.tool()
def list_documents(folder: str = None, limit: int = 20) -> str:
    """
    列出指定資料夾或所有的文件。
    
    Args:
        folder: 資料夾名稱 (可選)
        limit: 顯示數量 (預設 20)
        
    Returns:
        JSON 格式的文件列表
    """
    result = db.get_documents(folder=folder, limit=limit)
    
    # 簡化輸出，只回傳重要欄位
    simple_docs = []
    for doc in result.get('documents', []):
        simple_docs.append({
            "id": doc['id'],
            "filename": doc['filename'],
            "folder": doc['folder'],
            "status": doc['status'],
            "chunks_count": doc.get('chunks_count', 0),
            "tags": doc.get('tags', [])
        })
        
    return json.dumps(simple_docs, ensure_ascii=False, indent=2)

@mcp.tool()
def get_document_content(doc_id: str) -> str:
    """
    取得單一文件的完整內容（包含所有 Chunks）。
    
    Args:
        doc_id: 文件 ID
    """
    try:
        # 1. 取得 Metadata
        doc = db.get_document(doc_id)
        if not doc:
            return "找不到該文件。"
            
        # 2. 取得 Content Chunks
        chunks = get_document_chunks(doc_id)
        
        response = {
            "metadata": doc,
            "chunks_count": len(chunks),
            "chunks": chunks
        }
        
        return json.dumps(response, ensure_ascii=False, indent=2)
    except Exception as e:
        log(f"讀取文件內容錯誤: {str(e)}")
        return f"讀取錯誤: {str(e)}"

@mcp.tool()
def get_index_status() -> str:
    """
    查詢索引狀態與最近的任務資訊。
    """
    status = db.get_index_status()
    return json.dumps(status, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    # 在啟動 Server 之前先執行初始化
    initialize_services()
    
    # 預設使用 stdio
    #mcp.run()
    mcp.run(transport="streamable-http")