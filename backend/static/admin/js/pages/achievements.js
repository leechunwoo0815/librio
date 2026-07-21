(function() {
  'use strict';

  const TYPE_MAP = { 1: '晋级', 2: '读书里程碑', 3: '连续打卡', 4: '测验满分' };
  const TYPE_KEY_MAP = { 1: 'level_up', 2: 'book_milestone', 3: 'streak', 4: 'perfect_score' };
  const TYPE_BADGE_CLS = {
    'book_milestone': 'status-tag status-tag-milestone status status-approved',
    'streak': 'status-tag status-tag-streak status status-pending',
    'perfect_score': 'status-tag status-tag-perfect status status-active',
    'level_up': 'status-tag status-tag-level status',
    'reading_practice': 'status-tag status-tag-milestone status status-approved',
    'vocab_milestone': 'status-tag status-tag-milestone status status-approved',
    'perfect_streak': 'status-tag status-tag-perfect status status-active'
  };
  const TRIGGER_HINTS = {
    'level_up': '晋级徽章：示例 {"level":"B"}，代表孩子晋级到指定级别时触发。',
    'book_milestone': '读书里程碑：示例 {"count":10}，代表累计读完指定数量图书时触发。',
    'streak': '连续打卡：示例 {"days":7}，代表连续打卡指定天数时触发。',
    'perfect_score': '测验满分：示例 {"count":1}，代表测验获得满分次数达到指定值时触发。'
  };

  document.addEventListener('DOMContentLoaded', () => {
    loadAchievements();
    loadRecords();
    const typeSel = document.querySelector('select[name="type"]');
    if (typeSel) {
      typeSel.addEventListener('change', updateTriggerHint);
      updateTriggerHint();
    }
  });

  function updateTriggerHint() {
    const type = document.querySelector('select[name="type"]').value;
    const key = TYPE_KEY_MAP[type] || '';
    const hint = TRIGGER_HINTS[key] || '请根据成就类型填写 JSON 条件。';
    const hintEl = document.getElementById('triggerHint');
    if (hintEl) hintEl.textContent = hint;
    const ta = document.getElementById('triggerCondition');
    if (ta && key && !ta.value.trim()) {
      const examples = { level_up: '{"level":"B"}', book_milestone: '{"count":10}', streak: '{"days":7}', perfect_score: '{"count":1}' };
      ta.placeholder = '例如：' + examples[key];
    }
  }

  function explainTrigger(type, condition) {
    const key = typeof type === 'number' ? TYPE_KEY_MAP[type] : type;
    if (!condition) return '-';
    let obj = condition;
    if (typeof condition === 'string') {
      try { obj = JSON.parse(condition); } catch { return escapeHtml(condition); }
    }
    const parts = [];
    if (key === 'level_up' && obj.level) parts.push('晋级至 ' + obj.level);
    if (key === 'book_milestone' && obj.count != null) parts.push('累计读完 ' + obj.count + ' 本书');
    if (key === 'streak' && obj.days != null) parts.push('连续打卡 ' + obj.days + ' 天');
    if (key === 'perfect_score' && obj.count != null) parts.push('满分测验 ' + obj.count + ' 次');
    if (parts.length) return escapeHtml(parts.join('，'));
    return escapeHtml(JSON.stringify(obj));
  }

  async function loadAchievements() {
    try {
      const r = await api.get('/admin/api/advancement/achievements');
      const list = r || [];
      renderBadges(list);
      updateBadgeFilter(list);
      document.getElementById('badgeCount').textContent = '共 ' + list.length + ' 个徽章';
    } catch (err) {
      showToast(err.message || '加载成就失败', 'error');
      document.getElementById('badgeBody').innerHTML = '<tr><td colspan="6" class="text-center p-40 text-error">加载失败</td></tr>';
      document.getElementById('badgeCount').textContent = '';
    }
  }

  async function loadRecords() {
    try {
      const r = await api.get('/admin/api/advancement/achievements/records');
      const list = r || [];
      renderRecords(list);
    } catch (err) {
      /* records panel is secondary; silently handle */
      document.getElementById('recordsBody').innerHTML = '<tr><td colspan="5" class="text-center p-40 text-muted">暂无授予记录</td></tr>';
    }
  }

  function getTypeBadge(type) {
    const numericType = typeof type === 'number';
    const typeName = numericType ? TYPE_MAP[type] : type;
    const cls = TYPE_BADGE_CLS[typeName] || 'status-tag status-tag-milestone status status-approved';
    const label = numericType ? TYPE_MAP[type] : getTypeLabel(type);
    return '<span class="' + cls + '">' + escapeHtml(label) + '</span>';
  }

  function getTypeLabel(type) {
    if (!type) return '-';
    const map = {
      'level_up': '晋级徽章',
      'book_milestone': '阅读里程碑',
      'streak': '连续打卡',
      'perfect_score': '测验满分',
      'reading_practice': '阅读里程碑',
      'vocab_milestone': '阅读里程碑',
      'perfect_streak': '测验满分'
    };
    return map[type] || type;
  }

  function renderBadges(achievements) {
    if (!achievements.length) {
      document.getElementById('badgeBody').innerHTML = '<tr><td colspan="6" class="text-center p-40 text-muted">暂无成就定义</td></tr>';
      return;
    }
    document.getElementById('badgeBody').innerHTML = achievements.map(a => `
      <tr>
        <td class="badge-emoji">${escapeHtml(a.badge_emoji || '🏅')}</td>
        <td><strong>${escapeHtml(a.name || '-')}</strong></td>
        <td>${getTypeBadge(a.type)}</td>
        <td><div class="text-sm">${explainTrigger(a.type, a.trigger_condition)}</div><code class="trigger-code text-xs text-muted">${escapeHtml(a.trigger_condition != null ? (typeof a.trigger_condition === 'string' ? a.trigger_condition : JSON.stringify(a.trigger_condition)) : '-')}</code></td>
        <td>${a.award_count != null ? a.award_count : '-'}</td>
        <td>
          <div class="table-actions">
            <button class="btn btn-outline btn-sm" onclick="editBadge(${a.id})">编辑</button>
            <button class="btn btn-danger btn-sm" onclick="deleteBadge(${a.id})">删除</button>
          </div>
        </td>
      </tr>
    `).join('');
  }

  function updateBadgeFilter(achievements) {
    const sel = document.getElementById('badgeFilter');
    // clear existing options except first
    while (sel.options.length > 1) sel.remove(1);
    achievements.forEach(a => {
      const opt = document.createElement('option');
      opt.value = a.id;
      opt.textContent = a.name;
      sel.appendChild(opt);
    });
  }

  function renderRecords(records) {
    if (!records.length) {
      document.getElementById('recordsBody').innerHTML = '<tr><td colspan="5" class="text-center p-40 text-muted">暂无授予记录</td></tr>';
      return;
    }
    document.getElementById('recordsBody').innerHTML = records.map(r => `
      <tr>
        <td><strong>${escapeHtml(r.child_name || r.user_name || '-')}</strong></td>
        <td>${escapeHtml(r.badge_emoji || '')} ${escapeHtml(r.achievement_name || '-')}</td>
        <td>${getTypeBadge(r.achievement_type || r.type)}</td>
        <td class="record-time">${escapeHtml((r.achieved_at || r.awarded_at || '').slice(0, 16).replace('T', ' '))}</td>
        <td>${r.award_method === 'manual' ? '手动授予' : '自动'}</td>
      </tr>
    `).join('');
  }

  function switchAchTab(name, btn) {
    document.querySelectorAll('#achTabBar .tab-item').forEach(function(t) { t.classList.remove('active'); });
    btn.classList.add('active');
    document.getElementById('panel-badges').style.display = name === 'badges' ? 'block' : 'none';
    document.getElementById('panel-records').style.display = name === 'records' ? 'block' : 'none';
  }

  function openBadgeModal() {
    document.getElementById('editId').value = '';
    document.getElementById('modalTitle').textContent = '新增徽章';
    document.getElementById('submitBtn').textContent = '保存';
    document.getElementById('badgeForm').reset();
    updateTriggerHint();
    document.getElementById('badgeModal').classList.add('show');
  }

  function closeBadgeModal() {
    document.getElementById('badgeModal').classList.remove('show');
  }

  async function submitBadge(e) {
    e.preventDefault();
    const form = document.getElementById('badgeForm');
    const fd = new FormData(form);
    const body = {};
    for (const [k, v] of fd.entries()) {
      if (k === 'editId') continue;
      if (v === '') continue;
      if (k === 'trigger_condition') {
        // 数据库存储为 JSON 字符串，直接透传用户输入
        if (v) body[k] = v;
      } else if (k === 'type') {
        body[k] = Number(v);
      } else {
        body[k] = v;
      }
    }
    const editId = document.getElementById('editId').value;
    try {
      if (editId) {
        await api.put('/admin/api/advancement/achievements/' + editId, body);
        showToast('徽章更新成功');
      } else {
        await api.post('/admin/api/advancement/achievements', body);
        showToast('徽章创建成功');
      }
      closeBadgeModal();
      loadAchievements();
    } catch (err) {
      showToast(err.message || '操作失败', 'error');
    }
  }

  async function editBadge(id) {
    try {
      const achievements = await api.get('/admin/api/advancement/achievements');
      const badge = (achievements || []).find(a => a.id === id);
      if (!badge) {
        showToast('徽章不存在', 'error');
        return;
      }
      document.getElementById('editId').value = id;
      document.getElementById('modalTitle').textContent = '编辑徽章';
      document.getElementById('submitBtn').textContent = '保存修改';
      const form = document.getElementById('badgeForm');
      form.elements['name'].value = badge.name || '';
      form.elements['description'].value = badge.description || '';
      form.elements['badge_emoji'].value = badge.badge_emoji || '';
      form.elements['type'].value = badge.type || '';
      const tc = badge.trigger_condition;
      form.elements['trigger_condition'].value = tc != null ? (typeof tc === 'string' ? tc : JSON.stringify(tc)) : '';
      updateTriggerHint();
      document.getElementById('badgeModal').classList.add('show');
    } catch (err) {
      showToast('加载徽章信息失败', 'error');
    }
  }

  function showConfirmDialog(title, msg, onConfirm) {
    document.querySelector('#confirmDialog h2').textContent = title;
    document.getElementById('confirmMsg').textContent = msg;
    document.getElementById('confirmBtn').onclick = function() {
      closeModal('confirmDialog');
      onConfirm();
    };
    showModal('confirmDialog');
  }

  function deleteBadge(id) {
    showConfirmDialog('删除徽章', '确定删除该徽章？', function() {
      api.del('/admin/api/advancement/achievements/' + id).then(function() {
        showToast('删除成功');
        loadAchievements();
      }).catch(function(err) {
        showToast(err.message || '删除失败', 'error');
      });
    });
  }

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  window.achievementsPage = { TYPE_MAP, TYPE_KEY_MAP, TYPE_BADGE_CLS, TRIGGER_HINTS, updateTriggerHint, explainTrigger, loadAchievements, loadRecords, getTypeBadge, getTypeLabel, renderBadges, updateBadgeFilter, renderRecords, switchAchTab, openBadgeModal, closeBadgeModal, submitBadge, editBadge, showConfirmDialog, deleteBadge };
  for (var k in window.achievementsPage) window[k] = window.achievementsPage[k];

})();
