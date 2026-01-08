"""
Knowledge Hub 文件管理 API
"""
from flask import Blueprint, jsonify, request, abort
from models.database import db
from core.scanner import sync_documents

bp = Blueprint('documents', __name__, url_prefix='/api')


@bp.route('/documents', methods=['GET'])
def list_documents():
    """列出所有文件"""
    folder = request.args.get('folder')
    status = request.args.get('status')
    doc_type = request.args.get('type')
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 20, type=int)
    
    result = db.get_documents(
        folder=folder,
        status=status,
        doc_type=doc_type,
        page=page,
        limit=limit
    )
    
    return jsonify(result)


@bp.route('/documents/<doc_id>', methods=['GET'])
def get_document(doc_id):
    """取得單一文件詳情"""
    doc = db.get_document(doc_id)
    
    if not doc:
        return jsonify({
            'error': {
                'code': 'DOCUMENT_NOT_FOUND',
                'message': f"Document with id '{doc_id}' not found"
            }
        }), 404
    
    return jsonify(doc)


@bp.route('/documents/scan', methods=['POST'])
def scan_documents():
    """觸發目錄掃描"""
    data = request.get_json() or {}
    path = data.get('path')
    recursive = data.get('recursive', True)
    
    try:
        result = sync_documents(scan_path=path, recursive=recursive)
        return jsonify(result)
    except Exception as e:
        return jsonify({
            'error': {
                'code': 'SCAN_FAILED',
                'message': str(e)
            }
        }), 500


@bp.route('/documents/<doc_id>', methods=['DELETE'])
def delete_document(doc_id):
    """從索引中移除文件"""
    doc = db.get_document(doc_id)
    
    if not doc:
        return jsonify({
            'error': {
                'code': 'DOCUMENT_NOT_FOUND',
                'message': f"Document with id '{doc_id}' not found"
            }
        }), 404
    
    # 從向量資料庫刪除
    from core.vectordb import delete_document_chunks
    delete_document_chunks(doc_id)
    
    # 從 SQLite 刪除
    db.delete_document(doc_id)
    
    return jsonify({
        'status': 'success',
        'message': 'Document removed from index'
    })


@bp.route('/documents/<doc_id>/tags', methods=['POST'])
def set_tags(doc_id):
    """設定文件標籤"""
    doc = db.get_document(doc_id)
    
    if not doc:
        return jsonify({
            'error': {
                'code': 'DOCUMENT_NOT_FOUND',
                'message': f"Document with id '{doc_id}' not found"
            }
        }), 404
    
    data = request.get_json() or {}
    tags = data.get('tags', [])
    
    db.set_document_tags(doc_id, tags)
    
    return jsonify({
        'status': 'success',
        'document_id': doc_id,
        'tags': tags
    })


@bp.route('/documents/<doc_id>/tags/<tag>', methods=['DELETE'])
def remove_tag(doc_id, tag):
    """移除單一標籤"""
    doc = db.get_document(doc_id)
    
    if not doc:
        return jsonify({
            'error': {
                'code': 'DOCUMENT_NOT_FOUND',
                'message': f"Document with id '{doc_id}' not found"
            }
        }), 404
    
    current_tags = db.get_document_tags(doc_id)
    if tag in current_tags:
        current_tags.remove(tag)
        db.set_document_tags(doc_id, current_tags)
    
    return jsonify({
        'status': 'success',
        'document_id': doc_id,
        'tags': current_tags
    })


@bp.route('/folders', methods=['GET'])
def list_folders():
    """列出所有資料夾"""
    folders = db.get_folders()
    return jsonify({'folders': folders})


@bp.route('/tags', methods=['GET'])
def list_tags():
    """列出所有標籤"""
    tags = db.get_all_tags()
    return jsonify({'tags': tags})
