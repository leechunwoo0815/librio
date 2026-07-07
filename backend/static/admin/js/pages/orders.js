// backend/static/admin/js/pages/orders.js
// 订单管理页面逻辑

(function() {
  'use strict';

  const orderTypes = {1:'亲子课',2:'观察期',3:'正式会员',4:'季度',5:'半年'};
  const payStatuses = {0:'待支付',1:'已支付',2:'支付失败',3:'退款中',4:'已退款',5:'已关闭'};
  const statusBadgeClasses = {0:'status-pending',1:'status-paid',2:'status-pending',3:'status-refund',4:'status-refund',5:'status-pending'};

  var _confirmCb = null;
  var _currentOrder = null;
  var _searchTimeout = null;

  function showOrderConfirm(title, msg, needInput, inputLabel, cb) {
    document.getElementById('confirmTitle').textContent = title;
    document.getElementById('confirmMsg').textContent = msg;
    _confirmCb = cb;
    document.getElementById('confirmInputWrap').style.display = needInput ? 'block' : 'none';
    if (needInput && inputLabel) document.getElementById('confirmInputLabel').textContent = inputLabel;
    document.getElementById('confirmTextInput').value = '';
    document.getElementById('confirmModal').style.display = 'flex';
  }

  function hideConfirm() {
    document.getElementById('confirmModal').style.display = 'none';
    _confirmCb = null;
  }

  document.addEventListener('DOMContentLoaded', function() {
    loadOrders(1);
    document.getElementById('searchInput').addEventListener('keydown', function(e) {
      if (e.key === 'Enter') loadOrders(1);
    });
    document.getElementById('confirmBtn').addEventListener('click', function() {
      var input = document.getElementById('confirmTextInput').value.trim();
      if (_confirmCb) _confirmCb(input);
      hideConfirm();
    });
  });

  // 点击外部关闭下拉
  document.addEventListener('click', function(e) {
    if (!e.target.closest('#childSearchInput') && !e.target.closest('#childDropdown')) {
      var dropdown = document.getElementById('childDropdown');
      if (dropdown) dropdown.style.display = 'none';
    }
  });

  // ==================== 孩子搜索 ====================
  function searchChildrenForOrder() {
    clearTimeout(_searchTimeout);
    _searchTimeout = setTimeout(async function() {
      var keyword = document.getElementById('childSearchInput').value.trim();
      var dropdown = document.getElementById('childDropdown');
      if (!keyword || keyword.length < 1) { dropdown.style.display = 'none'; return; }

      try {
        var children = await api.get('/admin/api/children/search?keyword=' + encodeURIComponent(keyword));
        if (!children || children.length === 0) {
          dropdown.innerHTML = '<div style="padding:12px;color:var(--muted);text-align:center;">未找到匹配的孩子</div>';
        } else {
          var statusMap = {0:'体验',1:'观察期',2:'正式',3:'过期',4:'退出'};
          dropdown.innerHTML = children.map(function(c) {
            return '<div style="padding:10px 12px;cursor:pointer;border-bottom:1px solid var(--bg);display:flex;justify-content:space-between;align-items:center;" onclick="window.ordersPage.selectChildForOrder(' + c.id + ',\'' + (c.name||'') + '\',\'' + (c.english_name||'') + '\',' + c.status + ')">' +
              '<div><strong>' + escapeHtml(c.name||'未知') + '</strong>' + (c.english_name ? ' <span style="color:var(--muted);">(' + escapeHtml(c.english_name) + ')</span>' : '') + '</div>' +
              '<div style="font-size:12px;color:var(--muted);">' + (c.parent_name||'') + ' ' + (c.phone||'') + ' [' + (statusMap[c.status]||c.status) + ']</div>' +
            '</div>';
          }).join('');
        }
        dropdown.style.display = 'block';
      } catch (e) { dropdown.style.display = 'none'; }
    }, 300);
  }

  function selectChildForOrder(id, name, englishName, status) {
    document.getElementById('createChildId').value = id;
    document.getElementById('childSearchInput').value = name + (englishName ? ' (' + englishName + ')' : '');
    document.getElementById('childDropdown').style.display = 'none';
    var statusMap = {0:'体验',1:'观察期',2:'正式',3:'过期',4:'退出'};
    document.getElementById('selectedChildInfo').textContent = 'ID: ' + id + ' · 状态: ' + (statusMap[status]||status);
  }

  // ==================== 加载订单列表 ====================
  async function loadOrders(page) {
    var status = document.getElementById('filterStatus').value;
    var type = document.getElementById('filterType').value;
    var dateFrom = document.getElementById('dateFrom').value;
    var dateTo = document.getElementById('dateTo').value;
    var search = document.getElementById('searchInput').value.trim();

    var url = '/admin/api/orders?page=' + page + '&page_size=20';
    if (status) url += '&pay_status=' + status;
    if (type) url += '&order_type=' + type;
    if (dateFrom) url += '&date_from=' + dateFrom;
    if (dateTo) url += '&date_to=' + dateTo;
    if (search) url += '&search=' + encodeURIComponent(search);

    try {
      var data = await api.get(url);
      var orders = data.items || [];
      renderOrders(orders);
      renderPagination(data.total, data.page, data.page_size);
      var totalPages = Math.ceil(data.total / data.page_size);
      document.getElementById('orderCount').textContent = '共 ' + data.total + ' 条记录 · 第 ' + data.page + '/' + totalPages + ' 页';
      updateStats(data);
    } catch (e) {
      showToast('加载失败: ' + e.message, 'error');
    }
  }

  function updateStats(data) {
    var orders = data.items || [];
    var total = data.total || 0;
    var pending = orders.filter(function(o) { return o.pay_status === 0; }).length;
    var paid = orders.filter(function(o) { return o.pay_status === 1; }).length;
    var refund = orders.filter(function(o) { return o.pay_status === 3; }).length;
    document.getElementById('statTotal').textContent = total;
    document.getElementById('statPending').textContent = pending;
    document.getElementById('statPaid').textContent = paid;
    document.getElementById('statRefund').textContent = refund;
  }

  // ==================== 渲染订单列表 ====================
  function renderOrders(orders) {
    var tbody = document.getElementById('orderBody');
    if (!orders.length) {
      tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;padding:40px;color:var(--muted);">暂无订单</td></tr>';
      return;
    }
    tbody.innerHTML = orders.map(function(o) {
      var actions = '<span class="action-link" onclick="window.ordersPage.showDetail(\'' + o.order_no + '\')">详情</span>';
      actions += ' <span class="action-link" onclick="window.ordersPage.editOrder(\'' + o.order_no + '\')">编辑</span>';
      if (o.pay_status === 0) {
        actions += ' <span class="action-link" style="color:var(--error)" onclick="window.ordersPage.closeOrder(\'' + o.order_no + '\')">关闭</span>';
      }
      if (o.pay_status === 1) {
        actions += ' <span class="action-link" onclick="window.ordersPage.refundOrder(\'' + o.order_no + '\')">退款</span>';
      }
      actions += ' <span class="action-link" style="color:var(--error)" onclick="window.ordersPage.deleteOrder(\'' + o.order_no + '\')">删除</span>';

      return '<tr>' +
        '<td style="font-family:var(--font-mono);font-size:12px;">' + o.order_no + '</td>' +
        '<td>' + escapeHtml(o.user_name || '-') + '</td>' +
        '<td>' + (orderTypes[o.type] || o.type) + '</td>' +
        '<td class="amount" style="text-align:right;">' + formatMoney(o.amount) + '</td>' +
        '<td style="font-family:var(--font-mono);">' + formatDateTime(o.pay_time || o.create_time) + '</td>' +
        '<td><span class="status-badge ' + (statusBadgeClasses[o.pay_status]||'status-pending') + '">' + (payStatuses[o.pay_status]||o.pay_status) + '</span></td>' +
        '<td><div style="display:flex;gap:6px;flex-wrap:wrap;">' + actions + '</div></td>' +
        '</tr>';
    }).join('');
  }

  function renderPagination(total, page, pageSize) {
    var totalPages = Math.ceil(total / pageSize);
    var el = document.getElementById('pageBtns');
    if (totalPages <= 1) { el.innerHTML = ''; return; }
    var html = '';
    var start = Math.max(1, page - 2);
    var end = Math.min(totalPages, page + 2);
    for (var i = start; i <= end; i++) {
      html += '<button class="page-btn' + (i===page?' active':'') + '" onclick="window.ordersPage.loadOrders(' + i + ')">' + i + '</button>';
    }
    el.innerHTML = html;
  }

  // ==================== 新建订单 ====================
  function showCreateModal() { document.getElementById('createModal').style.display = 'flex'; }
  function hideCreateModal() { document.getElementById('createModal').style.display = 'none'; }

  async function createOrder() {
    var childId = parseInt(document.getElementById('createChildId').value);
    var type = parseInt(document.getElementById('createType').value);
    var remark = document.getElementById('createRemark').value.trim();

    if (!childId) { showToast('请输入孩子ID', 'warning'); return; }

    try {
      await api.post('/admin/api/orders', { child_id: childId, type: type, remark: remark });
      showToast('订单创建成功');
      hideCreateModal();
      loadOrders(1);
    } catch (e) { showToast('创建失败: ' + e.message, 'error'); }
  }

  // ==================== 查看详情 ====================
  async function showDetail(orderNo) {
    var modal = document.getElementById('detailModal');
    var content = document.getElementById('detailContent');
    var actions = document.getElementById('detailActions');
    modal.style.display = 'flex';
    content.innerHTML = '<div style="text-align:center;padding:20px;">加载中...</div>';
    actions.innerHTML = '';

    try {
      var orders = await api.get('/admin/api/orders?page=1&page_size=100');
      var order = (orders.items || []).find(function(o) { return o.order_no === orderNo; });
      if (!order) { content.innerHTML = '<div style="color:var(--error);">订单不存在</div>'; return; }
      _currentOrder = order;

      var html = '<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px 24px;font-size:14px;">';
      html += '<div><span style="color:var(--muted);">订单号：</span><code style="font-size:12px;">' + order.order_no + '</code></div>';
      html += '<div><span style="color:var(--muted);">订单类型：</span><strong>' + (orderTypes[order.type]||order.type) + '</strong></div>';
      html += '<div><span style="color:var(--muted);">家长姓名：</span>' + escapeHtml(order.user_name||'-') + '</div>';
      html += '<div><span style="color:var(--muted);">孩子姓名：</span>' + escapeHtml(order.child_name||'-') + '</div>';
      html += '<div><span style="color:var(--muted);">订单金额：</span><strong style="color:var(--success);">&yen;' + (parseFloat(order.amount)||0).toFixed(2) + '</strong></div>';
      html += '<div><span style="color:var(--muted);">支付状态：</span><span class="status-badge ' + (statusBadgeClasses[order.pay_status]||'') + '">' + (payStatuses[order.pay_status]||order.pay_status) + '</span></div>';
      html += '<div><span style="color:var(--muted);">创建时间：</span>' + formatDateTime(order.create_time) + '</div>';
      html += '<div><span style="color:var(--muted);">支付时间：</span>' + (order.pay_time ? formatDateTime(order.pay_time) : '-') + '</div>';
      if (order.remark) html += '<div style="grid-column:1/-1;"><span style="color:var(--muted);">备注：</span>' + escapeHtml(order.remark) + '</div>';
      html += '</div>';
      content.innerHTML = html;

      // 操作按钮
      var btns = '';
      if (order.pay_status === 0) {
        btns += '<button class="btn-primary" onclick="window.ordersPage.markPaid(\'' + order.order_no + '\')">标记已支付</button>';
        btns += '<button class="btn-outline" style="color:var(--error);border-color:var(--error);" onclick="window.ordersPage.closeOrder(\'' + order.order_no + '\')">关闭订单</button>';
      }
      if (order.pay_status === 1) {
        btns += '<button class="btn-outline" onclick="window.ordersPage.refundOrder(\'' + order.order_no + '\')">发起退款</button>';
      }
      if (order.pay_status === 3) {
        btns += '<button class="btn-primary" onclick="window.ordersPage.approveRefund(\'' + order.order_no + '\')">通过退款</button>';
        btns += '<button class="btn-outline" style="color:var(--error);border-color:var(--error);" onclick="window.ordersPage.rejectRefund(\'' + order.order_no + '\')">拒绝退款</button>';
      }
      actions.innerHTML = btns;
    } catch (e) { content.innerHTML = '<div style="color:var(--error);">加载失败: ' + e.message + '</div>'; }
  }

  function hideDetailModal() { document.getElementById('detailModal').style.display = 'none'; }

  // ==================== 编辑订单 ====================
  async function editOrder(orderNo) {
    showOrderConfirm('编辑订单', '修改订单 ' + orderNo + ' 的状态：', false, null, null);
    // 简化：直接显示状态修改选项
    var modal = document.getElementById('confirmModal');
    var msg = document.getElementById('confirmMsg');
    msg.innerHTML = '选择新状态：<select id="editStatusSelect" style="margin-left:8px;padding:6px;border:1px solid var(--border);border-radius:4px;">' +
      '<option value="0">待支付</option><option value="1">已支付</option><option value="5">已关闭</option></select>';
    document.getElementById('confirmInputWrap').style.display = 'none';
    document.getElementById('confirmModal').style.display = 'flex';

    _confirmCb = async function() {
      var newStatus = parseInt(document.getElementById('editStatusSelect').value);
      try {
        await api.put('/admin/api/orders/' + orderNo + '/status', { pay_status: newStatus });
        showToast('订单状态已更新');
        loadOrders(1);
      } catch (e) { showToast('更新失败: ' + e.message, 'error'); }
    };
  }

  // ==================== 标记已支付 ====================
  async function markPaid(orderNo) {
    showOrderConfirm('标记已支付', '确认将订单 ' + orderNo + ' 标记为已支付？', false, null, async function() {
      try {
        await api.put('/admin/api/orders/' + orderNo + '/status', { pay_status: 1 });
        showToast('已标记为已支付');
        hideDetailModal();
        loadOrders(1);
      } catch (e) { showToast('操作失败: ' + e.message, 'error'); }
    });
  }

  // ==================== 关闭订单 ====================
  async function closeOrder(orderNo) {
    showOrderConfirm('关闭订单', '确认关闭订单 ' + orderNo + '？关闭后用户将无法继续支付。', false, null, async function() {
      try {
        await api.put('/admin/api/orders/' + orderNo + '/status', { pay_status: 5 });
        showToast('订单已关闭');
        hideDetailModal();
        loadOrders(1);
      } catch (e) { showToast('关闭失败: ' + e.message, 'error'); }
    });
  }

  // ==================== 发起退款 ====================
  async function refundOrder(orderNo) {
    showOrderConfirm('发起退款', '确认对订单 ' + orderNo + ' 发起退款？退款金额将原路返回。', false, null, async function() {
      try {
        await api.post('/refund/', { order_no: orderNo, reason: '管理员发起退款' });
        showToast('退款申请已创建');
        hideDetailModal();
        loadOrders(1);
      } catch (e) { showToast('退款失败: ' + e.message, 'error'); }
    });
  }

  // ==================== 审核退款 ====================
  async function approveRefund(orderNo) {
    showOrderConfirm('通过退款', '确认通过订单 ' + orderNo + ' 的退款申请？', false, null, async function() {
      try {
        var refundInfo = await api.get('/admin/api/orders/' + orderNo + '/refund');
        if (!refundInfo.exists) { showToast('无退款申请', 'warning'); return; }
        await api.put('/admin/api/refunds/' + refundInfo.refund_id + '/audit', { action: 'approve', comment: '管理员审核通过' });
        showToast('退款已通过');
        hideDetailModal();
        loadOrders(1);
      } catch (e) { showToast('审核失败: ' + e.message, 'error'); }
    });
  }

  async function rejectRefund(orderNo) {
    showOrderConfirm('拒绝退款', '请输入拒绝原因：', true, '拒绝原因', async function(reason) {
      if (!reason) { showToast('请填写拒绝原因', 'warning'); return; }
      try {
        var refundInfo = await api.get('/admin/api/orders/' + orderNo + '/refund');
        if (!refundInfo.exists) { showToast('无退款申请', 'warning'); return; }
        await api.put('/admin/api/refunds/' + refundInfo.refund_id + '/audit', { action: 'reject', comment: reason });
        showToast('退款已拒绝');
        hideDetailModal();
        loadOrders(1);
      } catch (e) { showToast('审核失败: ' + e.message, 'error'); }
    });
  }

  // ==================== 删除订单 ====================
  async function deleteOrder(orderNo) {
    showOrderConfirm('删除订单', '确认删除订单 ' + orderNo + '？此操作不可撤销。', false, null, async function() {
      try {
        await api.del('/admin/api/orders/' + orderNo);
        showToast('订单已删除');
        loadOrders(1);
      } catch (e) { showToast('删除失败: ' + e.message, 'error'); }
    });
  }

  // ==================== 导出 ====================
  function exportOrders() {
    window.location.href = '/admin/export/orders';
  }

  // 暴露到全局供 HTML onclick 调用
  window.ordersPage = {
    loadOrders,
    exportOrders,
    showCreateModal,
    hideCreateModal,
    searchChildrenForOrder,
    selectChildForOrder,
    createOrder,
    showDetail,
    hideDetailModal,
    editOrder,
    markPaid,
    closeOrder,
    refundOrder,
    approveRefund,
    rejectRefund,
    deleteOrder,
    hideConfirm
  };
})();
