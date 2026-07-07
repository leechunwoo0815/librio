// backend/static/admin/js/admin.js
// MegaWords 管理端共享 JS — JWT管理 + API客户端 + Toast + Sidebar + 容错
// PC-005: 统一操作反馈  |  PC-026: 统一错误处理  |  PC-027: 防重复提交

const TOKEN_KEY = 'mw_admin_token';
const ADMIN_API = '/admin';

// ===== 操作日志系统 =====
const opLog = {
  _buffer: [],
  _timer: null,

  // 记录操作日志
  log(category, action, detail = {}) {
    const entry = {
      ts: new Date().toISOString(),
      page: location.pathname.split('/').pop(),
      category,  // 'api', 'click', 'nav', 'error', 'form'
      action,
      detail: typeof detail === 'object' ? JSON.stringify(detail) : String(detail),
    };
    this._buffer.push(entry);
    console.log(`[${category}] ${action}`, detail);

    // 批量发送到后端（每 2 秒或满 10 条）
    if (this._buffer.length >= 10) this.flush();
    if (!this._timer) this._timer = setTimeout(() => this.flush(), 2000);
  },

  // 发送日志到后端
  async flush() {
    if (this._buffer.length === 0) return;
    const logs = [...this._buffer];
    this._buffer = [];
    this._timer = null;
    try {
      await fetch('/admin/api/oplogs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ logs }),
      });
    } catch (e) { /* 静默失败 */ }
  },
};

// 记录页面导航
opLog.log('nav', 'page_load', { url: location.href, referrer: document.referrer });

// 记录所有按钮点击
document.addEventListener('click', (e) => {
  const btn = e.target.closest('button, a.action-link, .nav-link, [onclick]');
  if (btn) {
    const text = btn.textContent.trim().substring(0, 50);
    const onclick = btn.getAttribute('onclick') || '';
    opLog.log('click', text || onclick.substring(0, 50), {
      tag: btn.tagName,
      id: btn.id,
      class: btn.className,
    });
  }
});

// 记录表单提交
document.addEventListener('submit', (e) => {
  const form = e.target;
  opLog.log('form', 'submit', {
    action: form.action,
    id: form.id,
  });
});

// ===== Token 管理 =====
const auth = {
  getToken() { return localStorage.getItem(TOKEN_KEY); },
  setToken(token) { localStorage.setItem(TOKEN_KEY, token); },
  clearToken() { localStorage.removeItem(TOKEN_KEY); },
  isLoggedIn() { return !!this.getToken(); },
  requireAuth() {
    if (!this.isLoggedIn()) {
      window.location.href = '/admin/view/login';
      return false;
    }
    return true;
  },
  logout() {
    this.clearToken();
    window.location.href = '/admin/view/login';
  },
};

// ===== API 客户端（PC-026: 统一错误处理） =====
const api = {
  async request(method, url, body = null) {
    const headers = { 'Content-Type': 'application/json' };
    const token = auth.getToken();
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const opts = { method, headers };
    if (body) opts.body = JSON.stringify(body);

    const startTime = Date.now();
    opLog.log('api', `${method} ${url}`, { body: body ? JSON.stringify(body).substring(0, 200) : null });

    try {
      const resp = await fetch(url, opts);
      const duration = Date.now() - startTime;

      if (resp.status === 401) {
        opLog.log('error', `401 Unauthorized`, { url, duration });
        auth.logout();
        return null;
      }
      if (resp.status === 403) {
        opLog.log('error', `403 Forbidden`, { url, duration });
        showToast('您没有权限执行此操作', 'error');
        throw new Error('权限不足');
      }
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: `HTTP ${resp.status}` }));
        const msg = err.detail || err.message || `请求失败 (${resp.status})`;
        opLog.log('error', `API ${resp.status}`, { url, msg, duration });
        showToast(msg, 'error');
        throw new Error(msg);
      }

      const data = await resp.json();
      opLog.log('api', `✅ ${method} ${url}`, { status: resp.status, duration, dataKeys: Object.keys(data || {}).join(',') });
      return data;
    } catch (e) {
      if (e.name === 'TypeError' || e.message.includes('fetch')) {
        opLog.log('error', 'network_error', { url, message: e.message });
        showToast('网络异常，请检查网络连接', 'error');
        throw new Error('网络异常');
      }
      throw e;
    }
  },
  get(url) { return this.request('GET', url); },
  post(url, data) { return this.request('POST', url, data); },
  put(url, data) { return this.request('PUT', url, data); },
  del(url) { return this.request('DELETE', url); },
};

