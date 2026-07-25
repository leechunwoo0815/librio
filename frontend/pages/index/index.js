// frontend/pages/index/index.js
const api = require('../../utils/api')
const auth = require('../../utils/auth')

const QUOTES = [
  { text: 'The more that you read, the more things you will know.', trans: '你读的书越多，你知道的东西就越多。' },
  { text: 'A reader lives a thousand lives before he dies.', trans: '读书之人，死前已历千种人生。' },
  { text: 'Reading is to the mind what exercise is to the body.', trans: '阅读之于心灵，犹如运动之于身体。' },
  { text: 'Books are a uniquely portable magic.', trans: '书籍是一种独特的便携魔法。' },
  { text: 'Today a reader, tomorrow a leader.', trans: '今天的读者，明天的领袖。' },
]

Page({
  data: {
    child: null,
    currentLevel: null,
    advancement: null,
    todayStats: {},
    streak: 0,
    featuredBooks: [],
    quote: {},
    // Carousel
    currentSlide: 0,
    // Venue
    currentVenue: null,
    showVenueSheet: false,
    selectedVenueIndex: 0,
    venues: [],
    achievements: [],
    students: [],
    faqs: [],
    // Messages
    hasUnread: false,
    loadError: false,
    fabButtonText: '加载中...',
    alerts: [],
    children: [],
    showChildSwitcher: false,
  },

  async onShow() {
    const app = getApp()
    if (!app.globalData.token) { return }

    // F3：隐私政策版本升级后重新征求同意（每次启动最多提示一次）
    require('../../utils/consent').ensureOnce('privacy_policy')

    this.setData({ quote: QUOTES[Math.floor(Math.random() * QUOTES.length)] })
    // 从后端加载场馆数据
    try {
      const venues = await require('../../utils/api').getVenues()
      if (venues && venues.length > 0) {
        this.setData({ venues, currentVenue: venues[0] })
      }
    } catch (e) { /* 使用默认数据 */ }

    this.loadData()
    this.loadAlerts()
  },

  async loadData() {
    try {
      const children = await api.getChildren()
      if (!children || children.length === 0) {
        this.setData({ loadError: true })
        return
      }

      const child = auth.selectChild(children)
      if (!child) return

      // Multi-child switcher
      if (children.length > 1) {
        this.setData({ children, showChildSwitcher: true })
      }

      const [stats, todayStats, streak, level, achievements, books] = await Promise.all([
        api.getStatsSummary(child.id).catch(() => ({})),
        api.getTodayStats(child.id).catch(() => ({})),
        api.getStreak(child.id).catch(() => ({ current_streak: 0 })),
        api.getCurrentLevel(child.id).catch(() => null),
        api.getChildAchievements(child.id).catch(() => []),
        api.searchBooks({ page_size: 6 }).catch(() => ({ items: [] })),
      ])

      // 晋级进度：由 getCurrentLevel + getLevels 客户端组装（api.getAdvancement 不存在）
      let advancement = null
      try {
        if (level) {
          const levels = await api.getLevels().catch(() => [])
          const cur = (levels || []).find(l => l.id === level.level_id)
          const required = cur ? (cur.required_books || 5) : 5
          const read = level.books_read_at_level || 0
          advancement = {
            books_read: read,
            books_required: required,
            can_advance: read >= required,
            progress: Math.min(100, Math.round(read / Math.max(required, 1) * 100)),
          }
        }
      } catch (e) { /* 静默降级 */ }

      const students = []  // 同伴数据后端未提供，展示真实数据前不显示

      // FAQ 为静态内容（后端无 FAQ 接口）
      const faqs = [
        { question: '如何开始借书？', answer: '办理会员后，可在图书馆线下扫码借书，或在 App 上预约借书。' },
        { question: '如何查看阅读进度？', answer: '在我的页面可以查看孩子的阅读统计和连续打卡天数。' },
        { question: '图书可以借多久？', answer: '单次借阅周期为21天，逾期将锁死音频播放功能。' },
      ]

      const statusMap = { 0: '体验用户', 1: '观察期会员', 2: '正式会员', 3: '已过期', 4: '已退出' }
      var fabText = '立即报名 99 元亲子课'
      try {
        var tierData = await api.getTiers()
        var course = (tierData.tiers || []).find(function(t) { return t.type === 1 })
        if (course) fabText = '立即报名 ' + course.price + ' 元亲子课'
      } catch (e) { /* 静默降级 */ }

      this.setData({
        child: { ...child, ...stats, statusText: statusMap[child.status] || '' },
        currentLevel: level,
        advancement,
        students,
        faqs,
        achievements: (achievements || []).slice(0, 5).map(a => ({
          id: a.achievement_id, emoji: a.achievement_emoji || '🏅', name: a.achievement_name || '成就'
        })),
        todayStats,
        streak: streak.current_streak || 0,
        featuredBooks: books.items || [],
        fabButtonText: fabText,
      })
    } catch (e) {
      this.setData({ loadError: true })
    }
  },

  onRetry() {
    this.setData({ loadError: false })
    this.loadData()
  },

  async loadAlerts() {
    var child = auth.getCurrentChild()
    if (!child) return

    var alerts = []
    try {
      // 1. 借阅到期提醒
      var borrows = await api.getChildBorrows(child.id, 0).catch(function() { return [] })
      ;(borrows || []).forEach(function(b) {
        var days = Math.ceil((new Date(b.due_date) - new Date()) / 86400000)
        if (days < 0) {
          alerts.push({ level: 'danger', icon: '⚠️', text: (b.book_title || '图书') + ' 已逾期 ' + (-days) + ' 天', url: '/pages/shelf/shelf' })
        } else if (days <= 3) {
          alerts.push({ level: 'warning', icon: '⏰', text: (b.book_title || '图书') + ' 将在 ' + days + ' 天后到期', url: '/pages/shelf/shelf' })
        }
      })

      // 2. 会员到期提醒
      if (child.member_expire_time) {
        var days = Math.ceil((new Date(child.member_expire_time) - new Date()) / 86400000)
        if (days <= 7 && days >= 0) {
          alerts.push({ level: 'warning', icon: '🔔', text: '会员将在 ' + days + ' 天后到期', url: '/pages/member/member' })
        } else if (days < 0) {
          alerts.push({ level: 'danger', icon: '⚠️', text: '会员已过期，请续费', url: '/pages/member/member' })
        }
      }

      this.setData({ alerts: alerts })
      try {
        const msgs = await api.getMessages(null, 1)
        this.setData({ hasUnread: !!(msgs && msgs.unread_count > 0) })
      } catch (e) {
        this.setData({ hasUnread: false })
      }
    } catch (e) {
      // 静默失败，不影响首页
    }
  },

  onAlertTap(e) {
    var url = e.currentTarget.dataset.url
    if (url) wx.navigateTo({ url: url })
  },

  // Navigation
  goBooks() { wx.switchTab({ url: '/pages/books/books' }) },
  goShelf() { wx.switchTab({ url: '/pages/shelf/shelf' }) },
  goLeaderboard() { wx.navigateTo({ url: '/pages/member-pkg/leaderboard/leaderboard' }) },
  goVocab() { wx.navigateTo({ url: '/pages/reading-pkg/vocabulary/vocabulary' }) },
  goDetail(e) { wx.navigateTo({ url: `/pages/reading-pkg/book-detail/book-detail?id=${e.currentTarget.dataset.id}` }) },
  goLogin() { wx.navigateTo({ url: '/pages/login/login' }) },
  goHome() { /* already on home, do nothing or scroll to top */ },
  goActivities() { wx.navigateTo({ url: '/pages/activity-pkg/activity-list/activity-list' }) },
  goMember() { wx.switchTab({ url: '/pages/member/member' }) },
  goMessages() { wx.navigateTo({ url: '/pages/order-pkg/messages/messages' }) },
  goAchievement() { wx.navigateTo({ url: '/pages/member-pkg/achievement/achievement' }) },
  goCourse() { wx.navigateTo({ url: '/pages/order-pkg/observation/observation' }) },

  goVenueNav() {
    const venue = this.data.currentVenue
    if (venue) {
      if (venue.latitude && venue.longitude) {
        wx.openLocation({ name: venue.name, address: venue.address, latitude: Number(venue.latitude), longitude: Number(venue.longitude) })
      } else {
        wx.showToast({ title: '该场馆暂无定位信息', icon: 'none' })
      }
    }
  },

  // Carousel
  onSlideChange(e) {
    this.setData({ currentSlide: e.detail.current })
  },

  // Venue Sheet
  toggleVenue() {
    this.setData({ showVenueSheet: !this.data.showVenueSheet })
  },
  closeVenueSheet() {
    this.setData({ showVenueSheet: false })
  },
  preventBubble() {
    // prevent tap from bubbling to overlay
  },
  selectVenue(e) {
    const idx = e.currentTarget.dataset.index
    const venue = this.data.venues[idx]
    this.setData({
      selectedVenueIndex: idx,
      currentVenue: { ...venue, hours: '周二至周日 10:00–18:00' },
      showVenueSheet: false,
    })
  },

  // FAQ Accordion
  toggleFaq(e) {
    const idx = e.currentTarget.dataset.index
    const faqs = this.data.faqs.map((item, i) => ({
      ...item,
      open: i === idx ? !item.open : false,
    }))
    this.setData({ faqs })
  },

  // Child Switcher
  onSwitchChild(e) {
    const childId = e.currentTarget.dataset.id
    const child = (this.data.children || []).find(c => c.id === childId)
    if (child) {
      auth.selectChild([child])
      this.setData({ child, showChildSwitcher: false })
      this.loadData()
    }
  },

  toggleChildSwitcher() {
    this.setData({ showChildSwitcher: !this.data.showChildSwitcher })
  },
})
