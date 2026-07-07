// frontend/pages/activity-pkg/activity/activity.js
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
    testMode: false,
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
    await this.loadActivities()
  },

  loadTestData() {
    const testActivities = [
      {
        id: 1,
        title: '「好饿的毛毛虫」主题故事会',
        bannerText: '英文绘本故事会',
        start_date: '6月14日（周六）10:00',
        end_date: '',
        location: '人广馆',
        enrollment_count: 12,
        max_participants: 15,
        status: 'registering',
        statusText: '报名中',
        statusClass: 'status-open',
      },
      {
        id: 2,
        title: '暑期 AR 阅读 30 天挑战',
        bannerText: 'AR 阅读挑战赛',
        start_date: '7月1日',
        end_date: '7月30日',
        location: '全场馆',
        enrollment_count: 38,
        max_participants: 50,
        status: 'registering',
        statusText: '报名中',
        statusClass: 'status-open',
      },
      {
        id: 3,
        title: '「Love You Forever」母亲节亲子阅读',
        bannerText: '母亲节特别活动',
        start_date: '5月11日（周日）',
        end_date: '',
        location: '人广馆',
        enrollment_count: 15,
        max_participants: 15,
        status: 'ended',
        statusText: '已结束',
        statusClass: 'status-past',
      },
    ]
    this.setData({ activities: testActivities })
    this.applyFilter()
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
      this.setData({
        activities,
        loading: false,
      })
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
    this.setData({
      expandedId: this.data.expandedId === id ? 0 : id,
    })
  },

  async onEnrollActivity(e) {
    const activityId = e.currentTarget.dataset.id
    const child = require('../../utils/auth').getCurrentChild()
    if (!child) {
      wx.showToast({ title: '请先选择孩子', icon: 'none' })
      return
    }
    try {
      await require('../../utils/api').enrollActivity(activityId, child.id)
      wx.showToast({ title: '报名成功', icon: 'success' })
      this.loadActivities()
    } catch (err) {
      wx.showToast({ title: err.message || '报名失败', icon: 'none' })
    }
  },
})
