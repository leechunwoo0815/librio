(function() {
  'use strict';

  var currentPage = 1;
  var pageSize = 15;
  var deleteTarget = null;

  var MODULE_LABELS = { book: '图书', activity: '活动', teacher: '老师', venue: '场馆' };
  var MODULE_BADGE = { book: 'badge-accent', activity: 'badge-success', teacher: 'badge-warning', venue: 'badge-muted' };

  document.addEventListener('DOMContentLoaded', function() {
    loadRecycle(1);
    document.addEventListener('click', function(e) {
      var target = e.target.closest('[data-action]');
      if (!target) return;
      var action = target.getAttribute('data-action');
      var id = target.getAttribute('data-id');
      var mod = target.getAttribute('data-module');
      var name = target.getAttribute('data-name');
      var page = target.getAttribute('data-page');
      var modal = target.getAttribute('data-modal');
      if (action === 'load-recycle') loadRecycle(1);
      else if (action === 'load-recycle-page' && page) loadRecycle(Number(page));
      else if (action === 'restore-item' && mod && id) restoreItem(mod, Number(id));
      else if (action === 'show-delete-modal' && mod && id) showDeleteModal(name || '', mod, Number(id));
      else if (action === 'hide-delete-modal') hideDeleteModal();
      else if (action === 'confirm-delete') confirmDelete();
      else if (action === 'close-modal' && modal) closeModal(modal);
    });
    document.addEventListener('change', function(e) {
      var target = e.target.closest('[data-action="change-page-size"]');
      if (target) changePageSize(target.value);
    });
  });

  async function loadRecycle(page) {
    currentPage = page;
    var module = document.getElementById('moduleFilter').value;
    var url = '/admin/api/recycle-bin?page=' + page + '&page_size=' + pageSize;
    if (module) url += '&module=' + module;

    try {
      var data = await api.get(url);
      var items = data.items || [];
      var total = data.total || 0;
      renderTable(items);
      pageUi(total, page, pageSize);
    } catch (err) {
      document.getElementById('recycleTable').innerHTML =
        '<tr><td colspan="5" class="text-center p-40 text-muted">加载失败：' + escapeHtml(err.message || '未知错误') + '</td></tr>';
    }
  }

  function renderTable(items) {
    var tbody = document.getElementById('recycleTable');
    if (!items.length) {
      tbody.innerHTML = '<tr><td colspan="5" class="text-center p-40 text-muted">回收站为空</td></tr>';
      return;
    }
    tbody.innerHTML = items.map(function(item) {
      var mod = item.module || 'unknown';
      var label = MODULE_LABELS[mod] || mod;
      var badge = MODULE_BADGE[mod] || 'badge-muted';
      return '<tr>' +
        '<td><span class="badge ' + badge + '">' + escapeHtml(label) + '</span></td>' +
        '<td><strong>' + escapeHtml(item.name || '-') + '</strong>' +
          (item.isbn ? '<br><span class="text-xs text-muted">ISBN: ' + escapeHtml(item.isbn) + '</span>' : '') +
          (item.extra_info ? '<br><span class="text-xs text-muted">' + escapeHtml(item.extra_info) + '</span>' : '') +
        '</td>' +
        '<td>' + escapeHtml(item.deleted_by || '--') + '</td>' +
        '<td class="text-sm text-muted">' + formatDateTime(item.deleted_at) + '</td>' +
        '<td>' +
          '<button class="btn btn-success" data-action="restore-item" data-module="' + mod + '" data-id="' + item.id + '">恢复</button> ' +
          '<button class="btn btn-danger" data-action="show-delete-modal" data-name="' + jsEscape(item.name||'') + '" data-module="' + mod + '" data-id="' + item.id + '">永久删除</button>' +
        '</td>' +
      '</tr>';
    }).join('');
  }

  function showConfirmDialog(title, msg, onConfirm) {
    document.querySelector('#confirmDialog h2').textContent = title;
    document.getElementById('confirmMsg').textContent = msg;
    document.getElementById('confirmBtn').onclick = function() {
      closeModal('confirmDialog');
      onConfirm();
    };
    showModal('confirmDialog');
  }

  async function restoreItem(module, id) {
    showConfirmDialog('确认恢复', '确认恢复该记录？', async function() {
      try {
        await api.post('/admin/api/recycle-bin/' + module + '/' + id + '/restore');
        showToast('恢复成功');
        loadRecycle(currentPage);
      } catch (err) {
        showToast(err.message || '恢复失败', 'error');
      }
    });
  }

  function showDeleteModal(name, module, id) {
    deleteTarget = { module: module, id: id };
    document.getElementById('deleteItemName').textContent = name;
    document.getElementById('deleteModal').classList.add('show');
  }

  function hideDeleteModal() {
    document.getElementById('deleteModal').classList.remove('show');
    deleteTarget = null;
  }

  async function confirmDelete() {
    if (!deleteTarget) return;
    try {
      await api.del('/admin/api/recycle-bin/' + deleteTarget.module + '/' + deleteTarget.id);
      showToast('已永久删除');
      hideDeleteModal();
      loadRecycle(currentPage);
    } catch (e) {
      showToast('删除失败: ' + e.message, 'error');
    }
  }

  function pageUi(total, page, pageSize) {
    var el = document.getElementById('pagination');
    var totalPages = Math.ceil(total / pageSize);
    if (totalPages <= 1) { el.innerHTML = ''; return; }
    var html = '<div class="flex-center gap-8"><span class="text-muted">共 ' + total + ' 条</span><span class="text-xs text-muted">每页</span><select class="page-size-select" data-action="change-page-size"><option value="15"'+(pageSize===15?' selected':'')+'>15</option><option value="30"'+(pageSize===30?' selected':'')+'>30</option><option value="50"'+(pageSize===50?' selected':'')+'>50</option><option value="100"'+(pageSize===100?' selected':'')+'>100</option></select><span class="text-xs text-muted">条</span></div>';
    html += '<div class="pagination-info">第 ' + page + '/' + totalPages + ' 页</div>';
    html += '<div class="pagination-pages">';
    if (page > 1) html += '<a href="javascript:void(0)" data-action="load-recycle-page" data-page="' + (page-1) + '">&lt;</a>';
    var start = Math.max(1, page - 2);
    var end = Math.min(totalPages, page + 2);
    for (var i = start; i <= end; i++) {
      html += '<a href="javascript:void(0)" class="' + (i === page ? 'active' : '') + '" data-action="load-recycle-page" data-page="' + i + '">' + i + '</a>';
    }
    if (page < totalPages) html += '<a href="javascript:void(0)" data-action="load-recycle-page" data-page="' + (page+1) + '">&gt;</a>';
    html += '</div>';
    el.innerHTML = html;
  }

  function changePageSize(newSize) {
    pageSize = parseInt(newSize);
    loadRecycle(1);
  }


  window.recycleBinPage = { currentPage, pageSize, deleteTarget, MODULE_LABELS, MODULE_BADGE, loadRecycle, renderTable, showConfirmDialog, restoreItem, showDeleteModal, hideDeleteModal, confirmDelete, pageUi, changePageSize };
})();
