/**
 * Knowledge Hub - 前端應用
 */

const API_BASE = '/api';

// ===== 工具函數 =====

async function api(endpoint, options = {}) {
    const url = `${API_BASE}${endpoint}`;
    const config = {
        headers: { 'Content-Type': 'application/json' },
        ...options
    };
    
    if (config.body && typeof config.body === 'object') {
        config.body = JSON.stringify(config.body);
    }
    
    const response = await fetch(url, config);
    const data = await response.json();
    
    if (!response.ok) {
        throw new Error(data.error?.message || 'API 請求失敗');
    }
    
    return data;
}

function getTypeIcon(type) {
    const icons = {
        'pdf': '📕',
        'pptx': '📊',
        'md': '📝',
        'docx': '📘'
    };
    return icons[type] || '📄';
}

// ===== 視圖切換 =====

document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', (e) => {
        e.preventDefault();
        const viewName = item.dataset.view;
        
        // 更新導航狀態
        document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
        item.classList.add('active');
        
        // 切換視圖
        document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
        document.getElementById(`view-${viewName}`).classList.add('active');
        
        // 載入視圖資料
        if (viewName === 'documents') loadDocuments();
        if (viewName === 'settings') loadSettings();
    });
});

// ===== 文件管理 =====

async function loadDocuments() {
    const folder = document.getElementById('filter-folder').value;
    const status = document.getElementById('filter-status').value;
    const type = document.getElementById('filter-type').value;
    
    let query = '?';
    if (folder) query += `folder=${encodeURIComponent(folder)}&`;
    if (status) query += `status=${status}&`;
    if (type) query += `type=${type}&`;
    
    try {
        const data = await api(`/documents${query}`);
        renderDocuments(data.documents);
    } catch (err) {
        console.error('載入文件失敗:', err);
    }
}

function renderDocuments(documents) {
    const container = document.getElementById('documents-list');
    
    if (!documents.length) {
        container.innerHTML = '<p class="placeholder">沒有找到文件。點擊「掃描目錄」開始探索！</p>';
        return;
    }
    
    container.innerHTML = documents.map(doc => `
        <div class="document-card" data-id="${doc.id}">
            <div class="filename">
                <span class="type-icon">${getTypeIcon(doc.type)}</span>
                ${doc.filename}
            </div>
            <div class="folder">📁 ${doc.folder || '根目錄'}</div>
            <div class="meta">
                <span>${doc.size_kb} KB</span>
                <span>${doc.chunks_count || 0} chunks</span>
            </div>
            <span class="status ${doc.status}">${doc.status}</span>
        </div>
    `).join('');
}

async function loadFolders() {
    try {
        const data = await api('/folders');
        const select = document.getElementById('filter-folder');
        select.innerHTML = '<option value="">所有資料夾</option>';
        data.folders.forEach(folder => {
            select.innerHTML += `<option value="${folder.name}">${folder.name} (${folder.count})</option>`;
        });
    } catch (err) {
        console.error('載入資料夾失敗:', err);
    }
}

async function scanDocuments() {
    const btn = document.getElementById('btn-scan');
    btn.disabled = true;
    btn.textContent = '掃描中...';
    
    try {
        const result = await api('/documents/scan', { method: 'POST', body: {} });
        alert(`掃描完成！\n新增: ${result.new_files} 個\n更新: ${result.updated_files} 個\n總計: ${result.total_files} 個`);
        loadDocuments();
        loadFolders();
        loadIndexStatus();
    } catch (err) {
        alert('掃描失敗: ' + err.message);
    } finally {
        btn.disabled = false;
        btn.textContent = '🔄 掃描目錄';
    }
}

async function indexAll() {
    const btn = document.getElementById('btn-index-all');
    btn.disabled = true;
    btn.textContent = '處理中...';
    
    try {
        const result = await api('/index/process', { method: 'POST', body: {} });
        alert(`已開始處理 ${result.queued} 個文件！\n任務 ID: ${result.job_id}`);
        
        // 定時更新狀態
        const checkStatus = setInterval(async () => {
            await loadIndexStatus();
            const status = await api('/index/status');
            if (!status.processing) {
                clearInterval(checkStatus);
                loadDocuments();
                btn.disabled = false;
                btn.textContent = '⚙️ 建立索引';
            }
        }, 2000);
        
    } catch (err) {
        alert('建立索引失敗: ' + err.message);
        btn.disabled = false;
        btn.textContent = '⚙️ 建立索引';
    }
}

