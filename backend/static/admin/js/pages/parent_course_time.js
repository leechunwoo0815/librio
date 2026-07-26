// backend/static/admin/js/pages/parent_course_time.js
/* 亲子课时段管理 CRUD（B3） */
(function () {
  'use strict';

  var venues = [];
  var slots = [];

  function venueName(id) {
    var v = venues.find(function (x) { return x.id === id; });
    return v ? v.name : '#' + id;
  }

  function statusBadge(s) {
    if (s === 1) return '<span class="badge badge-success">可预约</span>';
    if (s === 0) return '<span class="badge badge-warning">已满</span>';
    return '<span class="badge badge-secondary">已关闭</span>';
  }

  function render() {
    var body = document.getElementById('slotBody');
    if (!slots.length) {
      body.innerHTML = '<tr><td colspan="7" class="text-center p-40 text-muted">暂无时段，点击右上角新建</td></tr>';
      return;
    }
    body.innerHTML = slots.map(function (s) {
      return '<tr>' +
        '<td>' + escapeHtml(venueName(s.venue_id)) + '</td>' +
        '<td>' + escapeHtml(s.course_date) + '</td>' +
        '<td>' + escapeHtml(s.start_time) + ' - ' + escapeHtml(s.end_time) + '</td>' +
        '<td>' + (s.max_participants != null ? s.max_participants : '--') + '</td>' +
        '<td>' + (s.current_participants != null ? s.current_participants : 0) + '</td>' +
        '<td>' + statusBadge(s.status) + '</td>' +
        '<td>' +
        '<span class="action-link" data-action="edit" data-id="' + s.id + '">编辑</span> · ' +
        '<span class="action-link danger" data-action="delete" data-id="' + s.id + '">删除</span>' +
        '</td>' +
        '</tr>';
    }).join('');
  }

  function loadVenues() {
    return api.get('/admin/api/venues').then(function (data) {
      venues = data.items || data || [];
      var filter = document.getElementById('venueFilter');
      var dialogVenue = document.getElementById('slotVenue');
      var opts = venues.map(function (v) {
        return '<option value="' + v.id + '">' + escapeHtml(v.name) + '</option>';
      }).join('');
      filter.innerHTML = '<option value="">全部场馆</option>' + opts;
      dialogVenue.innerHTML = opts;
    });
  }

  function loadSlots() {
    var vid = document.getElementById('venueFilter').value;
    var url = '/parent-course-time/admin' + (vid ? '?venue_id=' + vid : '');
    return api.get(url).then(function (data) {
      slots = data.items || data || [];
      render();
    }).catch(function (e) {
      showToast('加载失败: ' + e.message, 'error');
    });
  }

  function openDialog(slot) {
    document.getElementById('slotId').value = slot ? slot.id : '';
    document.getElementById('slotVenue').value = slot ? slot.venue_id : (venues[0] && venues[0].id);
    document.getElementById('slotDate').value = slot ? slot.course_date : '';
    document.getElementById('slotStart').value = slot ? slot.start_time : '10:00';
    document.getElementById('slotEnd').value = slot ? slot.end_time : '11:15';
    document.getElementById('slotMax').value = slot ? slot.max_participants : 30;
    document.getElementById('slotStatus').value = slot ? String(slot.status) : '1';
    document.getElementById('slotStatusGroup').style.display = slot ? 'block' : 'none';
    showModal('slotDialog');
  }

  function save() {
    var id = document.getElementById('slotId').value;
    var payload = {
      course_date: document.getElementById('slotDate').value,
      start_time: document.getElementById('slotStart').value,
      end_time: document.getElementById('slotEnd').value,
      max_participants: parseInt(document.getElementById('slotMax').value, 10),
    };
    if (!payload.course_date || !payload.start_time || !payload.end_time || !payload.max_participants) {
      showToast('请填写完整信息', 'error');
      return;
    }
    if (payload.start_time >= payload.end_time) {
      showToast('结束时间必须晚于开始时间', 'error');
      return;
    }
    var req;
    if (id) {
      payload.status = parseInt(document.getElementById('slotStatus').value, 10);
      req = api.put('/parent-course-time/admin/' + id, payload);
    } else {
      payload.venue_id = parseInt(document.getElementById('slotVenue').value, 10);
      req = api.post('/parent-course-time/admin', payload);
    }
    req.then(function () {
      showToast(id ? '时段已更新' : '时段已创建');
      closeModal('slotDialog');
      loadSlots();
    }).catch(function (e) {
      showToast('保存失败: ' + (e.message || '未知错误'), 'error');
    });
  }

  function del(id) {
    showConfirm('删除时段', '确认删除该时段？已报名的订单不受影响。', function () {
      api.del('/parent-course-time/admin/' + id).then(function () {
        showToast('已删除');
        loadSlots();
      }).catch(function (e) {
        showToast('删除失败: ' + (e.message || '未知错误'), 'error');
      });
    });
  }

  document.getElementById('btnNewSlot').addEventListener('click', function () { openDialog(null); });
  document.getElementById('slotSaveBtn').addEventListener('click', save);
  document.getElementById('venueFilter').addEventListener('change', loadSlots);
  document.querySelector('[data-action="close-modal"][data-modal="slotDialog"]')
    .addEventListener('click', function () { closeModal('slotDialog'); });
  document.getElementById('slotBody').addEventListener('click', function (e) {
    var el = e.target.closest('[data-action]');
    if (!el) return;
    var id = parseInt(el.dataset.id, 10);
    if (el.dataset.action === 'edit') {
      var slot = slots.find(function (s) { return s.id === id; });
      if (slot) openDialog(slot);
    }
    if (el.dataset.action === 'delete') del(id);
  });

  loadVenues().then(loadSlots);

  window.parentCourseTimePage = { loadSlots, openDialog };
})();
