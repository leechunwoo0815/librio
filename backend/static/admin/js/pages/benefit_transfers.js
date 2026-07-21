(function() {
  'use strict';

  var currentPage = 1;
  var pageSize = 15;
  var currentTab = 'pending';
  var currentAppId = null;

  function switchTab(tab) {
    currentTab = tab;
    currentPage = 1;
    loadTransfers(1);
    document.querySelectorAll('.filter-bar .btn').forEach(function(b) {
      b.className = b.className.replace('btn-primary', 'btn-outline');
    });
    var btns = document.querySelectorAll('.filter-bar .btn');
    btns[tab === 'pending' ? 0 : 1].className = btns[tab === 'pending' ? 0 : 1].className.replace('btn-outline', 'btn-primary');
  }

  async function loadTransfers(page) {
    currentPage = page;
    var status = currentTab === 'pending' ? 0 : undefined;
    var url = '/admin/api/benefit-transfers?page=' + page + '&page_size=' + pageSize;
    if (status !== undefined) url += '&status=' + status;

    try {
      var data = await api.get(url);
      var items = data.items || [];
      var total = data.total || 0;
      renderTable(items);
      pageUi(total, page, pageSize);
    } catch (err) {
      document.getElementById('transferTable').innerHTML =
        '<tr><td colspan="7" class="text-center p-40 text-muted">加载失败：' + escapeHtml(err.message || '未知错误') + '</td></tr>';
    }
  }

  function renderTable(items) {
    var tbody = document.getElementById('transferTable');
    if (!items.length) {
      tbody.innerHTML = '<tr><td colspan="7" class="text-center p-40 text-muted">暂无记录</td></tr>';
      return;
    }
    var statusMap = { 0: '<span class="badge badge-warning">待审核</span>', 1: '<span class="badge badge-success">已通过</span>', 2: '<span class="badge badge-error">已拒绝</span>' };
    tbody.innerHTML = items.map(function(app) {
      var statusHtml = statusMap[app.status] || '<span class="badge badge-muted">未知</span>';
      var actions = '';
      if (app.status === 0) {
        actions = '<button class="btn btn-sm btn-primary" onclick="openReview(' + app.id + ')">审核</button>';
      }
      return '<tr>' +
        '<td>' + app.id + '</td>' +
        '<td><strong>' + escapeHtml(app.user_name) + '</strong></td>' +
        '<td>' + escapeHtml(app.source_child_name) + '</td>' +
        '<td>' + escapeHtml(app.target_child_name) + '</td>' +
        '<td class="text-sm text-muted">' + formatDateTime(app.create_time) + '</td>' +
        '<td>' + statusHtml + '</td>' +
        '<td>' + actions + '</td>' +
      '</tr>';
    }).join('');
  }

  function openReview(appId) {
    currentAppId = appId;
    document.getElementById('reviewRemark').value = '';
    // Find the application data
    var rows = document.querySelectorAll('#transferTable tr');
    var cells = rows.length > 0 ? rows[0].querySelectorAll('td') : [];
    try {
      var data = window.__transferData ? window.__transferData[appId] : null;
    } catch(e) {}
    showModal('reviewModal');
  }

  async function doApprove() {
    if (!currentAppId) return;
    var remark = document.getElementById('reviewRemark').value;
    try {
      var res = await api.post('/admin/api/benefit-transfers/' + currentAppId + '/approve', { review_remark: remark });
      closeModal('reviewModal');
      showToast('审核通过，权益已转移');
      loadTransfers(currentPage);
    } catch (err) {
      showToast(err.message || '操作失败');
    }
  }

  async function doReject() {
    if (!currentAppId) return;
    var remark = document.getElementById('reviewRemark').value;
    try {
      var res = await api.post('/admin/api/benefit-transfers/' + currentAppId + '/reject', { review_remark: remark });
      closeModal('reviewModal');
      showToast('已拒绝转让申请');
      loadTransfers(currentPage);
    } catch (err) {
      showToast(err.message || '操作失败');
    }
  }

  function pageUi(total, page, pageSize) {
    var el = document.getElementById('pagination');
    var totalPages = Math.ceil(total / pageSize);
    if (totalPages <= 1) { el.innerHTML = ''; return; }
    var html = '<div class="flex-center gap-8"><span class="text-muted">共 ' + total + ' 条</span></div>';
    html += '<div class="pagination-info">第 ' + page + '/' + totalPages + ' 页</div>';
    html += '<div class="pagination-pages">';
    if (page > 1) html += '<a href="javascript:void(0)" onclick="loadTransfers(' + (page-1) + ')">&lt;</a>';
    var start = Math.max(1, page - 2);
    var end = Math.min(totalPages, page + 2);
    for (var i = start; i <= end; i++) {
      html += '<a href="javascript:void(0)" class="' + (i === page ? 'active' : '') + '" onclick="loadTransfers(' + i + ')">' + i + '</a>';
    }
    if (page < totalPages) html += '<a href="javascript:void(0)" onclick="loadTransfers(' + (page+1) + ')">&gt;</a>';
    html += '</div>';
    el.innerHTML = html;
  }

  document.addEventListener('DOMContentLoaded', function() {
    loadTransfers(1);
  });

  function escapeHtml(str) {
    if (!str) return '';
    var div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  function showToast(msg) {
    var el = document.createElement('div');
    el.className = 'toast toast-success';
    el.textContent = msg;
    document.body.appendChild(el);
    setTimeout(function() { el.remove(); }, 2000);
  }

  function formatDateTime(val) {
    if (!val) return '--';
    try { return new Date(val).toLocaleString('zh-CN'); } catch(e) { return val; }
  }

  window.benefitTransfersPage = { currentPage, pageSize, currentTab, currentAppId, switchTab, loadTransfers, renderTable, openReview, doApprove, doReject, pageUi };
  for (var k in window.benefitTransfersPage) window[k] = window.benefitTransfersPage[k];

})();
