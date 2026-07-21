(function() {
  'use strict';

  var currentReviewId = null;
  var currentTab = 'pending';
  var currentPage = 1;
  var pageSize = 15;
  var totalItems = 0;
  var searchKeyword = '';

  function getStatusParam() {
    if (currentTab === 'pending') return '0';
    if (currentTab === 'reviewed') return '1,2';
    return '';
  }

  function switchTab(btn, tab) {
    currentTab = tab;
    currentPage = 1;
    document.querySelectorAll('.tab-item').forEach(function(t) { t.classList.remove('active'); });
    btn.classList.add('active');
    loadSubmissions();
  }

  async function loadSubmissions() {
    searchKeyword = document.getElementById('searchInput').value.trim();
    var params = '?page=' + currentPage + '&page_size=' + pageSize;
    var statusParam = getStatusParam();
    if (statusParam) params += '&status=' + statusParam;

    try {
      var data = await api.get('/admin/api/advancement/submissions' + params);
      var items = data.items || [];

      // Client-side search filter (API doesn't support keyword search)
      if (searchKeyword) {
        var kw = searchKeyword.toLowerCase();
        items = items.filter(function(s) {
          return (s.child_name || '').toLowerCase().includes(kw) ||
                 (s.book_title || '').toLowerCase().includes(kw);
        });
      }

      totalItems = data.total || items.length;
      renderSubmissions(items);
      updateStats(data.items || []);
    } catch (e) {
      document.getElementById('subBody').innerHTML = '<tr><td colspan="6" class="text-center p-24 text-error">加载失败</td></tr>';
    }
  }

  function goToPage(page) {
    currentPage = page;
    loadSubmissions();
  }

  function onPageSizeChange(newSize) {
    pageSize = parseInt(newSize);
    currentPage = 1;
    loadSubmissions();
  }

  function updateStats(items) {
    var pending = 0, approved = 0, rejected = 0;
    var today = new Date().toISOString().slice(0, 10);
    var todayCount = 0;
    for (var i = 0; i < items.length; i++) {
      var s = items[i];
      if (s.status === 0) pending++;
      else if (s.status === 1) approved++;
      else if (s.status === 2) rejected++;
      if ((s.submitted_at||'').slice(0,10) === today) todayCount++;
    }
    document.getElementById('statPending').textContent = pending;
    document.getElementById('statApproved').textContent = approved;
    document.getElementById('statRejected').textContent = rejected;
    document.getElementById('statToday').textContent = todayCount;
  }

  function renderSubmissions(items) {
    if (!items.length) {
      document.getElementById('subBody').innerHTML = '<tr><td colspan="6" class="empty-state">暂无提交</td></tr>';
      renderPagination();
      return;
    }
    var statusMap = { 0: 'status-pending', 1: 'status-approved', 2: 'status-rejected' };
    var statusText = { 0: '待审核', 1: '已通过', 2: '已打回' };
    document.getElementById('subBody').innerHTML = items.map(function(s) {
      return '<tr>' +
        '<td><strong>' + escapeHtml(s.child_name||'--') + '</strong><br><span class="text-muted text-sm">' + escapeHtml(s.level||'') + '</span></td>' +
        '<td>' + escapeHtml(s.book_title||'--') + '</td>' +
        '<td>' + formatDateTime(s.submitted_at) + '</td>' +
        '<td>' + (s.total_pages ? s.total_pages + ' 页' : '-') + '</td>' +
        '<td><span class="status ' + (statusMap[s.status]||'') + '">' + (statusText[s.status]||'--') + '</span></td>' +
        '<td>' + (s.status === 0 ? '<button class="btn btn-primary btn-sm" onclick="openReview(' + s.id + ',\'' + jsEscape(s.child_name||'') + '\',\'' + jsEscape(s.book_title||'') + '\',\'' + jsEscape((s.submitted_at||'').slice(0,16)) + '\')">审核</button>' : '<button class="btn btn-outline btn-sm" onclick="openReview(' + s.id + ',\'' + jsEscape(s.child_name||'') + '\',\'' + jsEscape(s.book_title||'') + '\',\'' + jsEscape((s.submitted_at||'').slice(0,16)) + '\',true)">查看</button>') + '</td>' +
      '</tr>';
    }).join('');
    renderPagination();
  }

  function renderPagination() {
    renderPagination('subPagination', totalItems, currentPage, pageSize, 'goToPage', 'onPageSizeChange');
  }

  function openReview(id, child, book, time, readonly) {
    currentReviewId = id;
    document.getElementById('reviewChild').textContent = child;
    document.getElementById('reviewBook').textContent = book;
    document.getElementById('reviewTime').textContent = time;
    document.getElementById('reviewComment').value = '';
    document.getElementById('reviewComment').disabled = !!readonly;
    document.querySelector('#reviewModal .btn-danger').style.display = readonly ? 'none' : '';
    document.querySelector('#reviewModal .btn-primary').style.display = readonly ? 'none' : '';
    document.querySelector('#reviewModal .btn-secondary').textContent = readonly ? '关闭' : '取消';
    document.getElementById('reviewModal').classList.add('show');
  }

  async function doReview(status) {
    if (!currentReviewId) return;
    try {
      await api.put('/admin/api/advancement/submissions/' + currentReviewId + '/review', {
        status: status,
        comment: document.getElementById('reviewComment').value
      });
      showToast(status === 1 ? '审核通过' : '已打回');
      closeModal('reviewModal');
      loadSubmissions();
    } catch (e) {
      showToast('操作失败: ' + e.message, 'error');
    }
  }

  function escapeHtml(str) {
    if (!str) return '';
    var div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  document.addEventListener('DOMContentLoaded', loadSubmissions);

  window.submissionsPage = { currentReviewId, currentTab, currentPage, pageSize, totalItems, searchKeyword, getStatusParam, switchTab, loadSubmissions, goToPage, onPageSizeChange, updateStats, renderSubmissions, openReview, doReview };
  for (var k in window.submissionsPage) window[k] = window.submissionsPage[k];
})();
