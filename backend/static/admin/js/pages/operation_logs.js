(function() {
  'use strict';

  var currentPage = 1;
  var pageSize = 15;

  document.addEventListener('DOMContentLoaded', function() {
    // Set default date range (last 30 days)
    var now = new Date();
    var from = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
    document.getElementById('dateTo').value = now.toISOString().slice(0, 10);
    document.getElementById('dateFrom').value = from.toISOString().slice(0, 10);
    loadLogs(1);
  });

  async function loadLogs(page) {
    currentPage = page;
    var module = document.getElementById('moduleFilter').value;
    var url = '/admin/api/operation-logs?page=' + page + '&page_size=' + pageSize;
    if (module) url += '&module=' + module;

    try {
      var data = await api.get(url);
      var items = data.items || [];
      var total = data.total || 0;
      renderTable(items);
      pageUi(total, page, pageSize);
    } catch (err) {
      document.getElementById('logTable').innerHTML =
        '<tr><td colspan="6" class="text-center p-40 text-muted">加载失败：' + escapeHtml(err.message || '未知错误') + '</td></tr>';
    }
  }

  function renderTable(items) {
    var tbody = document.getElementById('logTable');
    if (!items.length) {
      tbody.innerHTML = '<tr><td colspan="6" class="text-center p-40 text-muted">暂无操作日志</td></tr>';
      return;
    }
    var moduleBadges = {
      config: 'badge-error', book: 'badge-accent', user: 'badge-accent',
      deposit: 'badge-warning', activity: 'badge-success'
    };
    var moduleLabels = {
      config: '系统', book: '图书', user: '用户', deposit: '押金', activity: '活动'
    };
    tbody.innerHTML = items.map(function(log) {
      var mod = log.module || guessModule(log.content);
      var badge = moduleBadges[mod] || 'badge-muted';
      return '<tr>' +
        '<td><strong>' + escapeHtml(String(log.admin_id || '--')) + '</strong></td>' +
        '<td class="text-sm text-muted">' + formatDateTime(log.create_time) + '</td>' +
        '<td><span class="badge ' + badge + '">' + escapeHtml(moduleLabels[mod] || mod || '-') + '</span></td>' +
        '<td>' + escapeHtml(log.operation || '-') + '</td>' +
        '<td>' + escapeHtml(log.content || '-') + '</td>' +
        '<td class="ip-addr">' + escapeHtml(log.ip || '--') + '</td>' +
      '</tr>';
    }).join('');
  }

  function guessModule(key) {
    if (!key) return 'system';
    key = String(key).toLowerCase();
    if (key.indexOf('config') >= 0 || key.indexOf('system') >= 0) return 'config';
    if (key.indexOf('book') >= 0) return 'book';
    if (key.indexOf('user') >= 0 || key.indexOf('admin') >= 0) return 'user';
    if (key.indexOf('deposit') >= 0) return 'deposit';
    if (key.indexOf('activity') >= 0) return 'activity';
    return 'config';
  }

  function pageUi(total, page, pageSize) {
    var el = document.getElementById('pagination');
    var totalPages = Math.ceil(total / pageSize);
    if (totalPages <= 1) { el.innerHTML = ''; return; }
    var html = '<div class="flex-center gap-8"><span class="text-muted">共 ' + total + ' 条</span><span class="text-xs text-muted">每页</span><select class="page-size-select" onchange="changePageSize(this.value)"><option value="15"'+(pageSize===15?' selected':'')+'>15</option><option value="30"'+(pageSize===30?' selected':'')+'>30</option><option value="50"'+(pageSize===50?' selected':'')+'>50</option><option value="100"'+(pageSize===100?' selected':'')+'>100</option></select><span class="text-xs text-muted">条</span></div>';
    html += '<div class="pagination-info">第 ' + page + '/' + totalPages + ' 页</div>';
    html += '<div class="pagination-pages">';
    if (page > 1) html += '<a href="javascript:void(0)" onclick="loadLogs(' + (page-1) + ')">&lt;</a>';
    var start = Math.max(1, page - 2);
    var end = Math.min(totalPages, page + 2);
    for (var i = start; i <= end; i++) {
      html += '<a href="javascript:void(0)" class="' + (i === page ? 'active' : '') + '" onclick="loadLogs(' + i + ')">' + i + '</a>';
    }
    if (page < totalPages) html += '<a href="javascript:void(0)" onclick="loadLogs(' + (page+1) + ')">&gt;</a>';
    html += '</div>';
    el.innerHTML = html;
  }

  function changePageSize(newSize) {
    pageSize = parseInt(newSize);
    loadLogs(1);
  }

  function exportLogs() {
    window.location.href = '/admin/export/operation-logs';
  }

  function escapeHtml(str) {
    if (!str) return '';
    var div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  window.operationLogsPage = { currentPage, pageSize, loadLogs, renderTable, guessModule, pageUi, changePageSize, exportLogs };
  for (var k in window.operationLogsPage) window[k] = window.operationLogsPage[k];
})();
