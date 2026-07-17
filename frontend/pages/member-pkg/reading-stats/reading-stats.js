// frontend/pages/member-pkg/reading-stats/reading-stats.js
const api = require('../../utils/api')
const auth = require('../../utils/auth')

Page({
  data: {
    child: null,
    summary: null,
    todayStats: null,
    trend: [],
    trendMax: 1,
    wordTrend: [],
    leaderboard: [],
    restLeaderboard: [],
    myRank: null,
    myScore: null,
    days: 7,
    period: 'day',
    booksRead: [],
  },

  async onShow() {
    if (!auth.requireAuth()) return
    await this.loadData()
  },

  async loadData() {
    try {
      const children = await api.getChildren()
      if (!children || children.length === 0) return

      const child = auth.selectChild(children)
      if (!child) return
      this.setData({ child })

      const [summary, todayStats, trend, board, bookshelf] = await Promise.all([
        api.getStatsSummary(child.id).catch((err) => { console.error('[getStatsSummary failed]', err); return {} }),
        api.getTodayStats(child.id).catch((err) => { console.error('[getTodayStats failed]', err); return {} }),
        api.getTrend(child.id, this.data.days).catch((err) => { console.error('[getTrend failed]', err); return [] }),
        api.getLeaderboard('total', null, 100).catch((err) => { console.error('[getLeaderboard failed]', err); return [] }),
        api.getBookshelf(child.id).catch((err) => { console.error('[getBookshelf failed]', err); return [] }),
      ])

      // Process trend for bar chart
      const trendArr = Array.isArray(trend) ? trend : []
      const maxVal = trendArr.reduce((m, d) => Math.max(m, d.reading_minutes || 0), 1)
      const trendDisplay = trendArr.map(d => ({
        ...d,
        label: (d.date || '').slice(5),
        reading_minutes: d.reading_minutes || 0,
        barHeight: Math.round(((d.reading_minutes || 0) / maxVal) * 100),
      }))

      // Process word trend for word count bar chart
      const wordMaxVal = trendArr.reduce((m, d) => Math.max(m, d.words_read || 0), 1)
      const wordTrendDisplay = trendArr.map(d => ({
        ...d,
        label: (d.date || '').slice(5),
        words_read: d.words_read || 0,
        barHeight: Math.round(((d.words_read || 0) / wordMaxVal) * 100),
      }))

      // Process bookshelf into booksRead
      const shelfItems = Array.isArray(bookshelf) ? bookshelf : []
      const booksRead = shelfItems.slice(0, 20).map(item => ({
        name: item.title || item.name || '',
        emoji: item.emoji || '📚',
        bgColor: item.bg_color || '#f0f4ff',
      }))

      // Process leaderboard: top 3 + rest + current user rank
      const boardArr = Array.isArray(board) ? board : []
      const top3 = boardArr.slice(0, 3)
      const rest = boardArr.slice(3, 10).map((item, idx) => ({
        ...item,
        rank: idx + 4,
        isMe: item.child_id === child.id,
      }))
      const myIdx = boardArr.findIndex(r => r.child_id === child.id)
      const myRank = myIdx >= 0 ? myIdx + 1 : null
      const myScore = myIdx >= 0 ? boardArr[myIdx].score : null

      this.setData({
        summary,
        todayStats,
        trend: trendDisplay,
        trendMax: maxVal,
        wordTrend: wordTrendDisplay,
        leaderboard: top3,
        restLeaderboard: rest,
        myRank,
        myScore,
        booksRead,
      })
    } catch (e) {
      console.error('loadData failed:', e)
    }
  },

  switchPeriod(e) {
    const period = e.currentTarget.dataset.period
    const days = period === 'day' ? 1 : period === 'week' ? 7 : period === 'month' ? 30 : 365
    this.setData({ period, days })
    this.loadData()
  },

  goLeaderboard() {
    wx.navigateTo({ url: '/pages/member-pkg/leaderboard/leaderboard' })
  },

  goWeekReport() {
    wx.navigateTo({ url: '/pages/member-pkg/learning-report/learning-report?type=week' })
  },

  goMonthReport() {
    wx.navigateTo({ url: '/pages/member-pkg/learning-report/learning-report?type=month' })
  },
})
