// frontend/pages/order-pkg/order-history/order-history.js
const api = require('../../utils/api')

const TYPE_MAP = { 1: '亲子课', 2: '观察期', 3: '正式会员' }
const STATUS_MAP = { 0: '待支付', 1: '已支付', 2: '已退款' }
const STATUS_CLASS = { 0: 'badge-pending', 1: 'badge-paid', 2: 'badge-refunded' }
const TYPE_ICON = { 1: '👨‍👩‍👧', 2: '🔍', 3: '👑' }
const TYPE_CLASS = { 1: 'type1', 2: 'type2', 3: 'type3' }
const PAGE_SIZE = 20

Page({
  data: {
    orders: [],
    allOrders: [],
    page: 1,
    total: 0,
    loading: false,
    hasMore: true,
    isEmpty: false,
    currentTab: 0,
  },

  onLoad() {
    const app = getApp()
    this.loadOrders(1)
  },

  onPullDownRefresh() {
    this.loadOrders(1).then(() => {
      wx.stopPullDownRefresh()
    })
  },

  switchTab(e) {
    const tab = parseInt(e.currentTarget.dataset.tab)
    this.setData({ currentTab: tab })
    this._filterOrders()
  },

  _filterOrders() {
    const { allOrders, currentTab } = this.data
    if (currentTab === 0) {
      this.setData({ orders: allOrders, isEmpty: allOrders.length === 0 })
    } else {
      const statusMap = { 1: 0, 2: 1, 3: 2 }
      const filtered = allOrders.filter(o => o.pay_status === statusMap[currentTab])
      this.setData({ orders: filtered, isEmpty: filtered.length === 0 })
    }
  },

  onReachBottom() {
    if (this.data.hasMore && !this.data.loading) {
      this.loadOrders(this.data.page + 1)
    }
  },

  async loadOrders(page) {
    if (this.data.loading) return
    this.setData({ loading: true })

    try {
      const res = await api.getOrders(page)
      const list = (res.list || []).map(order => ({
        ...order,
        typeText: TYPE_MAP[order.type] || '未知',
        statusText: STATUS_MAP[order.pay_status] || '未知',
        statusClass: STATUS_CLASS[order.pay_status] || '',
        icon: TYPE_ICON[order.type] || '📋',
        typeClass: TYPE_CLASS[order.type] || '',
        amountText: (order.amount != null && !isNaN(Number(order.amount))) ? Number(order.amount).toFixed(2) : '0.00',
        timeText: (order.create_time || '').slice(0, 16).replace('T', ' '),
        showCancel: order.pay_status === 0,
        showRefund: order.pay_status === 1,
        showActions: order.pay_status === 0 || order.pay_status === 1,
      }))

      const allOrders = page === 1 ? list : [...this.data.allOrders, ...list]
      const orders = allOrders
      const hasMore = orders.length < (res.total || 0)

      this.setData({
        allOrders,
        orders,
        page,
        total: res.total || 0,
        hasMore,
        isEmpty: orders.length === 0,
      })

      this._filterOrders()
    } catch (e) {
      console.error('Load orders failed:', e)
    } finally {
      this.setData({ loading: false });
    }
  },

  onCancel(e) {
    const orderId = e.currentTarget.dataset.id;
    wx.showModal({
      title: '确认取消',
      content: '确定要取消该订单吗？',
      success: async (res) => {
        if (!res.confirm) return;
        try {
          wx.showLoading({ title: '处理中...' });
          await api.cancelOrder(orderId);
          wx.hideLoading();
          wx.showToast({ title: '订单已取消', icon: 'success' });
          this.loadOrders(1);
        } catch (err) {
          wx.hideLoading();
          wx.showToast({ title: '取消失败，请稍后重试', icon: 'none' });
        }
      },
    });
  },

  async onRefund(e) {
    const orderId = e.currentTarget.dataset.id
    const res = await wx.showModal({
      title: '申请退款',
      content: '确定要申请退款吗？',
      confirmText: '申请退款',
      confirmColor: '#ef4444',
    })
    if (!res.confirm) return
    try {
      wx.showLoading({ title: '申请中...' })
      await api.refundOrder(orderId)
      wx.hideLoading()
      wx.showToast({ title: '退款申请已提交', icon: 'success' })
      this.loadOrders()
    } catch (e) {
      wx.hideLoading()
      wx.showToast({ title: e.message || '退款失败', icon: 'none' })
    }
  },
})
