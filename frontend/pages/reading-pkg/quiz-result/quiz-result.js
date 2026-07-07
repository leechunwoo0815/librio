// frontend/pages/reading-pkg/quiz-result/quiz-result.js
const api = require('../../utils/api')
const auth = require('../../utils/auth')

Page({
  data: {
    quizId: 0,
    bookId: 0,
    total: 0,
    correct: 0,
    score: 0,
    passed: false,
    wordsRead: 0,
    canAdvance: false,
    advanceInfo: null,
    childId: 0,
    showLevelUp: false,
    newLevel: null,
    confettiPieces: [],
    loading: false,
    loadError: false,
    // 错题回顾
    wrongQuestions: [],
    showWrongReview: false,
  },

  async onLoad(options) {
    const app = getApp()
    if (!auth.requireAuth()) return

    const quizId = parseInt(options.quizId) || 0
    const bookId = parseInt(options.bookId) || 0
    const total = parseInt(options.total) || 0
    const correct = parseInt(options.correct) || 0
    const score = parseInt(options.score) || 0
    const passed = options.passed === '1' || options.passed === 'true'

    this.setData({ quizId, bookId, total, correct, score, passed })

    // 加载错题数据
    try {
      var wrong = wx.getStorageSync('quiz_wrong_' + quizId) || []
      if (wrong.length > 0) {
        this.setData({ wrongQuestions: wrong })
      }
    } catch (e) { /* 静默 */ }

    // Generate confetti if passed
    if (passed) {
      this.generateConfetti()
    }

    // Get current child
    const child = auth.getCurrentChild()
    if (child) {
      this.setData({ childId: child.id })
      // Check advancement status if passed
      if (passed) {
        this.checkAdvancement(child.id)
      }
    }
  },

  generateConfetti() {
    var colors = ['#22c55e', '#5560cf', '#f59e0b', '#ef4444', '#8b7ef0']
    var pieces = []
    for (var i = 0; i < 30; i++) {
      pieces.push({
        left: Math.floor(Math.random() * 100),
        color: colors[Math.floor(Math.random() * colors.length)],
        delay: Math.random().toFixed(2),
        duration: (1.5 + Math.random() * 1.5).toFixed(2),
        size: Math.floor(12 + Math.random() * 12)
      })
    }
    this.setData({ confettiPieces: pieces })
  },

  async checkAdvancement(childId) {
    try {
      // 晋级由后端事件自动触发，前端查询当前级别确认
      const level = await api.getCurrentLevel(childId)
      if (level) {
        const update = {
          canAdvance: false,
          advanceInfo: level
        }
        // 检测是否有晋级信息，展示庆祝动画
        if (level.level_up || level.just_advanced) {
          update.showLevelUp = true
          update.newLevel = level.level_name || ('Level ' + (level.level_number || ''))
        }
        this.setData(update)
      }
    } catch (e) {
      console.error('getCurrentLevel failed', e)
      this.setData({ loadError: true })
    }
  },

  viewCertificate() {
    wx.navigateTo({
      url: `/pages/member-pkg/certificate/certificate?childId=${this.data.childId}`
    })
  },

  goBackToShelf() {
    wx.switchTab({
      url: '/pages/shelf/shelf'
    })
  },

  goBackToReader() {
    const bookId = this.data.bookId
    if (bookId) {
      wx.navigateTo({
        url: `/pages/reading-pkg/reader/reader?bookId=${bookId}`
      })
    } else {
      wx.switchTab({ url: '/pages/shelf/shelf' })
    }
  },

  retakeQuiz() {
    const { quizId, bookId } = this.data
    let url = `/pages/reading-pkg/quiz/quiz?quizId=${quizId}`
    if (bookId) url += `&bookId=${bookId}`
    wx.redirectTo({ url })
  },

  onRetry() {
    this.setData({ loadError: false, loading: true })
    const child = auth.getCurrentChild()
    if (child && this.data.passed) {
      this.checkAdvancement(child.id)
    }
    this.setData({ loading: false })
  },

  closeLevelUp() {
    this.setData({ showLevelUp: false })
  },

  toggleWrongReview() {
    this.setData({ showWrongReview: !this.data.showWrongReview })
  }
})
