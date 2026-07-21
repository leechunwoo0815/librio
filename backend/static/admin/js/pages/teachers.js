(function() {
  'use strict';

  const teacherGrid = document.getElementById('teacherGrid');
  const searchInput = document.getElementById('searchInput');
  const venueFilter = document.getElementById('venueFilter');
  const statusFilter = document.getElementById('statusFilter');

  document.addEventListener('DOMContentLoaded', () => {
    loadTeachers();
    loadVenues();
    searchInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') loadTeachers();
    });
    venueFilter.addEventListener('change', () => loadTeachers());
    statusFilter.addEventListener('change', () => loadTeachers());
  });

  async function loadVenues() {
    try {
      const result = await api.get('/admin/api/venues');
      const list = result.items || [];
      const venueSel = venueFilter;
      const modalSel = document.querySelector('#addForm select[name="venue_id"]');
      list.forEach(v => {
        const o1 = document.createElement('option');
        o1.value = v.id;
        o1.textContent = v.name;
        venueSel.appendChild(o1);
        const o2 = document.createElement('option');
        o2.value = v.id;
        o2.textContent = v.name;
        modalSel.appendChild(o2);
      });
    } catch (err) {
      /* venues load failure is non-blocking */
    }
  }

  async function loadTeachers() {
    try {
      let url = '/admin/api/teachers';
      const params = [];
      const kw = searchInput.value.trim();
      if (kw) params.push('keyword=' + encodeURIComponent(kw));
      const venue = venueFilter.value;
      if (venue) params.push('venue_id=' + venue);
      if (params.length) url += '?' + params.join('&');
      const data = await api.get(url);
      const teachers = data.items || data || [];
      renderTeachers(teachers);
    } catch (err) {
      showToast(err.message || '加载老师列表失败', 'error');
      teacherGrid.innerHTML = '<div class="text-center text-error p-40 grid-full">加载失败</div>';
    }
  }

  function getAvatarClass(index) {
    return 't' + ((index % 6) + 1);
  }

  function getInitial(name) {
    if (!name) return '?';
    return name.charAt(0).toUpperCase();
  }

  function getVenueName(teacher) {
    if (teacher.venue_name != null) return teacher.venue_name;
    return teacher.venue_id || '';
  }

  function getStatusInfo(teacher) {
    const status = teacher.status || 'online';
    if (status === 'online') return { cls: 'badge-online', text: '在线' };
    if (status === 'offline') return { cls: 'badge-offline', text: '离线' };
    if (status === 'leave') return { cls: 'badge-leave', text: '休假中' };
    return { cls: 'badge-online', text: '在线' };
  }

  function renderTeachers(teachers) {
    if (!teachers.length) {
      teacherGrid.innerHTML = '<div class="text-center text-muted p-40 grid-full">暂无老师数据</div>';
      return;
    }
    teacherGrid.innerHTML = teachers.map((t, i) => {
      const st = getStatusInfo(t);
      const venue = getVenueName(t);
      const role = t.title || t.expertise || '阅读顾问';
      const expertise = t.expertise || '';
      const tags = expertise ? expertise.split(/[,，、]/).filter(Boolean) : [];
      return `
        <div class="teacher-card">
          <div class="teacher-header">
            <div class="teacher-avatar ${getAvatarClass(i)}">${escapeHtml(getInitial(t.name))}</div>
            <div class="teacher-meta">
              <div class="teacher-name">${escapeHtml(t.name || '-')}</div>
              <div class="teacher-role">${escapeHtml(venue)}${venue ? ' · ' : ''}${escapeHtml(role)}</div>
            </div>
            <span class="teacher-status-badge ${st.cls}">${st.text}</span>
          </div>
          <div class="teacher-stats">
            <div class="tstat"><div class="tstat-val">${t.student_count != null ? t.student_count : 0}</div><div class="tstat-label">服务学员</div></div>
            <div class="tstat"><div class="tstat-val">${t.rating != null ? t.rating : '--'}</div><div class="tstat-label">评分</div></div>
            <div class="tstat"><div class="tstat-val">${t.monthly_hours != null ? t.monthly_hours : 0}</div><div class="tstat-label">本月课时</div></div>
          </div>
          <div class="teacher-tags">
            ${tags.map(tag => '<span class="tag">' + escapeHtml(tag.trim()) + '</span>').join('')}
          </div>
          <div class="teacher-admin-row" style="margin-top:8px;padding-top:8px;border-top:1px solid var(--border);font-size:13px;display:flex;align-items:center;justify-content:space-between;">
            <span>管理员：${t.admin_role_name ? escapeHtml(t.admin_role_name) : '<span class="text-muted">未创建</span>'}</span>
            <button class="action-btn btn-sm" onclick="openAdminAccountModal(${t.id}, ${t.admin_id || 0}, '${jsEscape(t.phone || '')}')">${t.admin_id ? '编辑' : '创建'}</button>
          </div>
          <div class="teacher-actions">
            <button class="action-btn" onclick="editTeacher(${t.id}, '${jsEscape(t.name || '')}', '${jsEscape(t.english_name || '')}', '${jsEscape(t.phone || '')}', ${t.venue_id || 0}, '${jsEscape(t.title || '')}', '${jsEscape(t.introduction || '')}', '${jsEscape(t.expertise || '')}', '${jsEscape(t.status || 'online')}')">编辑</button>
            <button class="action-btn" onclick="viewSchedule(${t.id}, '${jsEscape(t.name || '')}')">课表</button>
            <button class="action-btn" onclick="viewStudents(${t.id}, '${jsEscape(t.name || '')}')">学员</button>
            <button class="action-btn action-btn-danger" onclick="deleteTeacher(${t.id}, '${jsEscape(t.name || '')}')">删除</button>
          </div>
        </div>`;
    }).join('');
  }

  function openAddModal() {
    document.getElementById('editId').value = '';
    document.querySelector('#addModal h2').textContent = '添加老师';
    document.getElementById('submitBtn').textContent = '确认添加';
    document.getElementById('addForm').reset();
    showModal('addModal');
  }

  function closeAddModal() {
    closeModal('addModal');
  }

  async function submitTeacher(e) {
    e.preventDefault();
    const form = document.getElementById('addForm');
    const fd = new FormData(form);
    const body = {};
    for (const [k, v] of fd.entries()) {
      if (k === 'editId') continue;
      if (v === '') continue;
      if (k === 'venue_id') {
        body[k] = Number(v);
      } else {
        body[k] = v;
      }
    }
    const editId = document.getElementById('editId').value;
    try {
      if (editId) {
        await api.put('/admin/api/teachers/' + editId, body);
        showToast('老师更新成功');
      } else {
        await api.post('/admin/api/teachers', body);
        showToast('老师添加成功');
      }
      closeAddModal();
      loadTeachers();
    } catch (err) {
      showToast(err.message || '操作失败', 'error');
    }
  }

  function editTeacher(id, name, englishName, phone, venueId, title, introduction, expertise, status) {
    document.getElementById('editId').value = id;
    document.querySelector('#addModal h2').textContent = '编辑老师';
    document.getElementById('submitBtn').textContent = '保存修改';
    const form = document.getElementById('addForm');
    form.elements['name'].value = name;
    form.elements['english_name'].value = englishName;
    form.elements['phone'].value = phone;
    form.elements['venue_id'].value = venueId;
    form.elements['title'].value = title || '';
    form.elements['introduction'].value = introduction;
    form.elements['expertise'].value = expertise;
    form.elements['status'].value = status || 'online';
    showModal('addModal');
  }

  async function deleteTeacher(id, name) {
    showConfirm('删除老师', '确定删除老师"' + name + '"？此操作不可撤销。', async function() {
      try {
        await api.del('/admin/api/teachers/' + id);
        showToast('老师已删除');
        loadTeachers();
      } catch (err) {
        showToast(err.message || '删除失败', 'error');
      }
    });
  }

  async function viewSchedule(teacherId, teacherName) {
    try {
      const data = await api.get('/admin/api/teachers/' + teacherId + '/schedule');
      const schedules = data || [];
      const weekdays = ['', '周一', '周二', '周三', '周四', '周五', '周六', '周日'];
      let html = '<div class="p-20">';
      html += '<div class="flex-between mb-16">';
      html += '<h3 class="m-0">' + escapeHtml(teacherName) + ' 的课表</h3>';
      html += '<button class="btn-primary btn-sm" onclick="addSchedulePrompt(' + teacherId + ', \'' + jsEscape(teacherName) + '\')">+ 添加排班</button>';
      html += '</div>';
      if (schedules.length === 0) {
        html += '<p class="text-muted text-center p-20">暂无排班</p>';
      } else {
        html += '<table class="schedule-table">';
        html += '<thead><tr><th>星期</th><th>开始时间</th><th>结束时间</th><th>操作</th></tr></thead>';
        html += '<tbody>';
        schedules.forEach(function(s) {
          html += '<tr><td>' + (weekdays[s.weekday] || s.weekday) + '</td>';
          html += '<td>' + escapeHtml(s.start_time || '-') + '</td>';
          html += '<td>' + escapeHtml(s.end_time || '-') + '</td>';
          html += '<td><button class="action-btn action-btn-danger btn-sm" onclick="deleteScheduleItem(' + s.id + ', ' + teacherId + ', \'' + jsEscape(teacherName) + '\')">删除</button></td></tr>';
        });
        html += '</tbody></table>';
      }
      html += '</div>';
      showConfirm('课表 - ' + escapeHtml(teacherName), html, null, '关闭');
    } catch (err) {
      showToast('加载课表失败: ' + err.message, 'error');
    }
  }

  var schedPromptData = { teacherId: null, teacherName: '' };

  function showConfirmModal(title, msg, onConfirm) {
    document.querySelector('#confirmScheduleModal h2').textContent = title;
    document.getElementById('confirmScheduleMsg').textContent = msg;
    document.getElementById('confirmScheduleBtn').onclick = function() {
      closeModal('confirmScheduleModal');
      onConfirm();
    };
    showModal('confirmScheduleModal');
  }

  function addSchedulePrompt(teacherId, teacherName) {
    schedPromptData = { teacherId: teacherId, teacherName: teacherName };
    document.getElementById('schedWeekday').value = '';
    document.getElementById('schedStart').value = '';
    document.getElementById('schedEnd').value = '';
    showModal('schedulePromptModal');
  }

  function confirmAddSchedule() {
    var data = schedPromptData;
    if (!data.teacherId) return;
    var weekday = document.getElementById('schedWeekday').value.trim();
    var startTime = document.getElementById('schedStart').value.trim();
    var endTime = document.getElementById('schedEnd').value.trim();
    if (!weekday) { showToast('请输入星期', 'error'); return; }
    if (!startTime) { showToast('请输入开始时间', 'error'); return; }
    if (!endTime) { showToast('请输入结束时间', 'error'); return; }
    closeModal('schedulePromptModal');
    api.post('/admin/api/teachers/schedule', {
      teacher_id: data.teacherId,
      weekday: parseInt(weekday, 10),
      start_time: startTime,
      end_time: endTime,
    }).then(function() {
      showToast('排班添加成功');
      viewSchedule(data.teacherId, data.teacherName);
    }).catch(function(err) {
      showToast('添加排班失败: ' + (err.message || ''), 'error');
    });
  }

  async function deleteScheduleItem(scheduleId, teacherId, teacherName) {
    showConfirmModal('删除排班', '确定删除这条排班？', async function() {
      try {
        await api.del('/admin/api/teachers/schedule/' + scheduleId);
        showToast('排班已删除');
        viewSchedule(teacherId, teacherName);
      } catch (err) {
        showToast('删除排班失败: ' + (err.message || ''), 'error');
      }
    });
  }

  async function viewStudents(teacherId, teacherName) {
    try {
      const children = await api.get('/admin/api/teachers/' + teacherId + '/children');
      let html = '<div class="p-20">';
      html += '<h3 class="mb-16">' + escapeHtml(teacherName) + ' 负责的孩子</h3>';
      if (!children || children.length === 0) {
        html += '<p class="text-muted text-center p-20">暂无学员</p>';
      } else {
        html += '<table class="schedule-table"><thead><tr><th>姓名</th><th>年龄</th><th>状态</th></tr></thead><tbody>';
        children.forEach(function(c) {
          html += '<tr><td><span class="action-link" onclick="showChildDetail(' + c.id + ')">' + escapeHtml(c.name || '-') + '</span></td>';
          html += '<td>' + (c.age != null ? c.age + ' 岁' : '-') + '</td>';
          html += '<td>' + (c.status != null ? c.status : '-') + '</td></tr>';
        });
        html += '</tbody></table>';
      }
      html += '</div>';
      showConfirm('学员 - ' + escapeHtml(teacherName), html, null, '关闭');
    } catch (err) {
      showToast('加载学员失败: ' + (err.message || ''), 'error');
    }
  }

  async function showChildDetail(childId) {
    try {
      const d = await api.get('/admin/api/children/' + childId);
      const statusMap = {0:'体验用户',1:'观察期',2:'正式会员',3:'已过期',4:'已退出'};
      let html = '<div class="p-20">';
      html += '<h3 class="mb-16">' + escapeHtml(d.child.name) + '</h3>';
      html += '<div class="detail-grid text-base mb-16">';
      html += '<div><span class="text-muted">英文名：</span>' + escapeHtml(d.child.english_name || '-') + '</div>';
      html += '<div><span class="text-muted">年龄：</span>' + (d.child.age != null ? d.child.age + ' 岁' : '-') + '</div>';
      html += '<div><span class="text-muted">状态：</span>' + (statusMap[d.child.status] || d.child.status) + '</div>';
      html += '<div><span class="text-muted">AR等级：</span>' + (d.child.ar_level != null ? d.child.ar_level : '-') + '</div>';
      html += '<div><span class="text-muted">家长：</span>' + escapeHtml(d.parent.parent_name || '-') + '</div>';
      html += '<div><span class="text-muted">手机号：</span>' + escapeHtml(d.parent.phone || '-') + '</div>';
      html += '</div>';
      html += '<div class="flex gap-20 text-base">';
      html += '<div>总借阅：<strong>' + d.borrow_stats.total + '</strong></div>';
      html += '<div>当前借阅：<strong class="text-accent">' + d.borrow_stats.current + '</strong></div>';
      html += '<div>逾期：<strong class="text-error">' + d.borrow_stats.overdue + '</strong></div>';
      html += '</div>';
      html += '</div>';
      showConfirm('孩子详情', html, null, '关闭');
    } catch (err) {
      showToast('加载孩子详情失败: ' + (err.message || ''), 'error');
    }
  }

  async function openAdminAccountModal(teacherId, adminId, phone) {
    document.getElementById('adminAccountTeacherId').value = teacherId;
    document.getElementById('adminAccountAdminId').value = adminId;
    document.querySelector('#adminAccountModal h2').textContent = adminId ? '编辑管理员账号' : '创建管理员账号';
    document.getElementById('adminAccountSubmitBtn').textContent = '保存';

    var form = document.getElementById('adminAccountForm');
    form.reset();
    if (adminId) {
      document.getElementById('adminAccountPassword').required = false;
      document.getElementById('adminAccountPwdGroup').style.display = '';
    } else {
      document.getElementById('adminAccountPassword').required = true;
      document.getElementById('adminAccountPwdGroup').style.display = '';
    }

    var roleSel = document.getElementById('adminAccountRole');
    roleSel.innerHTML = '<option value="">加载中...</option>';
    try {
      var roles = await api.get('/admin/api/roles');
      roleSel.innerHTML = '<option value="">请选择</option>' +
        (roles.items || []).filter(function(r) { return r.code !== 'super_admin'; }).map(function(r) {
          return '<option value="' + r.id + '">' + escapeHtml(r.name) + '</option>';
        }).join('');
    } catch (e) {
      roleSel.innerHTML = '<option value="">请选择</option>';
    }

    if (adminId) {
      try {
        var admins = await api.get('/admin/api/admins');
        var admin = (admins.items || []).find(function(a) { return a.id === adminId; });
        if (admin) {
          document.getElementById('adminAccountUsername').value = admin.username || '';
          document.getElementById('adminAccountUsername').disabled = true;
          if (admin.admin_role_id) roleSel.value = admin.admin_role_id;
        }
      } catch (e) {}
    } else {
      document.getElementById('adminAccountUsername').value = phone || '';
      document.getElementById('adminAccountUsername').disabled = false;
    }

    showModal('adminAccountModal');
  }

  async function submitAdminAccount(e) {
    e.preventDefault();
    var teacherId = document.getElementById('adminAccountTeacherId').value;
    var adminId = document.getElementById('adminAccountAdminId').value;
    var username = document.getElementById('adminAccountUsername').value.trim();
    var roleId = parseInt(document.getElementById('adminAccountRole').value);
    var password = document.getElementById('adminAccountPassword').value;

    if (!username) { showToast('请输入用户名', 'error'); return; }
    if (!roleId) { showToast('请选择角色', 'error'); return; }

    try {
      if (adminId) {
        await api.put('/admin/api/admins/' + adminId, { admin_role_id: roleId, password: password || undefined });
        showToast('管理员账号已更新');
      } else {
        if (!password) { showToast('请输入密码', 'error'); return; }
        await api.post('/admin/api/admins', { username: username, password: password, admin_role_id: roleId, teacher_id: parseInt(teacherId) });
        showToast('管理员账号已创建');
      }
      closeModal('adminAccountModal');
      loadTeachers();
    } catch (err) {
      showToast(err.message || '操作失败', 'error');
    }
  }

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  window.teachersPage = { teacherGrid, searchInput, venueFilter, statusFilter, loadVenues, loadTeachers, getAvatarClass, getInitial, getVenueName, getStatusInfo, renderTeachers, openAddModal, closeAddModal, submitTeacher, editTeacher, deleteTeacher, viewSchedule, schedPromptData, showConfirmModal, addSchedulePrompt, confirmAddSchedule, deleteScheduleItem, viewStudents, showChildDetail, openAdminAccountModal, submitAdminAccount };
  for (var k in window.teachersPage) window[k] = window.teachersPage[k];

})();
