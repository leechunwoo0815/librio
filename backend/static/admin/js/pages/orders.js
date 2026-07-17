// backend/static/admin/js/pages/orders.js
// 订单管理页面逻辑

(function() {
  'use strict';

  const orderTypes = {1:'亲子课',2:'观察期',3:'正式会员',4:'季度',5:'半年'};
  const payStatuses = {0:'待支付',1:'已支付',2:'支付失败',3:'退款中',4:'已退款',5:'已关闭'};
  const statusBadgeClasses = {0:'status-pending',1:'status-paid',2:'status-pending',3:'status-refund',4:'status-refund',5:'status-pending'};

  var pageSize = 15;

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
    document.getElementById('confirmModal').classList.add('show');
  }

  function hideConfirm() {
    document.getElementById('confirmModal').classList.remove('show');
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
    // Populate age/grade dropdowns
    var agesHtml = '<option value="">请选择</option>';
    for (var i = 3; i <= 15; i++) agesHtml += '<option value="' + i + '">' + i + ' 岁</option>';
    document.getElementById('offlineChildAge').innerHTML = agesHtml;
    var grades = ['小班','中班','大班','一年级','二年级','三年级','四年级','五年级','六年级','初一','初二','初三'];
    var gradesHtml = '<option value="">请选择</option>';
    grades.forEach(function(g) { gradesHtml += '<option value="' + g + '">' + g + '</option>'; });
    document.getElementById('offlineChildGrade').innerHTML = gradesHtml;
    // Load venues
    (async function() {
      try {
        var result = await api.get('/admin/api/venues');
        var list = result.items || result.list || [];
        var sel = document.getElementById('offlineVenueId');
        list.forEach(function(v) {
          var o = document.createElement('option');
          o.value = v.id;
          o.textContent = v.name;
          sel.appendChild(o);
        });
      } catch (e) { /* non-blocking */ }
    })();
  });

  // 点击外部关闭下拉
  document.addEventListener('click', function(e) {
    if (!e.target.closest('#childSearchInput') && !e.target.closest('#childDropdown')) {
      var dropdown = document.getElementById('childDropdown');
      if (dropdown) dropdown.classList.add('hidden');
    }
  });

  // ==================== 孩子搜索 ====================
  function searchChildrenForOrder() {
    clearTimeout(_searchTimeout);
    _searchTimeout = setTimeout(async function() {
      var keyword = document.getElementById('childSearchInput').value.trim();
      var dropdown = document.getElementById('childDropdown');
      if (!keyword || keyword.length < 1) { dropdown.classList.add('hidden'); return; }

      try {
        var children = await api.get('/admin/api/children/search?keyword=' + encodeURIComponent(keyword));
        if (!children || children.length === 0) {
          dropdown.innerHTML = '<div style="padding:12px;color:var(--muted);text-align:center;">未找到匹配的孩子</div>';
        } else {
          var statusMap = {0:'体验',1:'观察期',2:'正式',3:'过期',4:'退出'};
          dropdown.innerHTML = '';
          children.forEach(function(c) {
            var div = document.createElement('div');
            div.style.cssText = 'padding:10px 12px;cursor:pointer;border-bottom:1px solid var(--bg);display:flex;justify-content:space-between;align-items:center;';
            div.onclick = function() { window.ordersPage.selectChildForOrder(c.id, c.name||'', c.english_name||'', c.status); };
            var leftDiv = document.createElement('div');
            var strong = document.createElement('strong');
            strong.textContent = c.name||'未知';
            leftDiv.appendChild(strong);
            if (c.english_name) {
              leftDiv.appendChild(document.createTextNode(' '));
              var engSpan = document.createElement('span');
              engSpan.style.cssText = 'color:var(--muted);';
              engSpan.textContent = '(' + c.english_name + ')';
              leftDiv.appendChild(engSpan);
            }
            div.appendChild(leftDiv);
            var rightDiv = document.createElement('div');
            rightDiv.style.cssText = 'font-size:12px;color:var(--muted);';
            rightDiv.textContent = (c.parent_name||'') + ' ' + (c.phone||'') + ' [' + (statusMap[c.status]||c.status) + ']';
            div.appendChild(rightDiv);
            dropdown.appendChild(div);
          });
        }
        dropdown.classList.remove('hidden');
      } catch (e) { dropdown.classList.add('hidden'); }
    }, 300);
  }

  function selectChildForOrder(id, name, englishName, status) {
    document.getElementById('createChildId').value = id;
    document.getElementById('childSearchInput').value = name + (englishName ? ' (' + englishName + ')' : '');
    document.getElementById('childDropdown').classList.add('hidden');
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

    var url = '/admin/api/orders?page=' + page + '&page_size=' + pageSize;
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
    tbody.innerHTML = '';
    orders.forEach(function(o) {
      var tr = document.createElement('tr');
      var td1 = document.createElement('td');
      td1.style.cssText = 'font-family:var(--font-mono);font-size:12px;';
      td1.textContent = o.order_no;
      tr.appendChild(td1);
      var td2 = document.createElement('td');
      td2.textContent = o.user_name || '-';
      tr.appendChild(td2);
      var td3 = document.createElement('td');
      td3.textContent = orderTypes[o.type] || o.type;
      tr.appendChild(td3);
      var td4 = document.createElement('td');
      td4.className = 'amount';
      td4.style.cssText = 'text-align:right;';
      td4.textContent = formatMoney(o.amount);
      tr.appendChild(td4);
      var td5 = document.createElement('td');
      td5.style.cssText = 'font-family:var(--font-mono);';
      td5.textContent = formatDateTime(o.pay_time || o.create_time);
      tr.appendChild(td5);
      var td6 = document.createElement('td');
      var statusSpan = document.createElement('span');
      statusSpan.className = 'status-badge ' + (statusBadgeClasses[o.pay_status]||'status-pending');
      statusSpan.textContent = payStatuses[o.pay_status]||o.pay_status;
      td6.appendChild(statusSpan);
      tr.appendChild(td6);
      var td7 = document.createElement('td');
      var actionDiv = document.createElement('div');
      actionDiv.style.cssText = 'display:flex;gap:6px;flex-wrap:wrap;';
      var actionLinks = [];
      var link1 = document.createElement('span');
      link1.className = 'action-link';
      link1.textContent = '\u8BE6\u60C5';
      link1.onclick = function() { window.ordersPage.showDetail(o.order_no); };
      actionLinks.push(link1);
      var link2 = document.createElement('span');
      link2.className = 'action-link';
      link2.textContent = '\u7F16\u8F91';
      link2.onclick = function() { window.ordersPage.editOrder(o.order_no); };
      actionLinks.push(link2);
      if (o.pay_status === 0) {
        var link3 = document.createElement('span');
        link3.className = 'action-link';
        link3.style.cssText = 'color:var(--error);';
        link3.textContent = '\u5173\u95ED';
        link3.onclick = function() { window.ordersPage.closeOrder(o.order_no); };
        actionLinks.push(link3);
      }
      if (o.pay_status === 1) {
        var link4 = document.createElement('span');
        link4.className = 'action-link';
        link4.textContent = '\u9000\u6B3E';
        link4.onclick = function() { window.ordersPage.refundOrder(o.order_no); };
        actionLinks.push(link4);
      }
      var link5 = document.createElement('span');
      link5.className = 'action-link';
      link5.style.cssText = 'color:var(--error);';
      link5.textContent = '\u5220\u9664';
      link5.onclick = function() { window.ordersPage.deleteOrder(o.order_no); };
      actionLinks.push(link5);
      actionLinks.forEach(function(l) { actionDiv.appendChild(l); actionDiv.appendChild(document.createTextNode(' ')); });
      td7.appendChild(actionDiv);
      tr.appendChild(td7);
      tbody.appendChild(tr);
    });
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

  // ==================== 新建订单（含线下兜底） ====================

  let _defaultPrices = {1: 99, 2: 500, 3: 5400, 4: 1350, 5: 2700};

  async function loadPrices() {
    try {
      const cfg = await api.get('/admin/api/config');
      const items = cfg && cfg.items || {};
      const map = {};
      const priceKeys = {
        price_parent_course: 1,
        price_observation: 2,
        price_official_member: 3,
        price_quarterly: 4,
        price_semi_annual: 5,
      };
      Object.keys(priceKeys).forEach(function(key) {
        if (items[key] && items[key].value) {
          map[priceKeys[key]] = parseInt(items[key].value) || 99;
        }
      });
      if (Object.keys(map).length) _defaultPrices = map;
    } catch (e) { /* 静默降级 */ }
  }
  loadPrices();

  function showCreateModal() {
    document.getElementById('createModal').classList.add('show');
    document.getElementById('offlineToggle').checked = false;
    document.getElementById('existingUserFields').style.display = 'block';
    document.getElementById('offlineUserFields').classList.add('hidden');
    document.querySelector('input[name="payStatus"][value="pending"]').checked = true;
    document.getElementById('paymentFields').classList.add('hidden');
    updateDefaultAmount();
  }

  function hideCreateModal() {     document.getElementById('createModal').classList.remove('show'); }

  function toggleOffline() {
    var isOffline = document.getElementById('offlineToggle').checked;
    document.getElementById('existingUserFields').style.display = isOffline ? 'none' : 'block';
    var uf = document.getElementById('offlineUserFields');
    if (isOffline) uf.classList.remove('hidden'); else uf.classList.add('hidden');
  }

  function togglePayStatus() {
    var isPaid = document.querySelector('input[name="payStatus"]:checked').value === 'paid';
    var pf = document.getElementById('paymentFields');
    if (isPaid) pf.classList.remove('hidden'); else pf.classList.add('hidden');
  }

  function updateDefaultAmount() {
    var type = parseInt(document.getElementById('createType').value);
    document.getElementById('offlineAmount').value = _defaultPrices[type] || '';
  }

  async function createOrder() {
    var isOffline = document.getElementById('offlineToggle').checked;
    var isPaid = document.querySelector('input[name="payStatus"]:checked').value === 'paid';

    var amount = parseFloat(document.getElementById('offlineAmount').value);
    if (!amount || amount <= 0) { showToast('请输入实收金额', 'warning'); return; }

    var body = {
      order_type: parseInt(document.getElementById('createType').value),
      amount: amount,
      remark: document.getElementById('createRemark').value.trim(),
    };

    if (isPaid) {
      body.pay_type = parseInt(document.getElementById('offlinePayType').value);
      if (!body.pay_type) { showToast('请选择付款方式', 'warning'); return; }
    }

    if (isOffline) {
      // 线下新用户
      body.parent_name = document.getElementById('offlineParentName').value.trim();
      body.phone = document.getElementById('offlinePhone').value.trim();
      body.child_name = document.getElementById('offlineChildName').value.trim();
      body.child_age = parseInt(document.getElementById('offlineChildAge').value);
      body.child_grade = document.getElementById('offlineChildGrade').value;
      body.venue_id = parseInt(document.getElementById('offlineVenueId').value) || null;

      if (!body.parent_name) { showToast('请输入家长姓名', 'warning'); return; }
      if (!body.phone || !/^1\d{10}$/.test(body.phone)) { showToast('请输入正确的11位手机号', 'warning'); return; }
      if (!body.child_name) { showToast('请输入孩子姓名', 'warning'); return; }
      if (!body.child_age) { showToast('请选择孩子年龄', 'warning'); return; }
      if (!body.child_grade) { showToast('请选择孩子年级', 'warning'); return; }

      try {
        var result = await api.post('/admin/api/orders/offline', body);
        var msg = '订单创建成功（单号：' + result.order_no + '）';
        if (result.default_password) msg += '，初始密码：' + result.default_password;
        showToast(msg);
        hideCreateModal();
        loadOrders(1);
      } catch (e) { showToast('创建失败: ' + e.message, 'error'); }
    } else {
      // 已有用户
      body.child_id = parseInt(document.getElementById('createChildId').value);
      if (!body.child_id) { showToast('请选择孩子', 'warning'); return; }

      try {
        var result = await api.post('/admin/api/orders', body);
        showToast('订单创建成功');
        hideCreateModal();
        loadOrders(1);
      } catch (e) { showToast('创建失败: ' + e.message, 'error'); }
    }
  }

  // ==================== 查看详情 ====================
  async function showDetail(orderNo) {
    var modal = document.getElementById('detailModal');
    var content = document.getElementById('detailContent');
    var actions = document.getElementById('detailActions');
    modal.classList.add('show');
    content.innerHTML = '<div style="text-align:center;padding:20px;">加载中...</div>';
    actions.innerHTML = '';

    try {
      var orders = await api.get('/admin/api/orders?page=1&page_size=100');
      var order = (orders.items || []).find(function(o) { return o.order_no === orderNo; });
      if (!order) { content.innerHTML = '<div style="color:var(--error);">订单不存在</div>'; return; }
      _currentOrder = order;

      var html = '<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px 24px;font-size:14px;">';
      html += '<div><span style="color:var(--muted);">订单号：</span><code style="font-size:12px;">' + escapeHtml(order.order_no) + '</code></div>';
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
      actions.innerHTML = '';
      if (order.pay_status === 0) {
        var btn1 = document.createElement('button');
        btn1.className = 'btn btn-primary';
        btn1.textContent = '\u6807\u8BB0\u5DF2\u652F\u4ED8';
        btn1.onclick = function() { window.ordersPage.markPaid(order.order_no); };
        actions.appendChild(btn1);
        var btn2 = document.createElement('button');
        btn2.className = 'btn btn-danger-outline';
        btn2.textContent = '\u5173\u95ED\u8BA2\u5355';
        btn2.onclick = function() { window.ordersPage.closeOrder(order.order_no); };
        actions.appendChild(btn2);
      }
      if (order.pay_status === 1) {
        var btn3 = document.createElement('button');
        btn3.className = 'btn btn-outline';
        btn3.textContent = '\u53D1\u8D77\u9000\u6B3E';
        btn3.onclick = function() { window.ordersPage.refundOrder(order.order_no); };
        actions.appendChild(btn3);
      }
      if (order.pay_status === 3) {
        var btn4 = document.createElement('button');
        btn4.className = 'btn btn-primary';
        btn4.textContent = '\u901A\u8FC7\u9000\u6B3E';
        btn4.onclick = function() { window.ordersPage.approveRefund(order.order_no); };
        actions.appendChild(btn4);
        var btn5 = document.createElement('button');
        btn5.className = 'btn btn-danger-outline';
        btn5.textContent = '\u62D2\u7EDD\u9000\u6B3E';
        btn5.onclick = function() { window.ordersPage.rejectRefund(order.order_no); };
        actions.appendChild(btn5);
      }
    } catch (e) {
      content.textContent = '';
      var errDiv = document.createElement('div');
      errDiv.style.cssText = 'color:var(--error);';
      errDiv.textContent = '\u52A0\u8F7D\u5931\u8D25: ' + e.message;
      content.appendChild(errDiv);
    }
  }

  function hideDetailModal() { document.getElementById('detailModal').classList.remove('show'); }

  // ==================== 编辑订单 ====================
  async function editOrder(orderNo) {
    showOrderConfirm('编辑订单', '修改订单 ' + orderNo + ' 的状态：', false, null, null);
    // 简化：直接显示状态修改选项
    var modal = document.getElementById('confirmModal');
    var msg = document.getElementById('confirmMsg');
    msg.innerHTML = '选择新状态：<select id="editStatusSelect" style="margin-left:8px;padding:6px;border:1px solid var(--border);border-radius:4px;">' +
      '<option value="0">待支付</option><option value="1">已支付</option><option value="5">已关闭</option></select>';
    document.getElementById('confirmInputWrap').style.display = 'none';
    document.getElementById('confirmModal').classList.add('show');

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
        var result = await api.post('/admin/api/orders/' + orderNo + '/refund', { reason: '管理员发起退款' });
        showToast(result.message || '退款已提交');
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

  function changePageSize(newSize) {
    pageSize = parseInt(newSize);
    loadOrders(1);
  }

  // ==================== 导出 ====================
  function exportOrders() {
    var token = auth.getToken();
    if (!token) { showToast('登录已过期，请重新登录', 'error'); return; }
    var url = '/admin/api/export/orders';
    fetch(url, { headers: { 'Authorization': 'Bearer ' + token } })
      .then(function(r) {
        if (!r.ok) throw new Error('导出失败');
        return r.blob();
      })
      .then(function(blob) {
        var link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = 'orders_export.csv';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(link.href);
      })
      .catch(function(err) { showToast(err.message, 'error'); });
  }

  // 暴露到全局供 HTML onclick 调用
  window.ordersPage = {
    loadOrders,
    exportOrders,
    showCreateModal,
    hideCreateModal,
    toggleOffline,
    togglePayStatus,
    updateDefaultAmount,
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
    hideConfirm,
    changePageSize
  };
})();
