import pdfplumber
from pathlib import Path
import sys
import traceback

# 目標檔案列表
targets = [
    "documents/Web_Fall2024_單元07_實例-Vue.pdf",
    "documents/Web_Fall2024_單元13_實例-前後端整合.pdf",
    "documents/Web_Fall2024_單元16_NodeJS介紹.pdf"
]

print(f"開始診斷 {len(targets)} 個失敗的 PDF 檔案...\n")

for target in targets:
    path = Path(target)
    print(f"👉 正在檢查: {path.name}")
    
    if not path.exists():
        print(f"   ❌ 檔案不存在: {path}")
        continue
        
    try:
        with pdfplumber.open(path) as pdf:
            print(f"   ✅ 成功開啟。頁數: {len(pdf.pages)}")
            print(f"   Metadata: {pdf.metadata}")
            
            # 嘗試讀取每一頁，找出是哪一頁出錯
            success_pages = 0
            for i, page in enumerate(pdf.pages):
                try:
                    text = page.extract_text()
                    if text:
                        success_pages += 1
                except Exception as e:
                    print(f"   ❌ 第 {i+1} 頁解析失敗: {e}")
            
            print(f"   解析狀況: {success_pages}/{len(pdf.pages)} 頁成功提取文字。")
            
    except Exception as e:
        print(f"   ❌ 無法開啟或解析檔案: {e}")
        # print(traceback.format_exc()) # 若需要詳細堆疊請打開
        
    print("-" * 50)
