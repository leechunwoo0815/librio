// frontend/pages/order-pkg/official/official.js
const api = require('../../utils/api')
const auth = require('../../utils/auth')

Page({
  data: {
    child: null,
    children: [],
    loading: false,
    isSecondChild: false,
    actualPrice: 0,
    origPrice: 0,
    savings: 0,
    secondChildPrice: 0,
    periodType: 3,
    priceMap: {},
    currentPeriodName: '年卡',
    currentPeriodUnit: '年',
    currentPeriodDays: 365,
    isIOS: false,
    features: [
      { icon: '📚', title: '全量图书无限阅读', desc: '平台所有图书随时在线阅读' },
      { icon: '🎯', title: 'A-Z 26级晋级体系', desc: '科学分级，循序渐进提升阅读能力' },
      { icon: '🏆', title: '排行榜竞技', desc: '与同龄小伙伴比拼阅读量，激发阅读兴趣' },
      { icon: '📜', title: '晋级证书', desc: '每通过一个级别即可获得专属晋级证书' },
      { icon: '⭐', title: '成就系统', desc: '丰富的成就徽章，记录每一个阅读里程碑' },
    ],
    comparisons: [
      { feature: '在线阅读图书', observation: true, official: true },
      { feature: '每日打卡', observation: true, official: true },
      { feature: '阅读统计', observation: true, official: true },
      { feature: '老师定期评估', observation: true, official: true },
      { feature: '观察期结束报告', observation: true, official: false },
      { feature: 'A-Z晋级体系', observation: false, official: true },
      { feature: '排行榜', observation: false, official: true },
      { feature: '晋级证书', observation: false, official: true },
      { feature: '成就系统', observation: false, official: true },
      { feature: '有效期', observation: '30天', official: '365天' },
    ],
  },

  onLoad() {
    const app = getApp()
    if (!auth.requireAuth()) return
    const systemInfo = wx.getSystemInfoSync()
    this.setData({ isIOS: systemInfo.platform === 'ios' })
    this.loadChild()
  },

  async loadChild() {
    try {
      const children = await api.getChildren()
      if (!children || children.length === 0) return

      const child = auth.selectChild(children)
      if (!child) return

      const detail = await api.getChild(child.id).catch(() => child)

      let priceMap = {}
      try {
        const tierData = await api.getTiers()
        const tiers = tierData.tiers || []
        tiers.forEach(t => { priceMap[t.type] = t.price })
      } catch (e) {
        console.error('Load tier price failed:', e)
        wx.showToast({ title: '加载价格信息失败', icon: 'none' })
        this.setData({ loading: false })
        return
      }

      const isSecondChild = children.some(c => c.id !== child.id && (c.status === 1 || c.status === 2))

      const periodType = this.data.periodType
      const rawPrice = priceMap[periodType]
      const actualPrice = (rawPrice != null && !isNaN(rawPrice)) ? Number(rawPrice) : 0
      const origPrice = actualPrice > 0 ? Math.round(actualPrice / 0.9) : 0
      const savings = origPrice - actualPrice
      const secondChildPrice = actualPrice > 0 ? Math.round(actualPrice * 0.9) : 0
      const periodInfo = this._periodInfo(periodType)
      this.setData({ child: detail, children, isSecondChild, priceMap, actualPrice, origPrice, savings, secondChildPrice, ...periodInfo })
    } catch (e) {
      console.error(e)
    }
  },

  _periodInfo(periodType) {
    const map = {
      3: { currentPeriodName: '年卡', currentPeriodUnit: '年', currentPeriodDays: 365 },
      4: { currentPeriodName: '季度', currentPeriodUnit: '季度', currentPeriodDays: 90 },
      5: { currentPeriodName: '半年', currentPeriodUnit: '半年', currentPeriodDays: 180 },
    }
    return map[periodType] || map[3]
  },

  switchPeriod(e) {
    const periodType = parseInt(e.currentTarget.dataset.period)
    if (periodType === this.data.periodType) return
    const priceMap = this.data.priceMap
    const rawPrice = priceMap[periodType]
    const actualPrice = (rawPrice != null && !isNaN(rawPrice)) ? Number(rawPrice) : 0
    const origPrice = actualPrice > 0 ? Math.round(actualPrice / 0.9) : 0
    const savings = origPrice - actualPrice
    const secondChildPrice = actualPrice > 0 ? Math.round(actualPrice * 0.9) : 0
    const periodInfo = this._periodInfo(periodType)
    this.setData({ periodType, actualPrice, origPrice, savings, secondChildPrice, ...periodInfo })
  },

  async handleOrder() {
    if (this.data.isIOS) {
      wx.showModal({
        title: '暂不支持 iOS 开通',
        content: '当前暂不支持 iOS 端开通，请使用安卓设备或联系客服办理',
        showCancel: false,
      })
      return
    }
    const child = this.data.child
    if (!child) {
      wx.showToast({ title: '请先添加孩子信息', icon: 'none' })
      return
    }

    this.setData({ loading: true })
    try {
      const order = await api.createOrder(child.id, this.data.periodType)
      const payParams = await api.getPayParams(order.id)
      if (!payParams || !payParams.timeStamp || !payParams.nonceStr || !payParams.package || !payParams.signType || !payParams.paySign) {
        throw new Error('支付参数异常，请稍后重试')
      }
      await new Promise((resolve, reject) => {
        wx.requestPayment({
          ...payParams,
          success: resolve,
          fail: reject,
        })
      })
      wx.showToast({ title: '开通成功', icon: 'success' })
      this._navTimer = setTimeout(() => {
        wx.navigateBack()
      }, 1500)
    } catch (e) {
      if (e.errMsg && e.errMsg.indexOf('cancel') > -1) {
        wx.showToast({ title: '已取消支付', icon: 'none' })
      } else {
        wx.showToast({ title: '支付失败，请重试', icon: 'none' })
      }
    } finally {
      this.setData({ loading: false })
    }
  },

  onUnload() {
    if (this._navTimer) { clearTimeout(this._navTimer); this._navTimer = null }
  },
})
