"""
Knowledge Hub 搜尋 API
"""
import time
from flask import Blueprint, jsonify, request
from models.database import db
from core.embedder import embed_text
from core.vectordb import search as vector_search

bp = Blueprint('search', __name__, url_prefix='/api')


@bp.route('/search', methods=['POST'])
def search():
    """語意搜尋"""
    data = request.get_json() or {}
    query = data.get('query', '').strip()
    top_k = data.get('top_k', 5)
    threshold = data.get('threshold', 0.0)
    filters = data.get('filter', {})
    
    if not query:
        return jsonify({
            'error': {
                'code': 'INVALID_REQUEST',
                'message': 'Query is required'
            }
        }), 400
    
    start_time = time.time()
    
    # 將查詢轉為向量
    query_embedding = embed_text(query)
    
    # 搜尋向量資料庫
    results = vector_search(
        query_embedding=query_embedding,
        top_k=top_k,
        threshold=threshold,
        filters=filters
    )
    
    # 補充文件資訊
    for result in results:
        doc = db.get_document(result['document_id'])
        if doc:
            result['filename'] = doc['filename']
            result['folder'] = doc.get('folder')
    
    search_time = round((time.time() - start_time) * 1000)
    
    return jsonify({
        'query': query,
        'results': results,
        'search_time_ms': search_time
    })


@bp.route('/chat', methods=['POST'])
def chat():
    """問答模式"""
    data = request.get_json() or {}
    question = data.get('question', '').strip()
    top_k = data.get('top_k', 5)
    include_sources = data.get('include_sources', True)
    model = data.get('model', 'auto')
    
    if not question:
        return jsonify({
            'error': {
                'code': 'INVALID_REQUEST',
                'message': 'Question is required'
            }
        }), 400
    
    start_time = time.time()
    
    # 先做語意搜尋
    query_embedding = embed_text(question)
    search_results = vector_search(
        query_embedding=query_embedding,
        top_k=top_k
    )
    
    if not search_results:
        return jsonify({
            'answer': '抱歉，我在知識庫中找不到相關的資訊。',
            'sources': [],
            'model_used': None,
            'response_time_ms': round((time.time() - start_time) * 1000)
        })
    
    # 組合 context
    context_parts = []
    for i, result in enumerate(search_results):
        doc = db.get_document(result['document_id'])
        filename = doc['filename'] if doc else 'Unknown'
        context_parts.append(f"[來源 {i+1}: {filename}]\n{result['text']}")
    
    context = "\n\n---\n\n".join(context_parts)
    
    # 呼叫 LLM 生成回答
    answer = generate_answer(question, context, model)
    
    # 準備來源資訊
    sources = []
    if include_sources:
        for result in search_results:
            doc = db.get_document(result['document_id'])
            sources.append({
                'document_id': result['document_id'],
                'filename': doc['filename'] if doc else '',
                'folder': doc.get('folder') if doc else '',
                'text': result['text'][:200] + '...' if len(result['text']) > 200 else result['text'],
                'page': result.get('page'),
                'score': result['score']
            })
    
    response_time = round((time.time() - start_time) * 1000)
    
    return jsonify({
        'answer': answer['text'],
        'sources': sources,
        'model_used': answer['model'],
        'response_time_ms': response_time
    })


def generate_answer(question: str, context: str, model: str = 'auto') -> dict:
    """
    使用 LLM 生成回答
    
    目前支援：
    - ollama: 使用本地 Ollama
    - claude: 使用 Claude API
    - openai: 使用 OpenAI API
    - auto: 自動選擇可用的
    """
    from config import Config
    
    prompt = f"""根據以下參考資料回答問題。如果參考資料中沒有相關資訊，請誠實說明。

參考資料：
{context}

問題：{question}

請用繁體中文回答："""
    
    # 嘗試使用 Ollama
    if model in ('auto', 'ollama'):
        try:
            answer = call_ollama(prompt, Config.LLM_MODEL)
            return {'text': answer, 'model': f'ollama/{Config.LLM_MODEL}'}
        except Exception as e:
            if model == 'ollama':
                raise e
    
    # 嘗試使用 Claude
    if model in ('auto', 'claude') and Config.CLAUDE_API_KEY:
        try:
            answer = call_claude(prompt, Config.CLAUDE_API_KEY)
            return {'text': answer, 'model': 'claude'}
        except Exception as e:
            if model == 'claude':
                raise e
    
    # 嘗試使用 OpenAI
    if model in ('auto', 'openai') and Config.OPENAI_API_KEY:
        try:
            answer = call_openai(prompt, Config.OPENAI_API_KEY)
            return {'text': answer, 'model': 'openai'}
        except Exception as e:
            if model == 'openai':
                raise e
    
    # 沒有可用的 LLM，回傳簡單回應
    return {
        'text': f'（LLM 未設定）以下是相關的參考資料摘要：\n\n{context[:500]}...',
        'model': None
    }


def call_ollama(prompt: str, model: str) -> str:
    """呼叫 Ollama API"""
    import requests
    
    response = requests.post(
        'http://localhost:11434/api/generate',
        json={
            'model': model,
            'prompt': prompt,
            'stream': False
        },
        timeout=60
    )
    response.raise_for_status()
    return response.json()['response']


def call_claude(prompt: str, api_key: str) -> str:
    """呼叫 Claude API"""
    import requests
    
    response = requests.post(
        'https://api.anthropic.com/v1/messages',
        headers={
            'x-api-key': api_key,
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json'
        },
        json={
            'model': 'claude-3-haiku-20240307',
            'max_tokens': 1024,
            'messages': [{'role': 'user', 'content': prompt}]
        },
        timeout=60
    )
    response.raise_for_status()
    return response.json()['content'][0]['text']


def call_openai(prompt: str, api_key: str) -> str:
    """呼叫 OpenAI API"""
    import requests
    
    response = requests.post(
        'https://api.openai.com/v1/chat/completions',
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        },
        json={
            'model': 'gpt-3.5-turbo',
            'messages': [{'role': 'user', 'content': prompt}],
            'max_tokens': 1024
        },
        timeout=60
    )
    response.raise_for_status()
    return response.json()['choices'][0]['message']['content']
