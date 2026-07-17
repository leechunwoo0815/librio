// frontend/pages/reading-pkg/reader/reader.js
// V3.1 音频伴读阅读器 — MP-001/002/003/004 全面优化
const api = require('../../utils/api')
const auth = require('../../utils/auth')
const storage = require('../../utils/storage')

const bgAudioManager = wx.getBackgroundAudioManager()

Page({
  data: {
    bookId: 0,
    book: {},
    sessionId: 0,
    childId: 0,
    isOverdue: false,
    overdueDays: 0,
    loading: true,
    loadError: false,

    // 音频状态
    audioPlaying: false,
    audioLoading: false,
    audioBuffering: false,
    audioProgress: 0,
    audioDuration: 0,
    audioCurrentTime: '0:00',
    audioTotalTime: '0:00',
    audioSpeed: 1.0,

    // MP-002: 续播确认
    showResumeDialog: false,
    pausedPosition: 0,

    // 查词
    lookupWord: '',
    lookupResult: null,
    showLookup: false,

    // 阅读统计
    startTime: 0,

    // 完成弹窗
    showCompletion: false,
    completionStats: { books: 0, words: 0, minutes: 0 },

    // MP-015: 打卡动画
    checkinTriggered: false,
    showCheckinAnimation: false,
    checkinStreak: 0,

    // 文本面板
    pages: [],
    currentPage: 1,
    segments: [],
    vocabMap: {},
  },

  async onLoad(options) {
    const bookId = parseInt(options.bookId) || parseInt(options.id)
    const child = auth.getCurrentChild()
    if (!bookId || !child) {
      wx.showToast({ title: '参数错误', icon: 'none' })
      setTimeout(() => wx.navigateBack(), 1500)
      return
    }

    this.setData({ bookId, childId: child.id, startTime: Date.now() })

    try {
      const book = await api.getBookDetail(bookId)
      this.setData({ book: book || {} })

      // MP-003: 逾期检查 — 友好引导页
      try {
        const borrows = await api.getChildBorrows(child.id, 0)
        if (borrows && borrows.length > 0) {
          const now = new Date()
          const overdue = borrows.find(b => new Date(b.due_date) < now)
          if (overdue) {
            const overdueDays = Math.floor((now - new Date(overdue.due_date)) / 86400000)
            this.setData({ isOverdue: true, overdueDays })
            return
          }
        }
      } catch (e) { /* 无借阅记录，继续 */ }

      // 开始阅读会话
      const existingSessionId = parseInt(options.sessionId)
      if (existingSessionId) {
        this.setData({ sessionId: existingSessionId })
      } else {
        try {
          const session = await api.startSession(child.id, bookId)
          this.setData({ sessionId: session.id || session.session_id || 0 })
        } catch (e) {
          console.error('[startSession failed]', e)
          wx.showToast({ title: '阅读会话创建失败', icon: 'none' })
        }
      }

      // MP-004: 恢复本地缓存进度
      const cached = storage.getReadProgress(bookId, child.id)
      if (cached && cached.audioPos > 0) {
        this.setData({ audioProgress: cached.audioPos })
      }

      // 加载文本页 + 生词
      try {
        const [pages, learningWords] = await Promise.all([
          api.getBookPages(bookId),
          api.getLearningWords(child.id),
        ])
        const vocabMap = {}
        if (learningWords && learningWords.length) {
          learningWords.forEach(w => { vocabMap[w] = true })
        }
        const sortedPages = (pages || []).sort((a, b) => a.page_number - b.page_number)
        const firstSegments = sortedPages.length ? this.buildSegments(sortedPages[0].text_content || '', vocabMap) : []
        this.setData({ pages: sortedPages, vocabMap, segments: firstSegments, currentPage: 1 })
      } catch (e) {
        console.error('Load pages/vocab failed:', e)
      }

      // 初始化音频
      if (book && book.has_audio) {
        if (book.audio_url) {
          this.initAudio(book)
        } else {
          this.setData({ audioLoading: false })
          console.warn('Book has_audio=true but audio_url is empty:', bookId)
        }
      }
      this.setData({ loading: false })
    } catch (e) {
      console.error('Load reader failed:', e)
      this.setData({ loadError: true, loading: false })
      wx.showToast({ title: '加载失败', icon: 'none' })
    }
  },

  onRetry() {
    this.setData({ loadError: false, loading: true })
    this.onLoad({ bookId: this.data.bookId, id: this.data.bookId })
  },

  onHide() {
    this._hideTime = Date.now()
    // MP-002: 暂停音频并记录位置
    if (this.data.audioPlaying) {
      this.setData({ pausedPosition: bgAudioManager.currentTime })
      bgAudioManager.pause()
    }
    // MP-004: 缓存进度到本地
    this._saveLocalProgress()
  },

  onShow() {
    // MP-002: 检测续播
    if (this.data.pausedPosition > 0) {
      this.setData({ showResumeDialog: true })
    }
  },

  async onUnload() {
    this._saveLocalProgress()
    try {
      await this.endSession()
    } catch (e) {
      console.error('[endSession failed in onUnload]', e)
    }
    // 移除所有事件监听（bgAudioManager 是全局单例，不移除会重复绑定）
    bgAudioManager.offTimeUpdate()
    bgAudioManager.offPlay()
    bgAudioManager.offPause()
    bgAudioManager.offStop()
    bgAudioManager.offEnded()
    bgAudioManager.offWaiting()
    bgAudioManager.offCanplay()
    bgAudioManager.offError()
    bgAudioManager.stop()
  },

  _saveLocalProgress() {
    storage.saveReadProgress(this.data.bookId, this.data.childId, {
      audioPos: bgAudioManager.currentTime || this.data.audioProgress,
      timestamp: Date.now(),
    })
  },

  // ==================== MP-002: 续播确认 ====================

  resumePlayback() {
    this.setData({ showResumeDialog: false })
    bgAudioManager.seek(this.data.pausedPosition)
    bgAudioManager.play()
    this.setData({ pausedPosition: 0 })
  },

  restartPlayback() {
    this.setData({ showResumeDialog: false, pausedPosition: 0 })
    bgAudioManager.seek(0)
    bgAudioManager.play()
  },

  // ==================== MP-001: 音频播放（全链路状态反馈） ====================

  initAudio(book) {
    const baseURL = getApp().globalData.baseURL || ''
    // MP-006: 锁屏控制适配
    bgAudioManager.title = book.title || 'DmkWords 听读'
    bgAudioManager.singer = book.author || ''
    bgAudioManager.coverImgUrl = book.cover
      ? (book.cover.startsWith('http') ? book.cover : baseURL + book.cover)
      : ''
    const audioUrl = book.audio_url.startsWith('http') ? book.audio_url : baseURL + book.audio_url
    bgAudioManager.src = audioUrl
    bgAudioManager.playbackRate = this.data.audioSpeed

    bgAudioManager.offTimeUpdate()
    bgAudioManager.offPlay()
    bgAudioManager.offPause()
    bgAudioManager.offStop()
    bgAudioManager.offEnded()
    bgAudioManager.offWaiting()
    bgAudioManager.offCanplay()
    bgAudioManager.offError()

    // MP-001: 加载状态
    this.setData({ audioLoading: true })

    bgAudioManager.onTimeUpdate(() => {
      if (!bgAudioManager.duration) return
      const newProgress = Math.floor(bgAudioManager.currentTime)
      const oldProgress = Math.floor(this.data.audioProgress)
      if (newProgress === oldProgress) return
      // 只更新进度（每秒变化的字段），减少 setData 开销
      const update = {
        audioProgress: bgAudioManager.currentTime,
        audioCurrentTime: this.formatTime(bgAudioManager.currentTime),
      }
      // duration 变化时才更新（通常只在首次加载时变化）
      if (Math.abs(bgAudioManager.duration - this.data.audioDuration) > 0.5) {
        update.audioDuration = bgAudioManager.duration
        update.audioTotalTime = this.formatTime(bgAudioManager.duration)
      }
      this.setData(update)
      // MP-004: 每 10 秒缓存一次进度
      if (newProgress % 10 === 0) {
        this._saveLocalProgress()
      }
      this._updateCurrentPage()
      // MP-015: 打卡动画 — 满 10 分钟自动触发
      if (!this.data.checkinTriggered && this.data.startTime > 0) {
        var totalMinutes = (Date.now() - this.data.startTime) / 60000
        if (totalMinutes >= 10) {
          this.setData({ checkinTriggered: true })
          this._triggerCheckinAnimation()
        }
      }
    })

    bgAudioManager.onPlay(() => {
      this.setData({ audioPlaying: true, audioLoading: false, audioBuffering: false })
    })

    bgAudioManager.onPause(() => {
      this.setData({ audioPlaying: false })
    })

    bgAudioManager.onStop(() => {
      this.setData({ audioPlaying: false })
    })

    bgAudioManager.onEnded(() => {
      this.setData({ audioPlaying: false, audioProgress: 0 })
      storage.remove(`read_progress_${this.data.bookId}_${this.data.childId}`)
      this.finishListening()
    })

    // MP-001: 缓冲状态
    bgAudioManager.onWaiting(() => {
      this.setData({ audioBuffering: true })
    })

    bgAudioManager.onCanplay(() => {
      this.setData({ audioBuffering: false, audioLoading: false })
    })

    // MP-001: 错误处理 — 友好弹窗
    bgAudioManager.onError((err) => {
      console.error('Audio error:', err)
      this.setData({ audioPlaying: false, audioLoading: false, audioBuffering: false })
      wx.showModal({
        title: '音频加载失败',
        content: '是否重试？',
        confirmText: '重试',
        cancelText: '返回',
        success: (res) => {
          if (res.confirm) {
            const baseURL = getApp().globalData.baseURL || ''
            const url = this.data.book.audio_url
            bgAudioManager.src = url.startsWith('http') ? url : baseURL + url
          } else {
            wx.navigateBack()
          }
        },
      })
    })
    bgAudioManager.play()
  },

  toggleAudio() {
    if (this.data.isOverdue) return
    if (this.data.audioPlaying) {
      bgAudioManager.pause()
    } else {
      bgAudioManager.play()
    }
  },

  seekAudio(e) {
    bgAudioManager.seek(e.detail.value)
  },

  rewind15() {
    const pos = Math.max(0, bgAudioManager.currentTime - 15)
    bgAudioManager.seek(pos)
  },

  forward15() {
    const pos = Math.min(bgAudioManager.duration, bgAudioManager.currentTime + 15)
    bgAudioManager.seek(pos)
  },

  // MP-005: 倍速切换即时反馈
  setSpeed(e) {
    const speed = parseFloat(e.currentTarget.dataset.speed)
    bgAudioManager.playbackRate = speed
    this.setData({ audioSpeed: speed })
    wx.vibrateShort({ type: 'light' })
  },

  formatTime(seconds) {
    if (!seconds || isNaN(seconds)) return '0:00'
    const m = Math.floor(seconds / 60)
    const s = Math.floor(seconds % 60)
    return `${m}:${s < 10 ? '0' : ''}${s}`
  },

  buildSegments(text, vocabMap) {
    if (!text) return []
    const tokens = text.split(/(\b[a-zA-Z\u00C0-\u024F]+(?:[-'\u2018\u2019][a-zA-Z\u00C0-\u024F]+)*\b)/)
    return tokens.map(token => {
      const lower = token.toLowerCase().replace(/[\u2018\u2019]/g, "'")
      if (vocabMap[lower]) {
        return { type: 'vocab', text: token, word: lower }
      }
      return { type: 'text', text: token }
    })
  },

  _updateCurrentPage() {
    const { pages, audioProgress, audioDuration, vocabMap } = this.data
    if (!pages.length || !audioDuration) return
    const pageIndex = Math.min(
      Math.floor((audioProgress / audioDuration) * pages.length),
      pages.length - 1
    )
    const newPage = pageIndex + 1
    if (newPage !== this.data.currentPage) {
      const page = pages[pageIndex]
      const segments = this.buildSegments(page.text_content || '', vocabMap)
      this.setData({ currentPage: newPage, segments })
    }
  },

  onVocabTap(e) {
    const word = e.currentTarget.dataset.word
    this.setData({ lookupWord: word })
    this.doLookup()
  },

  // ==================== MP-013: 查词弹窗（不中断音频） ====================

  toggleLookup() {
    this.setData({ showLookup: !this.data.showLookup })
  },

  onLookupInput(e) {
    this.setData({ lookupWord: e.detail.value })
  },

  async doLookup() {
    const word = this.data.lookupWord.trim().toLowerCase()
    if (!word) return
    try {
      const result = await api.lookupWord(word)
      if (result && result.word) {
        this.setData({ lookupResult: result })
      } else {
        // MP-012: 查词失败兜底
        this.setData({ lookupResult: { word, chinese_meaning: '未收录该词', found: false } })
      }
    } catch (e) {
      // MP-012: 网络异常兜底
      this.setData({ lookupResult: { word, chinese_meaning: '查询失败，请稍后再试', found: false, error: true } })
    }
  },

  onPlayLookupAudio(e) {
    const audioUrl = e.currentTarget.dataset.audio
    if (!audioUrl) return
    const audio = wx.createInnerAudioContext()
    audio.src = audioUrl
    audio.play()
  },

  async addLookupToVocab() {
    const result = this.data.lookupResult
    if (!result || !result.word) return
    try {
      await api.addToVocab(this.data.childId, result.word, this.data.bookId)
      wx.showToast({ title: '已加入生词本', icon: 'success' })
    } catch (e) {
      wx.showToast({ title: '添加失败', icon: 'none' })
    }
  },

  // ==================== MP-015: 打卡动画 ====================

  _triggerCheckinAnimation() {
    this.setData({ showCheckinAnimation: true, checkinStreak: (this.data.checkinStreak || 0) + 1 })
    try { wx.vibrateShort({ type: 'heavy' }) } catch (e) {}
    setTimeout(() => {
      this.setData({ showCheckinAnimation: false })
    }, 3000)
  },

  // ==================== 阅读完成 ====================

  async finishListening() {
    var minutes = Math.round((Date.now() - this.data.startTime) / 60000)
    var words = this.data.book.word_count || 0
    this.setData({
      showCompletion: true,
      completionStats: { books: 1, words: words, minutes: Math.max(1, minutes) },
    })
    await this.endSession()
  },

  closeCompletion() {
    this.setData({ showCompletion: false })
    wx.switchTab({ url: '/pages/shelf/shelf' })
  },

  goQuizFromCompletion() {
    this.setData({ showCompletion: false })
    this.goQuiz()
  },

  async endSession() {
    if (!this.data.sessionId) return
    const minutes = Math.round((Date.now() - this.data.startTime) / 60000)
    const words = this.data.book.word_count || 0
    try {
      await api.endSession(this.data.sessionId, 0, words, minutes)
    } catch (e) {
      console.error('[endSession failed]', e)
      wx.showToast({ title: '阅读记录保存失败', icon: 'none' })
    }
  },

  // ==================== 导航 ====================

  goQuiz() {
    wx.navigateTo({
      url: `/pages/reading-pkg/quiz/quiz?bookId=${this.data.bookId}&childId=${this.data.childId}`,
    })
  },

  closePage() {
    wx.navigateBack()
  },

  goBookshelf() {
    wx.switchTab({ url: '/pages/shelf/shelf' })
  },

  shareBook() {},

  onShareAppMessage() {
    return {
      title: `${this.data.book.title} - DmkWords 听读`,
      path: `/pages/reading-pkg/reader/reader?bookId=${this.data.bookId}`,
    }
  },
})
