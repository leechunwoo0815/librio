// frontend/pages/order-pkg/reservation/reservation.js
const api = require('../../utils/api')
const auth = require('../../utils/auth')

function formatTime(t) {
  if (!t) return ''
  return t.slice(0, 16).replace('T', ' ')
}

function computeCountdown(expiresAt) {
  if (!expiresAt) return null
  const diff = new Date(expiresAt).getTime() - Date.now()
  if (diff <= 0) return { text: '即将过期', urgent: true }
  const days = Math.floor(diff / 86400000)
  const hours = Math.floor((diff % 86400000) / 3600000)
  return {
    text: '\u5269\u4F59 ' + days + '\u5929 ' + hours + '\u5C0F\u65F6',
    urgent: diff < 21600000,
  }
}

Page({
  data: {
    activeReservations: [],
    expiredReservations: [],
    loading: true,
  },

  onLoad() {
    if (!auth.requireAuth()) return
    this.loadReservations()
  },

  onPullDownRefresh() {
    this.loadReservations().then(() => wx.stopPullDownRefresh())
  },

  async loadReservations() {
    this.setData({ loading: true })
    try {
      const child = auth.getCurrentChild()
      if (!child) {
        this.setData({ activeReservations: [], expiredReservations: [], loading: false })
        return
      }
      const res = await api.getReservations(child.id)
      const raw = Array.isArray(res) ? res : (res.list || [])
      const mapped = raw.map(r => {
        const cd = computeCountdown(r.expiresAt)
        return {
          ...r,
          formattedTime: formatTime(r.reservedAt),
          countdownText: cd ? cd.text : '',
          isUrgent: cd ? cd.urgent : false,
          showCountdown: r.status === 'active' && !!cd,
          showQueue: r.status === 'queue',
          queueText: r.queuePosition ? '\u6392\u961F\u4E2D \u7B2C' + r.queuePosition + '\u4F4D' : '\u6392\u961F\u4E2D',
          expiredBadgeText: r.status === 'cancelled' ? '\u5DF2\u53D6\u6D88' : '\u5DF2\u8FC7\u671F',
        }
      })
      this.setData({
        activeReservations: mapped.filter(r => r.status === 'active' || r.status === 'queue'),
        expiredReservations: mapped.filter(r => r.status === 'expired' || r.status === 'cancelled'),
      })
    } catch (e) {
      console.error('Load reservations failed:', e)
      wx.showToast({ title: '\u52A0\u8F7D\u5931\u8D25', icon: 'none' })
    } finally {
      this.setData({ loading: false })
    }
  },

  fulfillReservation(e) {
    const id = e.currentTarget.dataset.id
    const child = auth.getCurrentChild()
    if (!child) { wx.showToast({ title: '请先选择孩子', icon: 'none' }); return }
    wx.showModal({
      title: '确认取书',
      content: '确定要兑现该预约并借阅此书吗？',
      success: async (res) => {
        if (!res.confirm) return
        try {
          await api.fulfillReservation(id, child.id)
          wx.showToast({ title: '取书成功', icon: 'success' })
          this.loadReservations()
        } catch (err) {
          wx.showToast({ title: err.message || '取书失败', icon: 'none' })
        }
      },
    })
  },

  cancelReservation(e) {
    const id = e.currentTarget.dataset.id
    wx.showModal({
      title: '\u786E\u8BA4\u53D6\u6D88',
      content: '\u786E\u5B9A\u8981\u53D6\u6D88\u8BE5\u9884\u7EA6\u5417\uFF1F',
      success: async (res) => {
        if (!res.confirm) return
        try {
          await api.cancelReservation(id)
          wx.showToast({ title: '\u5DF2\u53D6\u6D88', icon: 'success' })
          this.loadReservations()
        } catch (err) {
          wx.showToast({ title: '\u53D6\u6D88\u5931\u8D25', icon: 'none' })
        }
      },
    })
  },

  goBack() {
    wx.navigateBack()
  },
})
