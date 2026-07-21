(function() {
  'use strict';

  var allConfigs = {};
  var _roles = [];
  var _teachers = [];

  document.addEventListener('DOMContentLoaded', function() {
    loadConfigs();
    loadAdmins();
    loadRoles();
  });

  async function loadRoles() {
    try {
      var data = await api.get('/admin/api/roles');
      _roles = data.items || [];
      var sel = document.getElementById('adminRoleSelect');
      sel.innerHTML = _roles.map(function(r) {
        return '<option value="' + r.id + '">' + escapeHtml(r.name) + '</option>';
      }).join('');
    } catch (e) {
      // fallback to static options
    }
  }

  async function loadTeachers() {
    try {
      var data = await api.get('/admin/api/teachers?page_size=200');
      _teachers = data.items || [];
      var sel = document.getElementById('teacherSelect');
      sel.innerHTML = '<option value="">请选择教师</option>' +
        _teachers.map(function(t) {
          return '<option value="' + t.id + '">' + escapeHtml(t.name) + '</option>';
        }).join('');
    } catch (e) {
      // silent
    }
  }

  function onRoleChange(sel) {
    var roleId = parseInt(sel.value);
    var role = _roles.find(function(r) { return r.id === roleId; });
    var group = document.getElementById('teacherSelectGroup');
    if (role && role.code === 'teacher') {
      group.style.display = '';
    } else {
      group.style.display = 'none';
    }
  }

  async function loadConfigs() {
    try {
      var data = await api.get('/admin/api/config');
      allConfigs = data || {};
      Object.entries(allConfigs).forEach(function(entry) {
        var key = entry[0], val = entry[1];
        var el = document.getElementById('cfg' + key.split('_').map(function(w) { return w.charAt(0).toUpperCase() + w.slice(1); }).join(''));
        if (el && val.value != null) el.value = val.value;
      });
    } catch (err) {
      showToast('加载配置失败', 'error');
    }
  }

  async function loadAdmins() {
    try {
      var data = await api.get('/admin/api/admins');
      var admins = data.items || [];
      if (!admins.length) {
        document.getElementById('adminBody').innerHTML = '<tr><td colspan="5" class="text-center p-20 text-muted">暂无管理员</td></tr>';
        return;
      }
      document.getElementById('adminBody').innerHTML = admins.map(function(a) {
        var badge = a.role === 0 ? 'role-super' : 'role-editor';
        return '<tr>' +
          '<td class="text-base fw-500">' + escapeHtml(a.name || a.username || '--') + '</td>' +
          '<td class="text-sm font-mono">' + escapeHtml(a.phone || '--') + '</td>' +
          '<td><span class="role-badge ' + badge + '">' + escapeHtml(a.role_name || '--') + '</span></td>' +
          '<td>' + (a.last_login ? formatDateTime(a.last_login) : '--') + '</td>' +
          '<td>' +
            '<button class="action-btn-edit" data-perm="admin.edit" onclick="editAdmin(' + a.id + ')">编辑</button>' +
            '<button class="action-btn-danger" data-perm="admin.delete" onclick="deleteAdmin(' + a.id + ', \'' + jsEscape(a.name || a.username) + '\')">删除</button>' +
          '</td>' +
        '</tr>';
      }).join('');
      reapplyPermissions();
    } catch (e) {
      // silent
    }
  }

  async function editAdmin(id) {
    try {
      var data = await api.get('/admin/api/admins');
      var admins = data.items || [];
      var admin = admins.find(function(a) { return a.id === id; });
      if (!admin) {
        showToast('管理员不存在', 'error');
        return;
      }
      document.getElementById('adminEditId').value = id;
      document.querySelector('#adminModal .modal-header h2').textContent = '编辑管理员';
      document.getElementById('adminSubmitBtn').textContent = '保存修改';
      var form = document.getElementById('adminForm');
      form.elements['username'].value = admin.username || '';
      form.elements['username'].disabled = true;
      form.elements['name'].value = admin.name || '';
      form.elements['password'].value = '';
      form.elements['admin_role_id'].value = admin.admin_role_id || '';
      await loadTeachers();
      if (admin.teacher_id) {
        form.elements['teacher_id'].value = admin.teacher_id;
      }
      onRoleChange(document.getElementById('adminRoleSelect'));
      showModal('adminModal');
    } catch (err) {
      showToast('加载管理员信息失败', 'error');
    }
  }

  function openAddAdminModal() {
    document.getElementById('adminEditId').value = '';
    document.querySelector('#adminModal .modal-header h2').textContent = '添加管理员';
    document.getElementById('adminSubmitBtn').textContent = '保存';
    var form = document.getElementById('adminForm');
    form.reset();
    form.elements['username'].disabled = false;
    document.getElementById('adminPassword').required = true;
    document.getElementById('teacherSelectGroup').style.display = 'none';
    loadTeachers();
    showModal('adminModal');
  }

  function closeAdminModal() {
    closeModal('adminModal');
    document.getElementById('adminPassword').required = true;
  }

  async function submitAdmin(e) {
    e.preventDefault();
    var form = document.getElementById('adminForm');
    var fd = new FormData(form);
    var body = {};
    for (var [k, v] of fd.entries()) {
      if (k === 'adminEditId') continue;
      if (v === '') continue;
      if (k === 'admin_role_id') {
        body[k] = Number(v);
      } else if (k === 'teacher_id') {
        body[k] = Number(v);
      } else if (k === 'role') {
        body[k] = Number(v);
      } else {
        body[k] = v;
      }
    }
    var editId = document.getElementById('adminEditId').value;
    try {
      if (editId) {
        await api.put('/admin/api/admins/' + editId, body);
        showToast('管理员更新成功');
      } else {
        await api.post('/admin/api/admins', body);
        showToast('管理员添加成功');
      }
      closeAdminModal();
      loadAdmins();
    } catch (err) {
      showToast(err.message || '操作失败', 'error');
    }
  }

  async function deleteAdmin(id, name) {
    showConfirm('删除管理员', '确定删除管理员"' + name + '"？此操作不可撤销。', async function() {
      try {
        await api.del('/admin/api/admins/' + id);
        showToast('管理员已删除');
        loadAdmins();
      } catch (err) {
        showToast(err.message || '删除失败', 'error');
      }
    });
  }

  async function saveAllSettings() {
    var keys = [
      { key: 'site_name', el: 'siteName' },
      { key: 'contact_phone', el: 'contactPhone' },
      { key: 'price_parent_course', el: 'cfgParentCoursePrice' },
      { key: 'price_observation', el: 'cfgObservationPrice' },
      { key: 'price_official_member', el: 'cfgOfficialPrice' },
      { key: 'price_quarterly', el: 'cfgQuarterlyPrice' },
      { key: 'price_semi_annual', el: 'cfgSemiAnnualPrice' },
      { key: 'deposit_amount', el: 'cfgDeposit' },
      { key: 'multi_child_discount', el: 'cfgMultiChild' },
      { key: 'borrow_limit', el: 'cfgBorrowLimit' },
      { key: 'borrow_period_days', el: 'cfgBorrowPeriod' },
      { key: 'lost_book_fine_multiplier', el: 'cfgLostPenalty' },
      { key: 'observation_remind_days', el: 'cfgMemberRemind' },
      { key: 'borrow_due_remind_days', el: 'cfgBorrowRemind' },
    ];
    var saved = 0, failed = 0;
    for (var i = 0; i < keys.length; i++) {
      var el = document.getElementById(keys[i].el);
      if (!el) continue;
      try {
        await api.put('/admin/api/config/' + encodeURIComponent(keys[i].key), { value: el.value });
        saved++;
      } catch (e) { failed++; }
    }
    showToast('保存完成：成功 ' + saved + ' 项' + (failed ? '，失败 ' + failed + ' 项' : ''));
  }

  function escapeHtml(str) {
    if (!str) return '';
    var div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  window.settingsPage = { allConfigs, _roles, _teachers, loadRoles, loadTeachers, onRoleChange, loadConfigs, loadAdmins, editAdmin, openAddAdminModal, closeAdminModal, submitAdmin, deleteAdmin, saveAllSettings };
  for (var k in window.settingsPage) window[k] = window.settingsPage[k];
})();
