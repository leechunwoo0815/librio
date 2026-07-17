const api = require('../../utils/api')
const auth = require('../../utils/auth')

Page({
  data: {
    activityDetail: null,
    isRegistered: false,
    capacityPercent: 0,
    remaining: 0,
    loading: true,
    toastVisible: false,
    toastMsg: '',
    enrollmentId: null,
    qrCodeUrl: '',
    isCheckinTime: false,
  },

  onLoad(options) {
    if (!auth.requireAuth()) return
    if (options.id) {
      this.loadActivityDetail(options.id)
    }
  },

  async loadActivityDetail(id) {
    this.setData({ loading: true })
    try {
      const detail = await api.getActivity(id)
      const registered = detail.enrollment_count || detail.registered_count || 0
      const capacity = detail.capacity || 1
      const pct = Math.min(Math.round((registered / capacity) * 100), 100)
      const enrollmentId = detail.enrollment_id || null

      const now = new Date()
      const startTime = new Date(detail.start_date)
      const endTime = new Date(detail.end_date)
      const oneHourBeforeStart = new Date(startTime.getTime() - 60 * 60 * 1000)
      const isCheckinTime = enrollmentId && now >= oneHourBeforeStart && now <= endTime

      this.setData({
        activityDetail: detail,
        isRegistered: detail.is_registered || false,
        capacityPercent: pct,
        remaining: capacity - registered,
        loading: false,
        enrollmentId,
        isCheckinTime,
      })

      if (enrollmentId) {
        const qrCodeUrl = await this.loadQrCode(enrollmentId)
        if (qrCodeUrl) {
          this.setData({ qrCodeUrl })
        }
      }
    } catch (e) {
      console.error(e)
      wx.showToast({ title: '加载活动详情失败', icon: 'none' })
      this.setData({ loading: false })
    }
  },

  async onRegister() {
    const id = this.data.activityDetail?.id
    if (!id) return
    const child = auth.getCurrentChild()
    if (!child) {
      wx.showToast({ title: '请先选择孩子', icon: 'none' })
      return
    }
    try {
      await api.enrollActivity(id, child.id)
      wx.showToast({ title: '报名成功', icon: 'success' })
      this.loadActivityDetail(id)
    } catch (e) {
      wx.showToast({ title: e.message || '报名失败', icon: 'none' })
    }
  },

  async onCancel() {
    const enrollmentId = this.data.enrollmentId
    if (!enrollmentId) { wx.showToast({ title: '未找到报名记录', icon: 'none' }); return }
    const activityId = this.data.activityDetail?.id
    try {
      await api.cancelEnrollment(enrollmentId)
      wx.showToast({ title: '已取消报名', icon: 'success' })
      this.loadActivityDetail(activityId)
    } catch (e) {
      wx.showToast({ title: e.message || '取消失败', icon: 'none' })
    }
  },

  async loadQrCode(enrollmentId) {
    try {
      const app = getApp()
      const baseURL = app.globalData.baseURL || 'https://api.dmkwords.cn'
      const scene = 'checkin_' + enrollmentId
      const page = 'pages/activity-pkg/activity-detail/activity-detail'
      const url = baseURL + '/wechat/qr-code?scene=' + scene + '&page=' + page
      const res = await new Promise((resolve, reject) => {
        wx.downloadFile({ url, success: (r) => resolve(r), fail: reject })
      })
      return res.tempFilePath
    } catch (e) {
      console.error('QR load failed:', e)
      return ''
    }
  },

  async onSelfCheckin() {
    const { enrollmentId } = this.data
    if (!enrollmentId) { wx.showToast({ title: '未找到报名记录', icon: 'none' }); return }
    try {
      await api.signIn(enrollmentId)
      wx.showToast({ title: '签到成功', icon: 'success' })
      this.setData({ isCheckinTime: false })
    } catch (e) {
      wx.showToast({ title: e.message || '签到失败', icon: 'none' })
    }
  },

  onShareAppMessage() {
    return {
      title: this.data.activityDetail?.title || '活动详情',
      path: `/pages/activity-pkg/activity-detail/activity-detail?id=${this.data.activityDetail?.id || ''}`,
    }
  },

  toggleFaq(e) {
    const index = e.currentTarget.dataset.index
    const detail = { ...this.data.activityDetail }
    const faqs = [...(detail.faqs || [])]
    faqs[index] = { ...faqs[index], open: !faqs[index].open }
    detail.faqs = faqs
    this.setData({ activityDetail: detail })
  },
})
