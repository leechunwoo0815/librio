// frontend/pages/member-pkg/learning-report/learning-report.js
const api = require('../../utils/api')
const auth = require('../../utils/auth')

Page({
  data: {
    loading: true,
    child: null,
    period: 'week',
    summary: null,
    trendData: [],
    maxMinutes: 1,
    suggestion: '',
    barLabels: [],
    testMode: false,
    reportTitle: '',
    reportPeriod: '',
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

  onShow() {
    if (this.data.testMode) return
    this.loadReport()
  },

  loadTestData() {
    this.setData({
      child: { id: 1, name: 'Mega' },
      summary: {
        total_minutes: 120,
        total_words: 8,
        books_finished: 8,
        checkin_days: 5,
      },
      trendData: [
        { date: '2026-06-03', minutes: 15, barHeight: 40, label: '一' },
        { date: '2026-06-04', minutes: 20, barHeight: 50, label: '二' },
        { date: '2026-06-05', minutes: 22, barHeight: 60, label: '三' },
        { date: '2026-06-06', minutes: 28, barHeight: 75, label: '四' },
        { date: '2026-06-07', minutes: 30, barHeight: 85, label: '五' },
        { date: '2026-06-08', minutes: 5, barHeight: 15, label: '六' },
        { date: '2026-06-09', minutes: 0, barHeight: 0, label: '日' },
      ],
      suggestion: '本周 AR 值稳步提升至 4.4，阅读速度也有明显进步。建议继续保持每天 20 分钟阅读习惯，可以开始尝试 AR 4.5-5.0 级别的桥梁书，挑战稍长篇幅的章节书。',
      reportTitle: '本周学习报告',
      reportPeriod: '2026年6月 · 第1周',
      loading: false,
    })
  },

  async loadReport() {
    this.setData({ loading: true })
    try {
      const child = auth.getCurrentChild()
      if (!child) {
        const children = await api.getChildren()
        if (!children || children.length === 0) {
          this.setData({ loading: false })
          return
        }
        this.setData({ child: children[0] })
        await this.fetchData(children[0].id)
      } else {
        this.setData({ child })
        await this.fetchData(child.id)
      }
    } catch (e) {
      console.error('Load learning report failed:', e)
      this.setData({ loading: false })
    }
  },

  async fetchData(childId) {
    const { period } = this.data
    const days = period === 'week' ? 7 : 30

    try {
      const [summary, trend, learningReport] = await Promise.all([
        api.getStatsSummary(childId).catch(() => ({})),
        api.getTrend(childId, days).catch(() => []),
        api.getLearningReport(childId).catch(() => null),
      ])

      const recentTrend = Array.isArray(trend) ? trend.slice(-7) : []
      const maxVal = Math.max(1, ...recentTrend.map(d => d.reading_minutes || d.minutes || 0))
      const barData = recentTrend.map(d => ({
        ...d,
        minutes: d.reading_minutes || d.minutes || 0,
        barHeight: Math.round(((d.reading_minutes || d.minutes || 0) / maxVal) * 100),
        label: this.formatBarLabel(d.date),
      }))
      const barLabels = barData.map(d => d.label)

      const now = new Date()
      const reportPeriod = period === 'week'
        ? `${now.getFullYear()}年${now.getMonth() + 1}月 · 第${Math.ceil(now.getDate() / 7)}周`
        : `${now.getFullYear()}年${now.getMonth() + 1}月`

      this.setData({
        summary: {
          total_minutes: summary.total_reading_minutes || summary.total_minutes || 0,
          total_words: summary.total_words_read || summary.total_words || 0,
          books_finished: summary.total_books_read || summary.books_finished || 0,
          checkin_days: summary.checkin_days || summary.total_checkin_days || 0,
        },
        learningReport: learningReport || null,
        trendData: barData,
        maxMinutes: maxVal,
        suggestion: summary.suggestion || '',
        barLabels,
        reportTitle: period === 'week' ? '本周学习报告' : '本月学习报告',
        reportPeriod,
        loading: false,
      })
    } catch (e) {
      console.error('Fetch report data failed:', e)
      this.setData({ loading: false })
    }
  },

  switchPeriod(e) {
    const period = e.currentTarget.dataset.period
    if (period === this.data.period) return
    this.setData({ period })
    if (this.data.child) {
      this.fetchData(this.data.child.id)
    }
  },

  formatBarLabel(dateStr) {
    if (!dateStr) return ''
    const d = new Date(dateStr)
    const days = ['日', '一', '二', '三', '四', '五', '六']
    return days[d.getDay()]
  },

  onShareAppMessage() {
    const child = this.data.child
    const name = child ? child.name : '小朋友'
    return {
      title: `${name}的学习报告 - MegaWords`,
      path: '/pages/member-pkg/learning-report/learning-report',
    }
  },

  onShareTap() {
    wx.showShareMenu({ withShareTicket: true })
  },
})
