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
    isTestMode: false,
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
    currentVenue: { name: '人广馆', address: '上海市黄浦区南京东路 800 号 3 楼', hours: '周二至周日 10:00–18:00' },
    showVenueSheet: false,
    selectedVenueIndex: 0,
    venues: [
      { name: '人广馆', address: '黄浦区南京东路 800 号 3 楼' },
      { name: '徐汇馆', address: '徐汇区漕溪北路 398 号 2 楼' },
      { name: '陆家嘴馆', address: '浦东新区陆家嘴环路 1000 号 B1' },
      { name: '松江馆', address: '松江区谷阳北路 166 号 1 楼' },
    ],
    // Achievements
    achievements: [
      { id: 1, emoji: '📚', name: '读完10本' },
      { id: 2, emoji: '🏅', name: '首次满分' },
      { id: 3, emoji: '⭐', name: '连续7天' },
      { id: 4, emoji: '🏆', name: '词汇达人' },
      { id: 5, emoji: '🎯', name: '精准答题' },
    ],
    // Students
    students: [
      { name: 'Lucy', age: 7, books_read: 268 },
      { name: 'Tom', age: 10, books_read: 512 },
      { name: 'Mia', age: 5, books_read: 96 },
      { name: 'Leo', age: 12, books_read: 389 },
      { name: 'Emma', age: 8, books_read: 185 },
    ],
    // FAQ
    faqs: [
      { question: '几岁可以开始英文原版阅读？', answer: '3 岁即可开始。我们根据孩子的年龄和英文基础，匹配适合的 AR 级别读物，从绘本启蒙到章节书循序渐进。', open: false },
      { question: '99 元亲子课包含什么内容？', answer: '一节 45 分钟线下亲子阅读体验课，专业老师一对一引导，含阅读能力评估报告一份。课后可直接办理观察期或正式会员。', open: false },
      { question: '书架上的书读完怎么办？', answer: '测评通过后书会自动从书架移除，您可以继续从图书馆选择新书加入书架。', open: false },
      { question: '书架最多放多少本书？', answer: '每位会员书架最多 20 本书。收藏夹不限数量。', open: false },
      { question: '多孩家庭有优惠吗？', answer: '第二个孩子起享受 8 折优惠，会员期与第一个孩子同步。报名时选择"多孩优惠"即可自动计算。', open: false },
    ],
    // Messages
    hasUnread: true,
    loadError: false,
    alerts: [],
    children: [],
    showChildSwitcher: false,
  },

  async onShow() {
    this.setData({ quote: QUOTES[Math.floor(Math.random() * QUOTES.length)] })
    // 从后端加载场馆数据
    try {
      const venues = await require('../../utils/api').getVenues()
      if (venues && venues.length > 0) {
        this.setData({ venues, currentVenue: venues[0] })
      }
    } catch (e) { /* 使用默认数据 */ }
    const app = getApp()
    this.setData({ isTestMode: app.globalData.isTestMode || app.globalData.token === 'test-token-mock' })

    // 先显示示例数据，再尝试加载真实数据
    this._loadDemoData()
    this.loadData()
    this.loadAlerts()
  },

  async loadData() {
    try {
      const children = await api.getChildren()
      if (!children || children.length === 0) {
        this._loadDemoData()
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
        api.searchBooks({ page_size: 6 }).catch(() => ({ list: [] })),
      ])

      const statusMap = { 0: '体验用户', 1: '观察期会员', 2: '正式会员', 3: '已过期', 4: '已退出' }
      this.setData({
        child: { ...child, ...stats, statusText: statusMap[child.status] || '' },
        currentLevel: level,
        achievements: (achievements || []).slice(0, 5).map(a => ({
          id: a.achievement_id, emoji: a.achievement_emoji || '🏅', name: a.achievement_name || '成就'
        })),
        todayStats,
        streak: streak.current_streak || 0,
        featuredBooks: books.list || [],
      })
    } catch (e) {
      const app = getApp()
      if (app.globalData.isTestMode || app.globalData.token === 'test-token-mock') {
        this._loadDemoData()
      } else {
        this.setData({ loadError: true })
      }
    }
  },

  onRetry() {
    this.setData({ loadError: false })
    this.loadData()
  },

  _loadDemoData() {
    this.setData({
      child: { name: '小明', english_name: 'Tom', status: 2, statusText: '正式会员' },
      currentLevel: { level_name: 'A', badge_emoji: '🌱' },
      advancement: { books_read: 3, books_required: 10, can_advance: false, progress: 30 },
      todayStats: { reading_minutes: 25, words_read: 1200, pages_read: 8 },
      streak: 7,
      featuredBooks: [
        { id: 1, title: "Charlotte's Web", ar_value: 4.4, word_count: 31836 },
        { id: 2, title: 'The Cat in the Hat', ar_value: 2.1, word_count: 1624 },
        { id: 3, title: 'Green Eggs and Ham', ar_value: 1.5, word_count: 820 },
        { id: 4, title: 'Goodnight Moon', ar_value: 1.8, word_count: 131 },
        { id: 5, title: 'Where the Wild Things Are', ar_value: 3.2, word_count: 1018 },
        { id: 6, title: 'The Very Hungry Caterpillar', ar_value: 2.9, word_count: 224 },
      ],
    })
  },

  async loadAlerts() {
    var app = getApp()
    if (app.globalData.isTestMode || app.globalData.token === 'test-token-mock') return
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
  goActivities() { wx.navigateTo({ url: '/pages/activity-pkg/activity/activity' }) },
  goMember() { wx.navigateTo({ url: '/pages/member/member' }) },
  goMessages() { wx.navigateTo({ url: '/pages/order-pkg/messages/messages' }) },
  goAchievement() { wx.navigateTo({ url: '/pages/member-pkg/achievement/achievement' }) },
  goCourse() { wx.navigateTo({ url: '/pages/order-pkg/observation/observation' }) },

  goDebugNav() { /* 仅 DEBUG 模式可用 */ },
  goVenueNav() {
    const venue = this.data.currentVenue
    if (venue) {
      wx.openLocation({ name: venue.name, address: venue.address })
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
    const child = this.data.children.find(c => c.id === childId)
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
