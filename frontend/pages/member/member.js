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
    tiers: [
      {
        type: 1,
        name: '亲子课',
        price: 99,
        unit: '次',
        tag: '入门体验',
        color: '#22c55e',
        features: ['1次亲子阅读课', '专业老师引导', '阅读能力初评', '阅读习惯培养指导'],
        cta: '立即报名',
      },
      {
        type: 2,
        name: '观察期',
        price: 500,
        unit: '/30天',
        tag: '深度体验',
        color: '#5560cf',
        features: ['在线阅读全量图书', '每日打卡记录', '阅读数据统计', '老师定期评估', '观察期结束报告'],
        cta: '立即报名',
      },
      {
        type: 3,
        name: '正式会员',
        price: 5400,
        unit: '/年',
        tag: '推荐',
        color: '#f59e0b',
        features: ['全量图书无限阅读', 'A-Z 26级晋级体系', '排行榜竞技', '晋级证书', '成就系统'],
        cta: '立即开通',
      },
    ],
  },

  onShow() {
    if (app.globalData.isTestMode || app.globalData.token === 'test-token-mock') {
      this._loadDemoData()
    } else {
      this.loadData()
    }
  },

  async loadData() {
    try {
      const children = await api.getChildren()
      if (!children || children.length === 0) return

      const child = auth.selectChild(children)
      if (!child) return

      const detail = await api.getChild(child.id).catch(() => child)
      const statusMap = { 0: '体验用户', 1: '观察期', 2: '正式会员', 3: '已过期', 4: '已退出' }
      const statusClassMap = { 0: '', 1: 'status-observation', 2: 'status-official', 3: 'status-expired' }

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

      this.setData({
        child: detail,
        children,
        userInfo,
        statusText: statusMap[detail.status] || '体验用户',
        statusClass: statusClassMap[detail.status] || '',
        expireText,
        countdownText,
      })
    } catch (e) {
      console.error('Load member data failed:', e)
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
      wx.showModal({
        title: '报名亲子课',
        content: '请联系客服报名亲子课，电话：400-XXX-XXXX',
        showCancel: false,
      })
    } else if (type === 2) {
      wx.navigateTo({ url: '/pages/order-pkg/observation/observation' })
    } else if (type === 3) {
      wx.navigateTo({ url: '/pages/order-pkg/official/official' })
    }
  },

  goOrderHistory() {
    wx.navigateTo({ url: '/pages/order-pkg/order-history/order-history' })
  },

  goRefund() {
    wx.navigateTo({ url: '/pages/order-pkg/refund-apply/refund-apply' })
  },

  _loadDemoData() {
    this.setData({
      child: {
        id: 1, name: '小明', english_name: 'Tom', age: 7, grade: '二年级',
        status: 2, member_expire_time: '2027-03-15T00:00:00',
        total_books_finished: 15, total_words_read: 42000, current_streak_days: 7,
      },
      children: [
        { id: 1, name: '小明', english_name: 'Tom', status: 2 },
      ],
      userInfo: { nickname: '家长' },
      statusText: '正式会员',
      statusClass: 'status-official',
      expireText: '2027-03-15',
      countdownText: '278天12小时后到期',
    })
  },
})
