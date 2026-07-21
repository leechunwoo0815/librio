(function() {
  'use strict';

document.addEventListener('DOMContentLoaded', function() {
  loadProfile();
  loadRecentLogs();
});

async function loadProfile() {
  try {
    // 从 token 中获取当前管理员 ID
    const token = localStorage.getItem('mw_admin_token');
    if (!token) return;
    const payload = JSON.parse(atob(token.split('.')[1]));
    const adminId = payload.sub;

    // 获取当前管理员信息
    const admin = await api.get('/admin/api/admins/' + adminId);
    if (admin) {
      document.getElementById('adminAvatar').textContent = (admin.name || admin.username || 'A').charAt(0).toUpperCase();
      document.getElementById('adminName').textContent = admin.name || admin.username || '-';
      document.getElementById('adminRole').textContent = admin.role_name || (admin.role === 0 ? '超级管理员' : '员工');
      document.getElementById('adminUsername').textContent = admin.username || '-';
      document.getElementById('adminPhone').textContent = admin.phone || '-';
      document.getElementById('adminLastLogin').textContent = admin.last_login ? formatDateTime(admin.last_login) : '-';
      document.getElementById('adminCreateTime').textContent = admin.create_time ? formatDateTime(admin.create_time) : '-';
    }
  } catch (err) {
    console.error('加载个人信息失败', err);
  }
}

async function loadRecentLogs() {
  try {
    const data = await api.get('/admin/api/operation-logs?page=1&page_size=5');
    const logs = data.items || [];
    if (logs.length === 0) {
      document.getElementById('recentLogs').innerHTML = '<p>暂无操作记录</p>';
      return;
    }
    let html = '<div class="flex-col gap-12">';
    logs.forEach(function(log) {
      html += '<div class="log-item">';
      html += '<div><strong>' + escapeHtml(log.module || '-') + '</strong> - ' + escapeHtml(log.action || '-') + '</div>';
      html += '<div class="text-muted text-sm">' + (log.create_time ? formatDateTime(log.create_time) : '-') + '</div>';
      html += '</div>';
    });
    html += '</div>';
    document.getElementById('recentLogs').innerHTML = html;
  } catch (err) {
    document.getElementById('recentLogs').innerHTML = '<p class="text-error">加载失败</p>';
  }
}

async function changePassword(e) {
  e.preventDefault();
  const form = document.getElementById('passwordForm');
  const fd = new FormData(form);
  const oldPassword = fd.get('old_password');
  const newPassword = fd.get('new_password');
  const confirmPassword = fd.get('confirm_password');

  if (newPassword !== confirmPassword) {
    showToast('两次输入的密码不一致', 'error');
    return;
  }

  try {
    // 从 token 中获取当前管理员 ID
    const token = localStorage.getItem('mw_admin_token');
    if (!token) return;
    const payload = JSON.parse(atob(token.split('.')[1]));
    const adminId = payload.sub;

    await api.put('/admin/api/admins/' + adminId + '/password', { old_password: oldPassword, new_password: newPassword });
    showToast('密码修改成功');
    form.reset();
  } catch (err) {
    showToast('密码修改失败: ' + err.message, 'error');
  }
}

function formatDateTime(isoStr) {
  if (!isoStr) return '-';
  const d = new Date(isoStr);
  return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0') + ' ' + String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0');
}

function escapeHtml(str) {
  if (!str) return '';
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

  window.profilePage = { loadProfile, loadRecentLogs, changePassword };
  for (var k in window.profilePage) window[k] = window.profilePage[k];
})();
