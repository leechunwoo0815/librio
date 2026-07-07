// frontend/pages/order-pkg/refund-apply/refund-apply.js
const api = require('../../utils/api')
const auth = require('../../utils/auth')
const storage = require('../../utils/storage')

const orderTypeMap = {
  observation: '观察期',
  official: '正式会员',
}

Page({
  data: {
    orders: [],
    orderNames: [],
    selectedOrderIndex: 0,
    selectedOrder: null,
    usedDays: 0,
    reason: '',
    refundAmount: 0,
    loading: true,
    submitting: false,
    dailyRate: 0,
    usedAmount: 0,
    totalDays: 30,
  },

  onLoad() {
    const app = getApp()
    if (!auth.requireAuth()) return
  },

  async onShow() {
    // MP-026: 检测退款草稿
    this._checkDraft()
    await this.loadOrders()
  },

  _checkDraft() {
    var draft = storage.getDraft('refund')
    if (draft && draft.reason) {
      var that = this
      wx.showModal({
        title: '恢复草稿',
        content: '检测到上次未完成的退款申请，是否恢复填写内容？',
        success: function(res) {
          if (res.confirm) {
            that.setData({
              usedDays: draft.usedDays || 0,
              reason: draft.reason || '',
              selectedOrderIndex: draft.selectedOrderIndex || 0,
            })
          } else {
            storage.clearDraft('refund')
          }
        }
      })
    }
  },

  _saveDraft() {
    storage.saveDraft('refund', {
      selectedOrderIndex: this.data.selectedOrderIndex,
      usedDays: this.data.usedDays,
      reason: this.data.reason,
    })
  },

  async loadOrders() {
    this.setData({ loading: true })
    try {
      // 只加载第一页（后端已按用户过滤，无需全量加载）
      const res = await api.getOrders(1)
      const items = Array.isArray(res) ? res : (res.items || res.data || [])

      const paidOrders = items.filter(o => o.pay_status === 1)
      const orderNames = paidOrders.map(o => {
        const type = orderTypeMap[o.type] || o.type
        return `${type} - ${o.amount}元`
      })

      this.setData({
        orders: paidOrders,
        orderNames,
        selectedOrder: paidOrders.length > 0 ? paidOrders[0] : null,
        selectedOrderIndex: 0,
        loading: false,
      })

      this.calcRefund()
    } catch (e) {
      console.error(e)
      this.setData({ loading: false })
    }
  },

  onOrderChange(e) {
    const idx = e.detail.value
    this.setData({
      selectedOrderIndex: idx,
      selectedOrder: this.data.orders[idx],
      usedDays: 0,
    })
    this.calcRefund()
  },

  onUsedDaysInput(e) {
    let val = parseInt(e.detail.value) || 0
    if (val < 0) val = 0
    this.setData({ usedDays: val })
    this.calcRefund()
  },

  onReasonInput(e) {
    this.setData({ reason: e.detail.value })
    this._saveDraft()
  },

  async calcRefund() {
    const { selectedOrder, usedDays } = this.data
    if (!selectedOrder) {
      this.setData({ refundAmount: 0, dailyRate: 0, usedAmount: 0, totalDays: 30 })
      return
    }

    // 退款金额由后端计算，前端仅展示
    try {
      const preview = await require('../../utils/api').getRefundPreview(selectedOrder.id, usedDays)
      const refund = preview.refund_amount || 0
      const amount = selectedOrder.amount || 0
      const dailyRate = Math.round((amount / (selectedOrder.type === 'official' ? 365 : 30)) * 100) / 100
      const usedAmount = Math.round((amount - refund) * 100) / 100
      const totalDays = selectedOrder.type === 'official' ? 365 : 30
      this.setData({
        refundAmount: Math.round(refund * 100) / 100,
        dailyRate,
        usedAmount,
        totalDays,
      })
    } catch (e) {
      // 降级：前端估算
      const amount = selectedOrder.amount || 0
      const totalDays = selectedOrder.type === 'official' ? 365 : 30
      const refund = Math.max(0, amount - (amount / totalDays * usedDays))
      this.setData({
        refundAmount: Math.round(refund * 100) / 100,
        dailyRate: Math.round((amount / totalDays) * 100) / 100,
        usedAmount: Math.round((amount / totalDays * usedDays) * 100) / 100,
        totalDays,
      })
    }
  },

  async onSubmitRefund() {
    const { selectedOrder, usedDays, reason, refundAmount } = this.data
    if (!selectedOrder) {
      wx.showToast({ title: '请选择订单', icon: 'none' })
      return
    }
    if (!reason.trim()) {
      wx.showToast({ title: '请填写退款原因', icon: 'none' })
      return
    }

    const res = await wx.showModal({
      title: '确认退款',
      content: `确定提交退款申请吗？预计退款金额: ${refundAmount} 元`,
      confirmText: '提交',
    })
    if (!res.confirm) return

    this.setData({ submitting: true })
    try {
      await api.applyRefund(selectedOrder.id, usedDays, reason.trim())
      storage.clearDraft('refund')
      wx.showToast({ title: '退款申请已提交', icon: 'success' })
      setTimeout(() => {
        wx.navigateBack()
      }, 1500)
    } catch (e) {
      wx.showToast({ title: e.message || '提交失败', icon: 'none' })
    } finally {
      this.setData({ submitting: false })
    }
  },
})
