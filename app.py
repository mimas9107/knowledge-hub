"""
Knowledge Hub - 個人 RAG 知識管理平台

啟動方式：python app.py
"""
from flask import Flask, render_template, send_from_directory
from config import Config

# 確保必要目錄存在
Config.ensure_dirs()

# 建立 Flask 應用
app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False  # 支援中文 JSON

# 註冊 API 藍圖
from api import blueprints
for bp in blueprints:
    app.register_blueprint(bp)


# ===== 前端路由 =====

@app.route('/')
def index():
    """首頁"""
    return render_template('index.html')


@app.route('/static/<path:filename>')
def static_files(filename):
    """靜態資源"""
    return send_from_directory('static', filename)


# ===== 錯誤處理 =====

@app.errorhandler(404)
def not_found(e):
    return {'error': {'code': 'NOT_FOUND', 'message': 'Resource not found'}}, 404


@app.errorhandler(500)
def server_error(e):
    return {'error': {'code': 'SERVER_ERROR', 'message': 'Internal server error'}}, 500


# ===== 啟動 =====

if __name__ == '__main__':
    print(f"""
╔══════════════════════════════════════════════════╗
║         Knowledge Hub - 知識管理平台             ║
╠══════════════════════════════════════════════════╣
║  掃描目錄: {str(Config.SCAN_DIR):<36} ║
║  資料目錄: {str(Config.DATA_DIR):<36} ║
║  Embedding: {Config.EMBEDDING_MODEL:<35} ║
╚══════════════════════════════════════════════════╝
    """)
    
    app.run(
        host=Config.HOST,
        port=Config.PORT,
        debug=Config.DEBUG
    )
