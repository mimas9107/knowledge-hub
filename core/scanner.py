"""
Knowledge Hub 文件掃描模組
"""
import os
import hashlib
from pathlib import Path
from config import Config

def generate_doc_id(filepath):
    """根據檔案路徑生成唯一 ID"""
    return hashlib.md5(filepath.encode('utf-8')).hexdigest()[:12]

def get_file_type(filepath):
    """取得檔案類型"""
    ext = Path(filepath).suffix.lower()
    type_map = {
        '.pdf': 'pdf',
        '.pptx': 'pptx',
        '.md': 'md',
        '.docx': 'docx'
    }
    return type_map.get(ext)

def scan_directory(scan_path=None, recursive=True):
    """
    掃描目錄中的文件
    
    Args:
        scan_path: 掃描路徑，預設使用設定檔的路徑
        recursive: 是否遞迴掃描子目錄
    
    Returns:
        list: 文件資訊列表
    """
    scan_path = Path(scan_path or Config.SCAN_DIR)
    
    if not scan_path.exists():
        return []
    
    documents = []
    
    # 選擇掃描方式
    if recursive:
        file_iter = scan_path.rglob('*')
    else:
        file_iter = scan_path.glob('*')
    
    for filepath in file_iter:
        # 跳過目錄
        if filepath.is_dir():
            continue
        
        # 檢查是否為支援的類型
        file_type = get_file_type(str(filepath))
        if not file_type:
            continue
        
        # 取得相對資料夾路徑（作為分類）
        try:
            relative_path = filepath.relative_to(scan_path)
            folder = str(relative_path.parent) if relative_path.parent != Path('.') else None
        except ValueError:
            folder = None
        
        # 建立文件資訊
        doc_info = {
            'id': generate_doc_id(str(filepath)),
            'filename': filepath.name,
            'filepath': str(filepath),
            'folder': folder,
            'type': file_type,
            'size_kb': round(filepath.stat().st_size / 1024),
            'status': 'pending',
            'metadata': {}
        }
        
        documents.append(doc_info)
    
    return documents


def sync_documents(scan_path=None, recursive=True):
    """
    同步文件到資料庫
    
    Returns:
        dict: 同步結果統計
    """
    from models.database import db
    
    # 掃描檔案系統
    scanned = scan_directory(scan_path, recursive)
    scanned_paths = {doc['filepath'] for doc in scanned}
    
    # 取得資料庫中現有文件
    existing = db.get_documents(limit=10000)
    existing_paths = {doc['filepath'] for doc in existing['documents']}
    
    # 統計
    new_files = 0
    updated_files = 0
    
    # 新增或更新文件
    for doc in scanned:
        if doc['filepath'] not in existing_paths:
            db.upsert_document(doc)
            new_files += 1
        else:
            # 檢查檔案大小是否變更
            db.upsert_document(doc)
            updated_files += 1
    
    # 註：這裡不自動刪除資料庫中已不存在的檔案
    # 讓使用者手動決定是否移除
    
    return {
        'status': 'success',
        'new_files': new_files,
        'updated_files': updated_files,
        'total_files': len(scanned)
    }
