// backend/static/admin/js/pages/users.js
// 用户管理页面逻辑

(function() {
  'use strict';

  let currentPage = 1, totalPages = 1;
  let currentDetailUserId = null;
  var pageSize = 15;

  const roleBadgeClasses = {0:'role-trial',1:'role-obs',2:'role-member',3:'role-obs',4:'role-obs'};
  const roleNames = {0:'体验课',1:'观察期',2:'正式会员',3:'已过期',4:'已退出'};

  document.addEventListener('DOMContentLoaded', () => {
    loadUsers(1);
    const searchEl = document.getElementById('searchInput');
    if (searchEl) searchEl.addEventListener('keydown', e => {
      if (e.key === 'Enter') loadUsers(1);
    });
    document.getElementById('statusFilter').addEventListener('change', function() { loadUsers(1); });
    document.getElementById('editForm').addEventListener('submit', function(e) { submitUserEdit(e); });
    document.getElementById('addChildForm').addEventListener('submit', function(e) { submitAddChild(e); });
    document.getElementById('editChildForm').addEventListener('submit', function(e) { submitEditChild(e); });
    document.getElementById('createUserForm').addEventListener('submit', function(e) { submitCreateUser(e); });
    document.body.addEventListener('click', function(e) {
      var el = e.target.closest('[data-pg]');
      if (!el) return;
      e.preventDefault();
      var fn = window.usersPage[el.getAttribute('data-pg')];
      if (typeof fn === 'function') fn();
    });
    document.body.addEventListener('click', function(e) {
      var el = e.target.closest('[data-action]');
      if (!el) return;
      e.preventDefault();
      var action = el.getAttribute('data-action');
      if (action === 'edit-user') {
        window.usersPage.editUser(parseInt(el.dataset.userId), el.dataset.parentName, el.dataset.phone, parseInt(el.dataset.status), parseInt(el.dataset.childId));
      } else if (action === 'edit-child') {
        window.usersPage.showEditChild(parseInt(el.dataset.childId), el.dataset.name, el.dataset.englishName, parseInt(el.dataset.age), el.dataset.grade);
      }
    });
    populateAgeSelects();
    populateGradeSelects();
    loadVenues();
  });

  function populateAgeSelects() {
    var agesHtml = '<option value="">请选择</option>';
    for (var i = 3; i <= 15; i++) { agesHtml += '<option value="' + i + '">' + i + ' 岁</option>'; }
    ['addChildAge', 'editChildAge', 'createChildAge'].forEach(function(id) {
      var el = document.getElementById(id);
      if (el) el.innerHTML = agesHtml;
    });
  }

  function populateGradeSelects() {
    var grades = ['小班','中班','大班','一年级','二年级','三年级','四年级','五年级','六年级','初一','初二','初三'];
    var html = '<option value="">请选择</option>';
    grades.forEach(function(g) { html += '<option value="' + g + '">' + g + '</option>'; });
    ['addChildGrade', 'editChildGrade', 'createChildGrade'].forEach(function(id) {
      var el = document.getElementById(id);
      if (el) el.innerHTML = html;
    });
  }

  async function loadVenues() {
    try {
      var result = await api.get('/admin/api/venues');
      var list = result.items || [];
      var sel = document.getElementById('createChildVenue');
      if (!sel) return;
      list.forEach(function(v) {
        var o = document.createElement('option');
        o.value = v.id;
        o.textContent = v.name;
        sel.appendChild(o);
      });
    } catch (err) { /* non-blocking */ }
  }

  async function loadUsers(page) {
    currentPage = page;
    const keyword = document.getElementById('searchInput').value.trim();
    const statusVal = document.getElementById('statusFilter').value;
    var url = '/admin/api/users?page=' + page + '&page_size=' + pageSize;
    if (keyword) url += '&search=' + encodeURIComponent(keyword);
    if (statusVal !== '') url += '&child_status=' + statusVal;
    try {
      const data = await api.get(url);
      const users = data.items || [];
      renderUsers(users);
      try { pageUi(data.total, data.page, data.page_size); } catch(e) { /* ignore */ }
      var pages = Math.ceil(data.total / data.page_size);
      var countEl = document.getElementById('userCount');
      if (countEl) countEl.textContent = '共 ' + data.total + ' 条记录 · 第 ' + data.page + '/' + pages + ' 页';
    } catch (err) {
      var tbody = document.getElementById('usersTable');
      if (tbody) tbody.innerHTML = '<tr><td colspan="8" class="text-center p-24 text-muted">加载失败: ' + escapeHtml(err.message) + '</td></tr>';
    }
  }

  function renderUsers(users) {
    const tbody = document.getElementById('usersTable');
    if (!tbody) return;
    if (!users.length) {
      tbody.innerHTML = '<tr><td colspan="8" class="text-center p-24 text-muted">暂无用户数据</td></tr>';
      return;
    }
    tbody.innerHTML = users.map(u => {
      var children = u.children || [];
      var firstChild = children.length > 0 ? children[0] : null;
      var childName = firstChild ? escapeHtml(firstChild.name || '-') : '-';
      var age = firstChild ? (firstChild.age ? firstChild.age + ' 岁' : '-') : '-';
      var grade = firstChild ? escapeHtml(firstChild.grade || '-') : '-';
      var status = firstChild ? firstChild.status : 0;
      var childId = firstChild ? firstChild.id : null;
      var roleName = roleNames[status] || '未知';
      var roleClass = roleBadgeClasses[status] || 'role-trial';
      var childCell = childId
        ? '<span class="action-link" onclick="usersPage.showChildDetail(' + childId + ')">' + childName + '</span>'
        : childName;
      var venueCell = children.length > 0 && children[0].venue_name ? escapeHtml(children[0].venue_name) : '-';
      return '<tr>' +
        '<td>' + escapeHtml(u.parent_name || '-') + '</td>' +
        '<td class="font-mono">' + escapeHtml(u.phone || '-') + '</td>' +
        '<td>' + childCell + '</td>' +
        '<td>' + age + '</td>' +
        '<td>' + grade + '</td>' +
        '<td><span class="role-badge ' + roleClass + '">' + roleName + '</span></td>' +
        '<td>' + venueCell + '</td>' +
        '<td><div class="table-actions">' +
          '<span class="action-link" onclick="usersPage.showDetail(' + u.id + ')">查看</span>' +
          '<span class="action-link" data-action="edit-user" data-user-id="' + u.id + '" data-parent-name="' + escapeAttr(u.parent_name || '') + '" data-phone="' + escapeAttr(u.phone || '') + '" data-status="' + status + '" data-child-id="' + childId + '">编辑</span>' +
        '</div></td>' +
        '</tr>';
    }).join('');
  }

  function pageUi(total, page, pageSize) {
    totalPages = Math.ceil(total / pageSize);
    const el = document.getElementById('pageBtns');
    if (!el) return;
    var html = '<div class="flex-center gap-8"><span class="text-muted">共 ' + total + ' 条</span>' +
      '<span class="text-xs text-muted">每页</span><select class="page-size-select" onchange="usersPage.changePageSize(this.value)">' +
      '<option value="15"' + (pageSize===15?' selected':'') + '>15</option>' +
      '<option value="30"' + (pageSize===30?' selected':'') + '>30</option>' +
      '<option value="50"' + (pageSize===50?' selected':'') + '>50</option>' +
      '<option value="100"' + (pageSize===100?' selected':'') + '>100</option></select>' +
      '<span class="text-xs text-muted">条</span></div>';
    if (totalPages > 1) {
      var start = Math.max(1, page - 2);
      var end = Math.min(totalPages, page + 2);
      for (var i = start; i <= end; i++) {
        html += '<button class="page-btn' + (i===page?' active':'') + '" onclick="usersPage.loadUsers(' + i + ')">' + i + '</button>';
      }
    }
    el.innerHTML = html;
  }

  function loadFirstPage() { loadUsers(1); }

  function changePageSize(newSize) {
    pageSize = parseInt(newSize);
    loadUsers(1);
  }

  async function showDetail(userId) {
    currentDetailUserId = userId;
    const modal = document.getElementById('detailModal');
    const content = document.getElementById('detailContent');
    if (!modal || !content) return;
    modal.classList.add('show');
    content.innerHTML = '<div class="text-center p-24">加载中...</div>';
    try {
      const d = await api.get('/admin/api/users/' + userId);
      const statusMap = {0:'体验用户',1:'观察期',2:'正式会员',3:'已过期',4:'已退出'};
      const orderTypeMap = {1:'亲子课',2:'观察期',3:'正式会员'};
      const payStatusMap = {0:'待支付',1:'已支付',3:'退款中',4:'已退款',5:'已关闭'};

      let html = '';
      html += '<div class="mb-20"><h3 class="text-lg accent-left mb-10">基本信息</h3>';
      html += '<div class="user-detail-grid">';
      html += '<div><span class="text-muted">家长姓名：</span><strong>' + escapeHtml(d.user.parent_name) + '</strong></div>';
      html += '<div><span class="text-muted">手机号：</span>' + escapeHtml(d.user.phone || '-') + '</div>';
      html += '<div><span class="text-muted">注册时间：</span>' + formatDateTime(d.user.create_time) + '</div>';
      html += '<div><span class="text-muted">总消费：</span><strong class="text-success">' + formatMoney(d.summary.total_spent) + '</strong></div>';
      html += '</div></div>';

      html += '<div class="mb-20"><h3 class="text-lg accent-left mb-10">孩子列表（' + d.children.length + '）<button class="btn btn-primary btn-sm" onclick="usersPage.showAddChild(' + d.user.id + ')">+ 添加孩子</button></h3>';
      if (d.children.length === 0) {
        html += '<div class="text-muted p-16">暂无孩子信息</div>';
      } else {
        html += '<div class="table-wrap"><table><thead><tr class="text-muted"><th>姓名</th><th>年龄</th><th>年级</th><th>场馆</th><th>状态</th><th>AR等级</th><th>阅读分钟</th><th>读完本数</th><th>连续打卡</th><th>会员到期</th><th>操作</th></tr></thead><tbody>';
        d.children.forEach(c => {
          html += '<tr><td><strong>' + escapeHtml(c.name) + '</strong>' + (c.english_name ? ' ('+escapeHtml(c.english_name)+')' : '') + '</td><td>' + c.age + '</td><td>' + escapeHtml(c.grade||'-') + '</td><td>' + escapeHtml(c.venue_name||'-') + '</td><td>' + (statusMap[c.status]||c.status) + '</td><td>' + (c.ar_level||'-') + '</td><td>' + (c.total_reading_minutes||0) + '</td><td>' + (c.total_books_finished||0) + '</td><td>' + (c.current_streak_days||0) + '天</td><td>' + (c.member_expire_time?formatDate(c.member_expire_time):'-') + '</td><td><div class="table-actions">' +
            '<span class="action-link" data-action="edit-child" data-child-id="' + c.id + '" data-name="' + escapeAttr(c.name||'') + '" data-english-name="' + escapeAttr(c.english_name||'') + '" data-age="' + (c.age||0) + '" data-grade="' + escapeAttr(c.grade||'') + '">编辑</span>' +
            '<span class="action-link text-error" onclick="usersPage.deleteChild(' + c.id + ')">删除</span>' +
          '</div></td></tr>';
        });
        html += '</tbody></table></div>';
      }
      html += '</div>';

      html += '<div class="mb-20"><h3 class="text-lg accent-left mb-10">借阅统计</h3>';
      html += '<div class="flex gap-20">';
      html += '<div>总借阅：<strong>' + d.borrow_stats.total + '</strong></div>';
      html += '<div>当前借阅：<strong class="text-accent">' + d.borrow_stats.current + '</strong></div>';
      html += '<div>逾期：<strong class="text-error">' + d.borrow_stats.overdue + '</strong></div>';
      html += '</div></div>';

      html += '<div class="mb-20"><h3 class="text-lg accent-left mb-10">订单记录（' + d.orders.length + '）</h3>';
      if (d.orders.length === 0) {
        html += '<div class="text-muted p-16">暂无订单</div>';
      } else {
        html += '<div class="table-wrap"><table><thead><tr class="text-muted"><th>订单号</th><th>类型</th><th>金额</th><th>状态</th><th>创建时间</th></tr></thead><tbody>';
        d.orders.forEach(o => {
          html += '<tr><td class="text-sm font-mono">' + o.order_no + '</td><td>' + (orderTypeMap[o.type]||o.type) + '</td><td>' + formatMoney(o.amount) + '</td><td>' + (payStatusMap[o.pay_status]||o.pay_status) + '</td><td>' + formatDateTime(o.create_time) + '</td></tr>';
        });
        html += '</tbody></table></div>';
      }
      html += '</div>';

      if (d.refunds && d.refunds.length > 0) {
        html += '<div class="mb-20"><h3 class="text-lg accent-left mb-10">退款记录（' + d.refunds.length + '）</h3>';
        html += '<div class="table-wrap"><table><thead><tr class="text-muted"><th>ID</th><th>金额</th><th>状态</th><th>时间</th></tr></thead><tbody>';
        d.refunds.forEach(r => {
          html += '<tr><td>' + r.id + '</td><td>' + formatMoney(r.amount) + '</td><td>' + r.status + '</td><td>' + formatDateTime(r.create_time) + '</td></tr>';
        });
        html += '</tbody></table></div></div>';
      }

      content.innerHTML = html;
    } catch (e) {
      content.innerHTML = '<div class="text-center p-24 text-error">加载失败：' + escapeHtml(e.message) + '</div>';
    }
  }

  async function showChildDetail(childId) {
    const modal = document.getElementById('childModal');
    const content = document.getElementById('childContent');
    if (!modal || !content) return;
    modal.classList.add('show');
    content.innerHTML = '<div class="text-center p-24">加载中...</div>';
    try {
      const d = await api.get('/admin/api/children/' + childId);
      const statusMap = {0:'体验用户',1:'观察期',2:'正式会员',3:'已过期',4:'已退出'};
      let html = '<div class="child-detail-grid">';
      html += '<div><span class="text-muted">姓名：</span><strong>' + escapeHtml(d.child.name) + '</strong>' + (d.child.english_name ? ' (' + escapeHtml(d.child.english_name) + ')' : '') + '</div>';
      html += '<div><span class="text-muted">年龄：</span>' + (d.child.age || '-') + ' 岁</div>';
      html += '<div><span class="text-muted">状态：</span>' + (statusMap[d.child.status] || d.child.status) + '</div>';
      html += '<div><span class="text-muted">AR等级：</span>' + (d.child.ar_level || '-') + '</div>';
      html += '<div><span class="text-muted">家长：</span>' + escapeHtml(d.parent.parent_name || '-') + '</div>';
      html += '<div><span class="text-muted">手机号：</span>' + escapeHtml(d.parent.phone || '-') + '</div>';
      html += '</div>';
      html += '<div class="flex gap-20 mb-8">';
      html += '<div>总借阅：<strong>' + d.borrow_stats.total + '</strong></div>';
      html += '<div>当前借阅：<strong class="text-accent">' + d.borrow_stats.current + '</strong></div>';
      html += '<div>逾期：<strong class="text-error">' + d.borrow_stats.overdue + '</strong></div>';
      html += '</div>';
      content.innerHTML = html;
    } catch (e) {
      content.innerHTML = '<div class="text-center p-24 text-error">加载失败：' + escapeHtml(e.message) + '</div>';
    }
  }

  function closeChildModal() {
    var el = document.getElementById('childModal');
    if (el) el.classList.remove('show');
  }

  function editUser(userId, parentName, phone, childStatus, childId) {
    document.getElementById('editUserId').value = userId;
    document.getElementById('editParentName').value = parentName;
    document.getElementById('editPhone').value = phone;
    document.getElementById('editChildStatus').value = String(childStatus || 0);
    var el = document.getElementById('editModal');
    if (el) el.classList.add('show');
  }

  function closeEditModal() {
    var el = document.getElementById('editModal');
    if (el) el.classList.remove('show');
  }

  async function submitUserEdit(e) {
    e.preventDefault();
    var btn = e.target.querySelector('button[type="submit"]');
    if (btn && btn.disabled) return;
    if (btn) { btn.disabled = true; btn.textContent = '提交中...'; }
    const userId = document.getElementById('editUserId').value;
    const body = {
      parent_name: document.getElementById('editParentName').value.trim(),
      phone: document.getElementById('editPhone').value.trim(),
      child_status: parseInt(document.getElementById('editChildStatus').value, 10),
    };
    try {
      await api.put('/admin/api/users/' + userId, body);
      showToast('用户信息更新成功');
      closeEditModal();
      loadUsers(currentPage);
    } catch (err) {
      showToast(err.message || '更新失败', 'error');
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = '保存'; }
    }
  }

  async function exportUsers() {
    const keyword = document.getElementById('searchInput').value.trim();
    let url = '/admin/api/users/export' + (keyword ? '?search=' + encodeURIComponent(keyword) : '');
    try {
      const resp = await fetch(url, { headers: { 'Authorization': 'Bearer ' + (localStorage.getItem('mw_admin_token') || '') } });
      if (!resp.ok) throw new Error(resp.statusText);
      const blob = await resp.blob();
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = 'users.csv';
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(a.href);
    } catch (err) {
      showToast('导出失败: ' + err.message, 'error');
    }
  }

  function showAddChild(userId) {
    currentDetailUserId = userId;
    document.getElementById('addChildUserId').value = userId;
    document.getElementById('addChildName').value = '';
    document.getElementById('addChildEnglishName').value = '';
    document.getElementById('addChildAge').value = '';
    document.getElementById('addChildGrade').value = '';
    var el = document.getElementById('addChildModal');
    if (el) el.classList.add('show');
  }

  function closeAddChildModal() {
    var el = document.getElementById('addChildModal');
    if (el) el.classList.remove('show');
  }

  async function submitAddChild(e) {
    e.preventDefault();
    var btn = e.target.querySelector('button[type="submit"]');
    if (btn && btn.disabled) return;
    if (btn) { btn.disabled = true; btn.textContent = '提交中...'; }
    const userId = document.getElementById('addChildUserId').value;
    const body = {
      name: document.getElementById('addChildName').value.trim(),
      english_name: document.getElementById('addChildEnglishName').value.trim() || null,
      age: parseInt(document.getElementById('addChildAge').value, 10),
      grade: document.getElementById('addChildGrade').value.trim(),
    };
    try {
      await api.post('/admin/api/users/' + userId + '/children', body);
      showToast('孩子添加成功');
      closeAddChildModal();
      showDetail(parseInt(userId));
    } catch (err) {
      showToast(err.message || '添加失败', 'error');
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = '添加'; }
    }
  }

  function showEditChild(childId, name, englishName, age, grade) {
    document.getElementById('editChildId').value = childId;
    document.getElementById('editChildName').value = name;
    document.getElementById('editChildEnglishName').value = englishName;
    document.getElementById('editChildAge').value = age;
    document.getElementById('editChildGrade').value = grade;
    var el = document.getElementById('editChildModal');
    if (el) el.classList.add('show');
  }

  function closeEditChildModal() {
    var el = document.getElementById('editChildModal');
    if (el) el.classList.remove('show');
  }

  async function submitEditChild(e) {
    e.preventDefault();
    var btn = e.target.querySelector('button[type="submit"]');
    if (btn && btn.disabled) return;
    if (btn) { btn.disabled = true; btn.textContent = '提交中...'; }
    const childId = document.getElementById('editChildId').value;
    const body = {};
    const name = document.getElementById('editChildName').value.trim();
    const englishName = document.getElementById('editChildEnglishName').value.trim();
    const age = document.getElementById('editChildAge').value;
    const grade = document.getElementById('editChildGrade').value.trim();
    if (name) body.name = name;
    if (englishName) body.english_name = englishName;
    if (age) body.age = parseInt(age, 10);
    if (grade) body.grade = grade;
    try {
      await api.put('/admin/api/children/' + childId, body);
      showToast('孩子更新成功');
      closeEditChildModal();
      if (currentDetailUserId) showDetail(currentDetailUserId);
    } catch (err) {
      showToast(err.message || '更新失败', 'error');
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = '保存修改'; }
    }
  }

  async function deleteChild(childId) {
    showConfirm('删除孩子', '确定要删除该孩子吗？此操作不可撤销。', async function() {
      try {
        await api.del('/admin/api/children/' + childId);
        showToast('孩子已删除');
        if (currentDetailUserId) showDetail(currentDetailUserId);
      } catch (err) {
        showToast(err.message || '删除失败', 'error');
      }
    });
  }

  function openCreateUserModal() {
    var form = document.getElementById('createUserForm');
    if (form) form.reset();
    var el = document.getElementById('createUserModal');
    if (el) el.classList.add('show');
  }

  function closeCreateUserModal() {
    var el = document.getElementById('createUserModal');
    if (el) el.classList.remove('show');
  }

  async function submitCreateUser(event) {
    event.preventDefault();
    var btn = event.target.querySelector('button[type="submit"]');
    if (btn && btn.disabled) return;
    if (btn) { btn.disabled = true; btn.textContent = '提交中...'; }
    var body = {
      parent_name: document.getElementById('createParentName').value.trim(),
      phone: document.getElementById('createPhone').value.trim(),
      password: document.getElementById('createPassword').value.trim() || null,
    };
    var childName = document.getElementById('createChildName').value.trim();
    if (childName) {
      body.child_name = childName;
      body.child_age = parseInt(document.getElementById('createChildAge').value) || null;
      body.child_grade = document.getElementById('createChildGrade').value.trim() || null;
      body.venue_id = parseInt(document.getElementById('createChildVenue').value) || null;
    }
    try {
      var result = await api.post('/admin/api/users', body);
      var msg = '用户创建成功';
      if (result.default_password) msg += '，初始密码：' + result.default_password;
      showToast(msg);
      closeCreateUserModal();
      loadUsers(1);
    } catch (err) {
      showToast(err.message || '创建失败', 'error');
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = '创建用户'; }
    }
  }

  // ── exports ──
  window.usersPage = {
    loadUsers, loadFirstPage, renderUsers, pageUi, changePageSize,
    showDetail, showChildDetail, closeChildModal,
    editUser, closeEditModal, submitUserEdit, exportUsers,
    showAddChild, closeAddChildModal, submitAddChild,
    showEditChild, closeEditChildModal, submitEditChild, deleteChild,
    openCreateUserModal, closeCreateUserModal, submitCreateUser,
  };
})();
