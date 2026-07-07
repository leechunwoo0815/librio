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
    testMode: false,
    daysUsed: 0,
    daysRemaining: 0,
    checks: [],
  },

  onLoad() {
    const app = getApp()
    if (app.globalData.isTestMode) {
      this.setData({ testMode: true, loading: false })
      this.loadTestData()
      return
    }
    if (!auth.requireAuth()) return
  },

  async onShow() {
    if (this.data.testMode) return
    await this.loadChildren()
  },

  loadTestData() {
    const testChildren = [
      { id: 1, name: 'Mega', age: 8, level: 3, avatar: '👦', avatarClass: 'a', status: 2 },
      { id: 2, name: 'Mini', age: 5, level: 1, avatar: '👧', avatarClass: 'b', status: 0 },
      { id: 3, name: '小明', age: 10, level: 5, avatar: '👦', avatarClass: 'a', status: 2 },
    ]
    this.setData({
      children: testChildren,
      sourceChild: testChildren[0],
      targetOptions: testChildren.filter(c => c.id !== testChildren[0].id),
      sourceStatusText: statusMap[testChildren[0].status] || '体验用户',
      targetChild: null,
      targetStatusText: '',
      daysUsed: 45,
      daysRemaining: 320,
      checks: [
        { text: '所有图书已归还（0 本在借）', pass: true },
        { text: '无未完成的测验', pass: true },
        { text: '无未处理的退款申请', pass: true },
      ],
    })
  },

  async loadChildren() {
    this.setData({ loading: true })
    try {
      const children = await api.getChildren()
      const currentChild = auth.getCurrentChild()
      const sourceChild = children.find(c => c.id === (currentChild ? currentChild.id : 0)) || children[0] || null
      const targetOptions = sourceChild ? children.filter(c => c.id !== sourceChild.id) : children

      this.setData({
        children,
        sourceChild,
        targetChild: null,
        targetOptions,
        sourceStatusText: sourceChild ? (statusMap[sourceChild.status] || '体验用户') : '',
        targetStatusText: '',
        loading: false,
      })
    } catch (e) {
      console.error(e)
      this.setData({ loading: false })
    }
  },

  onSourceChange(e) {
    const idx = e.detail.value
    const sourceChild = this.data.children[idx]
    const targetOptions = this.data.children.filter(c => c.id !== sourceChild.id)
    const targetChild = this.data.targetChild && this.data.targetChild.id === sourceChild.id ? null : this.data.targetChild
    this.setData({
      sourceChild,
      targetChild,
      targetOptions,
      sourceStatusText: statusMap[sourceChild.status] || '体验用户',
    })
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
      await api.transferBenefit(sourceChild.id, targetChild.id)
      wx.showToast({ title: '转让成功', icon: 'success' })
      await this.loadChildren()
    } catch (e) {
      wx.showToast({ title: e.message || '转让失败', icon: 'none' })
    } finally {
      this.setData({ submitting: false })
    }
  },
})
