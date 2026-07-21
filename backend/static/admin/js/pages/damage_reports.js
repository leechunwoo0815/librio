(function() {
  'use strict';

  var allReports = [];
  var currentFilter = '';
  var currentPage = 1;
  var pageSize = 20;

  document.addEventListener('DOMContentLoaded', function() { loadReports(); });

  async function loadReports() {
    try {
      var params = '?page=' + currentPage + '&page_size=' + pageSize;
      if (currentFilter) params += '&status=' + currentFilter;
      var data = await api.get('/admin/api/damage-reports' + params);
      var items = data.items || data || [];
      allReports = items;
      updateStats(items);
      renderReports(items);
    } catch (err) {
      document.getElementById('reportBody').innerHTML = '<tr><td colspan="8" class="text-center p-40 text-error">加载失败</td></tr>';
    }
  }

  function updateStats(items) {
    var pending = 0, disputed = 0, confirmed = 0, overridden = 0;
    items.forEach(function(r) {
      if (r.status === 0) pending++;
      else if (r.status === 2) disputed++;
      else if (r.status === 1) confirmed++;
      else if (r.status === 3) overridden++;
    });
    document.getElementById('statPending').textContent = pending;
    document.getElementById('statDisputed').textContent = disputed;
    document.getElementById('statConfirmed').textContent = confirmed;
    document.getElementById('statOverridden').textContent = overridden;
  }

  function filterTab(btn, status) {
    currentFilter = status;
    currentPage = 1;
    document.querySelectorAll('.tabs .tab').forEach(function(t) { t.classList.remove('active'); });
    btn.classList.add('active');
    loadReports();
  }

  var levelNames = { 1: '轻度', 2: '重度', 3: '丢失' };
  var levelColors = { 1: 'status-light', 2: 'status-heavy', 3: 'status-lost' };
  var statusNames = { 0: '待申诉', 1: '已确认', 2: '申诉中', 3: '已冲正' };
  var statusColors = { 0: 'status-pending', 1: 'status-confirmed', 2: 'status-disputed', 3: 'status-overridden' };

  function renderReports(items) {
    if (!items || !items.length) {
      document.getElementById('reportBody').innerHTML = '<tr><td colspan="8" class="text-center p-40 text-muted">暂无损坏记录</td></tr>';
      return;
    }
    document.getElementById('reportBody').innerHTML = items.map(function(r) {
      var levelName = levelNames[r.damage_level] || '未知';
      var levelColor = levelColors[r.damage_level] || '';
      var sName = statusNames[r.status] || '未知';
      var sColor = statusColors[r.status] || '';
      var fine = r.fine_amount ? '¥' + Number(r.fine_amount).toFixed(2) : '--';
      var time = r.create_time || '--';
      var actions = '';

      if (r.status === 2) {
        actions = '<a href="javascript:void(0)" onclick="showAppealDialog(' + r.id + ')" class="action-link">审核</a>';
      } else if (r.status === 0) {
        actions = '<span class="text-muted">申诉期</span>';
      } else {
        actions = '<span class="text-muted">--</span>';
      }

      return '<tr>' +
        '<td>' + r.id + '</td>' +
        '<td>' + r.borrow_record_id + '</td>' +
        '<td>' + escapeHtml(r.child_name || r.child_id) + '</td>' +
        '<td><span class="status-badge ' + levelColor + '">' + levelName + '</span></td>' +
        '<td class="amount">' + fine + '</td>' +
        '<td><span class="status-badge ' + sColor + '">' + sName + '</span></td>' +
        '<td class="font-mono-date">' + time + '</td>' +
        '<td>' + actions + '</td>' +
        '</tr>';
    }).join('');
  }

  function showCreateDialog() {
    document.getElementById('createBorrowId').value = '';
    document.getElementById('createLevel').value = '1';
    document.getElementById('createPhoto').value = '';
    document.getElementById('createDesc').value = '';
    openModal('createDialog');
  }

  window.confirmCreate = async function() {
    var borrowId = parseInt(document.getElementById('createBorrowId').value);
    var level = parseInt(document.getElementById('createLevel').value);
    var photo = document.getElementById('createPhoto').value.trim() || null;
    var desc = document.getElementById('createDesc').value.trim() || null;
    if (!borrowId || isNaN(borrowId)) { api.toast('请输入借阅记录ID'); return; }
    try {
      await api.post('/admin/api/damage-reports', {
        borrow_record_id: borrowId,
        damage_level: level,
        photo_url: photo,
        description: desc,
      });
      closeModal('createDialog');
      api.toast('登记成功');
      loadReports();
    } catch (err) { api.toast(err.message || '登记失败'); }
  };

  var currentReportId = null;

  window.showAppealDialog = async function(reportId) {
    currentReportId = reportId;
    try {
      var resp = await api.get('/admin/api/damage-reports?page=1&page_size=100');
      var items = resp.items || resp || [];
      var report = items.find(function(r) { return r.id === reportId; });
      if (!report) { api.toast('报告不存在'); return; }
      document.getElementById('appealInfo').textContent = '报告 #' + reportId + ' — 定级: ' + (levelNames[report.damage_level] || '未知') + ' 罚款: ¥' + Number(report.fine_amount || 0).toFixed(2);
      document.getElementById('appealReason').value = report.appeal_reason || '暂无申诉理由';
      document.getElementById('reviewAction').value = 'approve';
      document.getElementById('overrideLevel').value = '1';
      document.getElementById('overrideFine').value = '';
      document.getElementById('reviewRemark').value = '';
      toggleOverrideFields();
      openModal('appealDialog');
    } catch (err) { api.toast(err.message || '获取报告失败'); }
  };

  window.toggleOverrideFields = function() {
    var action = document.getElementById('reviewAction').value;
    document.getElementById('overrideFields').style.display = action === 'override' ? 'block' : 'none';
  };

  window.confirmReview = function() {
    var reportId = currentReportId;
    var action = document.getElementById('reviewAction').value;
    var reviewRemark = document.getElementById('reviewRemark').value.trim() || '';
    var body = { action: action, review_remark: reviewRemark };

    if (action === 'override') {
      var overrideLevel = parseInt(document.getElementById('overrideLevel').value);
      var overrideFine = parseFloat(document.getElementById('overrideFine').value);
      body.override_level = overrideLevel;
      body.override_fine = isNaN(overrideFine) ? 0 : overrideFine;
    }

    api.post('/admin/api/damage-reports/' + reportId + '/review', body).then(function() {
      closeModal('appealDialog');
      api.toast('审核完成');
      loadReports();
    }).catch(function(err) {
      api.toast(err.message || '审核失败');
    });
  };

  window.filterTab = filterTab;
})();
