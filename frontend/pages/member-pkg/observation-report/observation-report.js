// frontend/pages/member-pkg/observation-report/observation-report.js
const api = require('../../utils/api')
const auth = require('../../utils/auth')

Page({
  data: {
    loading: true,
    report: null,
    child: null,
    passRate: 0,
    weeklyData: [],
    levelInfo: null,
    remainingWords: 0,
    nextLevelName: '',
  },

  onLoad(options) {
    const app = getApp()
    if (!auth.requireAuth()) return
    this.loadReport()
  },

  goBack() {
    wx.navigateBack()
  },

  async loadReport() {
    this.setData({ loading: true })
    try {
      const child = auth.getCurrentChild()
      let childId
      if (!child) {
        const children = await api.getChildren()
        if (!children || children.length === 0) {
          this.setData({ loading: false, report: null })
          return
        }
        this.setData({ child: children[0] })
        childId = children[0].id
      } else {
        this.setData({ child })
        childId = child.id
      }
      await this.fetchReport(childId)
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
        try { await api.markReportViewed(report.id) } catch (e) { console.error('[markReportViewed failed]', e) }
      }

      // 并发加载周数据和级别信息
      await Promise.all([
        this.loadWeeklyData(childId),
        this.loadLevelInfo(childId, report),
      ])
    } catch (e) {
      console.error('Fetch report failed:', e)
      this.setData({ report: null, loading: false })
    }
  },

  async loadWeeklyData(childId) {
    try {
      const trend = await api.getTrend(childId, 42)
      if (!trend || !trend.length) return
      const weekMap = {}
      trend.forEach(d => {
        function getISOWeekNumber(d) {
          const date = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()))
          const dayNum = date.getUTCDay() || 7
          date.setUTCDate(date.getUTCDate() + 4 - dayNum)
          const yearStart = new Date(Date.UTC(date.getUTCFullYear(), 0, 1))
          return Math.ceil((((date - yearStart) / 86400000) + 1) / 7)
        }
        const date = new Date(d.date)
        const year = date.getFullYear()
        const week = getISOWeekNumber(date)
        const key = year + '-W' + String(week).padStart(2, '0')
        weekMap[key] = (weekMap[key] || 0) + (d.words_read || 0)
      })
      const maxWords = Math.max(...Object.values(weekMap), 1)
      const weeks = Object.keys(weekMap)
      const weeklyData = weeks.slice(-6).map((key, i, arr) => ({
        week: key.slice(-2) + '周',
        words: weekMap[key],
        percent: Math.round(weekMap[key] / maxWords * 100),
        isThisWeek: i === arr.length - 1,
      }))
      this.setData({ weeklyData })
    } catch (e) {
      console.error('Load weekly data failed:', e)
    }
  },

  async loadLevelInfo(childId, report) {
    try {
      const [levelInfo, levels] = await Promise.all([
        api.getCurrentLevel(childId),
        api.getLevels(),
      ])
      if (!levelInfo) return
      const currentLevel = levels.find(l => l.id === levelInfo.level_id)
      if (!currentLevel) return
      const booksRead = levelInfo.books_read_at_level || 0
      const requiredBooks = currentLevel.required_books || 5
      const booksRemaining = Math.max(requiredBooks - booksRead, 0)
      const avgWords = report.total_books_read > 0
        ? Math.round((report.total_words_read || 0) / report.total_books_read)
        : 0
      const remainingWords = booksRemaining * avgWords
      const sortedLevels = [...levels].sort((a, b) => a.sort_order - b.sort_order)
      const nextIdx = sortedLevels.findIndex(l => l.id === levelInfo.level_id) + 1
      const nextLevelName = nextIdx < sortedLevels.length ? sortedLevels[nextIdx].name : ''
      this.setData({
        levelInfo: { ...levelInfo, required_books: requiredBooks, progress_pct: Math.round(booksRead / requiredBooks * 100) },
        remainingWords,
        nextLevelName,
      })
    } catch (e) {
      console.error('Load level info failed:', e)
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
