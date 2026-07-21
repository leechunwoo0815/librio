(function() {
  'use strict';

loadAssessments();



  async function loadAssessments() {
    try {
      var resp = await api.get('/admin/api/assessment/list');
      var list = resp.items || resp || [];
      renderStats(resp.stats || {});
      renderTable(list);
      if (resp.stats) populateVenues(list);
    } catch (err) {
      showToast(err.message || '加载评估数据失败', 'error');
      document.getElementById('assessBody').innerHTML =
        '<tr><td colspan="9" class="text-center text-error p-40">加载失败</td></tr>';
    }
  }

  function renderStats(stats) {
    document.getElementById('statMonthTotal').textContent = stats.month_total != null ? stats.month_total : '--';
    document.getElementById('statPending').textContent = stats.pending != null ? stats.pending : '--';
    document.getElementById('statAvgArChange').textContent = stats.avg_ar_change != null ? '+' + stats.avg_ar_change : '--';
    document.getElementById('statAvgAccuracy').textContent = stats.avg_accuracy != null ? stats.avg_accuracy + '%' : '--';
  }

  var avatarColors = ['sa1','sa2','sa3','sa4','sa5'];
  function getAvatarClass(name) {
    var hash = 0;
    for (var i = 0; i < name.length; i++) hash = ((hash << 5) - hash) + name.charCodeAt(i);
    return avatarColors[Math.abs(hash) % avatarColors.length];
  }

  function renderTable(list) {
    var body = document.getElementById('assessBody');
    if (!list.length) {
      body.innerHTML = '<tr><td colspan="9" class="text-center text-muted p-40">暂无评估记录</td></tr>';
      return;
    }
    body.innerHTML = list.map(function(item) {
      var initial = (item.child_name || '?').charAt(0).toUpperCase();
      var avatarCls = getAvatarClass(item.child_name || '');
      var age = item.age ? ' · ' + item.age + '岁' : '';
      var currentAr = item.ar_level_after ? '<span class="level-badge">AR ' + item.ar_level_after + '</span>' : '&mdash;';
      var prevAr = item.ar_level_before ? '<span class="level-badge">AR ' + item.ar_level_before + '</span>' : '&mdash;';
      var arChange = item.ar_level_change ? '<span class="level-up">+' + item.ar_level_change + '</span>' : '&mdash;';
      var accuracy = '';
      if (item.comprehension_score != null) {
        var fillCls = item.comprehension_score >= 80 ? 'high' : (item.comprehension_score >= 60 ? 'mid' : 'low');
        accuracy = '<div class="score-bar-wrap"><div class="score-bar"><div class="score-bar-fill ' + fillCls + '" style="width:' + item.comprehension_score + '%"></div></div><span class="score-text">' + item.comprehension_score + '%</span></div>';
      } else {
        accuracy = '&mdash;';
      }
      var statusMap = { completed: ['status-completed','已完成'], pending: ['status-pending','待评估'], scheduled: ['status-scheduled','已安排'] };
      var st = statusMap[item.status] || ['','--'];
      var actions = buildActions(item);
      return '<tr>' +
        '<td><div class="student-cell"><div class="student-mini-avatar ' + avatarCls + '">' + initial + '</div><span>' + escapeHtml(item.child_name || '-') + age + '</span></div></td>' +
        '<td>' + escapeHtml(item.venue || '-') + '</td>' +
        '<td>' + (item.assess_date ? escapeHtml(item.assess_date) : '&mdash;') + '</td>' +
        '<td>' + currentAr + '</td>' +
        '<td>' + prevAr + '</td>' +
        '<td>' + arChange + '</td>' +
        '<td>' + accuracy + '</td>' +
        '<td><span class="status-badge ' + st[0] + '">' + st[1] + '</span></td>' +
        '<td><div class="action-btns">' + actions + '</div></td>' +
        '</tr>';
    }).join('');
  }

  function buildActions(item) {
    var html = '';
    if (item.status === 'completed') {
      html += '<button class="action-btn" onclick="viewReport(' + item.id + ')">报告</button>';
    } else if (item.status === 'pending') {
      html += '<button class="action-btn" onclick="scheduleAssessment(' + item.id + ')">安排</button>';
    } else if (item.status === 'scheduled') {
      html += '<button class="action-btn" onclick="editAssessment(' + item.id + ')">编辑</button>';
    }
    html += '<button class="action-btn" onclick="viewDetail(' + item.id + ')">详情</button>';
    return html;
  }

  function populateVenues(list) {
    var venues = {};
    list.forEach(function(i) { if (i.venue) venues[i.venue] = true; });
    var sel = document.getElementById('venueFilter');
    Object.keys(venues).sort().forEach(function(v) {
      var opt = document.createElement('option');
      opt.value = v; opt.textContent = v;
      sel.appendChild(opt);
    });
  }

  function filterTable() {
    var search = document.getElementById('searchInput').value.toLowerCase();
    var status = document.getElementById('statusFilter').value;
    var venue = document.getElementById('venueFilter').value;
    var rows = document.querySelectorAll('#assessBody tr');
    rows.forEach(function(row) {
      if (row.children.length < 9) return;
      var name = (row.querySelector('.student-cell span') || {}).textContent || '';
      var rowStatus = '';
      var badge = row.querySelector('.status-badge');
      if (badge) {
        if (badge.classList.contains('status-completed')) rowStatus = 'completed';
        else if (badge.classList.contains('status-pending')) rowStatus = 'pending';
        else if (badge.classList.contains('status-scheduled')) rowStatus = 'scheduled';
      }
      var rowVenue = row.children[1].textContent.trim();
      var matchSearch = !search || name.toLowerCase().indexOf(search) >= 0;
      var matchStatus = !status || rowStatus === status;
      var matchVenue = !venue || rowVenue === venue;
      if (matchSearch && matchStatus && matchVenue) {
        row.classList.remove('hidden');
      } else {
        row.classList.add('hidden');
      }
    });
  }

  function viewReport(id) {
    showToast('报告功能需要后端支持生成PDF', 'info');
  }

  async function viewDetail(id) {
    try {
      var data = await api.get('/admin/api/assessment/' + id);
      if (!data) {
        showToast('评估不存在', 'error');
        return;
      }
      var html = '<div class="p-20">';
      html += '<h3 class="mb-16">评估详情 #' + id + '</h3>';
      html += '<table class="detail-table">';
      html += '<tr><td class="detail-label">孩子</td><td>' + escapeHtml(data.child_name || '-') + '</td></tr>';
      html += '<tr><td class="detail-label">当前AR</td><td>' + (data.ar_level_after || '-') + '</td></tr>';
      html += '<tr><td class="detail-label">状态</td><td>' + escapeHtml(data.status || '-') + '</td></tr>';
      html += '<tr><td class="detail-label">评估日期</td><td>' + escapeHtml(data.assess_date || '-') + '</td></tr>';
      html += '<tr><td class="detail-label">备注</td><td>' + escapeHtml(data.notes || '-') + '</td></tr>';
      html += '</table></div>';
      showConfirm('评估详情', html, null, '关闭');
    } catch (err) {
      showToast('加载详情失败: ' + err.message, 'error');
    }
  }

  function toDateTimeLocalValue(isoStr) {
    if (!isoStr) return '';
    var d = new Date(isoStr);
    if (isNaN(d.getTime())) return '';
    var pad = function(n) { return n < 10 ? '0' + n : n; };
    return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()) + 'T' + pad(d.getHours()) + ':' + pad(d.getMinutes());
  }

  function scheduleAssessment(id) {
    showConfirm('安排评估', '确定将评估 #' + id + ' 状态改为"已安排"？', async function() {
      try {
        await api.put('/admin/api/assessment/' + id, { status: 'scheduled' });
        showToast('评估已安排');
        loadAssessments();
      } catch (err) {
        showToast('操作失败: ' + err.message, 'error');
      }
    });
  }

  async function editAssessment(id) {
    try {
      var data = await api.get('/admin/api/assessment/' + id);
      if (!data) {
        showToast('评估不存在', 'error');
        return;
      }
      document.getElementById('editId').value = id;
      document.querySelector('#assessModal h2').textContent = '编辑评估';
      document.getElementById('submitBtn').textContent = '保存修改';

      // 编辑模式：展示孩子信息，隐藏搜索区
      document.getElementById('newChildGroup').classList.add('hidden');
      document.getElementById('editChildGroup').classList.remove('hidden');
      var childInfo = (data.child_name || '未知');
      if (data.english_name) childInfo += ' / ' + data.english_name;
      document.getElementById('editChildInfo').textContent = childInfo;
      var subInfo = '';
      if (data.parent_name || data.parent_phone) {
        subInfo = '家长：' + (data.parent_name || '-') + ' ' + (data.parent_phone || '');
      }
      document.getElementById('editChildSubInfo').textContent = subInfo;
      document.getElementById('selectedChildId').value = data.child_id || '';

      document.getElementById('assessStatus').value = data.status || 'pending';
      document.getElementById('scheduledDate').value = toDateTimeLocalValue(data.scheduled_date);
      document.getElementById('arBefore').value = data.ar_level_before != null ? data.ar_level_before : '';
      document.getElementById('arAfter').value = data.ar_level_after != null ? data.ar_level_after : '';
      document.getElementById('comprehensionScore').value = data.comprehension_score != null ? data.comprehension_score : '';
      document.getElementById('assessNotes').value = data.notes || '';
      document.getElementById('assessRecommendation').value = data.recommendation || '';

      showModal('assessModal');
    } catch (err) {
      showToast('加载评估信息失败: ' + err.message, 'error');
    }
  }

  async function searchChildForAssessment() {
    var keyword = document.getElementById('childKeyword').value.trim();
    var sel = document.getElementById('childSelect');
    var errEl = document.getElementById('childSearchError');
    errEl.textContent = '';
    if (!keyword) {
      errEl.textContent = '请输入搜索关键词';
      return;
    }
    try {
      var list = await api.get('/admin/api/children/search?keyword=' + encodeURIComponent(keyword));
      sel.innerHTML = '<option value="">请选择孩子</option>';
      if (!list || !list.length) {
        errEl.textContent = '未找到匹配的孩子';
        return;
      }
      list.forEach(function(c) {
        var opt = document.createElement('option');
        opt.value = c.id;
        opt.textContent = (c.name || '-') + (c.english_name ? ' / ' + c.english_name : '') + (c.phone ? ' (' + c.phone + ')' : '');
        sel.appendChild(opt);
      });
    } catch (err) {
      errEl.textContent = '搜索失败: ' + err.message;
    }
  }

  function onChildSelected(sel) {
    document.getElementById('selectedChildId').value = sel.value;
  }

  function openNewAssessment() {
    document.getElementById('editId').value = '';
    document.querySelector('#assessModal h2').textContent = '新建评估';
    document.getElementById('submitBtn').textContent = '保存';
    document.getElementById('assessForm').reset();
    document.getElementById('newChildGroup').classList.remove('hidden');
    document.getElementById('editChildGroup').classList.add('hidden');
    document.getElementById('editChildInfo').textContent = '--';
    document.getElementById('selectedChildId').value = '';
    document.getElementById('childSelect').innerHTML = '<option value="">请选择孩子</option>';
    document.getElementById('childKeyword').value = '';
    document.getElementById('childSearchError').textContent = '';
    showModal('assessModal');
  }

  function closeAssessModal() {
    closeModal('assessModal');
  }

  async function submitAssessment(e) {
    e.preventDefault();
    var editId = document.getElementById('editId').value;
    if (!editId) {
      var childId = document.getElementById('selectedChildId').value;
      if (!childId) {
        showToast('请选择孩子', 'error');
        return;
      }
    }

    var body = {};
    if (!editId) body.child_id = Number(document.getElementById('selectedChildId').value);
    body.status = document.getElementById('assessStatus').value;

    var scheduled = document.getElementById('scheduledDate').value;
    if (scheduled) body.scheduled_date = new Date(scheduled).toISOString();

    var arBefore = document.getElementById('arBefore').value;
    if (arBefore !== '') body.ar_level_before = Number(arBefore);
    var arAfter = document.getElementById('arAfter').value;
    if (arAfter !== '') body.ar_level_after = Number(arAfter);
    var score = document.getElementById('comprehensionScore').value;
    if (score !== '') body.comprehension_score = Number(score);
    var notes = document.getElementById('assessNotes').value.trim();
    if (notes) body.notes = notes;
    var recommendation = document.getElementById('assessRecommendation').value.trim();
    if (recommendation) body.recommendation = recommendation;

    try {
      if (editId) {
        await api.put('/admin/api/assessment/' + editId, body);
        showToast('评估更新成功');
      } else {
        await api.post('/admin/api/assessment/', body);
        showToast('评估创建成功');
      }
      closeAssessModal();
      loadAssessments();
    } catch (err) {
      showToast(err.message || '操作失败', 'error');
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

  async function deleteAssessment(id) {
    showConfirmDialog('确认删除', '确定删除该评估记录？', async function() {
      try {
        await api.del('/admin/api/assessment/' + id);
        showToast('评估已删除');
        loadAssessments();
      } catch (err) {
        showToast(err.message || '删除失败', 'error');
      }
    });
  }

  function escapeHtml(str) {
    var div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  window.assessmentsPage = { loadAssessments, renderStats, avatarColors, getAvatarClass, renderTable, buildActions, populateVenues, filterTable, viewReport, viewDetail, toDateTimeLocalValue, scheduleAssessment, editAssessment, searchChildForAssessment, onChildSelected, openNewAssessment, closeAssessModal, submitAssessment, showConfirmDialog, deleteAssessment };
  for (var k in window.assessmentsPage) window[k] = window.assessmentsPage[k];

})();
