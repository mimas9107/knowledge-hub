"""
Knowledge Hub 設定管理
"""
import os
from pathlib import Path

def load_env(filepath='.env'):
    """載入環境變數檔案"""
    env_data = {}
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    env_data[key.strip()] = value.strip().strip('"').strip("'")
    return env_data

# 載入環境變數
_env = load_env()

class Config:
    """應用程式設定"""
    
    # 伺服器
    HOST = _env.get('HOST', '127.0.0.1')
    PORT = int(_env.get('PORT', 5002))
    DEBUG = _env.get('DEBUG', 'true').lower() == 'true'
    
    # 目錄路徑
    BASE_DIR = Path(__file__).parent
    SCAN_DIR = Path(_env.get('SCAN_DIR', './documents')).resolve()
    DATA_DIR = Path(_env.get('DATA_DIR', './data')).resolve()
    
    # 資料庫
    DB_PATH = Path(_env.get('DB_PATH', './data/knowledge.db')).resolve()
    CHROMA_PATH = Path(_env.get('CHROMA_PATH', './data/chroma')).resolve()
    
    # Embedding 設定
    EMBEDDING_MODEL = _env.get('EMBEDDING_MODEL', 'paraphrase-multilingual-MiniLM-L12-v2')
    CHUNK_SIZE = int(_env.get('CHUNK_SIZE', 500))
    CHUNK_OVERLAP = int(_env.get('CHUNK_OVERLAP', 50))
    
    # LLM 設定
    LLM_PROVIDER = _env.get('LLM_PROVIDER', 'ollama')
    LLM_MODEL = _env.get('LLM_MODEL', 'llama3')
    CLAUDE_API_KEY = _env.get('CLAUDE_API_KEY', '')
    OPENAI_API_KEY = _env.get('OPENAI_API_KEY', '')
    
    # 支援的文件類型
    SUPPORTED_TYPES = {'.pdf', '.pptx', '.md', '.docx'}
    
    @classmethod
    def ensure_dirs(cls):
        """確保必要目錄存在"""
        cls.DATA_DIR.mkdir(parents=True, exist_ok=True)
        cls.CHROMA_PATH.mkdir(parents=True, exist_ok=True)
        if not cls.SCAN_DIR.exists():
            print(f"⚠️  掃描目錄不存在: {cls.SCAN_DIR}")
    
    @classmethod
    def to_dict(cls):
        """輸出設定為字典（供 API 使用）"""
        return {
            'scan_path': str(cls.SCAN_DIR),
            'embedding_model': cls.EMBEDDING_MODEL,
            'chunk_size': cls.CHUNK_SIZE,
            'chunk_overlap': cls.CHUNK_OVERLAP,
            'llm_provider': cls.LLM_PROVIDER,
            'llm_model': cls.LLM_MODEL,
        }
