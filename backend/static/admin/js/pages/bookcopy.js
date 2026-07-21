(function() {
'use strict';

const STATUS_MAP = {0:'可借',1:'已借出',2:'维修中',3:'已丢失'};
const STATUS_CLASS = {0:'status-available',1:'status-borrowed',2:'status-damaged',3:'status-lost'};
const STATUS_TEXT = {0:'在馆',1:'借出',2:'损坏',3:'丢失'};
let allData = [];

function localEscapeHtml(str) {
  if (str == null) return '';
  var div = document.createElement('div');
  div.textContent = String(str);
  return div.innerHTML;
}

function localExportCSV(filename, headers, rows) {
  var csv = headers.join(',') + '\n';
  rows.forEach(function(row) {
    csv += row.map(function(cell) {
      var s = String(cell == null ? '' : cell);
      return '"' + s.replace(/"/g, '""') + '"';
    }).join(',') + '\n';
  });
  var blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8;' });
  var link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

function toggleForm(id) {
  document.getElementById(id).style.display = document.getElementById(id).style.display === 'none' ? 'block' : 'none';
}

async function loadData() {
  try {
    const r = await api.get('/admin/api/bookcopy');
    allData = r || [];
    renderTable(allData);
  } catch(e) {
    document.getElementById('dataBody').innerHTML = '<tr><td colspan="8">加载失败: '+escapeHtml(e.message)+'</td></tr>';
  }
}

function renderTable(data) {
  const tb = document.getElementById('dataBody');
  document.getElementById('paginationInfo').textContent = '共 ' + data.length + ' 条记录';
  if (!data || data.length === 0) {
    tb.innerHTML = '<tr><td colspan="8" class="text-center p-40 text-muted">暂无副本</td></tr>';
    return;
  }
  tb.innerHTML = data.map(c => {
    var statusKey = c.status || 0;
    var statusCls = STATUS_CLASS[statusKey] || 'status-available';
    var statusText = STATUS_TEXT[statusKey] || STATUS_MAP[statusKey] || statusKey;
    return '<tr>' +
      '<td class="font-mono text-sm">' + escapeHtml(c.barcode || '-') + '</td>' +
      '<td>' + escapeHtml(c.book_title || c.book_id || '-') + '</td>' +
      '<td class="font-mono text-sm">' + escapeHtml(c.isbn || '-') + '</td>' +
      '<td>' + escapeHtml(c.ar_value || '-') + '</td>' +
      '<td><span class="status-badge ' + statusCls + '">' + escapeHtml(statusText) + '</span></td>' +
      '<td>' + escapeHtml(c.location || '-') + '</td>' +
      '<td' + (!c.borrower_name ? ' style="color:var(--muted);"' : '') + '>' + escapeHtml(c.borrower_name || '--') + '</td>' +
      '<td><span class="action-link" onclick="viewDetail(\'' + c.id + '\')">详情</span>' +
      (statusKey === 1 ? ' · <span class="action-link" onclick="doReturn(\'' + c.id + '\')">归还</span>' : '') +
      (statusKey === 0 ? ' · <span class="action-link" onclick="editCopy(\'' + c.id + '\')">编辑</span>' : '') +
      '</td>' +
    '</tr>';
  }).join('');
}

function filterTable() {
  const q = document.getElementById('searchInput').value.toLowerCase();
  const statusVal = document.getElementById('statusFilter').value;
  const venueVal = document.getElementById('venueFilter').value;
  const statusRev = {'在馆':0,'借出':1,'丢失':3,'损坏':2};
  renderTable(allData.filter(c => {
    var matchSearch = !q || (c.barcode||'').toLowerCase().includes(q) || (c.book_title||'').toLowerCase().includes(q) || (c.isbn||'').toLowerCase().includes(q) || String(c.book_id).includes(q);
    var matchStatus = statusVal === '全部状态' || c.status === statusRev[statusVal];
    var matchVenue = venueVal === '全部场馆' || (c.location||'').includes(venueVal.replace('馆',''));
    return matchSearch && matchStatus && matchVenue;
  }));
}

function scanBarcode() {
  var barcode = document.getElementById('barcodeInput').value.trim();
  if (!barcode) return;
  document.getElementById('searchInput').value = barcode;
  filterTable();
}

function viewDetail(id) {
  var copy = allData.find(function(c) { return c.id === id; });
  if (!copy) {
    showToast('副本不存在', 'error');
    return;
  }
  var html = '<div class="p-20">';
  html += '<h3 class="mb-16">副本详情</h3>';
  html += '<table class="w-full detail-table">';
  html += '<tr><td class="detail-label">条码</td><td class="font-mono">' + localEscapeHtml(copy.barcode || '-') + '</td></tr>';
  html += '<tr><td class="detail-label">书名</td><td>' + localEscapeHtml(copy.book_title || '-') + '</td></tr>';
  html += '<tr><td class="detail-label">ISBN</td><td class="font-mono">' + localEscapeHtml(copy.isbn || '-') + '</td></tr>';
  html += '<tr><td class="detail-label">状态</td><td>' + localEscapeHtml(STATUS_TEXT[copy.status] || copy.status) + '</td></tr>';
  html += '<tr><td class="detail-label">位置</td><td>' + localEscapeHtml(copy.location || '-') + '</td></tr>';
  html += '<tr><td class="detail-label">借阅人</td><td>' + localEscapeHtml(copy.borrower_name || '-') + '</td></tr>';
  html += '</table></div>';
  showConfirm('副本详情', html, null, '关闭');
}

function editCopy(id) {
  var copy = allData.find(function(c) { return c.id === id; });
  if (!copy) {
    showToast('副本不存在', 'error');
    return;
  }
  document.getElementById('fBookId').value = copy.book_id || '';
  document.getElementById('fBarcode').value = copy.barcode || '';
  document.getElementById('fLocation').value = copy.location || '';
  document.getElementById('fNote').value = '';
  toggleForm('addForm');
}

async function doReturn(id) {
  showConfirm('归还图书', '确定将副本 #' + id + ' 标记为归还？', async function() {
    try {
      // 查找对应的借阅记录
      var copy = allData.find(function(c) { return c.id === id; });
      if (copy && copy.borrow_record_id) {
        await api.post('/admin/api/borrows/return', { borrow_record_id: copy.borrow_record_id });
        showToast('归还成功');
        loadData();
      } else {
        showToast('未找到借阅记录', 'error');
      }
    } catch (err) {
      showToast('归还失败: ' + err.message, 'error');
    }
  });
}

function exportExcel() {
  var headers = ['条码', '书名', 'ISBN', 'AR值', '状态', '位置', '借阅人'];
  var rows = (allData || []).map(c => [c.barcode, c.book_title, c.isbn, c.ar_value, STATUS_TEXT[c.status]||c.status, c.location, c.borrower_name || '--']);
  localExportCSV('bookcopy_export.csv', headers, rows);
  showToast('已导出 ' + rows.length + ' 条记录');
}

async function addItem(e) {
  e.preventDefault();
  const btn = document.querySelector('#addForm button[type="submit"]');
  btn.disabled = true;
  btn.textContent = '入库中...';
  try {
  await api.post('/admin/api/bookcopy/' + document.getElementById('fBookId').value + '/copies', {
    barcode: document.getElementById('fBarcode').value,
    location: document.getElementById('fLocation').value,
    condition_note: document.getElementById('fNote').value,
  });
  toggleForm('addForm');
  loadData();
  } catch (err) {
    showToast(err.message || '操作失败', 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = '入库';
  }
}

document.addEventListener('DOMContentLoaded', function() {
  if (typeof api === 'undefined') {
    document.getElementById('dataBody').innerHTML = '<tr><td colspan="8" class="text-center p-40 text-error">核心脚本未加载，请刷新页面</td></tr>';
    return;
  }
  document.getElementById('barcodeInput').addEventListener('keydown', function(e) {
    if (e.key === 'Enter') scanBarcode();
  });
  loadData();
});


  window.bookcopyPage = { STATUS_MAP, STATUS_CLASS, STATUS_TEXT, allData, localEscapeHtml, localExportCSV, toggleForm, loadData, renderTable, filterTable, scanBarcode, viewDetail, editCopy, doReturn, exportExcel, addItem };
  for (var k in window.bookcopyPage) window[k] = window.bookcopyPage[k];
})();
