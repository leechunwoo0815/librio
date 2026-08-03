/* pages/teacher_workbench.js — D1 老师工作台 + D2 课后反馈 */
(function() {
  'use strict';

  var STATUS_MAP = {
    0: '体验', 1: '观察期', 2: '正式', 3: '已过期', 4: '已退出', 5: '校友'
  };

  function esc(s) {
    return escapeHtml(s == null ? '' : String(s));
  }

  function fmtTime(iso) {
    if (!iso) return '--';
    var d = new Date(iso);
    if (isNaN(d)) return iso;
    return (d.getMonth() + 1) + '月' + d.getDate() + '日 ' +
      ('0' + d.getHours()).slice(-2) + ':' + ('0' + d.getMinutes()).slice(-2);
  }

  async function loadWorkbench() {
    try {
      var data = await api.get('/admin/api/teacher/workbench');
      renderStats(data);
      renderCourses(data.today_schedules || []);
      renderPending(data.pending_submissions || []);
      renderChildren(data.children || []);
      renderGuidance(data.recent_guidance || []);
    } catch (e) {
      showToast('加载工作台失败: ' + e.message, 'error');
      document.getElementById('courseBody').innerHTML = '<tr><td colspan="2" class="text-center p-24 text-error">加载失败</td></tr>';
    }
  }

  function renderStats(data) {
    document.getElementById('statCourses').textContent = (data.today_schedules || []).length;
    document.getElementById('statPending').textContent = data.pending_submissions_count || 0;
    document.getElementById('statChildren').textContent = data.children_count || 0;
    document.getElementById('statGuidance').textContent = (data.recent_guidance || []).length;
  }

  function renderCourses(list) {
    var body = document.getElementById('courseBody');
    if (!list.length) {
      body.innerHTML = '<tr><td colspan="2" class="empty-state">今日暂无排课</td></tr>';
      return;
    }
    body.innerHTML = list.map(function(s) {
      return '<tr><td>' + esc(s.start_time) + ' - ' + esc(s.end_time) + '</td><td>' + esc(s.course_type || '1对1指导') + '</td></tr>';
    }).join('');
  }

  function renderPending(list) {
    var body = document.getElementById('pendingBody');
    if (!list.length) {
      body.innerHTML = '<tr><td colspan="3" class="empty-state">暂无待审核提交</td></tr>';
      return;
    }
    body.innerHTML = list.map(function(s) {
      return '<tr><td>' + esc(s.child_name) + '</td><td>' + esc(s.book_title) + '</td><td>' + fmtTime(s.submitted_at) + '</td></tr>';
    }).join('');
  }

  function renderChildren(list) {
    var body = document.getElementById('childBody');
    var select = document.getElementById('feedbackChild');
    if (!list.length) {
      body.innerHTML = '<tr><td colspan="5" class="empty-state">暂无负责的孩子</td></tr>';
    } else {
      body.innerHTML = list.map(function(c) {
        return '<tr><td>' + esc(c.name) + '</td><td>' + esc(STATUS_MAP[c.status] || c.status) + '</td><td>' + esc(c.level_name || '--') + '</td><td>' + (c.total_books_finished || 0) + ' 本</td><td>' + (c.current_streak_days || 0) + ' 天</td></tr>';
      }).join('');
    }
    // 反馈表单的孩子下拉（仅在读：观察期/正式）
    select.innerHTML = '<option value="">选择孩子…</option>' + list.filter(function(c) {
      return c.status === 1 || c.status === 2;
    }).map(function(c) {
      return '<option value="' + c.id + '">' + esc(c.name) + '</option>';
    }).join('');
  }

  function renderGuidance(list) {
    var body = document.getElementById('guidanceBody');
    if (!list.length) {
      body.innerHTML = '<tr><td colspan="3" class="empty-state">暂无指导记录</td></tr>';
      return;
    }
    body.innerHTML = list.map(function(g) {
      return '<tr><td>' + esc(g.child_name) + '</td><td>' + esc(g.content) + '</td><td>' + fmtTime(g.guidance_date) + '</td></tr>';
    }).join('');
  }

  async function submitFeedback() {
    var childId = document.getElementById('feedbackChild').value;
    var content = document.getElementById('feedbackContent').value.trim();
    if (!childId) { showToast('请选择孩子', 'error'); return; }
    if (!content) { showToast('请填写反馈内容', 'error'); return; }
    try {
      await api.post('/admin/api/teacher/feedback', {
        child_id: parseInt(childId),
        content: content
      });
      showToast('反馈已发送给家长');
      document.getElementById('feedbackContent').value = '';
      document.getElementById('feedbackChild').value = '';
      loadWorkbench();
    } catch (e) {
      showToast('发送失败: ' + e.message, 'error');
    }
  }

  document.addEventListener('DOMContentLoaded', loadWorkbench);
  document.addEventListener('DOMContentLoaded', function() {
    document.addEventListener('click', function(e) {
      var target = e.target.closest('[data-action]');
      if (!target) return;
      var action = target.getAttribute('data-action');
      if (action === 'submit-feedback') {
        submitFeedback();
      }
    });
  });

  window.teacherWorkbenchPage = { loadWorkbench: loadWorkbench, submitFeedback: submitFeedback };
})();