// ===== 确认对话框 =====
// 兼容两种调用方式：
//   showConfirm(title, msg, cb)              — 简单确认
//   showConfirm(title, msg, needInput, inputLabel, cb) — 带输入框
function showConfirm(title, msg, cbOrNeedInput, inputLabelOrCb, cbOrNull) {
  if (arguments.length <= 2 || typeof cbOrNeedInput === 'function') {
    // 简单模式: showConfirm(title, msg) 或 showConfirm(title, msg, cb)
    const cb = typeof cbOrNeedInput === 'function' ? cbOrNeedInput : null;
    const fullMsg = title ? `${title}\n${msg}` : msg;
    if (window.confirm(fullMsg) && cb) cb();
  } else {
    // 带输入框模式: showConfirm(title, msg, needInput, inputLabel, cb)
    if (cbOrNeedInput) {
      const input = window.prompt(`${title}\n${msg}\n${inputLabelOrCb || '请输入:'}`);
      if (input !== null && cbOrNull) cbOrNull(input.trim());
    } else {
      if (window.confirm(title ? `${title}\n${msg}` : msg)) {
        if (cbOrNull) cbOrNull('');
      }
    }
  }
}

// ===== Toast 通知（PC-005: 统一反馈） =====
function showToast(message, type = 'success') {
  let container = document.querySelector('.toast-container');
  if (!container) {
    container = document.createElement('div');
    container.className = 'toast-container';
    container.style.cssText = 'position:fixed;top:20px;right:20px;z-index:9999;display:flex;flex-direction:column;gap:8px;';
    document.body.appendChild(container);
  }
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  const s = getComputedStyle(document.documentElement);
  const colors = { success: s.getPropertyValue('--success').trim(), error: s.getPropertyValue('--error').trim(), warning: s.getPropertyValue('--warning').trim(), info: s.getPropertyValue('--accent').trim() };
  toast.style.cssText = `padding:12px 20px;border-radius:8px;color:#fff;font-size:14px;background:${colors[type] || colors.success};box-shadow:0 4px 12px rgba(0,0,0,0.15);animation:slideIn 0.3s ease;`;
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 3000);
}

// ===== PC-027: 防重复提交 =====
const _submitLocks = new Set();

async function submitWithLock(btn, fn) {
  const key = btn.id || btn.textContent || 'default';
  if (_submitLocks.has(key)) {
    showToast('请勿重复提交', 'warning');
    return;
  }
  _submitLocks.add(key);
  btn.dataset.originalText = btn.textContent;
  btn.disabled = true;
  btn.textContent = '提交中...';
  try {
    const result = await fn();
    showToast('操作成功', 'success');
    return result;
  } catch (e) {
    // showToast 已在 api.request 中处理
    throw e;
  } finally {
    _submitLocks.delete(key);
    btn.disabled = false;
    btn.textContent = btn.dataset.originalText || '提交';
  }
}

// ===== Sidebar 高亮 =====
function initSidebar() {
  const path = location.pathname.split('/').pop() || 'dashboard';
  document.querySelectorAll('.sidebar-nav .nav-link').forEach(link => {
    const href = link.getAttribute('href') || '';
    const page = href.split('/').pop();
    if (page === path) link.classList.add('active');
  });

  const logoutBtn = document.querySelector('.logout-btn');
  if (logoutBtn) logoutBtn.addEventListener('click', () => auth.logout());

  const adminName = document.querySelector('.top-bar .name');
  if (adminName) adminName.textContent = localStorage.getItem('mw_admin_name') || '管理员';
}

// ===== 格式化工具 =====
function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str ?? '';
  return div.innerHTML;
}

function formatDate(str) {
  if (!str) return '-';
  return new Date(str).toLocaleDateString('zh-CN');
}
function formatDateTime(str) {
  if (!str) return '-';
  return new Date(str).toLocaleString('zh-CN');
}
function formatMoney(n) {
  if (n === null || n === undefined) return '-';
  return `¥${Number(n).toLocaleString('zh-CN', { minimumFractionDigits: 2 })}`;
}

// ===== PC-004: 批量操作工具 =====
function initBatchSelect(tableSelector) {
  const table = document.querySelector(tableSelector);
  if (!table) return;
  // 表头添加全选复选框
  const th = document.createElement('th');
  th.innerHTML = '<input type="checkbox" class="batch-select-all" />';
  const thead = table.querySelector('thead tr');
  if (thead) thead.insertBefore(th, thead.firstChild);

  // 每行添加复选框
  table.querySelectorAll('tbody tr').forEach(row => {
    const td = document.createElement('td');
    td.innerHTML = '<input type="checkbox" class="batch-select" />';
    row.insertBefore(td, row.firstChild);
  });

  // 全选逻辑
  const selectAll = table.querySelector('.batch-select-all');
  if (selectAll) {
    selectAll.addEventListener('change', () => {
      table.querySelectorAll('.batch-select').forEach(cb => { cb.checked = selectAll.checked; });
      updateBatchToolbar(tableSelector);
    });
  }
  table.querySelectorAll('.batch-select').forEach(cb => {
    cb.addEventListener('change', () => updateBatchToolbar(tableSelector));
  });
}

