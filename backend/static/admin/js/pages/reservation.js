(function() {
  'use strict';

  var allReservations = [];
  var currentFilter = '';

  document.addEventListener('DOMContentLoaded', function() { loadReservations(); });

  async function loadReservations() {
    try {
      var data = await api.get('/admin/api/reservations');
      allReservations = data.items || data || [];
      updateStats(allReservations);
      renderReservations(allReservations);
    } catch (err) {
      document.getElementById('reservationBody').innerHTML = '<tr><td colspan="6" class="text-center p-40 text-error">加载失败</td></tr>';
    }
  }

  function updateStats(items) {
    var active = items.filter(function(r) { return r.status === 0; }).length;
    var today = new Date().toISOString().slice(0,10);
    var todayNew = items.filter(function(r) { return (r.create_time||'').slice(0,10) === today; }).length;
    var now = Date.now();
    var expiring = items.filter(function(r) {
      if (r.status !== 0 || !r.expire_time) return false;
      var exp = new Date(r.expire_time).getTime();
      return exp > now && exp - now < 24 * 60 * 60 * 1000;
    }).length;
    document.getElementById('statActive').textContent = active;
    document.getElementById('statToday').textContent = todayNew;
    document.getElementById('statExpiring').textContent = expiring;
  }

  function filterTab(btn, status) {
    currentFilter = status;
    document.querySelectorAll('.tabs .tab').forEach(function(t) { t.classList.remove('active'); });
    btn.classList.add('active');
    var filtered = status ? allReservations.filter(function(r) {
      if (status === 'ACTIVE') return r.status === 0;
      if (status === 'EXPIRED') return r.status === 2;
      if (status === 'PICKED') return r.status === 1;
      return true;
    }) : allReservations;
    renderReservations(filtered);
  }

  function renderReservations(items) {
    if (!items.length) {
      document.getElementById('reservationBody').innerHTML = '<tr><td colspan="6" class="text-center p-40 text-muted">暂无预约</td></tr>';
      return;
    }
    var statusMap = { 0: { cls: 'status-active', text: '有效' }, 1: { cls: 'status-picked', text: '已取书' }, 2: { cls: 'status-expired', text: '已过期' }, 3: { cls: 'status-cancelled', text: '已取消' } };
    document.getElementById('reservationBody').innerHTML = items.map(function(r) {
      var s = statusMap[r.status] || { cls: '', text: r.status };
      var actions = '';
      if (r.status === 0) {
        actions = '<span class="action-link" data-action="fulfill" data-id="' + r.id + '" data-child="' + r.child_id + '">确认取书</span> · <span class="action-link danger" data-action="cancel-reservation" data-id="' + r.id + '">取消预约</span>';
      } else if (r.status === 3) {
        actions = '<span class="action-link text-muted cursor-default">已取消</span>';
      } else {
        actions = '<span class="action-link text-muted cursor-default">--</span>';
      }
      return '<tr>' +
        '<td>' + escapeHtml(r.child_name || r.child_id || '--') + '</td>' +
        '<td>' + escapeHtml(r.book_title || r.book_id || '--') + '</td>' +
        '<td class="font-mono">' + formatDateTime(r.create_time) + '</td>' +
        '<td class="font-mono">' + formatDateTime(r.expire_time) + '</td>' +
        '<td><span class="status-badge ' + s.cls + '">' + s.text + '</span></td>' +
        '<td>' + actions + '</td>' +
      '</tr>';
    }).join('');
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

  function fulfill(reservationId, childId) {
    showConfirmDialog('确认取书', '确认取书？', function() {
      api.post('/admin/api/reservations/fulfill', { reservation_id: reservationId, child_id: childId }).then(function() {
        showToast('取书确认成功');
        loadReservations();
      }).catch(function(e) {
        showToast('操作失败: ' + e.message, 'error');
      });
    });
  }

  function cancelReservation(id) {
    showConfirmDialog('取消预约', '确认取消此预约？', function() {
      api.put('/admin/api/reservations/' + id + '/cancel').then(function() {
        showToast('预约已取消');
        loadReservations();
      }).catch(function(e) {
        showToast('取消失败: ' + e.message, 'error');
      });
    });
  }


  // Data-action delegation for migrated inline handlers
  document.querySelector('.tabs')?.addEventListener('click', function(e) {
    var tab = e.target.closest('[data-action="filter-tab"]');
    if (tab) filterTab(tab, tab.getAttribute('data-filter'));
  });
  document.querySelector('[data-action="close-modal"]')?.addEventListener('click', function() { closeModal('confirmDialog'); });
  document.getElementById('reservationBody').addEventListener('click', function(e) {
    var el = e.target.closest('[data-action]');
    if (!el) return;
    if (el.getAttribute('data-action') === 'fulfill') fulfill(parseInt(el.dataset.id), parseInt(el.dataset.child));
    if (el.getAttribute('data-action') === 'cancel-reservation') cancelReservation(parseInt(el.dataset.id));
  });

  // B1a 扫码枪取书：扫副本条码回车 → 条码驱动 fulfill（自动匹配最早待取预约）
  var scanInput = document.getElementById('scanFulfillInput');
  var lastScanAt = 0;
  if (scanInput) {
    scanInput.addEventListener('keydown', function(e) {
      if (e.key !== 'Enter') return;
      var barcode = scanInput.value.trim();
      if (!barcode) return;
      var now = Date.now();
      if (now - lastScanAt < 500) { scanInput.value = ''; return; }  // 防连续误扫
      lastScanAt = now;
      scanInput.value = '';
      scanInput.disabled = true;
      api.post('/admin/api/reservations/fulfill', { barcode: barcode }).then(function() {
        showToast('取书成功（' + barcode + '）');
        loadReservations();
      }).catch(function(err) {
        showToast('取书失败: ' + (err.message || '未知错误'), 'error');
      }).finally(function() {
        scanInput.disabled = false;
        scanInput.focus();
      });
    });
    scanInput.focus();
  }

  window.reservationPage = { allReservations, currentFilter, loadReservations, updateStats, filterTab, renderReservations, showConfirmDialog, fulfill, cancelReservation };

})();
