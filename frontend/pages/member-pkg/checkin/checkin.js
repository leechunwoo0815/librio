// frontend/pages/member-pkg/checkin/checkin.js
const api = require('../../utils/api')
const auth = require('../../utils/auth')

Page({
  data: {
    child: null,
    streak: { current_streak: 0, longest_streak: 0 },
    todayStats: null,
    calendar: [],
    gridCells: [],
    year: 2026,
    month: 6,
    yearMonth: '',
    todayStr: '',
    checkedToday: false,
    monthNames: ['一月', '二月', '三月', '四月', '五月', '六月', '七月', '八月', '九月', '十月', '十一月', '十二月'],
    streakBadges: [],
    records: [],
    loading: true,
    loadError: false,
  },

  async onShow() {
    const app = getApp()
    if (app.globalData.isTestMode) {
      this._loadTestModeData()
      return
    }
    if (!auth.requireAuth()) return

    const now = new Date()
    const todayStr = this.formatDate(now)
    this.setData({
      year: now.getFullYear(),
      month: now.getMonth() + 1,
      todayStr,
      yearMonth: this.buildYearMonth(now.getFullYear(), now.getMonth() + 1),
    })

    try {
      const children = await api.getChildren()
      if (!children || children.length === 0) return

      const child = auth.selectChild(children)
      if (!child) return
      this.setData({ child })

      await this.loadAllData()
    } catch (e) {
      console.error('onShow failed:', e)
    }
  },

  _loadTestModeData() {
    const streak = { current_streak: 21, longest_streak: 35 }
    const checkinDays = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21]
    const today = 10
    const checkinSet = new Set(checkinDays.map(d => '2026-06-' + String(d).padStart(2, '0')))
    const gridCells = this.buildGrid(2026, 6, checkinSet)

    this.setData({
      streak,
      year: 2026,
      month: 6,
      todayStr: '2026-06-10',
      yearMonth: '2026年6月',
      checkedToday: true,
      todayStats: {
        book_name: "Charlotte's Web",
        reading_minutes: 25,
        checkin_time: '08:32',
      },
      gridCells,
      calendar: checkinDays,
      streakBadges: this._buildBadges(streak.current_streak),
      records: [
        { date: '6月4日 星期三', book_name: "Charlotte's Web", pages: '第10-12页', duration: 25 },
        { date: '6月3日 星期二', book_name: 'Fantastic Mr. Fox', pages: '第8-13页', duration: 32 },
        { date: '6月2日 星期一', book_name: "Charlotte's Web", pages: '第6-9页', duration: 20 },
      ],
    })
  },

  _buildBadges(currentStreak) {
    const badges = [
      { target: 7, icon: '🏅', name: '7天徽章' },
      { target: 14, icon: '🎖️', name: '14天徽章' },
      { target: 21, icon: '🏆', name: '21天徽章' },
      { target: 30, icon: '👑', name: '30天徽章' },
    ]
    return badges.map(b => ({
      ...b,
      unlocked: currentStreak >= b.target,
    }))
  },

  async loadAllData() {
    const { child, year, month } = this.data
    if (!child) return

    this.setData({ loading: true, loadError: false })
    try {
      const [streak, calendar, todayStats] = await Promise.all([
        api.getStreak(child.id).catch(() => ({ current_streak: 0, longest_streak: 0 })),
        api.getCheckinCalendar(child.id, year, month).catch(() => []),
        api.getTodayStats(child.id).catch(() => null),
      ])

      const checkinSet = new Set((calendar || []).map(d => String(d)))
      const checkedToday = checkinSet.has(this.data.todayStr)
      const gridCells = this.buildGrid(year, month, checkinSet)

      this.setData({
        streak,
        calendar: calendar || [],
        checkinSet,
        gridCells,
        checkedToday,
        todayStats,
        streakBadges: this._buildBadges(streak.current_streak),
        loading: false,
        loadError: false,
      })
    } catch (e) {
      console.error('loadAllData failed:', e)
      this.setData({ loading: false, loadError: true })
    }
  },

  onRetry() {
    this.loadAllData()
  },

  buildGrid(year, month, checkinSet) {
    const firstDay = new Date(year, month - 1, 1).getDay()
    const daysInMonth = new Date(year, month, 0).getDate()
    const cells = []

    // Adjust so Monday = first column
    const adjustedFirstDay = firstDay === 0 ? 6 : firstDay - 1
    for (let i = 0; i < adjustedFirstDay; i++) {
      cells.push({ key: 'empty-' + i, empty: true })
    }
    for (let d = 1; d <= daysInMonth; d++) {
      const ds = this.formatDate(new Date(year, month - 1, d))
      cells.push({
        key: ds,
        day: d,
        dateStr: ds,
        checked: checkinSet.has(ds),
        isToday: ds === this.data.todayStr,
      })
    }
    return cells
  },

  buildYearMonth(year, month) {
    return year + '年' + month + '月'
  },

  formatDate(d) {
    const y = d.getFullYear()
    const m = String(d.getMonth() + 1).padStart(2, '0')
    const dd = String(d.getDate()).padStart(2, '0')
    return `${y}-${m}-${dd}`
  },

  prevMonth() {
    let { year, month } = this.data
    if (month === 1) { year--; month = 12 } else { month-- }
    this.setData({
      year,
      month,
      yearMonth: this.buildYearMonth(year, month),
    })
    this.loadMonth()
  },

  nextMonth() {
    let { year, month } = this.data
    if (month === 12) { year++; month = 1 } else { month++ }
    this.setData({
      year,
      month,
      yearMonth: this.buildYearMonth(year, month),
    })
    this.loadMonth()
  },

  async loadMonth() {
    const { child, year, month } = this.data
    if (!child) return

    try {
      const calendar = await api.getCheckinCalendar(child.id, year, month)
      const checkinSet = new Set((calendar || []).map(d => String(d)))
      const gridCells = this.buildGrid(year, month, checkinSet)
      this.setData({ calendar: calendar || [], checkinSet, gridCells })
    } catch (e) {
      console.error('loadMonth failed:', e)
    }
  },

  onShareAppMessage() {
    const { child, streak } = this.data
    const name = child ? (child.chinese_name || '小朋友') : '小朋友'
    return {
      title: `${name} 已连续打卡 ${streak.current_streak} 天，一起加油！`,
      path: '/pages/index/index',
    }
  },
})