// ===== 索引狀態 =====

async function loadIndexStatus() {
    try {
        const status = await api('/index/status');
        document.getElementById('indexed-count').textContent = status.indexed || 0;
        document.getElementById('pending-count').textContent = status.pending || 0;
    } catch (err) {
        console.error('載入狀態失敗:', err);
    }
}

// ===== 搜尋 =====

async function doSearch() {
    const query = document.getElementById('search-input').value.trim();
    if (!query) return;
    
    const container = document.getElementById('search-results');
    container.innerHTML = '<div class="loading"></div>';
    
    try {
        const result = await api('/search', {
            method: 'POST',
            body: { query, top_k: 10 }
        });
        
        if (!result.results.length) {
            container.innerHTML = '<p class="placeholder">沒有找到相關結果</p>';
            return;
        }
        
        container.innerHTML = result.results.map(item => `
            <div class="result-item">
                <div class="source">📄 ${item.filename} ${item.page ? `(第 ${item.page} 頁)` : ''}</div>
                <div class="text">${item.text}</div>
                <div class="score">相關度: ${(item.score * 100).toFixed(1)}%</div>
            </div>
        `).join('');
        
    } catch (err) {
        container.innerHTML = '<p class="placeholder">搜尋失敗: ' + err.message + '</p>';
    }
}

// ===== 問答 =====

async function sendChat() {
    const input = document.getElementById('chat-input');
    const question = input.value.trim();
    if (!question) return;
    
    const container = document.getElementById('chat-messages');
    
    // 顯示使用者訊息
    container.innerHTML += `<div class="message user"><p>${question}</p></div>`;
    input.value = '';
    container.scrollTop = container.scrollHeight;
    
    // 顯示載入中
    container.innerHTML += `<div class="message assistant" id="loading-msg"><div class="loading"></div></div>`;
    
    try {
        const result = await api('/chat', {
            method: 'POST',
            body: { question, include_sources: true }
        });
        
        // 移除載入訊息
        document.getElementById('loading-msg')?.remove();
        
        // 顯示回答
        let answerHtml = `<p>${result.answer}</p>`;
        if (result.sources?.length) {
            answerHtml += `<div class="sources"><small>參考來源: ${result.sources.map(s => s.filename).join(', ')}</small></div>`;
        }
        
        container.innerHTML += `<div class="message assistant">${answerHtml}</div>`;
        container.scrollTop = container.scrollHeight;
        
    } catch (err) {
        document.getElementById('loading-msg')?.remove();
        container.innerHTML += `<div class="message assistant"><p>抱歉，發生錯誤: ${err.message}</p></div>`;
    }
}

// ===== 設定 =====

async function loadSettings() {
    try {
        const settings = await api('/settings');
        document.getElementById('setting-scan-path').value = settings.scan_path || '';
        document.getElementById('setting-embedding-model').value = settings.embedding_model || '';
        document.getElementById('setting-chunk-size').value = settings.chunk_size || '';
        document.getElementById('setting-llm-provider').value = settings.llm_provider || '';
    } catch (err) {
        console.error('載入設定失敗:', err);
    }
}

// ===== 事件綁定 =====

document.getElementById('btn-scan').addEventListener('click', scanDocuments);
document.getElementById('btn-index-all').addEventListener('click', indexAll);
document.getElementById('btn-search').addEventListener('click', doSearch);
document.getElementById('search-input').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') doSearch();
});
document.getElementById('btn-chat').addEventListener('click', sendChat);
document.getElementById('chat-input').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendChat();
});

// 篩選器變更
['filter-folder', 'filter-status', 'filter-type'].forEach(id => {
    document.getElementById(id).addEventListener('change', loadDocuments);
});

// ===== 初始化 =====

document.addEventListener('DOMContentLoaded', () => {
    loadDocuments();
    loadFolders();
    loadIndexStatus();
});
