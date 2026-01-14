#!/usr/bin/env python3
"""
Knowledge Hub - Memory Optimized Document Indexing CLI

獨立的CLI工具，用於索引文檔到向量資料庫，避免記憶體耗盡問題。
不依賴Flask應用，專門處理大量文檔的批次索引作業。

使用方法：
    python scripts/index_documents.py --resume
    python scripts/index_documents.py --full-reindex --batch-size 3
    python scripts/index_documents.py --single-file "documents/example.pdf"
"""

import os
import sys
import json
import time
import argparse
import psutil
import traceback
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple

# 設定專案路徑
sys.path.append(str(Path(__file__).parent.parent))

from config import Config
from models.database import db
from core.scanner import scan_directory, sync_documents
from core.parser import parse_document
from core.chunker import chunk_document_with_pages
from core.embedder import embed_texts
from core.vectordb import add_chunks, delete_document_chunks


class MemoryMonitor:
    """記憶體使用量監控"""

    def __init__(self, max_memory_mb: Optional[int] = None):
        self.max_memory_mb = max_memory_mb or (psutil.virtual_memory().available // (1024 * 1024) * 0.8)  # 80%可用記憶體
        self.process = psutil.Process()
        self.start_memory = self.get_memory_usage()

    def get_memory_usage(self) -> int:
        """取得目前記憶體使用量 (MB)"""
        return self.process.memory_info().rss // (1024 * 1024)

    def check_memory_limit(self) -> bool:
        """檢查是否超過記憶體限制"""
        current = self.get_memory_usage()
        return current > self.max_memory_mb

    def get_memory_stats(self) -> Dict:
        """取得記憶體統計"""
        current = self.get_memory_usage()
        return {
            'current_mb': current,
            'max_allowed_mb': self.max_memory_mb,
            'usage_percent': (current / self.max_memory_mb) * 100 if self.max_memory_mb > 0 else 0,
            'available_mb': psutil.virtual_memory().available // (1024 * 1024)
        }


class DocumentIndexer:
    """文檔索引器 - 記憶體優化版本"""

    def __init__(self, memory_monitor: MemoryMonitor, batch_size: int = 5, verbose: bool = False):
        self.memory_monitor = memory_monitor
        self.batch_size = batch_size
        self.verbose = verbose
        self.stats = {
            'processed': 0,
            'successful': 0,
            'failed': 0,
            'skipped': 0,
            'memory_peaks': []
        }

    def log(self, message: str, level: str = 'INFO'):
        """記錄訊息"""
        if self.verbose or level in ['ERROR', 'WARNING']:
            timestamp = datetime.now().strftime('%H:%M:%S')
            print(f"[{timestamp}] {level}: {message}")

    def check_file_size_limit(self, filepath: str, max_size_mb: int = 50) -> bool:
        """檢查文件大小是否超過限制"""
        size_mb = Path(filepath).stat().st_size / (1024 * 1024)
        if size_mb > max_size_mb:
            self.log(f"文件過大 ({size_mb:.1f}MB > {max_size_mb}MB): {filepath}", 'WARNING')
            return False
        return True

    def cleanup_memory(self):
        """手動清理記憶體"""
        import gc
        gc.collect()

        # 記錄記憶體使用峰值
        mem_stats = self.memory_monitor.get_memory_stats()
        self.stats['memory_peaks'].append(mem_stats['current_mb'])

        if self.verbose:
            self.log(f"記憶體清理完成，目前使用: {mem_stats['current_mb']}MB")

    def process_single_document(self, doc: Dict) -> Tuple[bool, str]:
        """
        處理單一文檔

        Args:
            doc: 文檔資訊字典

        Returns:
            (成功標記, 錯誤訊息)
        """
        doc_id = doc['id']
        filepath = doc['filepath']
        filename = doc['filename']

        try:
            # 檢查記憶體使用量
            if self.memory_monitor.check_memory_limit():
                return False, "記憶體使用量過高"

            # 檢查文件大小
            if not self.check_file_size_limit(filepath):
                return False, "文件過大"

            self.log(f"處理文檔: {filename} (ID: {doc_id})")

            # 更新狀態為處理中
            db.update_document_status(doc_id, 'processing')

            # 1. 解析文檔
            self.log(f"  - 解析文檔中: {filepath}", 'DEBUG')
            try:
                parsed = parse_document(filepath)
                if parsed and parsed.get('text'):
                    self.log(f"    解析成功，文字長度: {len(parsed['text'])} 字元，頁數: {len(parsed.get('pages', []))}", 'DEBUG')
                else:
                    self.log(f"    解析失敗或無文字內容", 'WARNING')
            except Exception as parse_e:
                self.log(f"    解析異常: {str(parse_e)}", 'ERROR')
                raise

            if not parsed or not parsed.get('text'):
                error_msg = "解析失敗：無法提取文字"
                self.log(f"   ❌ {error_msg}")
                db.update_document_status(doc_id, 'failed')
                return False, error_msg

            # 3. 切分文檔
            self.log(f"   - 切分中...", 'DEBUG')
            chunks = chunk_document_with_pages(
                parsed.get('pages', []),
                chunk_size=Config.CHUNK_SIZE,
                use_smart_chunking=True
            )

            if not chunks:
                error_msg = "切分失敗：無有效chunk"
                self.log(f"   ❌ {error_msg}")
                db.update_document_status(doc_id, 'failed')
                return False, error_msg

            # 2. 切分文檔
            self.log(f"  - 切分中...", 'DEBUG')
            chunks = chunk_document_with_pages(
                parsed.get('pages', []),
                chunk_size=Config.CHUNK_SIZE,
                use_smart_chunking=True
            )

            if not chunks:
                error_msg = "切分失敗：無有效chunk"
                self.log(f"  ❌ {error_msg}")
                # Update with error info - implementation depends on database schema
                # For now, just mark as failed
                db.update_document_status(doc_id, 'failed')
                return False, error_msg

            # 3. 分批生成嵌入向量 (記憶體優化)
            self.log(f"  - 向量化 {len(chunks)} chunks...", 'DEBUG')
            texts = [c['text'] for c in chunks]
            embeddings = []

            # 分批處理嵌入
            batch_size = Config.EMBEDDING_BATCH_SIZE
            total_embeddings = 0
            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i:i + batch_size]
                self.log(f"    處理嵌入批次 {i//batch_size + 1}/{(len(texts) + batch_size - 1)//batch_size} ({len(batch_texts)} 個文字)", 'DEBUG')
                try:
                    batch_embeddings = embed_texts(batch_texts)
                    embeddings.extend(batch_embeddings)
                    total_embeddings += len(batch_embeddings)
                    self.log(f"    批次嵌入成功，累計: {total_embeddings}/{len(texts)}", 'DEBUG')
                except Exception as embed_e:
                    self.log(f"    嵌入異常: {str(embed_e)}", 'ERROR')
                    raise

            if len(embeddings) != len(chunks):
                raise ValueError(f"嵌入數量不匹配: 期望 {len(chunks)}, 實際 {len(embeddings)}")

                # 檢查記憶體
                if self.memory_monitor.check_memory_limit():
                    error_msg = "嵌入過程中記憶體不足"
                    self.log(f"   ❌ {error_msg}")
                    db.update_document_status(doc_id, 'failed')
                    return False, error_msg

            # 4. 儲存到向量資料庫
            self.log(f"  - 儲存到向量資料庫...", 'DEBUG')

            # 補充metadata
            for chunk in chunks:
                chunk['metadata'].update({
                    'filename': filename,
                    'folder': doc.get('folder'),
                    'type': doc.get('type')
                })

            add_chunks(doc_id, chunks, embeddings)

            # 5. 更新狀態
            db.update_document_status(doc_id, 'indexed', chunks_count=len(chunks))

            self.log(f"  ✅ 成功索引 {len(chunks)} chunks")
            return True, ""

        except Exception as e:
            error_details = traceback.format_exc()
            error_msg = f"處理異常: {str(e)}\n詳細錯誤:\n{error_details}"
            self.log(f"  ❌ {error_msg}", 'ERROR')
            db.update_document_status(doc_id, 'failed')
            return False, error_msg

        finally:
            # 清理記憶體
            self.cleanup_memory()

    def process_batch(self, documents: List[Dict], job_id: str) -> Dict:
        """
        批次處理文檔

        Args:
            documents: 要處理的文檔列表
            job_id: 作業ID，用於進度追蹤

        Returns:
            處理統計
        """
        batch_stats = {
            'total': len(documents),
            'successful': 0,
            'failed': 0,
            'skipped': 0
        }

        self.log(f"開始處理批次，共 {len(documents)} 個文檔")

        for i, doc in enumerate(documents):
            doc_id = doc['id']
            filename = doc['filename']

            self.log(f"[{i+1}/{len(documents)}] 處理: {filename}")

            # 處理單一文檔
            success, error_msg = self.process_single_document(doc)

            if success:
                batch_stats['successful'] += 1
                self.stats['successful'] += 1
            else:
                batch_stats['failed'] += 1
                self.stats['failed'] += 1
                self.log(f"文檔處理失敗: {filename} - {error_msg}", 'ERROR')

            self.stats['processed'] += 1

            # 更新作業進度
            if job_id:
                db.update_job(job_id, processed=self.stats['processed'])

            # 批次間的小暫停，讓系統恢復
            time.sleep(0.1)

        return batch_stats

    def get_pending_documents(self, limit: Optional[int] = None) -> List[Dict]:
        """取得待處理的文檔"""
        result = db.get_documents(status='pending', limit=limit or 1000)
        return result['documents']

    def get_failed_documents(self, limit: Optional[int] = None) -> List[Dict]:
        """取得失敗的文檔"""
        result = db.get_documents(status='failed', limit=limit or 1000)
        return result['documents']


