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

  // ── 隐私与数据（P0-1/P0-3）──

  onOpenPrivacy() {
    wx.showActionSheet({
      itemList: ['查看我的同意记录', '撤回语音数据同意', '撤回儿童信息同意（删除孩子数据）', '查看隐私政策'],
      success: (res) => {
        if (res.tapIndex === 0) this._showConsentRecords()
        else if (res.tapIndex === 1) this._withdrawConsent('voice_recording', '语音数据')
        else if (res.tapIndex === 2) this._withdrawChildData()
        else if (res.tapIndex === 3) {
          wx.navigateTo({ url: '/pages/agreement/privacy-policy/privacy-policy' })
        }
      },
    })
  },

  async _showConsentRecords() {
    const request = require('../../utils/request')
    try {
      const res = await request.get('/user/consent')
      const consents = (res && res.consents) || []
      const TYPE_NAME = { privacy_policy: '隐私政策', child_data: '儿童信息收集', voice_recording: '语音数据收集' }
      const text = consents.length === 0
        ? '暂无同意记录'
        : consents.map(c => {
            const t = TYPE_NAME[c.consent_type] || c.consent_type
            const time = (c.create_time || '').slice(0, 10)
            return `${t}：${c.withdrawn_at ? '已撤回' : '已同意'}（${time}，${c.consent_version}）`
          }).join('\n')
      wx.showModal({ title: '我的同意记录', content: text, showCancel: false })
    } catch (e) {
      wx.showToast({ title: '查询失败，请重试', icon: 'none' })
    }
  },

  _withdrawConsent(type, label) {
    const request = require('../../utils/request')
    wx.showModal({
      title: `撤回${label}同意`,
      content: `撤回后相关功能将立即停止。确定撤回${label}同意吗？`,
      confirmText: '确定撤回',
      success: async (m) => {
        if (!m.confirm) return
        try {
          await request.post('/user/consent/withdraw', { consent_type: type })
          wx.showToast({ title: '已撤回', icon: 'success' })
        } catch (e) {
          wx.showToast({ title: e.message || '撤回失败', icon: 'none' })
        }
      },
    })
  },

  _withdrawChildData() {
    const request = require('../../utils/request')
    wx.showModal({
      title: '删除孩子数据',
      content: '撤回儿童信息同意将为您的所有孩子发起数据删除：\n• 阅读记录、打卡、生词本等数据将永久删除\n• 交易凭证按法规保留\n• 提交后 24 小时内可在孩子管理中取消\n\n确定继续吗？',
      confirmText: '确定删除',
      confirmColor: '#e6432d',
      success: async (m) => {
        if (!m.confirm) return
        try {
          await request.post('/user/consent/withdraw', { consent_type: 'child_data' })
          wx.showModal({ title: '已提交', content: '删除请求已提交，24 小时内将完成数据清理。', showCancel: false })
        } catch (e) {
          wx.showModal({ title: '无法删除', content: e.message || '请先处理未完成事项', showCancel: false })
        }
      },
    })
  },

})
