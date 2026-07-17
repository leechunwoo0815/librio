const api = require('../../utils/api')
const auth = require('../../utils/auth')

const STATUS_MAP = {
  paid: { text: '已缴纳', icon: '✅', cls: 'status-paid', badgeCls: 'badge-success' },
  unpaid: { text: '未缴纳', icon: '⚠️', cls: 'status-unpaid', badgeCls: 'badge-warning' },
  refunding: { text: '退款中', icon: '⏳', cls: 'status-refunding', badgeCls: 'badge-info' },
  refunded: { text: '已退', icon: '↩️', cls: 'status-refunded', badgeCls: 'badge-info' },
  deducted: { text: '已扣', icon: '❌', cls: 'status-deducted', badgeCls: 'badge-error' },
}

Page({
  data: {
    depositInfo: null,
    loading: true,
    statusText: '',
    statusIcon: '',
    statusCls: '',
    statusBadgeCls: '',
  },

  onLoad() {
    if (!auth.requireAuth()) return
    this.loadDepositInfo()
  },

  async loadDepositInfo() {
    this.setData({ loading: true })
    try {
      const child = auth.getCurrentChild()
      if (!child) {
        wx.showToast({ title: '请先选择孩子', icon: 'none' })
        this.setData({ depositInfo: null, loading: false })
        return
      }
      const info = await api.getDepositStatus(child.id)
      const s = STATUS_MAP[info.status] || STATUS_MAP.paid
      this.setData({
        depositInfo: info,
        statusText: s.text,
        statusIcon: s.icon,
        statusCls: s.cls,
        statusBadgeCls: s.badgeCls,
        loading: false,
      })
    } catch (e) {
      console.error('获取押金信息失败:', e)
      wx.showToast({ title: e.message || '获取押金信息失败', icon: 'none' })
      this.setData({ depositInfo: null, loading: false })
    }
  },

  _getActionButton(info) {
    switch (info.status) {
      case 'paid':
        return {
          type: 'outline',
          text: '申请退款',
          handler: 'onRefund',
        }
      case 'unpaid':
        return {
          type: 'primary',
          text: `缴纳押金 ¥${info.balance || info.depositAmount || '0'}`,
          handler: 'onPay',
        }
      case 'refunding':
        return null
      case 'refunded':
        return {
          type: 'primary',
          text: `重新缴纳押金 ¥${info.balance || info.depositAmount || '0'}`,
          handler: 'onPay',
        }
      case 'deducted':
        return {
          type: 'danger',
          text: `补缴押金 ¥${info.fine}`,
          handler: 'onTopUp',
        }
      default:
        return null
    }
  },

  onRefund() {
    const child = auth.getCurrentChild()
    if (!child) {
      wx.showToast({ title: '请先选择孩子', icon: 'none' })
      return
    }
    wx.showModal({
      title: '申请退款',
      content: '确认申请退还押金吗？退款前请确保无未还图书且无未缴罚款。',
      success: (res) => {
        if (res.confirm) {
          wx.showLoading({ title: '提交中...' })
          api.refundDeposit(child.id).then(() => {
            wx.hideLoading()
            wx.showToast({ title: '退款申请已提交', icon: 'success' })
            this.loadDepositInfo()
          }).catch((e) => {
            wx.hideLoading()
            wx.showToast({ title: e.message || '申请失败', icon: 'none' })
          })
        }
      },
    })
  },

  async onPay() {
    const child = auth.getCurrentChild()
    if (!child) {
      wx.showToast({ title: '请先选择孩子', icon: 'none' })
      return
    }
    this.setData({ loading: true })
    try {
      const res = await api.payDeposit(child.id)
      const payParams = res.pay_params || res
      if (!payParams.timeStamp || !payParams.nonceStr || !payParams.package || !payParams.signType || !payParams.paySign) {
        throw new Error('支付参数异常，请稍后重试')
      }
      await new Promise((resolve, reject) => {
        wx.requestPayment({
          ...payParams,
          success: resolve,
          fail: reject,
        })
      })
      wx.showToast({ title: '支付成功', icon: 'success' })
      this.loadDepositInfo()
    } catch (e) {
      if (e.errMsg && e.errMsg.indexOf('cancel') > -1) {
        wx.showToast({ title: '已取消支付', icon: 'none' })
      } else {
        wx.showToast({ title: e.message || '支付失败', icon: 'none' })
      }
    } finally {
      this.setData({ loading: false })
    }
  },

  async onTopUp() {
    const child = auth.getCurrentChild()
    if (!child) {
      wx.showToast({ title: '请先选择孩子', icon: 'none' })
      return
    }
    const res = await wx.showModal({
      title: '补缴押金',
      content: `确认补缴押金 ¥${this.data.depositInfo.fine} 吗？`,
    })
    if (!res.confirm) return
    this.setData({ loading: true })
    try {
      const payParams = await api.repayDeposit(child.id)
      await new Promise((resolve, reject) => {
        wx.requestPayment({
          ...payParams,
          success: resolve,
          fail: reject,
        })
      })
      wx.showToast({ title: '补缴成功', icon: 'success' })
      this.loadDepositInfo()
    } catch (e) {
      if (e.errMsg && e.errMsg.indexOf('cancel') > -1) {
        wx.showToast({ title: '已取消支付', icon: 'none' })
      } else {
        wx.showToast({ title: e.message || '补缴失败', icon: 'none' })
      }
    } finally {
      this.setData({ loading: false })
    }
  },

  goBack() {
    wx.navigateBack()
  },
})