// frontend/pages/member/member.js
const api = require('../../utils/api')
const auth = require('../../utils/auth')
const app = getApp()

Page({
  data: {
    child: null,
    children: [],
    userInfo: null,
    statusText: '',
    statusClass: '',
    expireText: '',
    countdownText: '',
    tiers: [],
    loadError: false,
    loading: true,
  },

  onShow() {
    this.loadData()
  },

  async loadData() {
    this.setData({ loading: true, loadError: false })
    try {
      const children = await api.getChildren()
      if (!children || children.length === 0) return

      const child = auth.selectChild(children)
      if (!child) return

      const detail = await api.getChild(child.id).catch(() => child)
      const statusMap = { 0: '体验用户', 1: '观察期', 2: '正式会员', 3: '已过期', 4: '已退出' }
      const statusClassMap = { 0: '', 1: 'observation', 2: 'official', 3: 'expired' }

      let expireText = ''
      let countdownText = ''
      const now = Date.now()

      if (detail.member_expire_time) {
        const expireTime = new Date(detail.member_expire_time).getTime()
        if (expireTime > now) {
          const diff = expireTime - now
          const days = Math.floor(diff / (1000 * 60 * 60 * 24))
          const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60))
          countdownText = days > 0 ? `${days}天${hours}小时后到期` : `${hours}小时后到期`
          expireText = detail.member_expire_time.slice(0, 10)
        } else {
          expireText = '会员已过期'
          countdownText = ''
        }
      }

      const userInfo = app.globalData.userInfo || {}

      let tiers = []
      try {
        const tierData = await api.getTiers()
        tiers = (tierData.tiers || []).map(t => ({
          type: t.type,
          name: t.name,
          price: t.price,
          unit: t.unit,
          tag: t.discount_tag,
          features: t.features || [],
          cta: t.cta,
        }))
      } catch (e) {
        console.error('Load tiers failed:', e)
      }

      this.setData({
        child: detail,
        children,
        userInfo,
        statusText: statusMap[detail.status] || '体验用户',
        statusClass: statusClassMap[detail.status] || '',
        expireText,
        countdownText,
        tiers,
        loading: false,
        loadError: false,
      })
    } catch (e) {
      console.error('Load member data failed:', e)
      this.setData({ loadError: true, loading: false })
    }
  },

  switchChild(e) {
    const idx = e.currentTarget.dataset.index
    const child = this.data.children[idx]
    if (!child) return
    app.globalData.currentChild = child
    wx.setStorageSync('currentChildId', child.id)
    this.loadData()
  },

  goTier(e) {
    const type = e.currentTarget.dataset.type
    if (type === 1) {
      wx.navigateTo({ url: '/pages/order-pkg/observation/observation' })
    } else if (type === 2) {
      wx.navigateTo({ url: '/pages/order-pkg/observation/observation' })
    } else if (type === 3) {
      wx.navigateTo({ url: '/pages/order-pkg/official/official' })
    }
  },

  onRetry() { this.loadData() },

  goOrderHistory() {
    wx.navigateTo({ url: '/pages/order-pkg/order-history/order-history' })
  },

  goRefund() {
    wx.navigateTo({ url: '/pages/order-pkg/refund-apply/refund-apply' })
  },

  showAbout() {
    wx.showModal({
      title: '关于我们',
      content: 'DmkWords 儿童英语阅读平台\n版本 0.1.0\nwww.dmkwords.cn',
      showCancel: false
    })
  },

})
