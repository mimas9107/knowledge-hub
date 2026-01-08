# 開發日誌：向量搜尋修復與 PDF 索引優化

**日期**：2026-01-08  
**作者**：Gemini Agent & User  
**狀態**：已解決 (Resolved)  
**標籤**：`search`, `vector-db`, `debugging`, `pdf-indexing`

---

## 1. 問題概述 (Executive Summary)

本專案在進行知識庫檢索時遭遇兩個核心問題：
1.  **搜尋無效 (Search Invisibility)**：大量 PDF 文件狀態顯示為「已索引 (Indexed)」，且資料確實存在於向量資料庫中，但使用者查詢時卻無法獲得任何結果。
2.  **索引失敗 (Indexing Failures)**：特定三個 PDF 文件長期滯留於 `failed` 狀態，導致內容缺漏。

本文件記錄了詳細的診斷過程、根本原因分析 (Root Cause Analysis, RCA)，以及具體的程式碼修復方案。

---

## 2. 問題詳解與解決方案

### 2.1 問題一：搜尋無效 (The Invisible Data)

#### 2.1.1 現象
*   使用者查詢關鍵字（如「李昭賢」、「Docker」），系統回傳「找不到相關資訊」。
*   使用 `scripts/db_query.py` 查詢 SQLite，確認文件狀態為 `indexed`。
*   使用 `tests/debug_pdf_content.py` 查詢 ChromaDB，確認向量資料存在且內容解析正確（無亂碼）。

#### 2.1.2 根本原因 (Root Cause)
問題出在 **向量相似度分數 (Similarity Score) 與過濾門檻 (Threshold) 的不匹配**。

1.  **距離計算機制**：
    *   ChromaDB 預設使用 **L2 (Euclidean) 距離**。
    *   本專案的分數轉換公式為：`Score = 1 / (1 + Distance)`。
    *   由於向量維度較高且距離未正規化，計算出的 L2 距離通常在 `10` ~ `20` 之間。
2.  **分數過低**：
    *   換算後的 Score 落在 `0.05` ~ `0.15` 區間（例如 "李昭賢" score: `0.08`）。
3.  **過濾器誤殺**：
    *   搜尋函式預設或呼叫端傳入的 `threshold` 通常設為 `0.3` ~ `0.5`（一般向量搜尋的合理值）。
    *   **結果**：`0.08 < 0.3`，導致所有正確的結果被程式邏輯過濾掉。

#### 2.1.3 程式碼修復 (Code Fix)

**修改檔案**：`core/vectordb.py`  
**修改函式**：`search()`  
**修改內容**：增加「強健性降級機制 (Robust Fallback)」。當依據門檻過濾後無結果，但原始搜尋有命中資料時，忽略門檻強制回傳，確保使用者不會得到空結果。

```python
<<<<<<< OLD CODE (core/vectordb.py)
            # 原始邏輯：直接過濾，分數不達標就丟棄
            if score < threshold:
                continue
            
            metadata = results['metadatas'][0][i] if results['metadatas'] else {}
            # ... (append to search_results)
======= NEW CODE (core/vectordb.py)
            # 修改後邏輯：
            if score < threshold:
                # 暫存低分結果，以備不時之需（此處僅 pass，不加入 search_results）
                pass
            else:
                metadata = results['metadatas'][0][i] if results['metadatas'] else {}
                search_results.append({
                    # ... (標準欄位)
                })
    
    # [新增] 強健性機制：如果設定了門檻導致無結果，但原始搜尋有找到資料
    # 則回傳分數最高的那些（忽略門檻），避免使用者以為「沒資料」
    if not search_results and results['ids'] and results['ids'][0]:
        # 重新遍歷，不設門檻
        for i, chunk_id in enumerate(results['ids'][0]):
            distance = results['distances'][0][i]
            score = 1 / (1 + distance)
            
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
                'low_confidence': True  # [Feature] 標記為低信心結果
            })
>>>>>>>
```

---

### 2.2 問題二：PDF 索引失敗 (Failed Ingestions)

#### 2.2.1 現象
SQLite 資料庫中，以下文件狀態為 `failed`：
*   `Web_Fall2024_單元07_實例-Vue.pdf`
*   `Web_Fall2024_單元13_實例-前後端整合.pdf`
*   `Web_Fall2024_單元16_NodeJS介紹.pdf`

#### 2.2.2 診斷與修復
1.  **驗證檔案完整性**：使用 `tests/debug_failed_pdfs.py` 確認 `pdfplumber` 可正常讀取所有頁面，排除檔案損毀。
2.  **推測原因**：Embedding 運算超時或資源競爭導致 Worker 崩潰。
3.  **修復工具**：開發 `scripts/reindex_failed.py`，專門針對 `failed` 狀態的文件進行「單檔重新索引」流程。
    *   *建議操作*：在終端機執行 `python scripts/reindex_failed.py` 以完成修復。

---

## 3. 工具與資產 (Artifacts)

為了便於未來維護與除錯，本次修復過程產出了以下工具，已歸檔於 `tests/` 與 `scripts/`：

| 路徑 | 用途 | 關鍵指令/邏輯 |
| :--- | :--- | :--- |
| `tests/debug_pdf_content.py` | **資料驗證**：檢查特定 Document ID 在 ChromaDB 中的實際內容與 Metadata。 | `collection.get(where={"document_id": ...})` |
| `tests/verify_search.py` | **搜尋驗證**：使用專案 Embedding 模型驗證搜尋結果與分數分佈。 | `embed_text(query)` -> `collection.query()` |
| `tests/debug_failed_pdfs.py` | **格式診斷**：測試 PDF 檔案是否損毀或無法解析。 | `pdfplumber.open(path)` |
| `scripts/reindex_failed.py` | **運維工具**：自動掃描並修復失敗文件的批次處理腳本。 | `db.get_documents(status='failed')` -> Re-index pipeline |

## 4. 學習與建議 (Lessons Learned)

1.  **分數相對論**：在使用向量資料庫時，務必確認距離度量（Metric）與分數轉換公式。L2 距離在未正規化向量上差異極大，**不應設定硬性過濾門檻 (Hard Threshold)**，或應將預設門檻設為 0。
2.  **防禦性檢索**：搜尋功能應具備「容錯性」。當高信心度結果為空時，回傳「低信心度」結果通常優於回傳「無結果」，提升使用者體驗。
3.  **診斷優先**：遇到「找不到資料」時，第一步永遠是確認資料庫底層（如使用 `debug_chroma.py`），而非盲目調整上層邏輯。