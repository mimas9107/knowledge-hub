"""
Knowledge Hub 索引處理 API
"""
import uuid
import threading
from flask import Blueprint, jsonify, request
from models.database import db
from core.parser import parse_document
from core.chunker import chunk_document_with_pages
from core.embedder import embed_texts
from core.vectordb import add_chunks

bp = Blueprint('index', __name__, url_prefix='/api/index')

# 處理中的任務
_processing_jobs = {}


def process_documents_task(job_id: str, document_ids: list, force: bool = False):
    """背景處理文件索引任務"""
    processed = 0
    failed = 0
    errors = []
    
    total = len(document_ids)
    
    print(f"\n{'='*50}")
    print(f"開始處理索引任務: {job_id}")
    print(f"待處理文件數: {total}")
    print(f"{'='*50}\n")
    
    for doc_id in document_ids:
        try:
            doc = db.get_document(doc_id)
            if not doc:
                continue
            
            # 跳過已索引的（除非 force）
            if doc['status'] == 'indexed' and not force:
                continue
            
            # 更新狀態為處理中
            db.update_document_status(doc_id, 'processing')
            
            # 解析文件
            parsed = parse_document(doc['filepath'])
            if not parsed:
                raise Exception("無法解析文件")
                
            print(f"         解析完成，切分段落...")
            
            # 切分 chunks
            chunks = chunk_document_with_pages(
                parsed.get('pages', []),
            )
            
            if not chunks:
                raise Exception("文件內容為空")
            
            # 加入文件資訊到 metadata
            for chunk in chunks:
                chunk['metadata']['document_id'] = doc_id
                chunk['metadata']['filename'] = doc['filename']
                chunk['metadata']['folder'] = doc.get('folder')
            
            print(f"         產生 {len(chunks)} 個 chunks，建立向量...")
            
            # 產生 embeddings
            texts = [c['text'] for c in chunks]
            embeddings = embed_texts(texts)
            
            # 儲存到向量資料庫
            add_chunks(doc_id, chunks, embeddings)
            
            # 更新文件狀態
            db.update_document_status(doc_id, 'indexed', chunks_count=len(chunks))
            
            # 更新 metadata
            if parsed.get('metadata'):
                doc_data = db.get_document(doc_id)
                doc_data['metadata'] = parsed['metadata']
                db.upsert_document(doc_data)
            
            processed += 1
            
            print(f"         ✓ 完成！")
            
        except Exception as e:
            failed += 1
            errors.append({'document_id': doc_id, 'error': str(e)})
            db.update_document_status(doc_id, 'failed')
            
            print(f"         ✗ 失敗: {e}")
        
        # 更新任務進度
        db.update_job(job_id, processed=processed, failed=failed)
    
    # 任務完成
    status = 'completed' if failed == 0 else 'completed_with_errors'
    db.update_job(job_id, status=status, error=errors if errors else None)
    
    print(f"\n{'='*50}")
    print(f"任務完成: {job_id}")
    print(f"成功: {processed}, 失敗: {failed}")
    print(f"{'='*50}\n")
    
    # 從記憶體中移除
    if job_id in _processing_jobs:
        del _processing_jobs[job_id]


@bp.route('/process', methods=['POST'])
def process_index():
    """處理文件建立索引"""
    data = request.get_json() or {}
    document_ids = data.get('document_ids', [])
    force = data.get('force', False)
    
    # 如果沒指定文件，取得所有 pending 的
    if not document_ids:
        result = db.get_documents(status='pending', limit=1000)
        document_ids = [doc['id'] for doc in result['documents']]
    
    if not document_ids:
        return jsonify({
            'status': 'success',
            'message': 'No documents to process',
            'queued': 0
        })
    
    # 建立任務
    job_id = f"job-{uuid.uuid4().hex[:8]}"
    db.create_job(job_id, len(document_ids))
    
    # 背景執行
    thread = threading.Thread(
        target=process_documents_task,
        args=(job_id, document_ids, force)
    )
    thread.daemon = True
    thread.start()
    
    _processing_jobs[job_id] = {
        'thread': thread,
        'document_ids': document_ids
    }
    
    return jsonify({
        'status': 'processing',
        'job_id': job_id,
        'queued': len(document_ids)
    })


@bp.route('/status', methods=['GET'])
def get_index_status():
    """查詢索引處理狀態"""
    stats = db.get_index_status()
    
    # 檢查是否有進行中的任務
    processing = None
    for job_id, job_info in _processing_jobs.items():
        job = db.get_job(job_id)
        if job and job['status'] == 'processing':
            processing = {
                'job_id': job_id,
                'progress_percent': round(
                    (job['processed_files'] / job['total_files']) * 100
                ) if job['total_files'] > 0 else 0
            }
            break
    
    return jsonify({
        **stats,
        'processing': processing
    })


@bp.route('/jobs/<job_id>', methods=['GET'])
def get_job_status(job_id):
    """查詢特定任務狀態"""
    job = db.get_job(job_id)
    
    if not job:
        return jsonify({
            'error': {
                'code': 'JOB_NOT_FOUND',
                'message': f"Job with id '{job_id}' not found"
            }
        }), 404
    
    return jsonify({
        'job_id': job['id'],
        'status': job['status'],
        'started_at': job['started_at'],
        'finished_at': job['finished_at'],
        'processed': job['processed_files'],
        'failed': job['failed_files'],
        'errors': job['error_log'] or []
    })
