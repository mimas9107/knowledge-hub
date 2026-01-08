"""
Knowledge Hub 向量資料庫模組

使用 ChromaDB 儲存和查詢向量
"""
from typing import List, Dict, Optional
from config import Config

# 全域 ChromaDB 客戶端
_client = None
_collection = None

COLLECTION_NAME = "knowledge_chunks"


def get_collection():
    """取得或建立 ChromaDB collection"""
    global _client, _collection
    
    if _collection is None:
        try:
            import chromadb
            from chromadb.config import Settings
        except ImportError:
            raise ImportError("請安裝 chromadb: pip install chromadb")
        
        # 確保目錄存在
        Config.CHROMA_PATH.mkdir(parents=True, exist_ok=True)
        
        # 建立持久化客戶端
        _client = chromadb.PersistentClient(
            path=str(Config.CHROMA_PATH),
            settings=Settings(anonymized_telemetry=False)
        )
        
        # 取得或建立 collection
        _collection = _client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"embedding_model": Config.EMBEDDING_MODEL}
        )
        
        print(f"ChromaDB collection 已就緒，目前有 {_collection.count()} 筆資料")
    
    return _collection


def add_chunks(document_id: str, chunks: List[Dict], embeddings: List[List[float]]):
    """
    新增文件的 chunks 到向量資料庫
    
    Args:
        document_id: 文件 ID
        chunks: chunk 列表，每個包含 {index, text, metadata}
        embeddings: 對應的向量列表
    """
    collection = get_collection()
    
    # 先刪除該文件的舊資料
    delete_document_chunks(document_id)
    
    if not chunks:
        return
    
    # 準備資料
    ids = [f"{document_id}_chunk_{c['index']}" for c in chunks]
    documents = [c['text'] for c in chunks]
    metadatas = []
    
    for chunk in chunks:
        meta = {
            'document_id': document_id,
            'chunk_index': chunk['index'],
            **chunk.get('metadata', {})
        }
        # ChromaDB metadata 只支援基本類型
        meta = {k: v for k, v in meta.items() if isinstance(v, (str, int, float, bool))}
        metadatas.append(meta)
    
    # 批次新增
    collection.add(
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas
    )


def delete_document_chunks(document_id: str):
    """刪除指定文件的所有 chunks"""
    collection = get_collection()
    
    # 查詢該文件的所有 chunk IDs
    results = collection.get(
        where={"document_id": document_id},
        include=[]
    )
    
    if results['ids']:
        collection.delete(ids=results['ids'])


def get_document_chunks(document_id: str) -> List[Dict]:
    """
    取得文件的所有 chunks
    
    Args:
        document_id: 文件 ID
        
    Returns:
        list: Chunk 列表，每個包含 {index, text, page}
    """
    collection = get_collection()
    
    results = collection.get(
        where={"document_id": document_id},
        include=["documents", "metadatas"]
    )
    
    chunks = []
    if results['ids']:
        for i, chunk_id in enumerate(results['ids']):
            chunks.append({
                "index": results['metadatas'][i].get("chunk_index", 0),
                "text": results['documents'][i],
                "page": results['metadatas'][i].get("page")
            })
    
    # 按 chunk_index 排序
    chunks.sort(key=lambda x: x["index"])
    return chunks


def search(
    query_embedding: List[float],
    top_k: int = 5,
    threshold: float = 0.0,
    filters: Dict = None
) -> List[Dict]:
    """
    向量相似度搜尋
    
    Args:
        query_embedding: 查詢向量
        top_k: 回傳前 K 筆結果
        threshold: 相似度門檻（0-1，越高越嚴格）
        filters: 篩選條件 {folders, types, tags}
    
    Returns:
        list: 搜尋結果
    """
    collection = get_collection()
    
    # 建立 where 條件
    where = None
    if filters:
        conditions = []
        
        if filters.get('folders'):
            conditions.append({
                "folder": {"$in": filters['folders']}
            })
        
        if filters.get('document_ids'):
            conditions.append({
                "document_id": {"$in": filters['document_ids']}
            })
        
        if len(conditions) == 1:
            where = conditions[0]
        elif len(conditions) > 1:
            where = {"$and": conditions}
    
    # 執行查詢
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        where=where,
        include=["documents", "metadatas", "distances"]
    )
    
    # 整理結果
    search_results = []
    
    if results['ids'] and results['ids'][0]:
        for i, chunk_id in enumerate(results['ids'][0]):
            # ChromaDB 回傳的是距離，轉換為相似度分數
            distance = results['distances'][0][i]
            score = 1 / (1 + distance)  # 轉換為 0-1 分數
            
            if score < threshold:
                # 暫存低分結果，以備不時之需
                pass
            else:
                metadata = results['metadatas'][0][i] if results['metadatas'] else {}
                search_results.append({
                    'chunk_id': chunk_id,
                    'document_id': metadata.get('document_id', ''),
                    'chunk_index': metadata.get('chunk_index', 0),
                    'text': results['documents'][0][i] if results['documents'] else '',
                    'score': round(score, 4),
                    'page': metadata.get('page'),
                    'folder': metadata.get('folder'),
                })
    
    # 強健性機制：如果設定了門檻導致無結果，但原始搜尋有找到資料
    # 則回傳分數最高的那些（忽略門檻），避免使用者以為「沒資料」
    if not search_results and results['ids'] and results['ids'][0]:
        # 重新遍歷，不設門檻
        for i, chunk_id in enumerate(results['ids'][0]):
            distance = results['distances'][0][i]
            score = 1 / (1 + distance)
            
            # 為了避免回傳太離譜的結果，這裡可以設一個極低門檻 (例如 0.01)
            # 但考慮到現狀，直接回傳 top_k 即可
            if len(search_results) >= top_k:
                break
                
            metadata = results['metadatas'][0][i] if results['metadatas'] else {}
            search_results.append({
                'chunk_id': chunk_id,
                'document_id': metadata.get('document_id', ''),
                'chunk_index': metadata.get('chunk_index', 0),
                'text': results['documents'][0][i] if results['documents'] else '',
                'score': round(score, 4),
                'page': metadata.get('page'),
                'folder': metadata.get('folder'),
                'low_confidence': True  # 標記為低信心結果
            })

    return search_results


def get_collection_stats() -> Dict:
    """取得 collection 統計資訊"""
    collection = get_collection()
    return {
        'total_chunks': collection.count(),
        'collection_name': COLLECTION_NAME
    }
