// backend/static/admin/js/pages/activities.js
// 活动管理页面逻辑

(function() {
  'use strict';

  const actTypes = {1:'读书交流',2:'讲座',3:'CityWalk',4:'郊游',5:'大会',6:'其他'};
  const actStatuses = {0:'草稿',1:'报名中',2:'报名截止',3:'进行中',4:'已结束',5:'已取消'};
  const statusBadgeClasses = {0:'status-draft',1:'status-open',2:'status-end',3:'status-open',4:'status-end',5:'status-end'};

  let currentSigninActivityId = null;

  function onFreeChange() {
    const isFree = document.getElementById('actFree').value;
    document.getElementById('priceGroup').classList.toggle('hidden', isFree !== '0');
  }

  function onTypeChange() {
    // 预留：不同类型可能有不同的表单字段
  }

  let currentPage = 1;
  const pageSize = 20;

  async function loadActivities(page) {
    currentPage = page || currentPage;
    try {
      const result = await api.get('/admin/api/activities?page=' + currentPage + '&page_size=' + pageSize);
      const activities = result.items || [];
      const total = result.total || 0;
      if (!activities.length) {
        if (currentPage > 1 && total > 0) {
          currentPage = 1;
          return loadActivities(1);
        }
        document.getElementById('actBody').innerHTML = '<tr><td colspan="6" style="text-align:center;padding:40px;color:var(--muted);">暂无活动，点击上方按钮创建</td></tr>';
        document.getElementById('pageInfo').textContent = '共 ' + total + ' 条记录';
        document.getElementById('pageBtns').innerHTML = '';
        return;
      }
      document.getElementById('pageInfo').textContent = '共 ' + total + ' 条记录';
      AdminPagination.render('#pageBtns', total, currentPage, pageSize, function(p) { loadActivities(p); });
      document.getElementById('actBody').innerHTML = activities.map(function(a) {
        const badgeClass = statusBadgeClasses[a.status] || 'status-draft';
        const statusName = actStatuses[a.status] || a.status;
        let timeStr = formatDateTime(a.start_time);
        if (a.end_time) timeStr += ' ~ ' + formatDateTime(a.end_time);
        const typeName = actTypes[a.type] || a.type;
        const priceStr = a.is_free ? '免费' : ('¥' + (a.price || 0));

        let actions = '';
        if (a.status === 0) { // 草稿
          actions += '<span class="action-link" onclick="window.activitiesPage.publishActivity(' + a.id + ')">发布</span> ';
          actions += '<span class="action-link" onclick="window.activitiesPage.editActivity(' + a.id + ')">编辑</span> ';
          actions += '<span class="action-link" style="color:var(--error)" onclick="window.activitiesPage.deleteActivity(' + a.id + ')">删除</span>';
        } else if (a.status === 1) { // 报名中
          actions += '<span class="action-link" onclick="window.activitiesPage.showSigninModal(' + a.id + ')">报名管理</span> ';
          actions += '<span class="action-link" onclick="window.activitiesPage.editActivity(' + a.id + ')">编辑</span> ';
          actions += '<span class="action-link" style="color:var(--error)" onclick="window.activitiesPage.cancelActivity(' + a.id + ')">取消</span>';
        } else if (a.status === 3) { // 进行中
          actions += '<span class="action-link" onclick="window.activitiesPage.showSigninModal(' + a.id + ')">签到</span> ';
          actions += '<span class="action-link" onclick="window.activitiesPage.finishActivity(' + a.id + ')">结束</span>';
        } else {
          actions += '<span class="action-link" onclick="window.activitiesPage.showSigninModal(' + a.id + ')">查看</span>';
        }

        return '<tr>' +
          '<td><strong>' + escapeHtml(a.title) + '</strong>' + (a.location ? '<br><span style="font-size:12px;color:var(--muted);">' + escapeHtml(a.location) + '</span>' : '') + '</td>' +
          '<td style="font-family:var(--font-mono);font-size:12px;">' + timeStr + '</td>' +
          '<td>' + typeName + ' · ' + priceStr + '</td>' +
          '<td>' + (a.current_participants||0) + ' / ' + (a.max_participants||'不限') + '</td>' +
          '<td><span class="status-badge ' + badgeClass + '">' + statusName + '</span></td>' +
          '<td><div style="display:flex;gap:8px;">' + actions + '</div></td>' +
          '</tr>';
      }).join('');
    } catch (e) {
      showToast('加载活动列表失败: ' + (e.message || ''), 'error');
      document.getElementById('actBody').innerHTML = '<tr><td colspan="6" style="text-align:center;padding:40px;color:var(--error);">加载失败</td></tr>';
    }
  }

  function showCreateModal() {
    document.querySelector('#createModal h2').textContent = '创建活动';
    document.getElementById('editActivityId').value = '';
    document.getElementById('submitBtn').textContent = '创建';
    document.getElementById('actTitle').value = '';
    document.getElementById('actType').value = '1';
    document.getElementById('actStart').value = '';
    document.getElementById('actEnd').value = '';
    document.getElementById('actVenue').value = '';
    document.getElementById('actMax').value = '30';
    document.getElementById('actFree').value = '1';
    document.getElementById('actPrice').value = '';
    document.getElementById('actDesc').value = '';
    document.getElementById('priceGroup').style.display = 'none';
    document.getElementById('createModal').classList.add('show');
  }

  function hideCreateModal() {
    document.getElementById('createModal').classList.remove('show');
  }

  async function editActivity(id) {
    try {
      const a = await api.get('/admin/api/activities/' + id);
      document.querySelector('#createModal h2').textContent = '编辑活动';
      document.getElementById('editActivityId').value = id;
      document.getElementById('submitBtn').textContent = '保存';
      document.getElementById('actTitle').value = a.title || '';
      document.getElementById('actType').value = a.type || 1;
      document.getElementById('actStart').value = a.start_time ? a.start_time.substring(0, 16) : '';
      document.getElementById('actEnd').value = a.end_time ? a.end_time.substring(0, 16) : '';
      document.getElementById('actVenue').value = a.location || '';
      document.getElementById('actMax').value = a.max_participants || 30;
      document.getElementById('actFree').value = a.is_free ? '1' : '0';
      document.getElementById('actPrice').value = a.price || '';
      document.getElementById('actDesc').value = a.description || '';
      document.getElementById('priceGroup').classList.toggle('hidden', a.is_free);
      document.getElementById('createModal').classList.add('show');
    } catch (e) { showToast('加载活动详情失败', 'error'); }
  }

  async function submitActivity() {
    const title = document.getElementById('actTitle').value.trim();
    if (!title) { showToast('请输入活动标题', 'warning'); return; }

    const body = {
      title: title,
      type: parseInt(document.getElementById('actType').value),
      start_time: document.getElementById('actStart').value || null,
      end_time: document.getElementById('actEnd').value || null,
      location: document.getElementById('actVenue').value || null,
      max_participants: parseInt(document.getElementById('actMax').value) || 30,
      is_free: parseInt(document.getElementById('actFree').value),
      price: document.getElementById('actFree').value === '0' ? parseFloat(document.getElementById('actPrice').value) || 0 : 0,
      description: document.getElementById('actDesc').value || null,
    };

    const editId = document.getElementById('editActivityId').value;
    try {
      if (editId) {
        await api.put('/admin/api/activities/' + editId, body);
        showToast('活动更新成功');
      } else {
        await api.post('/admin/api/activities', body);
        showToast('活动创建成功');
      }
      hideCreateModal();
      loadActivities();
    } catch (e) { showToast('操作失败: ' + e.message, 'error'); }
  }

  async function publishActivity(id) {
    showConfirm('发布活动', '确定将此活动发布为"报名中"状态？', async function() {
      try {
        await api.put('/admin/api/activities/' + id, { status: 1 });
        showToast('活动已发布');
        loadActivities();
      } catch (e) { showToast('发布失败: ' + e.message, 'error'); }
    });
  }

  async function cancelActivity(id) {
    showConfirm('取消活动', '确定取消此活动？已报名的用户将收到通知。', async function() {
      try {
        await api.put('/admin/api/activities/' + id + '/cancel');
        showToast('活动已取消');
        loadActivities();
      } catch (e) { showToast('取消失败: ' + e.message, 'error'); }
    });
  }

  async function finishActivity(id) {
    showConfirm('结束活动', '确定将此活动标记为已结束？', async function() {
      try {
        await api.put('/admin/api/activities/' + id, { status: 4 });
        showToast('活动已结束');
        loadActivities();
      } catch (e) { showToast('操作失败: ' + e.message, 'error'); }
    });
  }

  async function deleteActivity(id) {
    showConfirm('删除活动', '确定删除此活动？此操作不可撤销。', async function() {
      try {
        await api.del('/admin/api/activities/' + id);
        showToast('活动已删除');
        loadActivities();
      } catch (e) { showToast('删除失败: ' + e.message, 'error'); }
    });
  }

  async function showSigninModal(activityId) {
    currentSigninActivityId = activityId;
    document.getElementById('signinModal').style.display = 'flex';
    document.getElementById('signinCheckAll').checked = false;
    const listEl = document.getElementById('signinList');
    listEl.innerHTML = '<div style="text-align:center;color:var(--muted);padding:20px;">加载中...</div>';
    try {
      const data = await api.get('/admin/api/activities/' + activityId + '/enrollments');
      const enrollments = (data && data.items) ? data.items : (data || []);
      if (!enrollments.length) {
        listEl.innerHTML = '<div style="text-align:center;color:var(--muted);padding:20px;">暂无报名记录</div>';
        return;
      }
      listEl.innerHTML = enrollments.map(function(e) {
        return '<label style="display:flex;align-items:center;gap:10px;padding:8px 12px;border-bottom:1px solid var(--bg);cursor:pointer;">' +
          '<input type="checkbox" class="signin-check" value="' + e.child_id + '" ' + (e.checked_in ? 'disabled checked' : '') + ' />' +
          '<span style="font-weight:500;">' + escapeHtml(e.child_name || '未知') + '</span>' +
          '<span style="font-size:12px;color:var(--muted);">' + escapeHtml(e.english_name || '') + '</span>' +
          '<span style="font-size:12px;color:var(--muted);">' + escapeHtml(e.parent_name || '') + '</span>' +
          (e.checked_in ? '<span class="status-badge status-open" style="margin-left:auto;">已签到</span>' : '') +
          '</label>';
      }).join('');
    } catch (err) {
      listEl.innerHTML = '<div style="text-align:center;color:var(--error);padding:20px;">加载失败: ' + escapeHtml(err.message) + '</div>';
    }
  }

  function hideSigninModal() {
    document.getElementById('signinModal').style.display = 'none';
    currentSigninActivityId = null;
  }

  function toggleSigninAll() {
    const checked = document.getElementById('signinCheckAll').checked;
    document.querySelectorAll('.signin-check:not(:disabled)').forEach(function(cb) { cb.checked = checked; });
  }

  async function submitSignin() {
    const selected = [];
    document.querySelectorAll('.signin-check:checked:not(:disabled)').forEach(function(cb) { selected.push(parseInt(cb.value)); });
    if (!selected.length) { showToast('请至少选择一个未签到的孩子', 'warning'); return; }
    try {
      await api.post('/admin/api/activities/' + currentSigninActivityId + '/checkin', { child_ids: selected });
      showToast('签到成功，共 ' + selected.length + ' 人');
      hideSigninModal();
      loadActivities();
    } catch (err) { showToast('签到失败: ' + err.message, 'error'); }
  }

  document.addEventListener('DOMContentLoaded', function() {
    loadActivities();

    // onchange handlers
    const typeEl = document.getElementById('actType');
    if (typeEl) typeEl.addEventListener('change', onTypeChange);
    const freeEl = document.getElementById('actFree');
    if (freeEl) freeEl.addEventListener('change', onFreeChange);
    const checkAll = document.getElementById('signinCheckAll');
    if (checkAll) checkAll.addEventListener('change', toggleSigninAll);

    // signin overlay click-to-close
    const signinModal = document.getElementById('signinModal');
    if (signinModal) {
      signinModal.addEventListener('click', function(e) {
        if (e.target === this) hideSigninModal();
      });
    }

    // Delegated handler for data-pg buttons
    document.body.addEventListener('click', function(e) {
      const el = e.target.closest('[data-pg]');
      if (!el) return;
      const fn = window.activitiesPage[el.getAttribute('data-pg')];
      if (typeof fn === 'function') {
        e.preventDefault();
        fn();
      }
    });
  });

  // 暴露到全局供 HTML onclick 调用
  window.activitiesPage = {
    onFreeChange,
    onTypeChange,
    loadActivities,
    showCreateModal,
    hideCreateModal,
    editActivity,
    submitActivity,
    publishActivity,
    cancelActivity,
    finishActivity,
    deleteActivity,
    showSigninModal,
    hideSigninModal,
    toggleSigninAll,
    submitSignin
  };
})();
