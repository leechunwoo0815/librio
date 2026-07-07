// frontend/pages/member-pkg/observation-report/observation-report.js
const api = require('../../utils/api')
const auth = require('../../utils/auth')

Page({
  data: {
    loading: true,
    report: null,
    child: null,
    passRate: 0,
  },

  onLoad(options) {
    const app = getApp()
    if (!auth.requireAuth()) return
    this.loadReport()
  },

  async loadReport() {
    this.setData({ loading: true })
    try {
      const child = auth.getCurrentChild()
      if (!child) {
        const children = await api.getChildren()
        if (!children || children.length === 0) {
          this.setData({ loading: false, report: null })
          return
        }
        this.setData({ child: children[0] })
        await this.fetchReport(children[0].id)
      } else {
        this.setData({ child })
        await this.fetchReport(child.id)
      }
    } catch (e) {
      console.error('Load observation report failed:', e)
      this.setData({ loading: false, report: null })
    }
  },

  async fetchReport(childId) {
    try {
      // 优先获取详情版报告
      const report = await api.getObservationReportDetail(childId).catch(() => api.getObservationReport(childId))
      const passRate = report.quizzes_attempted > 0
        ? Math.round(report.quizzes_passed / report.quizzes_attempted * 100)
        : 0
      this.setData({ report, passRate, loading: false })

      // 标记报告已查看
      if (report && report.id) {
        try { await api.markReportViewed(report.id) } catch (e) { /* silent */ }
      }
    } catch (e) {
      console.error('Fetch report failed:', e)
      this.setData({ report: null, loading: false })
    }
  },

  goToOfficial() {
    wx.navigateTo({ url: '/pages/order-pkg/official/official' })
  },

  formatDate(dateStr) {
    if (!dateStr) return ''
    const d = new Date(dateStr)
    const y = d.getFullYear()
    const m = String(d.getMonth() + 1).padStart(2, '0')
    const day = String(d.getDate()).padStart(2, '0')
    return `${y}.${m}.${day}`
  },
})
