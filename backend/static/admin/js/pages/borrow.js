// backend/static/admin/js/pages/borrow.js
// 扫码借还页面逻辑

(function() {
  'use strict';

  let currentBook = null;
  let searchTimeout = null;

  document.addEventListener('DOMContentLoaded', () => {
    const barcodeInput = document.getElementById('barcodeInput');
    if (barcodeInput) {
      barcodeInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') lookupBarcode();
      });
    }

    document.addEventListener('click', (e) => {
      if (!e.target.closest('.child-selector')) {
        const dropdown = document.getElementById('childDropdown');
        if (dropdown) dropdown.style.display = 'none';
      }
    });
  });

  // PC-013: child search with debounce
  function searchChildrenDebounced() {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(searchChildren, 300);
  }

  async function searchChildren() {
    const query = document.getElementById('childSearchInput').value.trim();
    const dropdown = document.getElementById('childDropdown');
    if (!query || query.length < 1) { dropdown.style.display = 'none'; return; }
    try {
      const children = await api.get('/admin/api/children/search?keyword=' + encodeURIComponent(query));
      if (!children || children.length === 0) {
        dropdown.innerHTML = '<div style="padding:12px;color:#999;">未找到匹配的孩子</div>';
      } else {
        const statusMap = { 0: '体验', 1: '观察期', 2: '正式', 3: '过期', 4: '退出' };
        const depositMap = { 0: '押金未交', 1: '押金已交', 2: '已退', 3: '已扣' };
        dropdown.innerHTML = children.map(c =>
          '<div style="padding:10px 12px;cursor:pointer;border-bottom:1px solid #f0f0f0;" onclick="window.borrowPage.selectChild(' + c.id + ',\'' + (c.name || '').replace(/'/g, "\\'") + '\',' + c.status + ',' + c.deposit_status + ',' + c.current_borrow_count + ')">' +
            '<strong>' + escapeHtml(c.name || '未知') + '</strong> ' + (c.english_name ? '(' + escapeHtml(c.english_name) + ') ' : '') +
            '<span style="color:#999;font-size:12px;margin-left:8px;">' + escapeHtml(c.parent_name || '') + ' ' + escapeHtml(c.phone || '') + '</span>' +
            '<span style="font-size:11px;color:var(--muted);margin-left:8px;">[' + (statusMap[c.status] || c.status) + '] [' + (depositMap[c.deposit_status] || '未知') + '] [借阅:' + c.current_borrow_count + ']</span>' +
          '</div>'
        ).join('');
      }
      dropdown.style.display = 'block';
    } catch (e) { dropdown.style.display = 'none'; }
  }

  function selectChild(id, name, status, depositStatus, borrowCount) {
    document.getElementById('childIdInput').value = id;
    document.getElementById('childSearchInput').value = name;
    document.getElementById('childDropdown').style.display = 'none';
    const statusMap = { 0: '体验', 1: '观察期', 2: '正式', 3: '过期', 4: '退出' };
    const depositMap = { 0: '押金未交', 1: '押金已交', 2: '已退', 3: '已扣' };

    const warnings = [];
    if (depositStatus !== 1) warnings.push('押金未缴纳');
    if (status === 3 || status === 4) warnings.push('会员已过期/退出');
    if (borrowCount >= 20) warnings.push('已达借阅上限');

    let html = name + ' (' + (statusMap[status] || status) + ') · ' + (depositMap[depositStatus] || '未知') + ' · 当前借阅' + borrowCount + '本';
    if (warnings.length > 0) {
      html += ' <span style="color:var(--error);font-weight:bold;">&#x26A0;&#xFE0F; ' + warnings.join('、') + '</span>';
    }
    document.getElementById('selectedChild').innerHTML = html;
  }

  async function lookupBarcode() {
    const barcode = document.getElementById('barcodeInput').value.trim();
    if (!barcode) { showToast('请输入条码', 'warning'); return; }
    try {
      const result = await api.get('/admin/api/books?keyword=' + encodeURIComponent(barcode));
      const books = result.items || result || [];
      if (books.length > 0) {
        currentBook = books[0];
        document.getElementById('bookTitle').textContent = currentBook.title;
        document.getElementById('bookIsbn').textContent = currentBook.isbn || '-';
        document.getElementById('bookBarcode').textContent = barcode;
        document.getElementById('bookAr').textContent = currentBook.ar_value || '-';
        document.getElementById('bookStock').textContent = (currentBook.available_stock || 0) + ' / ' + (currentBook.total_stock || 0);
        document.getElementById('scanResult').classList.add('show');
      } else {
        showToast('未找到条码「' + barcode + '」对应的图书', 'warning');
        document.getElementById('scanResult').classList.remove('show');
      }
    } catch (e) {
      showToast('查询失败: ' + (e.message || '网络异常'), 'error');
    }
  }

  async function doBorrow() {
    const childId = parseInt(document.getElementById('childIdInput').value);
    if (!childId || !currentBook) { showToast('请先选择孩子并扫描图书', 'error'); return; }
    try {
      const r = await api.post('/admin/api/borrows', { child_id: childId, book_id: currentBook.id });
      showToast('借出成功！到期: ' + (r.due_date || '21天后'));
      loadRecords(childId);
    } catch (e) {
      const msg = e.message || '';
      if (msg.includes('库存不足')) {
        showToast('该书库存不足，暂无可借副本', 'error');
      } else if (msg.includes('借阅上限')) {
        showToast('该孩子已达借阅上限，请先归还部分图书', 'error');
      } else if (msg.includes('已借阅')) {
        showToast('该孩子已借阅此书，请先归还', 'error');
      } else if (msg.includes('押金') || msg.includes('会员')) {
        showToast('该孩子无借阅权限，请检查押金和会员状态', 'error');
      } else {
        showToast('借出失败: ' + msg, 'error');
      }
    }
  }

  async function doReturn() {
    const childId = parseInt(document.getElementById('childIdInput').value);
    if (!childId || !currentBook) { showToast('请输入孩子ID并扫描图书', 'error'); return; }
    try {
      const records = await api.get('/admin/api/borrows/' + childId + '?status=0');
      const record = (records || []).find(r => r.book_id === currentBook.id);
      if (!record) { showToast('未找到借阅记录', 'error'); return; }
      await api.post('/admin/api/borrows/return', { borrow_record_id: record.id });
      showToast('归还成功！');
      loadRecords(childId);
    } catch (e) { showToast('归还失败: ' + e.message, 'error'); }
  }

  async function loadRecords(childId) {
    try {
      const records = await api.get('/admin/api/borrows/' + childId);
      const tbody = document.getElementById('recordsBody');
      document.getElementById('recordsCount').textContent = '（共 ' + (records || []).length + ' 条）';
      tbody.innerHTML = (records || []).map(r =>
        '<tr>' +
          '<td style="font-family:var(--font-mono);">' + formatDateTime(r.borrow_time) + '</td>' +
          '<td>' + (r.child_name || r.child_id || '-') + '</td>' +
          '<td><span class="status-badge ' + (r.status === 0 ? 'status-borrow' : 'status-return') + '">' + (r.status === 0 ? '借出' : r.status === 1 ? '归还' : r.status === 2 ? '逾期' : '丢失') + '</span></td>' +
          '<td>' + (r.book_title || r.book_id || '-') + '</td>' +
          '<td style="font-family:var(--font-mono);font-size:12px;">' + (r.barcode || '-') + '</td>' +
        '</tr>'
      ).join('');
    } catch (e) { /* silent */ }
  }

  // PC-015: overdue reminders
  async function sendOverdueReminders() {
    showConfirm('发送逾期提醒', '确认向所有逾期未还书的家长发送提醒消息？', async function() {
      try {
        const result = await api.post('/admin/api/borrows/send-overdue-reminders', {});
        const count = result.sent_count || 0;
        if (count > 0) {
          showToast('已向 ' + count + ' 位家长发送提醒');
        } else {
          showToast('当前无逾期记录', 'info');
        }
      } catch (e) {
        showToast('发送失败: ' + (e.message || '未知错误'), 'error');
      }
    });
  }

  // 页面自带的自定义确认弹窗（当前未使用，保留关闭能力）
  function closeConfirmModal() {
    const modal = document.getElementById('confirmModal');
    if (modal) modal.style.display = 'none';
  }

  // 暴露到全局供 HTML onclick 调用
  window.borrowPage = {
    searchChildrenDebounced,
    searchChildren,
    selectChild,
    lookupBarcode,
    doBorrow,
    doReturn,
    loadRecords,
    sendOverdueReminders,
    closeConfirmModal
  };
})();
