"""
測試智慧章節切分功能
"""
import sys
sys.path.insert(0, '.')

from core.chunker import detect_headings, split_by_headings, chunk_by_sections

# 測試文本
test_markdown = """
# Python 基礎教學

這是課程的簡介，介紹 Python 語言的特色。

## 第一章：變數與型別

Python 是一種動態型別語言，不需要事先宣告變數型別。

變數可以直接賦值使用：
```python
x = 10
name = "Alice"
```

### 1.1 數值型別

Python 支援整數、浮點數、複數等數值型別。

### 1.2 字串型別

字串可以用單引號或雙引號表示。

## 第二章：流程控制

流程控制包含條件判斷和迴圈結構。

### 2.1 if 條件判斷

使用 if、elif、else 進行條件判斷。

### 2.2 for 迴圈

for 迴圈用於遍歷序列：
```python
for i in range(10):
    print(i)
```

## 第三章：函數

函數是可重複使用的程式碼區塊。
"""

test_chinese = """
第一章：系統概述

本系統是一個知識管理平台，用於整理和搜尋文件。

一、功能特色

系統提供以下主要功能：語意搜尋、問答模式、文件管理。

二、技術架構

採用 Flask 作為後端框架，ChromaDB 作為向量資料庫。

第二章：安裝指南

本章說明如何安裝和設定系統。

(一) 環境需求

需要 Python 3.10 以上版本。

(二) 安裝步驟

1. 下載程式碼
2. 安裝依賴套件
3. 設定環境變數
"""

print("=" * 60)
print("測試 1：偵測 Markdown 標題")
print("=" * 60)

headings = detect_headings(test_markdown)
for h in headings:
    indent = "  " * (h['level'] - 1)
    print(f"{indent}[Level {h['level']}] {h['title']}")

print("\n" + "=" * 60)
print("測試 2：偵測中文標題")
print("=" * 60)

headings = detect_headings(test_chinese)
for h in headings:
    print(f"[Level {h['level']}] {h['title']}")

print("\n" + "=" * 60)
print("測試 3：按章節切分 Markdown")
print("=" * 60)

sections = split_by_headings(test_markdown)
for i, sec in enumerate(sections):
    title = sec['title'] or '(無標題)'
    content_preview = sec['content'][:50].replace('\n', ' ') + '...'
    print(f"章節 {i}: {title}")
    print(f"  內容預覽: {content_preview}")
    print()

print("=" * 60)
print("測試 4：智慧 Chunk 切分（含標題前綴）")
print("=" * 60)

chunks = chunk_by_sections(test_markdown, chunk_size=200)
for chunk in chunks:
    print(f"[Chunk {chunk['index']}] (章節: {chunk['metadata'].get('section_title', 'N/A')})")
    print(f"  {chunk['text'][:80]}...")
    print()

print("=" * 60)
print(f"總共產生 {len(chunks)} 個 chunks")
print("=" * 60)
