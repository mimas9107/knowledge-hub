"""
Knowledge Hub 設定 API
"""
from flask import Blueprint, jsonify, request
from config import Config

bp = Blueprint('settings', __name__, url_prefix='/api')


@bp.route('/settings', methods=['GET'])
def get_settings():
    """取得系統設定"""
    return jsonify(Config.to_dict())


@bp.route('/settings', methods=['PUT'])
def update_settings():
    """更新系統設定（目前僅回傳，實際修改需要改 .env 檔案）"""
    data = request.get_json() or {}
    
    # 注意：這裡只是示意，實際要修改設定需要寫入 .env 檔案
    # 並重啟服務才會生效
    
    return jsonify({
        'status': 'info',
        'message': '設定修改需要編輯 .env 檔案並重啟服務',
        'current_settings': Config.to_dict()
    })
