const api = require('../../utils/api')
const auth = require('../../utils/auth')

// Activity status: 0=未发布 1=报名中 2=报名截止 3=进行中 4=已结束 5=已取消
const statusTextMap = {
  0: '未发布',
  1: '报名中',
  2: '报名截止',
  3: '进行中',
  4: '已结束',
  5: '已取消',
}

const statusClassMap = {
  1: 'status-open',
  2: 'status-full',
  3: 'status-open',
  4: 'status-past',
  5: 'status-past',
}

// ActivityEnrollment status: 0=待审核 1=已通过 2=已拒绝 3=已取消 4=已签到
function mapEnrollment(a) {
  const es = a.my_enrollment_status
  return {
    enrolled: es === 0 || es === 1,
    checked_in: es === 4,
    enrollment_id: a.my_enrollment_id || null,
  }
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
      const child = auth.getCurrentChild()
      const res = await api.getActivities(child && child.id)
      const fmt = (t) => (t || '').slice(0, 10)
      const activities = (Array.isArray(res) ? res : (res.items || res.data || []))
        .filter(a => a.status !== 0 && a.status !== 5)  // 用户端不显示未发布/已取消
        .map(a => {
          const enr = mapEnrollment(a)
          return {
            ...a,
            start_date: fmt(a.start_time),
            end_date: fmt(a.end_time),
            enrollment_count: a.current_participants || 0,
            capacity: a.max_participants || 0,
            activity_started: a.status === 3,
            ...enr,
            statusText: statusTextMap[a.status] || a.status,
            statusClass: statusClassMap[a.status] || '',
            bannerText: a.title || '',
          }
        })
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
      filtered = activities.filter(a => a.status !== 4)
    } else {
      filtered = activities.filter(a => a.status === 4)
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
