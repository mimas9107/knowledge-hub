import json
import os
from core.vectordb import search as vector_search
from core.embedder import embed_text
from models.database import db

def manual_search(query, top_k=5, threshold=0.0):
    try:
        # 1. 將查詢轉為向量
        query_embedding = embed_text(query)
        
        # 2. 進行向量搜尋
        results = vector_search(
            query_embedding=query_embedding,
            top_k=top_k,
            threshold=threshold
        )
        
        if not results:
            return "沒有找到相關內容。"
            
        # 3. 格式化輸出
        formatted_results = []
        for r in results:
            # 獲取檔名以提供更好的來源資訊
            doc_id = r.get('document_id', '')
            doc_info = db.get_document(doc_id)
            filename = doc_info.get('filename', 'Unknown') if doc_info else 'Unknown'
            
            formatted_results.append({
                "source": filename,
                "score": r.get('score', 0),
                "text": r.get('text', '').strip(),
                "page": r.get('page')
            })
            
        return json.dumps(formatted_results, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {str(e)}"

if __name__ == "__main__":
    print(manual_search("HTML 標籤說明"))
