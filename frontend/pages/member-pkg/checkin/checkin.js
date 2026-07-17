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
      const [streak, calendar, todayStats, records] = await Promise.all([
        api.getStreak(child.id).catch(() => ({ current_streak: 0, longest_streak: 0 })),
        api.getCheckinCalendar(child.id, year, month).catch(() => []),
        api.getTodayStats(child.id).catch(() => null),
        api.getCheckinRecords(child.id).catch(() => []),
      ])

      const checkinArr = (calendar || []).map(d => String(d))
      const checkedToday = checkinArr.indexOf(this.data.todayStr) >= 0
      const gridCells = this.buildGrid(year, month, checkinArr)

      this.setData({
        streak,
        calendar: calendar || [],
        checkinArr,
        gridCells,
        checkedToday,
        todayStats,
        records,
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

  buildGrid(year, month, checkinArr) {
    const checkinSet = new Set(checkinArr)
    const daysInMonth = new Date(year, month, 0).getDate()
    const cells = []

    const firstDay = new Date(year, month - 1, 1).getDay()
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
      const checkinArr = (calendar || []).map(d => String(d))
      const gridCells = this.buildGrid(year, month, checkinArr)
      this.setData({ calendar: calendar || [], checkinArr, gridCells })
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
