"""
Knowledge Hub 文字切分模組 v0.2.0

智慧章節切分：根據標題/章節結構切分，保留上下文
"""
import re
from typing import List, Dict, Optional, Tuple
from config import Config


# ===== 標題偵測模式 =====

# Markdown 標題
MD_HEADING_PATTERN = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)

# 常見中文標題模式
CN_HEADING_PATTERNS = [
    re.compile(r'^第[一二三四五六七八九十\d]+[章節課]\s*[:：]?\s*(.*)$', re.MULTILINE),
    re.compile(r'^[一二三四五六七八九十]+[、.]\s*(.+)$', re.MULTILINE),
    re.compile(r'^[\d]+[.、]\s*(.+)$', re.MULTILINE),
    re.compile(r'^[（(][\d一二三四五六七八九十]+[)）]\s*(.+)$', re.MULTILINE),
]

# 英文標題模式
EN_HEADING_PATTERNS = [
    re.compile(r'^Chapter\s+\d+[:.]?\s*(.*)$', re.MULTILINE | re.IGNORECASE),
    re.compile(r'^Section\s+\d+[:.]?\s*(.*)$', re.MULTILINE | re.IGNORECASE),
    re.compile(r'^Part\s+\d+[:.]?\s*(.*)$', re.MULTILINE | re.IGNORECASE),
]


def detect_headings(text: str) -> List[Dict]:
    """
    偵測文字中的標題
    
    Returns:
        list: [{'pos': 位置, 'level': 層級, 'title': 標題文字, 'full_match': 完整匹配}]
    """
    headings = []
    
    # Markdown 標題
    for match in MD_HEADING_PATTERN.finditer(text):
        headings.append({
            'pos': match.start(),
            'level': len(match.group(1)),  # # 數量 = 層級
            'title': match.group(2).strip(),
            'full_match': match.group(0)
        })
    
    # 中文標題
    for pattern in CN_HEADING_PATTERNS:
        for match in pattern.finditer(text):
            # 避免重複（檢查位置是否已有標題）
            if not any(h['pos'] == match.start() for h in headings):
                headings.append({
                    'pos': match.start(),
                    'level': 2,  # 預設層級
                    'title': match.group(0).strip(),
                    'full_match': match.group(0)
                })
    
    # 英文標題
    for pattern in EN_HEADING_PATTERNS:
        for match in pattern.finditer(text):
            if not any(h['pos'] == match.start() for h in headings):
                headings.append({
                    'pos': match.start(),
                    'level': 2,
                    'title': match.group(0).strip(),
                    'full_match': match.group(0)
                })
    
    # 按位置排序
    headings.sort(key=lambda x: x['pos'])
    
    return headings


def split_by_headings(text: str) -> List[Dict]:
    """
    根據標題切分文字為章節
    
    Returns:
        list: [{'title': 章節標題, 'content': 內容, 'level': 層級}]
    """
    headings = detect_headings(text)
    
    if not headings:
        # 沒有偵測到標題，整份文件視為單一章節
        return [{'title': None, 'content': text.strip(), 'level': 0}]
    
    sections = []
    
    # 處理第一個標題之前的內容
    if headings[0]['pos'] > 0:
        pre_content = text[:headings[0]['pos']].strip()
        if pre_content:
            sections.append({
                'title': None,
                'content': pre_content,
                'level': 0
            })
    
    # 處理每個標題區段
    for i, heading in enumerate(headings):
        start = heading['pos']
        end = headings[i + 1]['pos'] if i + 1 < len(headings) else len(text)
        
        section_text = text[start:end].strip()
        # 移除標題本身，只保留內容
        content = section_text[len(heading['full_match']):].strip()
        
        sections.append({
            'title': heading['title'],
            'content': content,
            'level': heading['level']
        })
    
    return sections


def chunk_text(
    text: str,
    chunk_size: int = None,
    chunk_overlap: int = None,
    metadata: Dict = None
) -> List[Dict]:
    """
    將文字切分成 chunks（基本版，按字數切分）
    
    Args:
        text: 要切分的文字
        chunk_size: 每個 chunk 的目標字元數
        chunk_overlap: chunk 之間的重疊字元數
        metadata: 附加到每個 chunk 的元資料
    
    Returns:
        list: chunk 列表，每個包含 {index, text, metadata}
    """
    chunk_size = chunk_size or Config.CHUNK_SIZE
    chunk_overlap = chunk_overlap or Config.CHUNK_OVERLAP
    metadata = metadata or {}
    
    if not text or not text.strip():
        return []
    
    # 先按段落分割
    paragraphs = text.split('\n\n')
    paragraphs = [p.strip() for p in paragraphs if p.strip()]
    
    chunks = []
    current_chunk = []
    current_length = 0
    
    for para in paragraphs:
        para_length = len(para)
        
        # 如果單一段落就超過 chunk_size，需要進一步切分
        if para_length > chunk_size:
            if current_chunk:
                chunks.append('\n\n'.join(current_chunk))
                current_chunk = []
                current_length = 0
            
            sub_chunks = split_long_text(para, chunk_size, chunk_overlap)
            chunks.extend(sub_chunks)
        
        elif current_length + para_length > chunk_size:
            if current_chunk:
                chunks.append('\n\n'.join(current_chunk))
            
            if chunk_overlap > 0 and current_chunk:
                overlap_text = current_chunk[-1]
                if len(overlap_text) <= chunk_overlap:
                    current_chunk = [overlap_text, para]
                    current_length = len(overlap_text) + para_length
                else:
                    current_chunk = [para]
                    current_length = para_length
            else:
                current_chunk = [para]
                current_length = para_length
        
        else:
            current_chunk.append(para)
            current_length += para_length
    
    if current_chunk:
        chunks.append('\n\n'.join(current_chunk))
    
    result = []
    for i, chunk_text_content in enumerate(chunks):
        result.append({
            'index': i,
            'text': chunk_text_content,
            'metadata': {**metadata, 'chunk_index': i}
        })
    
    return result


