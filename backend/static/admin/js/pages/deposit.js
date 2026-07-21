(function() {
  'use strict';

  var allDeposits = [];
  var currentFilter = '';

  document.addEventListener('DOMContentLoaded', function() { loadDeposits(); });

  async function loadDeposits() {
    try {
      var data = await api.get('/admin/api/deposits');
      allDeposits = data.items || data || [];
      updateStats(allDeposits);
      renderDeposits(allDeposits);
    } catch (err) {
      document.getElementById('depositBody').innerHTML = '<tr><td colspan="6" class="text-center p-40 text-error">加载失败</td></tr>';
    }
  }

  function updateStats(items) {
    var total = 0, refunding = 0, deducted = 0, fine = 0;
    items.forEach(function(d) {
      var amt = Number(d.amount || 0);
      if (d.status === 'PAID' || d.status === 'paid') total += amt;
      if (d.status === 'REFUNDING' || d.status === 'refunding') refunding += amt;
      if (d.status === 'DEDUCTED' || d.status === 'deducted') deducted += amt;
      if (d.fine_amount) fine += Number(d.fine_amount);
    });
    document.getElementById('statTotal').textContent = formatMoney(total);
    document.getElementById('statRefunding').textContent = formatMoney(refunding);
    document.getElementById('statDeducted').textContent = formatMoney(deducted);
    document.getElementById('statFine').textContent = formatMoney(fine);
  }

  function filterTab(btn, status) {
    currentFilter = status;
    document.querySelectorAll('.tabs .tab').forEach(function(t) { t.classList.remove('active'); });
    btn.classList.add('active');
    var statusMap = { PAID: 1, REFUNDING: 4, REFUNDED: 2, DEDUCTED: 3 };
    var statusVal = statusMap[status];
    var filtered = statusVal !== undefined ? allDeposits.filter(function(d) { return d.status === statusVal; }) : allDeposits;
    renderDeposits(filtered);
  }

  function renderDeposits(items) {
    if (!items.length) {
      document.getElementById('depositBody').innerHTML = '<tr><td colspan="6" class="text-center p-40 text-muted">暂无押金记录</td></tr>';
      return;
    }
    var statusMap = {
      PAID: { cls: 'status-paid', text: '已缴纳' },
      UNPAID: { cls: 'status-pending', text: '未缴纳' },
      REFUNDING: { cls: 'status-refunding', text: '退款中' },
      REFUNDED: { cls: 'status-returned', text: '已退' },
      DEDUCTED: { cls: 'status-deducted', text: '已扣' },
    };
    document.getElementById('depositBody').innerHTML = items.map(function(d) {
      var statusKey = (d.status||'').toUpperCase();
      var s = statusMap[statusKey] || { cls: '', text: d.status };
      var actions = [];
      if (statusKey === 'PAID') {
        actions.push('<span class="action-link" onclick="requestRefund(' + d.child_id + ')">退款</span>');
        actions.push('<span class="action-link" onclick="deductDeposit(' + d.child_id + ')">扣除</span>');
      } else if (statusKey === 'UNPAID') {
        actions.push('<span class="action-link" onclick="payDeposit(' + d.child_id + ')">代缴</span>');
      } else if (statusKey === 'REFUNDING') {
        actions.push('<span class="action-link" onclick="markRefunded(' + d.child_id + ')">标记到账</span>');
        actions.push('<span class="action-link" onclick="cancelRefund(' + d.child_id + ')">取消退款</span>');
      } else if (statusKey === 'DEDUCTED' || statusKey === 'REFUNDED') {
        actions.push('<span class="action-link" onclick="payDeposit(' + d.child_id + ')">重新缴纳</span>');
      }
      var actionHtml = actions.length ? actions.join(' · ') : '<span class="action-link text-muted cursor-default">--</span>';
      return '<tr>' +
        '<td>' + escapeHtml(d.child_name || d.child_id || '--') + '</td>' +
        '<td><span class="status-badge ' + s.cls + '">' + s.text + '</span></td>' +
        '<td class="amount">' + formatMoney(d.amount) + '</td>' +
        '<td class="amount" style="color:' + (d.fine_amount ? 'var(--error)' : 'var(--muted)') + '">' + formatMoney(d.fine_amount || 0) + '</td>' +
        '<td class="font-mono-date">' + formatDateTime(d.create_time) + '</td>' +
        '<td>' + actionHtml + '</td>' +
      '</tr>';
    }).join('');
  }

  var deductChildId = null;

  function showConfirmDialog(title, msg, onConfirm) {
    document.querySelector('#confirmDialog h2').textContent = title;
    document.getElementById('confirmMsg').textContent = msg;
    document.getElementById('confirmBtn').onclick = function() {
      closeModal('confirmDialog');
      onConfirm();
    };
    showModal('confirmDialog');
  }

  function requestRefund(childId) {
    showConfirmDialog('确认退款', '确认为孩子 ' + childId + ' 申请押金退款？', function() {
      api.post('/admin/api/deposits/refund', { child_id: childId }).then(function() {
        showToast('退款申请已提交');
        loadDeposits();
      }).catch(function(e) {
        showToast('退款失败: ' + e.message, 'error');
      });
    });
  }

  function cancelRefund(childId) {
    showConfirmDialog('取消退款', '确认取消孩子 ' + childId + ' 的退款申请？', function() {
      api.post('/admin/api/deposits/' + childId + '/cancel-refund').then(function() {
        showToast('退款申请已取消');
        loadDeposits();
      }).catch(function(e) {
        showToast('取消失败: ' + e.message, 'error');
      });
    });
  }

  function markRefunded(childId) {
    showConfirmDialog('标记到账', '确认孩子 ' + childId + ' 的押金退款已到账？', function() {
      api.post('/admin/api/deposits/' + childId + '/mark-refunded').then(function() {
        showToast('已标记退款到账');
        loadDeposits();
      }).catch(function(e) {
        showToast('标记失败: ' + e.message, 'error');
      });
    });
  }

  function payDeposit(childId) {
    showConfirmDialog('缴纳押金', '确认为孩子 ' + childId + ' 代缴/重新缴纳押金？', function() {
      api.post('/admin/api/deposits/pay', { child_id: childId }).then(function() {
        showToast('押金缴纳成功');
        loadDeposits();
      }).catch(function(e) {
        showToast('缴纳失败: ' + e.message, 'error');
      });
    });
  }

  function deductDeposit(childId) {
    deductChildId = childId;
    document.getElementById('deductReason').value = '图书损坏/丢失';
    document.getElementById('deductAmount').value = '100';
    showModal('deductDialog');
  }

  function confirmDeduct() {
    var childId = deductChildId;
    if (!childId) return;
    var reason = document.getElementById('deductReason').value.trim();
    var amountStr = document.getElementById('deductAmount').value.trim();
    if (!reason) {
      showToast('请输入扣除原因', 'error');
      return;
    }
    var amount = parseFloat(amountStr);
    if (isNaN(amount) || amount <= 0) {
      showToast('金额不正确', 'error');
      return;
    }
    closeModal('deductDialog');
    api.post('/admin/api/deposits/deduct', { child_id: childId, amount: amount.toFixed(2), reason: reason }).then(function() {
      showToast('押金扣除成功');
      loadDeposits();
    }).catch(function(e) {
      showToast('扣除失败: ' + e.message, 'error');
    });
  }

  function escapeHtml(str) {
    if (!str) return '';
    var div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  window.depositPage = { allDeposits, currentFilter, loadDeposits, updateStats, filterTab, renderDeposits, deductChildId, showConfirmDialog, requestRefund, cancelRefund, markRefunded, payDeposit, deductDeposit, confirmDeduct };
  for (var k in window.depositPage) window[k] = window.depositPage[k];

})();
