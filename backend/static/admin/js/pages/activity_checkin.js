(function() {
  'use strict';

  document.addEventListener('DOMContentLoaded', function() { loadActivities(); });

  async function loadActivities() {
    try {
      var data = await api.get('/admin/api/activities');
      var items = data.items || data || [];
      var sel = document.getElementById('activitySelect');
      items.forEach(function(a) {
        var opt = document.createElement('option');
        opt.value = a.id;
        opt.textContent = (a.title||'') + '（' + (a.start_time||'').slice(0,10) + '）';
        sel.appendChild(opt);
      });
    } catch (e) {
      // silent
    }
  }

  async function loadAttendees() {
    var activityId = document.getElementById('activitySelect').value;
    if (!activityId) return;
    try {
      var data = await api.get('/admin/api/activities/' + activityId + '/enrollments');
      var items = data.items || data || [];
      renderAttendees(items);
      updateProgress(items);
    } catch (e) {
      document.getElementById('attendeeBody').innerHTML = '<tr><td colspan="5" class="text-center p-40 text-error">加载失败</td></tr>';
    }
  }

  function updateProgress(items) {
    var total = items.length;
    var checked = items.filter(function(e) { return e.sign_in_time; }).length;
    var unchecked = total - checked;
    var pct = total > 0 ? Math.round(checked / total * 100) : 0;
    document.getElementById('statChecked').textContent = checked;
    document.getElementById('statUnchecked').textContent = unchecked;
    document.getElementById('statTotal').textContent = total;
    document.getElementById('progressPct').textContent = pct + '%';
    document.getElementById('progressFill').style.width = pct + '%';
  }

  function renderAttendees(items) {
    if (!items.length) {
      document.getElementById('attendeeBody').innerHTML = '<tr><td colspan="5" class="text-center p-40 text-muted">暂无报名记录</td></tr>';
      return;
    }
    document.getElementById('attendeeBody').innerHTML = items.map(function(e) {
      var isChecked = !!e.sign_in_time;
      var statusBadge = isChecked ? '<span class="status-badge status-checked">已签到</span>' : '<span class="status-badge status-unchecked">未签到</span>';
      var time = isChecked ? formatDateTime(e.sign_in_time) : '--';
      var phone = e.parent_phone ? e.parent_phone.replace(/(\d{3})\d{4}(\d{4})/, '$1****$2') : '--';
      var actions = isChecked
        ? '<span class="action-link text-muted">--</span>'
        : '<span class="action-link" onclick="manualSignIn(' + JSON.stringify(e.ticket_code || '').replace(/"/g, '&quot;') + ')">手动签到</span>';
      return '<tr>' +
        '<td>' + escapeHtml(e.child_name || e.child_id || '--') + '</td>' +
        '<td>' + statusBadge + '</td>' +
        '<td class="font-mono">' + time + '</td>' +
        '<td class="font-mono text-sm">' + phone + '</td>' +
        '<td>' + actions + '</td>' +
      '</tr>';
    }).join('');
  }

  async function doSignIn() {
    var code = document.getElementById('scanInput').value.trim();
    if (!code) { showToast('请输入签到码', 'error'); return; }
    try {
      await api.put('/admin/api/activities/enroll/' + encodeURIComponent(code) + '/sign-in');
      showToast('签到成功');
      document.getElementById('scanInput').value = '';
      loadAttendees();
    } catch (e) {
      showToast('签到失败: ' + e.message, 'error');
    }
  }

  async function manualSignIn(ticketCode) {
    if (!ticketCode) { showToast('缺少签到码', 'error'); return; }
    try {
      await api.put('/admin/api/activities/enroll/' + encodeURIComponent(ticketCode) + '/sign-in');
      showToast('手动签到成功');
      loadAttendees();
    } catch (e) {
      showToast('签到失败: ' + e.message, 'error');
    }
  }

  function escapeHtml(str) {
    if (!str) return '';
    var div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  // Enter key on scan input
  document.getElementById('scanInput').addEventListener('keydown', function(e) {
    if (e.key === 'Enter') doSignIn();
  });

  window.activityCheckinPage = { loadActivities, loadAttendees, updateProgress, renderAttendees, doSignIn, manualSignIn, escapeHtml };
  for (var k in window.activityCheckinPage) window[k] = window.activityCheckinPage[k];
})();
