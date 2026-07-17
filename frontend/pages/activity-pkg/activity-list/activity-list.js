const api = require('../../utils/api')
const auth = require('../../utils/auth')

const statusTextMap = {
  registering: '报名中',
  registration_closed: '报名截止',
  in_progress: '进行中',
  ended: '已结束',
}

const statusClassMap = {
  registering: 'status-open',
  registration_closed: 'status-full',
  in_progress: 'status-open',
  ended: 'status-past',
}

Page({
  data: {
    activities: [],
    filteredActivities: [],
    filterTab: 'upcoming',
    loading: true,
  },

  onLoad() {
    if (!auth.requireAuth()) return
  },

  async onShow() {
    await this.loadActivities()
  },

  async loadActivities() {
    this.setData({ loading: true })
    try {
      const res = await api.getActivities()
      const activities = (Array.isArray(res) ? res : (res.items || res.data || [])).map(a => ({
        ...a,
        statusText: statusTextMap[a.status] || a.status,
        statusClass: statusClassMap[a.status] || '',
        bannerText: a.title || '',
      }))
      this.setData({ activities, loading: false })
      this.applyFilter()
    } catch (e) {
      console.error(e)
      this.setData({ loading: false })
    }
  },

  onFilterChange(e) {
    const tab = e.currentTarget.dataset.tab
    this.setData({ filterTab: tab })
    this.applyFilter()
  },

  applyFilter() {
    const { activities, filterTab } = this.data
    let filtered
    if (filterTab === 'upcoming') {
      filtered = activities.filter(a => a.status !== 'ended')
    } else {
      filtered = activities.filter(a => a.status === 'ended')
    }
    this.setData({ filteredActivities: filtered })
  },

  onTapActivity(e) {
    const id = e.currentTarget.dataset.id
    wx.navigateTo({
      url: `/pages/activity-pkg/activity-detail/activity-detail?id=${id}`,
    })
  },

  async onEnrollActivity(e) {
    const activityId = e.currentTarget.dataset.id
    const child = auth.getCurrentChild()
    if (!child) {
      wx.showToast({ title: '请先选择孩子', icon: 'none' })
      return
    }
    const activity = this.data.activities.find(a => a.id === activityId)
    const title = activity ? activity.title : '该活动'
    const modalRes = await wx.showModal({
      title: '确认报名',
      content: `确定要为 ${child.name} 报名「${title}」吗？`,
      confirmText: '确认报名',
    })
    if (!modalRes.confirm) return
    try {
      await api.enrollActivity(activityId, child.id)
      wx.showToast({ title: '报名成功', icon: 'success' })
      this.loadActivities()
    } catch (err) {
      wx.showToast({ title: err.message || '报名失败', icon: 'none' })
    }
  },

  async onCancelEnroll(e) {
    const enrollmentId = e.currentTarget.dataset.enrollmentid
    if (!enrollmentId) { wx.showToast({ title: '未找到报名记录', icon: 'none' }); return }
    try {
      await api.cancelEnrollment(enrollmentId)
      wx.showToast({ title: '已取消报名', icon: 'success' })
      this.loadActivities()
    } catch (err) {
      wx.showToast({ title: err.message || '取消失败', icon: 'none' })
    }
  },
})
