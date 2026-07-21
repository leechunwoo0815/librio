(function() {
  'use strict';

  var _currentRoleId = null;

  document.addEventListener('DOMContentLoaded', function() {
    loadRolesPage();
  });

  var _deleteRoleId = null;
  var _renameRoleId = null;

  async function loadRolesPage() {
    try {
      var data = await api.get('/admin/api/roles');
      var roles = data.items || [];
      var html = roles.map(function(r) {
        var canEdit = document.body.dataset.canEditRole === 'true';
        var actions = '';
        if (canEdit) {
          actions += '<button class="action-btn-edit" onclick="openPermModal(' + r.id + ')">编辑权限</button>';
          if (!r.is_system) {
            actions += '<button class="action-btn-edit" onclick="deleteRole(' + r.id + ', \'' + jsEscape(r.name) + '\')" style="color:var(--danger)">删除</button>';
          }
        }
        var renameIcon = canEdit ? '<span class="rename-icon" onclick="renameRole(' + r.id + ', \'' + jsEscape(r.name) + '\', \'' + jsEscape(r.description || '') + '\')" style="cursor:pointer;margin-left:6px;font-size:13px;color:var(--text-muted)">&#9998;</span>' : '';
        return '<div class="role-card">' +
          '<div class="role-card-info">' +
            '<div class="role-card-name">' + escapeHtml(r.name) + renameIcon + ' <span class="role-badge role-editor">' + escapeHtml(r.code) + '</span>' + (r.is_system ? ' <span class="system-badge">系统</span>' : '') + '</div>' +
            '<div class="role-card-meta">' + escapeHtml(r.description || '') + ' — 权限 ' + r.permission_count + ' 项</div>' +
          '</div>' +
          '<div class="role-card-actions">' +
            actions +
          '</div>' +
        '</div>';
      }).join('');
      document.getElementById('roleList').innerHTML = html || '<div class="text-center p-20 text-muted">暂无角色</div>';
    } catch (e) {
      document.getElementById('roleList').innerHTML = '<div class="text-center p-20 text-muted">加载失败</div>';
    }
  }

  async function openPermModal(roleId) {
    _currentRoleId = roleId;
    document.getElementById('permModalBody').innerHTML = '<div class="text-center p-20 text-muted">加载中...</div>';
    showModal('permModal');
    try {
      var data = await api.get('/admin/api/roles/' + roleId + '/permissions');
      var groups = data.groups || [];
      var html = '';
      groups.forEach(function(g) {
        var allChecked = g.permissions.every(function(p) { return p.is_assigned; });
        html += '<div class="perm-group">' +
          '<div class="perm-group-title">' + escapeHtml(g.group_name) + '</div>' +
          '<div class="select-all-row"><label><input type="checkbox" onchange="toggleGroup(this, \'' + jsEscape(g.group_name) + '\')" ' + (allChecked ? 'checked' : '') + ' /> 全选</label></div>' +
          '<div class="perm-grid" data-group="' + escapeHtml(g.group_name) + '">';
        g.permissions.forEach(function(p) {
          html += '<label><input type="checkbox" class="perm-cb" value="' + escapeHtml(p.code) + '" data-group="' + escapeHtml(g.group_name) + '" ' + (p.is_assigned ? 'checked' : '') + ' /> <span>' + escapeHtml(p.name) + '</span></label>';
        });
        html += '</div></div>';
      });
      document.getElementById('permModalBody').innerHTML = html;
    } catch (e) {
      document.getElementById('permModalBody').innerHTML = '<div class="text-center p-20 text-muted">加载权限失败</div>';
    }
  }

  function toggleGroup(el, groupName) {
    var checked = el.checked;
    document.querySelectorAll('.perm-cb[data-group="' + groupName + '"]').forEach(function(cb) {
      cb.checked = checked;
    });
  }

  async function savePermissions() {
    var codes = [];
    document.querySelectorAll('.perm-cb:checked').forEach(function(cb) {
      codes.push(cb.value);
    });
    var btn = document.getElementById('savePermBtn');
    btn.disabled = true;
    btn.textContent = '保存中...';
    try {
      await api.put('/admin/api/roles/' + _currentRoleId + '/permissions', { permission_codes: codes });
      showToast('权限更新成功');
      closeModal('permModal');
      loadRolesPage();
    } catch (err) {
      showToast(err.message || '保存失败', 'error');
    } finally {
      btn.disabled = false;
      btn.textContent = '保存权限';
    }
  }

  async function createRole() {
    document.getElementById('newRoleName').value = '';
    document.getElementById('newRoleCode').value = '';
    document.getElementById('newRoleTemplate').value = '';
    showModal('createRoleModal');
  }

  async function confirmCreateRole() {
    var name = document.getElementById('newRoleName').value.trim();
    var code = document.getElementById('newRoleCode').value.trim();
    var template = document.getElementById('newRoleTemplate').value;
    if (!name) { showToast('请输入角色名', 'error'); return; }
    if (!code) { showToast('请输入角色代码', 'error'); return; }
    if (!/^[a-z0-9_]+$/.test(code)) { showToast('角色代码仅支持小写字母、数字和下划线', 'error'); return; }
    var btn = document.getElementById('confirmCreateRoleBtn');
    btn.disabled = true; btn.textContent = '创建中...';
    try {
      var result = await api.post('/admin/api/roles', { code: code, name: name });
      var newRoleId = result.id;
      showToast('角色创建成功');
      closeModal('createRoleModal');
      if (template) {
        var templateRoleMap = { staff: 'staff', teacher: 'teacher' };
        var rolesResp = await api.get('/admin/api/roles');
        var allRoles = rolesResp.items || [];
        var templateRole = allRoles.find(function(r) { return r.code === templateRoleMap[template]; });
        if (templateRole) {
          var permResp = await api.get('/admin/api/roles/' + templateRole.id + '/permissions');
          var codes = [];
          (permResp.groups || []).forEach(function(g) {
            (g.permissions || []).forEach(function(p) {
              if (p.is_assigned) codes.push(p.code);
            });
          });
          await api.put('/admin/api/roles/' + newRoleId + '/permissions', { permission_codes: codes });
        }
      }
      loadRolesPage();
      openPermModal(newRoleId);
    } catch (err) {
      showToast(err.message || '创建失败', 'error');
    } finally {
      btn.disabled = false; btn.textContent = '创建';
    }
  }

  async function deleteRole(roleId, roleName) {
    _deleteRoleId = roleId;
    document.getElementById('deleteRoleConfirmText').textContent = '确定删除角色「' + roleName + '」？';
    showModal('deleteRoleModal');
  }

  async function confirmDeleteRole() {
    if (!_deleteRoleId) return;
    var btn = document.getElementById('confirmDeleteRoleBtn');
    btn.disabled = true; btn.textContent = '删除中...';
    try {
      await api.del('/admin/api/roles/' + _deleteRoleId);
      showToast('角色已删除');
      closeModal('deleteRoleModal');
      loadRolesPage();
    } catch (err) {
      showToast(err.message || '删除失败', 'error');
    } finally {
      btn.disabled = false; btn.textContent = '删除';
      _deleteRoleId = null;
    }
  }

  async function renameRole(roleId, currentName, currentDesc) {
    _renameRoleId = roleId;
    document.getElementById('renameRoleName').value = currentName || '';
    document.getElementById('renameRoleDesc').value = currentDesc || '';
    showModal('renameRoleModal');
  }

  async function confirmRenameRole() {
    if (!_renameRoleId) return;
    var name = document.getElementById('renameRoleName').value.trim();
    var desc = document.getElementById('renameRoleDesc').value.trim();
    if (!name) { showToast('请输入角色名', 'error'); return; }
    var btn = document.getElementById('confirmRenameRoleBtn');
    btn.disabled = true; btn.textContent = '保存中...';
    try {
      await api.put('/admin/api/roles/' + _renameRoleId, { name: name, description: desc });
      showToast('角色已更新');
      closeModal('renameRoleModal');
      loadRolesPage();
    } catch (err) {
      showToast(err.message || '更新失败', 'error');
    } finally {
      btn.disabled = false; btn.textContent = '保存';
      _renameRoleId = null;
    }
  }

  window.rolesPage = { _currentRoleId, loadRolesPage, openPermModal, toggleGroup, savePermissions, createRole, confirmCreateRole, deleteRole, confirmDeleteRole, renameRole, confirmRenameRole };
  for (var k in window.rolesPage) window[k] = window.rolesPage[k];
})();
