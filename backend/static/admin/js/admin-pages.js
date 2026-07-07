// backend/static/admin/js/admin-pages.js
// 管理端页面级公共组件 — 列表/分页/确认弹窗/批量操作
// PC-030: 统一页面交互组件，减少模板内联 JS 重复

(function(global) {
  'use strict';

  // ===== 轻量 HTML 消毒：仅允许常用富文本标签，剥离事件处理器与危险协议 =====
  function sanitizeHtml(raw) {
    if (!raw) return '';
    const allowed = new Set([
      'div', 'span', 'p', 'br', 'hr', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
      'strong', 'b', 'em', 'i', 'u', 'a', 'img', 'table', 'thead', 'tbody',
      'tr', 'th', 'td', 'ul', 'ol', 'li', 'dl', 'dt', 'dd', 'code', 'pre',
      'blockquote', 'small', 'sub', 'sup', 'mark', 'del', 'ins'
    ]);

    let doc;
    try {
      doc = new DOMParser().parseFromString(String(raw), 'text/html');
    } catch (e) {
      // 降级：直接返回纯文本
      return String(raw);
    }

    const toRemove = [];
    const walker = doc.createTreeWalker(doc.body, NodeFilter.SHOW_ELEMENT);
    let node;
    while ((node = walker.nextNode())) {
      const tag = node.tagName.toLowerCase();
      if (!allowed.has(tag)) {
        toRemove.push(node);
        continue;
      }
      // 剥离事件处理器与 javascript: 协议
      for (let i = node.attributes.length - 1; i >= 0; i--) {
        const attr = node.attributes[i];
        const name = attr.name.toLowerCase();
        const value = (attr.value || '').trim().toLowerCase();
        if (name.startsWith('on') || (name === 'href' && value.startsWith('javascript:'))) {
          node.removeAttribute(attr.name);
        }
      }
    }
    toRemove.forEach(function(el) {
      if (el.parentNode) el.parentNode.removeChild(el);
    });
    return doc.body.innerHTML;
  }

  // ===== AdminConfirm：统一确认弹窗（替代原生 confirm/prompt） =====
  class AdminConfirm {
    constructor() {
      this._init();
    }

    _init() {
      if (document.getElementById('admin-confirm-modal')) return;
      const el = document.createElement('div');
      el.id = 'admin-confirm-modal';
      el.style.cssText = 'display:none;position:fixed;inset:0;background:rgba(0,0,0,0.5);z-index:1100;align-items:center;justify-content:center;';
      el.innerHTML = `
        <div style="background:#fff;border-radius:12px;width:420px;max-width:90vw;padding:24px;box-shadow:0 20px 40px rgba(0,0,0,0.2);" role="dialog" aria-modal="true" aria-labelledby="admin-confirm-title">
          <h3 id="admin-confirm-title" style="margin:0 0 12px;font-size:18px;">确认操作</h3>
          <div id="admin-confirm-body" style="margin:0 0 20px;font-size:14px;color:var(--fg);line-height:1.5;"></div>
          <div id="admin-confirm-input-wrap" style="display:none;margin-bottom:16px;">
            <label id="admin-confirm-input-label" style="display:block;font-size:13px;color:var(--muted);margin-bottom:4px;">请输入：</label>
            <input type="text" id="admin-confirm-input" style="width:100%;padding:10px;border:1px solid var(--border);border-radius:8px;box-sizing:border-box;" />
          </div>
          <div style="display:flex;justify-content:flex-end;gap:8px;">
            <button class="btn btn-secondary" id="admin-confirm-cancel">取消</button>
            <button class="btn btn-primary" id="admin-confirm-ok">确认</button>
          </div>
        </div>
      `;
      document.body.appendChild(el);

      this.modal = el;
      this.titleEl = document.getElementById('admin-confirm-title');
      this.bodyEl = document.getElementById('admin-confirm-body');
      this.inputWrap = document.getElementById('admin-confirm-input-wrap');
      this.inputLabel = document.getElementById('admin-confirm-input-label');
      this.inputEl = document.getElementById('admin-confirm-input');
      this.okBtn = document.getElementById('admin-confirm-ok');
      this.cancelBtn = document.getElementById('admin-confirm-cancel');

      this.cancelBtn.addEventListener('click', () => this._close(false));
      this.okBtn.addEventListener('click', () => this._close(true));
      this.inputEl.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') this._close(true);
      });
      this.modal.addEventListener('click', (e) => {
        if (e.target === this.modal) this._close(false);
      });
      // ESC 关闭
      this._keyHandler = (e) => {
        if (e.key === 'Escape' && this.modal.style.display === 'flex') this._close(false);
      };
      document.addEventListener('keydown', this._keyHandler);
    }

    _close(confirmed) {
      this.modal.style.display = 'none';
      if (this._callback) {
        if (this._needInput) {
          // 输入框模式：确认传值，取消传 null
          const value = confirmed ? this.inputEl.value.trim() : null;
          this._callback(value);
        } else if (confirmed) {
          // 简单确认模式：只有确认才回调，并传 true
          this._callback(true);
        }
        // 简单确认模式下取消不调用 callback
      }
      this._callback = null;
      this._needInput = false;
    }

    // show(title, body, callback) — 简单确认
    // show(title, body, needInput, inputLabel, callback) — 带输入框
    show(title, body, arg3, arg4, arg5) {
      let needInput = false;
      let inputLabel = '';
      let callback = null;

      if (typeof arg3 === 'function') {
        callback = arg3;
      } else if (typeof arg5 === 'function') {
        needInput = !!arg3;
        inputLabel = arg4 || '';
        callback = arg5;
      }

      this._callback = callback;
      this._needInput = needInput;

      this.titleEl.textContent = title || '确认操作';
      this.bodyEl.innerHTML = sanitizeHtml(body || '');
      this.inputWrap.style.display = needInput ? 'block' : 'none';
      this.inputLabel.textContent = inputLabel || '请输入：';
      this.inputEl.value = '';
      this.modal.style.display = 'flex';
      if (needInput) setTimeout(() => this.inputEl.focus(), 50);
    }
  }

  const confirmInstance = new AdminConfirm();

  // ===== AdminTable：通用表格加载与分页 =====
  class AdminTable {
    constructor(options) {
      this.url = options.url;
      this.bodySelector = options.bodySelector;
      this.emptyText = options.emptyText || '暂无数据';
      this.errorText = options.errorText || '加载失败';
      this.columns = options.columns || [];
      this.renderRow = options.renderRow;
      this.onData = options.onData || null;
      this.paginationSelector = options.paginationSelector || null;
      this.infoSelector = options.infoSelector || null;
      this.pageSize = options.pageSize || 20;
      this.currentPage = 1;
      this.total = 0;
      this.items = [];
      this._buildUrl = options.buildUrl || null;
    }

    async load(page = 1) {
      this.currentPage = page;
      const tbody = document.querySelector(this.bodySelector);
      if (!tbody) return;
      const cols = this.columns.length || (tbody.closest('table')?.querySelectorAll('thead th').length || 1);
      tbody.innerHTML = `<tr><td colspan="${cols}" style="text-align:center;padding:40px;color:var(--muted);">加载中...</td></tr>`;

      try {
        const url = this._buildUrl ? this._buildUrl(page, this.pageSize) : `${this.url}?page=${page}&page_size=${this.pageSize}`;
        const data = await api.get(url);
        this.items = data.items || data || [];
        this.total = data.total || this.items.length;
        this.render(this.items, this.total);
        if (this.onData) this.onData(data);
      } catch (err) {
        tbody.innerHTML = `<tr><td colspan="${cols}" style="text-align:center;padding:40px;color:var(--error);">${this.errorText}：${escapeHtml(err.message || '未知错误')}</td></tr>`;
      }
    }

    render(items, total) {
      const tbody = document.querySelector(this.bodySelector);
      if (!tbody) return;
      const cols = this.columns.length || (tbody.closest('table')?.querySelectorAll('thead th').length || 1);

      if (!items.length) {
        tbody.innerHTML = `<tr><td colspan="${cols}" style="text-align:center;padding:40px;color:var(--muted);">${this.emptyText}</td></tr>`;
      } else if (this.renderRow) {
        tbody.innerHTML = items.map((item, idx) => this.renderRow(item, idx, items)).join('');
      }

      if (this.infoSelector) {
        document.querySelector(this.infoSelector).textContent = `共 ${total || 0} 条`;
      }

      if (this.paginationSelector) {
        AdminPagination.render(this.paginationSelector, total, this.currentPage, this.pageSize, (p) => this.load(p));
      }
    }

    reload() {
      return this.load(this.currentPage);
    }
  }

  // ===== AdminPagination：通用分页渲染 =====
  const AdminPagination = {
    render(containerSelector, total, page, pageSize, onChange) {
      const el = typeof containerSelector === 'string' ? document.querySelector(containerSelector) : containerSelector;
      if (!el) return;
      const totalPages = Math.ceil(total / pageSize);
      if (totalPages <= 1) { el.innerHTML = ''; return; }

      let html = `<span style="font-size:13px;color:var(--muted);">共 ${total} 条 · ${page}/${totalPages} 页</span>`;
      const start = Math.max(1, page - 2);
      const end = Math.min(totalPages, page + 2);

      if (page > 1) html += `<button class="btn-outline btn-sm" data-page="${page - 1}">上一页</button>`;
      for (let i = start; i <= end; i++) {
        html += `<button class="${i === page ? 'btn-primary' : 'btn-outline'} btn-sm" data-page="${i}" ${i === page ? 'disabled' : ''}>${i}</button>`;
      }
      if (page < totalPages) html += `<button class="btn-outline btn-sm" data-page="${page + 1}">下一页</button>`;

      el.innerHTML = html;
      el.querySelectorAll('button[data-page]').forEach(btn => {
        btn.addEventListener('click', () => {
          const p = parseInt(btn.dataset.page, 10);
          if (onChange) onChange(p);
        });
      });
    }
  };

  // ===== AdminModal：通用弹窗控制 =====
  class AdminModal {
    constructor(selector) {
      this.el = typeof selector === 'string' ? document.querySelector(selector) : selector;
    }
    open() { if (this.el) this.el.style.display = 'flex'; }
    close() { if (this.el) this.el.style.display = 'none'; }
    show() { this.open(); }
    hide() { this.close(); }
  }

  // ===== BatchSelect：表格行批量选择 =====
  const BatchSelect = {
    _registry: new WeakMap(),

    _cleanup(table) {
      const old = this._registry.get(table);
      if (!old) return;
      if (old.selectAll && old.selectAllHandler) {
        old.selectAll.removeEventListener('change', old.selectAllHandler);
      }
      if (old.rowHandlers) {
        old.rowHandlers.forEach(({ cb, fn }) => cb.removeEventListener('change', fn));
      }
      this._registry.delete(table);
    },

    init(tableSelector, onChange) {
      const table = document.querySelector(tableSelector);
      if (!table) return;

      // 先清理旧监听器，避免重复绑定
      this._cleanup(table);

      const selectAll = table.querySelector('.select-all');
      const rowChecks = Array.from(table.querySelectorAll('.row-check'));
      const handlers = { selectAll, selectAllHandler: null, rowHandlers: [] };

      const handleChange = () => {
        if (onChange) onChange(this.getSelectedIds(tableSelector));
      };

      const handleSelectAllChange = () => {
        rowChecks.forEach(cb => { cb.checked = selectAll.checked; });
        handleChange();
      };

      if (selectAll) {
        selectAll.addEventListener('change', handleSelectAllChange);
        handlers.selectAllHandler = handleSelectAllChange;
      }

      rowChecks.forEach(cb => {
        const fn = () => {
          if (selectAll) {
            const all = rowChecks;
            selectAll.checked = all.every(c => c.checked);
            selectAll.indeterminate = all.some(c => c.checked) && !selectAll.checked;
          }
          handleChange();
        };
        cb.addEventListener('change', fn);
        handlers.rowHandlers.push({ cb, fn });
      });

      this._registry.set(table, handlers);
    },

    getSelectedIds(tableSelector) {
      const table = document.querySelector(tableSelector);
      if (!table) return [];
      return Array.from(table.querySelectorAll('.row-check:checked')).map(cb => cb.value);
    },

    getSelectedRows(tableSelector) {
      const table = document.querySelector(tableSelector);
      if (!table) return [];
      return Array.from(table.querySelectorAll('.row-check:checked')).map(cb => cb.closest('tr'));
    }
  };

  // ===== 导出到全局 =====
  global.AdminConfirm = confirmInstance;
  global.AdminTable = AdminTable;
  global.AdminPagination = AdminPagination;
  global.AdminModal = AdminModal;
  global.BatchSelect = BatchSelect;

  // 覆盖全局 showConfirm，保持调用签名兼容
  global.showConfirm = function(title, body, arg3, arg4, arg5) {
    confirmInstance.show(title, body, arg3, arg4, arg5);
  };
})(window);
