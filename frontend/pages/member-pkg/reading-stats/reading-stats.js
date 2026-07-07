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
    const app = getApp()
    if (app.globalData.isTestMode) {
      this._loadTestModeData()
      return
    }
    if (!auth.requireAuth()) return
    await this.loadData()
  },

  _loadTestModeData() {
    const leaderboard = [
      { child_id: '1', child_name: 'Tom', score: 3120, avatar: '🧑' },
      { child_id: '2', child_name: 'Lily', score: 2450, avatar: '👩' },
      { child_id: '3', child_name: '小明', score: 1980, avatar: '👦' },
      { child_id: '4', child_name: 'Anna', score: 1650, avatar: '🐶' },
      { child_id: '5', child_name: 'Mike', score: 1520, avatar: '🐻' },
      { child_id: '6', child_name: 'Emma', score: 1380, avatar: '🦊' },
      { child_id: '7', child_name: 'Mega', score: 1200, avatar: '🐱' },
    ]

    const trend = [
      { date: '2026-05-29', reading_minutes: 20, label: '5/29', barHeight: 50 },
      { date: '2026-05-30', reading_minutes: 28, label: '5/30', barHeight: 69 },
      { date: '2026-05-31', reading_minutes: 35, label: '5/31', barHeight: 88 },
      { date: '2026-06-01', reading_minutes: 15, label: '6/1', barHeight: 38 },
      { date: '2026-06-02', reading_minutes: 32, label: '6/2', barHeight: 80 },
      { date: '2026-06-03', reading_minutes: 40, label: '6/3', barHeight: 100 },
      { date: '2026-06-04', reading_minutes: 25, label: '6/4', barHeight: 63, isToday: true },
    ]

    const wordTrend = [
      { date: '2026-05-29', words: 180, label: '5/29', barHeight: 56 },
      { date: '2026-05-30', words: 250, label: '5/30', barHeight: 78 },
      { date: '2026-05-31', words: 300, label: '5/31', barHeight: 94 },
      { date: '2026-06-01', words: 200, label: '6/1', barHeight: 63 },
      { date: '2026-06-02', words: 270, label: '6/2', barHeight: 84 },
      { date: '2026-06-03', words: 320, label: '6/3', barHeight: 100 },
      { date: '2026-06-04', words: 280, label: '6/4', barHeight: 88, isToday: true },
    ]

    this.setData({
      summary: {
        total_reading_minutes: 120,
        total_words_read: 3200,
        books_finished: 3,
        vocabulary_count: 47,
        level_name: '词汇新手',
        level_letter: 'B',
        books_for_next_level: 8,
        next_level_name: '故事探索者',
        badge_count: 5,
        streak_days: 12,
        perfect_quizzes: 3,
      },
      todayStats: {
        reading_minutes: 25,
        pages_read: 12,
        new_words: 5,
        words_read: 320,
      },
      trend,
      trendMax: 40,
      wordTrend,
      leaderboard: leaderboard.slice(0, 3),
      restLeaderboard: leaderboard.slice(3).map((item, idx) => ({
        ...item,
        rank: idx + 4,
        isMe: item.child_id === '7',
      })),
      myRank: 7,
      myScore: 1200,
      booksRead: [
        { emoji: '🐛', name: 'The Very Hungry Caterpillar', bgColor: 'rgba(96, 212, 130, 0.15)' },
        { emoji: '🐘', name: 'Horton Hears a Who!', bgColor: 'rgba(232, 163, 23, 0.15)' },
        { emoji: '🐱', name: 'The Cat in the Hat', bgColor: 'rgba(123, 104, 238, 0.12)' },
        { emoji: '🐶', name: 'Go, Dog. Go!', bgColor: 'rgba(52, 199, 89, 0.15)' },
        { emoji: '🐻', name: 'Brown Bear', bgColor: 'rgba(215, 60, 60, 0.08)' },
      ],
    })
  },

  async loadData() {
    try {
      const children = await api.getChildren()
      if (!children || children.length === 0) return

      const child = auth.selectChild(children)
      if (!child) return
      this.setData({ child })

      const [summary, todayStats, trend, board] = await Promise.all([
        api.getStatsSummary(child.id).catch(() => ({})),
        api.getTodayStats(child.id).catch(() => ({})),
        api.getTrend(child.id, this.data.days).catch(() => []),
        api.getLeaderboard('total', null, 100).catch(() => []),
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
        wordTrend: trendDisplay,
        leaderboard: top3,
        restLeaderboard: rest,
        myRank,
        myScore,
      })
    } catch (e) {
      console.error('loadData failed:', e)
    }
  },

  switchPeriod(e) {
    const period = e.currentTarget.dataset.period
    this.setData({ period })
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
