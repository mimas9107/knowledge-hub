# Knowledge Hub - CLI 索引工具使用指南

## 概述

`scripts/index_documents.py` 是一個記憶體優化的獨立CLI工具，用於索引文檔到向量資料庫。它專門設計來解決記憶體耗盡的問題，不依賴Flask應用。

## 主要特性

- 🧠 **記憶體優化**: 批次處理、自動清理、文件大小限制
- 🔄 **進度恢復**: 中斷後可繼續未完成的作業
- 📊 **進度追蹤**: 資料庫記錄處理狀態和統計
- 🧪 **測試模式**: dry-run模式用於測試配置
- ⚙️ **靈活配置**: 可調整批次大小、記憶體限制等

## 使用方法

### 基本用法

```bash
# 繼續未完成的作業 (推薦)
python scripts/index_documents.py

# 或明確指定
python scripts/index_documents.py --resume
```

### 其他選項

```bash
# 重新索引所有文件
python scripts/index_documents.py --full-reindex

# 處理單一文件
python scripts/index_documents.py --single-file "documents/example.pdf"

# 自訂批次大小 (減少記憶體使用)
python scripts/index_documents.py --batch-size 3

# 設定記憶體限制 (MB)
python scripts/index_documents.py --max-memory 2000

# 測試模式 (不實際處理)
python scripts/index_documents.py --dry-run --verbose
```

## 記憶體優化策略

1. **批次處理**: 每次處理少量文件，避免同時載入太多內容
2. **文件大小檢查**: 跳過超過50MB的文件
3. **及時清理**: 每個文件處理後強制垃圾回收
4. **嵌入批次**: 將向量生成分批處理
5. **記憶體監控**: 監控使用量，接近限制時發出警告

## 進度追蹤

- 使用 `index_jobs` 表追蹤作業進度
- 每個文件狀態記錄在 `documents` 表中
- 支持多個並行作業（不同作業ID）

## 故障排除

### 記憶體不足
- 降低 `--batch-size` (預設5，建議3或更小)
- 增加 `--max-memory` 限制
- 檢查系統可用記憶體

### 處理失敗的文件
```bash
# 重新處理失敗的文件
python scripts/reindex_failed.py
```

### 查看處理狀態
```bash
# 檢查資料庫狀態
python tests/dbcheck.py
```

## 效能建議

- **大量文件**: 使用小批次大小 (2-3)
- **大文件**: 考慮增加 `--max-memory`
- **測試環境**: 先用 `--dry-run` 測試配置
- **監控**: 使用 `--verbose` 查看詳細進度

## 與原始系統的差異

此CLI工具與原始Flask應用獨立運作，專注於：
- 索引作業，不提供Web界面
- 記憶體效率優化
- 批次和進度管理
- 錯誤恢復機制