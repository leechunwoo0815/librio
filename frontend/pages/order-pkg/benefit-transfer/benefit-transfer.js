// frontend/pages/order-pkg/benefit-transfer/benefit-transfer.js
const api = require('../../utils/api')
const auth = require('../../utils/auth')

const statusMap = {
  0: '体验用户',
  1: '观察期会员',
  2: '正式会员',
  3: '已过期',
  4: '已退出',
}

Page({
  data: {
    children: [],
    sourceChild: null,
    targetChild: null,
    targetOptions: [],
    sourceStatusText: '',
    targetStatusText: '',
    loading: true,
    submitting: false,
    daysUsed: 0,
    daysRemaining: 0,
    checks: [],
    records: [],
    recordsLoading: true,
  },

  onLoad() {
    if (!auth.requireAuth()) return
    this.computeBenefitData(auth.getCurrentChild())
    this.loadRecords()
  },

  async onShow() {
    await this.loadChildren()
  },

  async loadChildren() {
    this.setData({ loading: true })
    try {
      const children = await api.getChildren()
      const safeChildren = children || []
      const currentChild = auth.getCurrentChild()
      const sourceChild = safeChildren.find(c => c.id === (currentChild ? currentChild.id : 0)) || safeChildren[0] || null
      const targetOptions = sourceChild ? safeChildren.filter(c => c.id !== sourceChild.id) : safeChildren

      this.setData({
        children,
        sourceChild,
        targetChild: null,
        targetOptions,
        sourceStatusText: sourceChild ? (statusMap[sourceChild.status] || '体验用户') : '',
        targetStatusText: '',
        loading: false,
      })
      this.computeBenefitData(sourceChild)
    } catch (e) {
      console.error(e)
      this.setData({ loading: false })
    }
  },

  computeBenefitData(child) {
    if (!child) {
      this.setData({ daysUsed: 0, daysRemaining: 0, checks: [] })
      return
    }

    const checks = []
    let daysUsed = 0
    let daysRemaining = 0

    if (child.member_start_time) {
      const start = new Date(child.member_start_time.replace(' ', 'T'))
      const now = new Date()
      daysUsed = Math.max(0, Math.floor((now - start) / (1000 * 60 * 60 * 24)))
    }

    if (child.member_expire_time) {
      const expire = new Date(child.member_expire_time.replace(' ', 'T'))
      const now = new Date()
      daysRemaining = Math.max(0, Math.floor((expire - now) / (1000 * 60 * 60 * 24)))
    }

    if (child.status === 0) {
      checks.push({ pass: false, text: '体验用户，暂无权益可转让' })
    } else if (child.status === 3) {
      checks.push({ pass: false, text: '该孩子会员已过期，无权益可转让' })
    } else if (child.status === 4) {
      checks.push({ pass: false, text: '该孩子已退出，无权益可转让' })
    }

    this.setData({ daysUsed, daysRemaining, checks })
  },

  onSourceChange(e) {
    const idx = e.detail.value
    const sourceChild = this.data.children[idx]
    const targetOptions = (this.data.children || []).filter(c => c.id !== sourceChild.id)
    const targetChild = this.data.targetChild && this.data.targetChild.id === sourceChild.id ? null : this.data.targetChild
    this.setData({
      sourceChild,
      targetChild,
      targetOptions,
      sourceStatusText: statusMap[sourceChild.status] || '体验用户',
    })
    this.computeBenefitData(sourceChild)
  },

  onTargetChange(e) {
    const idx = e.currentTarget.dataset.idx
    const targetChild = this.data.targetOptions[idx]
    this.setData({
      targetChild,
      targetStatusText: statusMap[targetChild.status] || '体验用户',
    })
  },

  async onConfirmTransfer() {
    const { sourceChild, targetChild } = this.data
    if (!sourceChild || !targetChild) {
      wx.showToast({ title: '请选择目标孩子', icon: 'none' })
      return
    }

    const sourceStatusText = statusMap[sourceChild.status] || '体验用户'
    const res = await wx.showModal({
      title: '确认转让',
      content: `确定将 ${sourceChild.name} 的 ${sourceStatusText} 权益转让给 ${targetChild.name} 吗？转让后 ${sourceChild.name} 的会员将变为已过期。`,
      confirmText: '确认转让',
      confirmColor: '#ef4444',
    })
    if (!res.confirm) return

    this.setData({ submitting: true })
    try {
      const res = await api.transferBenefit(sourceChild.id, targetChild.id)
      this.setData({ submitting: false })
      wx.showToast({ title: '申请已提交，等待管理员审核', icon: 'success' })
      this._navTimer = setTimeout(() => { wx.navigateBack() }, 1500)
    } catch (e) {
      wx.showToast({ title: e.message || '提交失败', icon: 'none' })
      this.setData({ submitting: false })
    }
  },

  async loadRecords() {
    this.setData({ recordsLoading: true })
    try {
      const records = await api.getTransferRecords()
      this.setData({ records: Array.isArray(records) ? records : [], recordsLoading: false })
    } catch (e) {
      console.error('Load records failed:', e)
      this.setData({ records: [], recordsLoading: false })
    }
  },

  onUnload() {
    if (this._navTimer) { clearTimeout(this._navTimer); this._navTimer = null }
  },
})
