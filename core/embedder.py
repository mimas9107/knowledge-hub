"""
Knowledge Hub Embedding 模組

使用 sentence-transformers 將文字轉換為向量
"""
from typing import List, Optional
from config import Config

# 全域模型實例（延遲載入）
_model = None


def get_model():
    """取得或載入 Embedding 模型"""
    global _model
    
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError(
                "請安裝 sentence-transformers: pip install sentence-transformers"
            )
        
        print(f"載入 Embedding 模型: {Config.EMBEDDING_MODEL}")
        _model = SentenceTransformer(Config.EMBEDDING_MODEL)
        print("模型載入完成")
    
    return _model


def embed_text(text: str) -> List[float]:
    """
    將單一文字轉換為向量
    
    Args:
        text: 輸入文字
    
    Returns:
        list: 向量（float 列表）
    """
    model = get_model()
    embedding = model.encode(text, convert_to_numpy=True)
    return embedding.tolist()


def embed_texts(texts: List[str], batch_size: int = 32) -> List[List[float]]:
    """
    批次將文字轉換為向量
    
    Args:
        texts: 文字列表
        batch_size: 批次大小
    
    Returns:
        list: 向量列表
    """
    if not texts:
        return []
    
    model = get_model()
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=len(texts) > 10,
        convert_to_numpy=True
    )
    
    return embeddings.tolist()


def get_embedding_dimension() -> int:
    """取得 Embedding 維度"""
    model = get_model()
    return model.get_sentence_embedding_dimension()