def chunk_by_sections(
    text: str,
    chunk_size: int = None,
    include_title_prefix: bool = True,
    metadata: Dict = None
) -> List[Dict]:
    """
    智慧切分：根據標題/章節切分，保留章節上下文
    
    Args:
        text: 要切分的文字
        chunk_size: 每個 chunk 的最大字元數
        include_title_prefix: 是否在 chunk 開頭加上章節標題
        metadata: 附加元資料
    
    Returns:
        list: chunk 列表
    """
    chunk_size = chunk_size or Config.CHUNK_SIZE
    metadata = metadata or {}
    
    if not text or not text.strip():
        return []
    
    # 先按章節切分
    sections = split_by_headings(text)
    
    all_chunks = []
    current_section_title = None
    
    for section in sections:
        title = section['title']
        content = section['content']
        level = section['level']
        
        if not content:
            continue
        
        # 更新當前章節標題（用於子 chunk）
        if title:
            current_section_title = title
        
        # 準備標題前綴
        title_prefix = f"[{current_section_title}] " if include_title_prefix and current_section_title else ""
        prefix_len = len(title_prefix)
        effective_chunk_size = chunk_size - prefix_len
        
        # 如果章節內容夠短，直接作為一個 chunk
        if len(content) <= effective_chunk_size:
            chunk_text_content = title_prefix + content if title_prefix else content
            all_chunks.append({
                'text': chunk_text_content,
                'metadata': {
                    **metadata,
                    'section_title': current_section_title,
                    'section_level': level
                }
            })
        else:
            # 章節太長，需要細切
            sub_chunks = chunk_text(
                content,
                chunk_size=effective_chunk_size,
                metadata={
                    **metadata,
                    'section_title': current_section_title,
                    'section_level': level
                }
            )
            
            # 為每個子 chunk 加上標題前綴
            for sub in sub_chunks:
                if title_prefix:
                    sub['text'] = title_prefix + sub['text']
                all_chunks.append(sub)
    
    # 重新編號
    for i, chunk in enumerate(all_chunks):
        chunk['index'] = i
        chunk['metadata']['chunk_index'] = i
    
    return all_chunks


def split_long_text(text: str, chunk_size: int, overlap: int) -> List[str]:
    """
    切分超長文字，優先在句子邊界切分
    """
    separators = ['。', '！', '？', '. ', '! ', '? ', '\n', '；', '; ']
    
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + chunk_size
        
        if end >= len(text):
            chunks.append(text[start:])
            break
        
        best_split = end
        for sep in separators:
            pos = text.rfind(sep, start, end)
            if pos > start:
                best_split = pos + len(sep)
                break
        
        chunks.append(text[start:best_split])
        start = best_split - overlap if overlap > 0 else best_split
    
    return chunks


def chunk_document_with_pages(
    pages: List[Dict],
    chunk_size: int = None,
    use_smart_chunking: bool = True
) -> List[Dict]:
    """
    切分文件（保留頁碼資訊）
    
    Args:
        pages: 頁面列表，每個包含 {page, text}
        chunk_size: chunk 大小
        use_smart_chunking: 是否使用智慧章節切分
    
    Returns:
        list: chunk 列表，包含頁碼資訊
    """
    chunk_size = chunk_size or Config.CHUNK_SIZE
    
    # 合併所有頁面文字（保留頁碼標記）
    full_text = ""
    page_markers = []  # [(position, page_num), ...]
    
    for page_info in pages:
        page_num = page_info.get('page', 1)
        page_text = page_info.get('text', '').strip()
        
        if not page_text:
            continue
        
        page_markers.append((len(full_text), page_num))
        full_text += page_text + "\n\n"
    
    if not full_text.strip():
        return []
    
    # 選擇切分策略
    if use_smart_chunking:
        all_chunks = chunk_by_sections(full_text, chunk_size=chunk_size)
    else:
        all_chunks = chunk_text(full_text, chunk_size=chunk_size)
    
    # 為每個 chunk 標記頁碼（根據位置推算）
    # 簡化處理：取 chunk 在原文的大概位置
    current_pos = 0
    for chunk in all_chunks:
        chunk_len = len(chunk['text'])
        
        # 找出這個 chunk 對應的頁碼
        page_num = 1
        for pos, pn in page_markers:
            if pos <= current_pos:
                page_num = pn
            else:
                break
        
        chunk['metadata']['page'] = page_num
        current_pos += chunk_len
    
    return all_chunks
