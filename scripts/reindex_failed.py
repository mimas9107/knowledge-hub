import os
import sys
import json
from pathlib import Path
from datetime import datetime

# 設定專案路徑
sys.path.append(os.getcwd())

from models.database import db
from core.parser import parse_document
from core.chunker import chunk_document_with_pages
from core.embedder import embed_texts
from core.vectordb import add_chunks

def reindex_failed_documents():
    """重新索引失敗的文件"""
    
    # 1. 查詢失敗的文件 (限制 PDF 且一次處理 5 個)
    with db.get_connection() as conn:
        failed_docs = conn.execute(
            "SELECT * FROM documents WHERE status = 'failed' AND type = 'pdf' LIMIT 5"
        ).fetchall()
        
    if not failed_docs:
        print("✅ 沒有失敗的文件需要處理。")
        return

    print(f"🔄 發現 {len(failed_docs)} 個失敗的文件，準備重新索引...\n")
    
    success_count = 0
    
    for row in failed_docs:
        doc = dict(row)
        filepath = doc['filepath']
        doc_id = doc['id']
        filename = doc['filename']
        
        print(f"👉 正在處理: {filename} ...")
        
        try:
            # 2. 解析文件
            print(f"   - 解析中...", end='\r')
            parsed = parse_document(filepath)
            
            if not parsed or not parsed.get('text'):
                print(f"   ❌ 解析失敗: 無法提取文字")
                continue
                
            # 3. 切分 (保留頁碼)
            print(f"   - 切分中...   ", end='\r')
            chunks = chunk_document_with_pages(
                parsed.get('pages', []),
                chunk_size=500, # 使用預設或從 config 讀
                use_smart_chunking=True
            )
            
            if not chunks:
                print(f"   ❌ 切分失敗: 無有效 chunk")
                continue
            
            # 4. 轉向量
            print(f"   - 向量化中 ({len(chunks)} chunks)...", end='\r')
            texts = [c['text'] for c in chunks]
            embeddings = embed_texts(texts)
            
            # 5. 寫入向量資料庫
            print(f"   - 寫入資料庫...", end='\r')
            
            # 補充 metadata
            for chunk in chunks:
                chunk['metadata'].update({
                    'filename': filename,
                    'folder': doc.get('folder'),
                    'type': doc.get('type')
                })
                
            add_chunks(doc_id, chunks, embeddings)
            
            # 6. 更新狀態
            db.update_document_status(doc_id, 'indexed', chunks_count=len(chunks))
            
            print(f"   ✅ 成功索引！ ({len(chunks)} chunks)      ")
            success_count += 1
            
        except Exception as e:
            print(f"   ❌ 處理發生錯誤: {str(e)}           ")
            import traceback
            # traceback.print_exc()
            
    print("-" * 50)
    print(f"🏁 完成。成功: {success_count}, 失敗: {len(failed_docs) - success_count}")

if __name__ == "__main__":
    reindex_failed_documents()
