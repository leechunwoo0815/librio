(function() {
  'use strict';

document.addEventListener('DOMContentLoaded', async () => {
  try {
    const data = await api.get('/admin/api/dashboard');
    if (data) {
      document.getElementById('s-users').textContent = (data.total_users || 0).toLocaleString();
      document.getElementById('s-children').textContent = (data.total_children || 0).toLocaleString();
      document.getElementById('s-orders').textContent = (data.total_orders || 0).toLocaleString();
      document.getElementById('s-revenue').textContent = formatMoney(data.total_revenue);
      document.getElementById('s-dau').textContent = (data.daily_active_users || 0).toLocaleString();
      document.getElementById('s-new-week').textContent = (data.new_users_this_week || 0).toLocaleString();
      document.getElementById('s-active-borrows').textContent = (data.active_borrows || 0).toLocaleString();
      document.getElementById('s-quiz-pass-rate').textContent = (data.quiz_pass_rate || 0).toFixed(1) + '%';
      document.getElementById('s-reading-time').textContent = (data.today_reading_minutes || 0).toLocaleString() + '分钟';
      document.getElementById('s-new-words').textContent = (data.today_new_words || 0).toLocaleString();
      document.getElementById('s-reading-count').textContent = (data.today_voice_count || 0).toLocaleString();
    }
  } catch (e) {
    console.error('Dashboard load failed:', e);
  }
});

  window.dashboardPage = {};
})();
