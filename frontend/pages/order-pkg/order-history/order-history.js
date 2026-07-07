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
        amountText: Number(order.amount).toFixed(2),
        timeText: (order.create_time || '').slice(0, 16).replace('T', ' '),
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
      this.setData({ loading: false })
    }
  },
})