function updateBatchToolbar(tableSelector) {
  const table = document.querySelector(tableSelector);
  const selected = table.querySelectorAll('.batch-select:checked');
  let toolbar = document.getElementById('batch-toolbar');
  if (selected.length > 0) {
    if (!toolbar) {
      toolbar = document.createElement('div');
      toolbar.id = 'batch-toolbar';
      toolbar.style.cssText = 'position:sticky;bottom:0;background:var(--accent);color:#fff;padding:10px 16px;display:flex;align-items:center;gap:12px;border-radius:8px 8px 0 0;';
      table.parentNode.appendChild(toolbar);
    }
    toolbar.innerHTML = `<span>已选 ${selected.length} 项</span>
      <button class="btn-sm" style="background:#fff;color:var(--accent);border:none;padding:4px 12px;border-radius:4px;cursor:pointer;" onclick="batchDelete('${tableSelector}')">批量删除</button>
      <button class="btn-sm" style="background:#fff;color:var(--accent);border:none;padding:4px 12px;border-radius:4px;cursor:pointer;" onclick="batchExport('${tableSelector}')">导出</button>`;
    toolbar.style.display = 'flex';
  } else if (toolbar) {
    toolbar.style.display = 'none';
  }
}

function getSelectedIds(tableSelector) {
  const table = document.querySelector(tableSelector);
  const ids = [];
  table.querySelectorAll('.batch-select:checked').forEach(cb => {
    const row = cb.closest('tr');
    const idCell = row.querySelector('td:nth-child(2)');
    if (idCell) ids.push(idCell.textContent.trim());
  });
  return ids;
}

async function batchDelete(tableSelector, apiBaseUrl) {
  const ids = getSelectedIds(tableSelector);
  if (!ids.length) return;
  if (!confirm(`确定删除选中的 ${ids.length} 项？`)) return;
  if (!apiBaseUrl) {
    showToast('未配置删除接口', 'error');
    return;
  }
  try {
    let okCount = 0;
    for (const id of ids) {
      try {
        await api.del(`${apiBaseUrl}/${id}`);
        okCount++;
      } catch (e) { /* api.request 已 toast 错误 */ }
    }
    if (okCount > 0) {
      showToast(`已删除 ${okCount} 项`, 'success');
      location.reload();
    }
  } catch (e) { /* 错误已在 api.request 中处理 */ }
}

// ===== PC-003: 表单草稿缓存 =====
const DraftCache = {
  save(pageKey, formData) {
    try {
      localStorage.setItem(`draft_${pageKey}`, JSON.stringify({ data: formData, ts: Date.now() }));
    } catch (e) { /* silent */ }
  },
  load(pageKey) {
    try {
      const raw = localStorage.getItem(`draft_${pageKey}`);
      if (!raw) return null;
      const { data, ts } = JSON.parse(raw);
      // 24h 过期
      if (Date.now() - ts > 86400000) { localStorage.removeItem(`draft_${pageKey}`); return null; }
      return data;
    } catch (e) { return null; }
  },
  clear(pageKey) {
    try { localStorage.removeItem(`draft_${pageKey}`); } catch (e) { /* silent */ }
  },
};

// ===== 表单校验 =====
function validateField(input) {
  const errEl = input.parentNode.querySelector('.field-error') ||
    (() => { const el = document.createElement('span'); el.className = 'field-error'; el.style.cssText = 'color:var(--error);font-size:12px;margin-top:4px;display:block'; input.parentNode.appendChild(el); return el; })();
  if (input.required && !input.value.trim()) {
    errEl.textContent = '此项为必填';
    input.style.borderColor = 'var(--error)';
    return false;
  }
  const pattern = input.dataset.validate;
  if (pattern && input.value.trim()) {
    const re = new RegExp(pattern);
    if (!re.test(input.value)) {
      errEl.textContent = input.dataset.validateMsg || '格式不正确';
      input.style.borderColor = 'var(--error)';
      return false;
    }
  }
  errEl.textContent = '';
  input.style.borderColor = '';
  return true;
}

// ===== 页面初始化 =====
document.addEventListener('DOMContentLoaded', () => {
  initSidebar();
  // PC-002: 自动绑定表单校验
  document.querySelectorAll('input[data-validate], input[required]').forEach(input => {
    input.addEventListener('blur', () => validateField(input));
    input.addEventListener('input', () => {
      const errEl = input.parentNode.querySelector('.field-error');
      if (errEl && input.value.trim()) validateField(input);
    });
  });
  // 全局表单拦截已移除（P0-13）：各页面使用 api.* 自行处理表单提交
});