def create_index_job(total_files: int) -> str:
    """建立索引作業"""
    job_id = f"job_{int(time.time())}"
    db.create_job(job_id, total_files)
    return job_id


def main():
    """主程式"""
    job_id = None  # 初始化以避免 linter 錯誤

    parser = argparse.ArgumentParser(
        description="Knowledge Hub - 記憶體優化文檔索引CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用範例:
  python scripts/index_documents.py --resume                    # 繼續上次作業
  python scripts/index_documents.py --full-reindex --batch-size 3  # 重新索引所有，批次大小3
  python scripts/index_documents.py --single-file "documents/example.pdf"  # 處理單一文件
  python scripts/index_documents.py --dry-run --verbose         # 模擬運行，詳細輸出
        """
    )

    parser.add_argument('--resume', action='store_true',
                       help='繼續上次未完成的作業 (預設)')
    parser.add_argument('--full-reindex', action='store_true',
                       help='重新索引所有文件')
    parser.add_argument('--single-file', type=str,
                       help='只處理指定的單一文件')
    parser.add_argument('--batch-size', type=int, default=5,
                       help='每批處理的文件數量 (預設: 5)')
    parser.add_argument('--max-memory', type=int,
                       help='記憶體限制 (MB)，預設為可用記憶體的80%')
    parser.add_argument('--dry-run', action='store_true',
                       help='模擬運行，不實際處理文件')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='詳細輸出')

    args = parser.parse_args()

    # 設定預設行為
    if not any([args.resume, args.full_reindex, args.single_file]):
        args.resume = True

    # 初始化
    print("🔄 Knowledge Hub - 記憶體優化文檔索引器")
    print(f"📁 掃描目錄: {Config.SCAN_DIR}")
    print(f"💾 資料目錄: {Config.DATA_DIR}")
    print()

    # 初始化記憶體監控
    memory_monitor = MemoryMonitor(args.max_memory)

    if args.verbose:
        mem_stats = memory_monitor.get_memory_stats()
        print(f"🧠 記憶體限制: {mem_stats['max_allowed_mb']}MB")
        print(f"📊 可用記憶體: {mem_stats['available_mb']}MB")
        print()

    # 初始化索引器
    indexer = DocumentIndexer(memory_monitor, args.batch_size, args.verbose)

    try:
        # 掃描並同步文件
        if not args.dry_run:
            print("🔍 掃描並同步文件到資料庫...")
            sync_result = sync_documents(scan_path=str(Config.SCAN_DIR), recursive=True)
            print(f"📄 發現 {sync_result['total_files']} 個文件，新增 {sync_result['new_files']} 個")
            print()

        # 決定要處理的文件
        documents_to_process = []

        if args.single_file:
            # 處理單一文件
            filepath = Path(args.single_file)
            if not filepath.exists():
                print(f"❌ 文件不存在: {args.single_file}")
                return 1

            # 掃描並同步該文件
            if not args.dry_run:
                sync_documents(scan_path=str(filepath.parent), recursive=False)

            # 從資料庫取得該文件
            doc_id = None  # 需要生成doc_id
            from core.scanner import generate_doc_id
            doc_id = generate_doc_id(str(filepath))

            doc = db.get_document(doc_id)
            if doc:
                documents_to_process = [doc]
            else:
                print(f"❌ 無法在資料庫中找到文件: {args.single_file}")
                return 1

        elif args.full_reindex:
            # 重新索引所有文件
            print("🔄 重新索引所有文件...")
            if not args.dry_run:
                # 將所有indexed文件重設為pending
                with db.get_connection() as conn:
                    conn.execute("UPDATE documents SET status = 'pending' WHERE status = 'indexed'")

            documents_to_process = indexer.get_pending_documents()

        else:  # args.resume (預設)
            # 繼續未完成的作業
            print("▶️ 繼續未完成的作業...")

            # 取得pending和failed文件
            pending_docs = indexer.get_pending_documents()
            failed_docs = indexer.get_failed_documents()

            documents_to_process = pending_docs + failed_docs

            if not documents_to_process:
                print("✅ 沒有待處理的文件")
                return 0

        if not documents_to_process:
            print("❌ 沒有找到要處理的文件")
            return 1

        print(f"📋 待處理文件數量: {len(documents_to_process)}")
        print(f"📦 批次大小: {args.batch_size}")
        if args.dry_run:
            print("🧪 這是模擬運行，不會實際處理文件")
        print()

        # 建立作業
        job_id = None
        if not args.dry_run and not args.single_file:
            job_id = create_index_job(len(documents_to_process))
            print(f"📝 作業ID: {job_id}")
            print()

        # 批次處理
        start_time = time.time()
        total_batches = (len(documents_to_process) + args.batch_size - 1) // args.batch_size

        for batch_idx in range(total_batches):
            batch_start = batch_idx * args.batch_size
            batch_end = min(batch_start + args.batch_size, len(documents_to_process))
            batch_docs = documents_to_process[batch_start:batch_end]

            print(f"🔄 處理批次 {batch_idx + 1}/{total_batches} ({len(batch_docs)} 個文件)")

            if args.dry_run:
                # 模擬處理
                for doc in batch_docs:
                    indexer.log(f"模擬處理: {doc['filename']}")
                    time.sleep(0.1)  # 模擬處理時間
                batch_stats = {'successful': len(batch_docs), 'failed': 0, 'skipped': 0}
            else:
                # 實際處理
                batch_stats = indexer.process_batch(batch_docs, job_id or "")

            print(f"   ✅ 成功: {batch_stats['successful']}, ❌ 失敗: {batch_stats['failed']}")
            print()

            # 批次間的記憶體檢查
            mem_stats = memory_monitor.get_memory_stats()
            if mem_stats['usage_percent'] > 90:
                indexer.log("記憶體使用率過高，強制清理...", 'WARNING')
                indexer.cleanup_memory()

        # 完成作業
        if not args.dry_run and job_id:
            db.update_job(job_id, status='completed')

        # 總結
        elapsed_time = time.time() - start_time

        print("🏁 處理完成!")
        print(f"⏱️  總耗時: {elapsed_time:.1f} 秒")
        print(f"📊 總處理: {indexer.stats['processed']} 個文件")
        print(f"✅ 成功: {indexer.stats['successful']}")
        print(f"❌ 失敗: {indexer.stats['failed']}")

        if indexer.stats['memory_peaks']:
            max_memory = max(indexer.stats['memory_peaks'])
            print(f"🧠 記憶體峰值: {max_memory}MB")

        return 0 if indexer.stats['failed'] == 0 else 1

    except KeyboardInterrupt:
        print("\n⚠️ 收到中斷信號，正在清理...")
        if 'job_id' in locals() and job_id and not args.dry_run:
            db.update_job(job_id, status='failed')
        return 130

    except Exception as e:
        print(f"❌ 發生錯誤: {str(e)}")
        if 'job_id' in locals() and job_id and not args.dry_run:
            db.update_job(job_id, status='failed')
        return 1


if __name__ == '__main__':
    exit(main())