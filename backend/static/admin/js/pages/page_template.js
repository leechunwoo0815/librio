(function() {
  'use strict';

var currentPage = 1, pageSize = 20, total = 0;

// ── 初始化 ────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', function() {
  loadData(1);
  document.getElementById('searchInput').addEventListener('keydown', function(e) {
    if (e.key === 'Enter') loadData(1);
  });
  // ESC 关闭所有弹窗
  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
      ['createModal','detailModal','confirmModal'].forEach(closeModal);
    }
  });
});

// ── 加载列表数据 ──────────────────────────────────────────
function loadData(page) {
  currentPage = page || 1;
  var q = document.getElementById('searchInput').value;
  var s = document.getElementById('statusFilter').value;

  // 显示骨架屏
  showSkeleton('skeleton', 4);
  document.getElementById('dataBody').classList.add('hidden');
  document.getElementById('emptyState').classList.add('hidden');

  // TEMPLATE SCAFFOLD: 将 '/admin/api/xxx/...' 替换为实际 API 端点路径
  fetch('/admin/api/xxx/list?page=' + currentPage + '&page_size=' + pageSize
    + '&search=' + encodeURIComponent(q) + '&status=' + encodeURIComponent(s), {
    headers: { 'Authorization': 'Bearer ' + auth.getToken() }
  })
  .then(function(r) { return r.json(); })
  .then(function(data) {
    hideSkeleton('skeleton');
    total = data.total || 0;
    renderTable(data.items || []);
    renderPagination('pageBtns', total, currentPage, pageSize, 'loadData');
    document.getElementById('pageInfo').textContent =
      '共 ' + total + ' 条记录 · 第 ' + currentPage + '/' + Math.ceil(total / pageSize) + ' 页';
  })
  .catch(function(err) {
    hideSkeleton('skeleton');
    console.error('加载失败', err);
  });
}

// ── 渲染表格行 ────────────────────────────────────────────
function renderTable(items) {
  var tbody = document.getElementById('dataBody');
  var empty = document.getElementById('emptyState');
  tbody.innerHTML = '';
  if (!items || items.length === 0) {
    tbody.classList.add('hidden');
    empty.classList.remove('hidden');
    return;
  }
  tbody.classList.remove('hidden');
  empty.classList.add('hidden');
  items.forEach(function(item) {
    var tr = document.createElement('tr');
    tr.innerHTML =
      '<td>' + escapeHtml(item.field1) + '</td>' +
      '<td>' + escapeHtml(item.field2) + '</td>' +
      '<td>' + escapeHtml(item.field3) + '</td>' +
      '<td><div class="table-actions">' +
        '<button class="action-link" onclick="showDetail(' + item.id + ')">详情</button>' +
        '<button class="action-link" onclick="editItem(' + item.id + ')">编辑</button>' +
        '<button class="action-link text-error" onclick="deleteItem(' + item.id + ')">删除</button>' +
      '</div></td>';
    tbody.appendChild(tr);
  });
}

// ── CRUD 操作 ────────────────────────────────────────────
function openCreateModal() {
  document.getElementById('createForm').reset();
  showModal('createModal');
}

function submitCreate() {
  var name = document.getElementById('createName').value;
  if (!name) { showToast('请填写名称', 'error'); return; }

  // TEMPLATE SCAFFOLD: 将 '/admin/api/xxx' 替换为实际 API 端点路径
  fetch('/admin/api/xxx', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': 'Bearer ' + auth.getToken()
    },
    body: JSON.stringify({ name: name, desc: document.getElementById('createDesc').value })
  })
  .then(function(r) {
    if (!r.ok) throw new Error('创建失败');
    return r.json();
  })
  .then(function() {
    closeModal('createModal');
    loadData(1);
  })
  .catch(function(err) { showToast(err.message, 'error'); });
}

function showDetail(id) {
  document.getElementById('detailContent').innerHTML = '<p class="text-muted">加载中...</p>';
  showModal('detailModal');

  // TEMPLATE SCAFFOLD: 将 '/admin/api/xxx/...' 替换为实际 API 端点路径
  fetch('/admin/api/xxx/' + id, {
    headers: { 'Authorization': 'Bearer ' + auth.getToken() }
  })
  .then(function(r) { return r.json(); })
  .then(function(item) {
    document.getElementById('detailContent').innerHTML =
      '<div class="form-group"><label>名称</label><p>' + escapeHtml(item.name) + '</p></div>' +
      '<div class="form-group"><label>描述</label><p>' + escapeHtml(item.desc || '无') + '</p></div>';
  })
  .catch(function(err) {
    document.getElementById('detailContent').innerHTML = '<p class="text-error">加载失败</p>';
  });
}

function editItem(id) {
  // TEMPLATE SCAFFOLD: 将 '/admin/api/xxx/...' 替换为实际 API 端点路径
  fetch('/admin/api/xxx/' + id, {
    headers: { 'Authorization': 'Bearer ' + auth.getToken() }
  })
  .then(function(r) { return r.json(); })
  .then(function(item) {
    document.getElementById('createName').value = item.name;
    document.getElementById('createDesc').value = item.desc || '';
    showModal('createModal');
    // 保存时改为更新
    document.querySelector('#createModal .btn-primary').onclick = function() { submitEdit(id); };
  });
}

function submitEdit(id) {
  var name = document.getElementById('createName').value;
  // TEMPLATE SCAFFOLD: 将 '/admin/api/xxx/...' 替换为实际 API 端点路径
  fetch('/admin/api/xxx/' + id, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': 'Bearer ' + auth.getToken()
    },
    body: JSON.stringify({ name: name, desc: document.getElementById('createDesc').value })
  })
  .then(function(r) {
    if (!r.ok) throw new Error('更新失败');
    return r.json();
  })
  .then(function() {
    closeModal('createModal');
    loadData(currentPage);
  })
  .catch(function(err) { showToast(err.message, 'error'); });
}

var deleteTargetId = null;

function deleteItem(id) {
  deleteTargetId = id;
  document.getElementById('confirmMsg').textContent = '确定要删除此项吗？此操作不可撤销。';
  document.getElementById('confirmBtn').onclick = confirmDelete;
  showModal('confirmModal');
}

function confirmDelete() {
  // TEMPLATE SCAFFOLD: 将 '/admin/api/xxx/...' 替换为实际 API 端点路径
  fetch('/admin/api/xxx/' + deleteTargetId, {
    method: 'DELETE',
    headers: { 'Authorization': 'Bearer ' + auth.getToken() }
  })
  .then(function(r) {
    if (!r.ok) throw new Error('删除失败');
    closeModal('confirmModal');
    loadData(currentPage);
  })
  .catch(function(err) { showToast(err.message, 'error'); });
}

function confirmAction() {
  // 由调用方设置 confirmBtn.onclick
  closeModal('confirmModal');
}

  window.pageTemplatePage = { currentPage, pageSize, total, loadData, renderTable, openCreateModal, submitCreate, showDetail, editItem, submitEdit, deleteTargetId, deleteItem, confirmDelete, confirmAction };
  for (var k in window.pageTemplatePage) window[k] = window.pageTemplatePage[k];

})();
