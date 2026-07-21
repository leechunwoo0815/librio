(function() {
  'use strict';

  var currentReportId = null;
  var reports = [];

  async function loadReports() {
    try {
      var keyword = document.getElementById('searchInput').value.trim();
      var url = '/admin/api/reports/observation';
      if (keyword) url += '?keyword=' + encodeURIComponent(keyword);
      var data = await api.get(url);
      reports = data.items || data || [];
      renderReports(reports);
      updateStats(reports);
    } catch (err) {
      document.getElementById('reportBody').innerHTML = '<tr><td colspan="9" style="text-align:center;padding:40px;color:var(--error);">加载失败：' + escapeHtml(err.message || '未知错误') + '</td></tr>';
    }
  }

  function updateStats(items) {
    document.getElementById('statTotal').textContent = items.length;
    var generated = items.filter(function(r) { return r.status === 1; }).length;
    var viewed = items.filter(function(r) { return r.status === 2; }).length;
    document.getElementById('statGenerated').textContent = generated;
    document.getElementById('statViewed').textContent = viewed;
    var totalMinutes = items.reduce(function(s, r) { return s + (r.total_reading_minutes || 0); }, 0);
    document.getElementById('statPassRate').textContent = items.length ? Math.round(totalMinutes / items.length) + '分钟' : '--';
  }

  function renderReports(items) {
    var statusFilter = document.getElementById('statusFilter').value;
    if (statusFilter) {
      var statusInt = parseInt(statusFilter);
      items = items.filter(function(r) { return r.status === statusInt; });
    }
    if (!items.length) {
      document.getElementById('reportBody').innerHTML = '<tr><td colspan="9" style="text-align:center;padding:40px;color:var(--muted);">暂无报告</td></tr>';
      return;
    }
    document.getElementById('reportBody').innerHTML = items.map(function(r, i) {
      var statusClass = r.status === 2 ? 'status-viewed' : 'status-generated';
      var statusText = r.status === 2 ? '已查看' : '已生成';
      return '<tr data-status="' + r.status + '">' +
        '<td><strong>' + escapeHtml(r.child_name || '--') + '</strong><br><span style="color:var(--muted);font-size:12px">' + escapeHtml(r.level_at_end || r.level_at_start || '') + '</span></td>' +
        '<td>' + escapeHtml((r.start_date||'').slice(0,10)) + ' - ' + escapeHtml((r.end_date||'').slice(0,10)) + '</td>' +
        '<td>' + (r.total_books_read || 0) + ' 本</td>' +
        '<td>' + (r.total_words_read || 0).toLocaleString() + ' 词</td>' +
        '<td><span style="font-weight:600">' + (r.total_reading_minutes || 0) + ' 分钟</span></td>' +
        '<td style="max-width:140px"><span style="font-size:12px;color:var(--muted)">' + escapeHtml(r.teacher_comment || '暂无评语') + '</span></td>' +
        '<td>' + escapeHtml((r.create_time||'').slice(0,10)) + '</td>' +
        '<td><span class="status ' + statusClass + '">' + statusText + '</span></td>' +
        '<td>' +
          '<button class="btn btn-primary btn-sm" onclick="window.reportsPage.openPanel(' + i + ')">查看</button> ' +
          '<button class="btn btn-outline btn-sm" onclick="window.reportsPage.openComment(' + i + ')">添加评语</button>' +
        '</td>' +
      '</tr>';
    }).join('');
  }

  function openPanel(idx) {
    var r = reports[idx];
    document.getElementById('panelTitle').textContent = (r.child_name||'') + ' - 观察期报告';
    var html = '';
    html += '<div class="report-section"><h4><span class="icon" style="background:var(--accent-soft);color:var(--accent)">&#9679;</span> 基本信息</h4>';
    html += '<div class="report-meta">';
    html += '<div class="meta-item"><div class="label">学生姓名</div><div class="value">' + escapeHtml(r.child_name||'') + '</div></div>';
    html += '<div class="meta-item"><div class="label">当前级别</div><div class="value">' + escapeHtml(r.level_at_end || r.level_at_start || '') + '</div></div>';
    html += '<div class="meta-item"><div class="label">观察期</div><div class="value">' + escapeHtml((r.start_date||'').slice(0,10)) + ' - ' + escapeHtml((r.end_date||'').slice(0,10)) + '</div></div>';
    html += '<div class="meta-item"><div class="label">报告生成时间</div><div class="value">' + escapeHtml((r.create_time||'').slice(0,10)) + '</div></div>';
    html += '</div></div>';
    html += '<div class="report-section"><h4><span class="icon" style="background:var(--secondary-soft);color:#2d8f4a">&#9679;</span> 阅读统计</h4>';
    html += '<div class="report-meta">';
    html += '<div class="meta-item"><div class="label">阅读本数</div><div class="value" style="color:var(--accent)">' + (r.total_books_read||0) + ' 本</div></div>';
    html += '<div class="meta-item"><div class="label">阅读词数</div><div class="value" style="color:var(--accent)">' + (r.total_words_read||0).toLocaleString() + ' 词</div></div>';
    html += '<div class="meta-item"><div class="label">阅读时长</div><div class="value" style="color:var(--accent)">' + (r.total_reading_minutes||0) + ' 分钟</div></div>';
    html += '<div class="meta-item"><div class="label">状态</div><div class="value"><span class="status status-' + (r.status||'') + '">' + (r.status === 2 ? '已查看' : '已生成') + '</span></div></div>';
    html += '</div></div>';
    if (r.summary) {
      html += '<div class="report-section"><h4><span class="icon" style="background:var(--warning-soft);color:#8a6a20">&#9679;</span> 阅读总结</h4><div class="comment-box">' + escapeHtml(r.summary) + '</div></div>';
    }
    if (r.teacher_comment) {
      html += '<div class="report-section"><h4><span class="icon" style="background:var(--accent-soft);color:var(--accent)">&#9679;</span> 老师评语</h4><div class="comment-box">' + escapeHtml(r.teacher_comment) + '</div></div>';
    }
    html += '<div style="display:flex;gap:8px;padding-top:8px;border-top:1px solid var(--border)">';
    html += '<button class="btn btn-outline" onclick="window.reportsPage.closePanel();window.reportsPage.openComment(' + idx + ')">添加评语</button>';
    html += '</div>';
    document.getElementById('panelBody').innerHTML = html;
    document.getElementById('panelOverlay').classList.add('show');
    document.getElementById('sidePanel').classList.add('open');
  }

  function closePanel() {
    document.getElementById('panelOverlay').classList.remove('show');
    document.getElementById('sidePanel').classList.remove('open');
  }

  function openComment(idx) {
    var r = reports[idx];
    currentReportId = r.id;
    document.getElementById('commentStudent').textContent = (r.child_name||'') + ' · ' + (r.level_at_end || r.level_at_start || '');
    document.getElementById('commentText').value = r.teacher_comment || '';
    document.getElementById('commentModal').classList.add('show');
  }

  function hideCommentModal() {
    document.getElementById('commentModal').classList.remove('show');
  }

  async function saveComment() {
    if (!currentReportId) return;
    try {
      await api.put('/admin/api/reports/observation/' + currentReportId + '/comment', { comment: document.getElementById('commentText').value });
      showToast('评语保存成功');
      document.getElementById('commentModal').classList.remove('show');
      loadReports();
    } catch (e) {
      showToast('保存失败: ' + e.message, 'error');
    }
  }

  async function generateReports() {
    try {
      var result = await api.post('/admin/api/reports/observation/generate');
      showToast(result.message || '报告生成完成');
      loadReports();
    } catch (e) {
      showToast('生成失败: ' + e.message, 'error');
    }
  }

  document.addEventListener('DOMContentLoaded', function() {
    loadReports();
    document.body.addEventListener('click', function(e) {
      var el = e.target.closest('[data-pg]');
      if (!el) return;
      e.preventDefault();
      var fn = window.reportsPage[el.getAttribute('data-pg')];
      if (typeof fn === 'function') fn();
    });
  });

  window.reportsPage = {
    loadReports: loadReports,
    generateReports: generateReports,
    openPanel: openPanel,
    closePanel: closePanel,
    openComment: openComment,
    hideCommentModal: hideCommentModal,
    saveComment: saveComment
  };
})();
