// frontend/pages/reading-pkg/quiz/quiz.js
// MP-007: 答题进度本地保存 + MP-008: 提交失败保留答案 + MP-009: 题库为空引导
const api = require('../../utils/api')
const auth = require('../../utils/auth')
const storage = require('../../utils/storage')

Page({
  data: {
    quizId: 0,
    bookId: 0,
    bookTitle: '',
    questions: [],
    currentQ: 0,
    totalQ: 0,
    selected: '',
    answers: {},
    submitting: false,
    showConfirm: false,
    question: {},
    submitRetries: 0,  // MP-008: 重试计数
    loading: true,
    loadError: false,
    elapsedSeconds: 0,
  },

  async onLoad(options) {
    const app = getApp()
    if (!auth.requireAuth()) return

    const bookId = parseInt(options.bookId) || 0
    if (!bookId) {
      wx.showToast({ title: '参数错误', icon: 'none' })
      this._navTimer = setTimeout(() => { wx.navigateBack(); }, 1500)
      return
    }

    this._urlChildId = parseInt(options.childId) || null
    this.setData({ bookId })

    // Start timer
    this._timerInterval = setInterval(() => {
      const sec = this.data.elapsedSeconds + 1
      const mm = Math.floor(sec / 60)
      const ss = String(sec % 60).padStart(2, '0')
      this.setData({ elapsedSeconds: sec, elapsedText: mm + ':' + ss })
    }, 1000)

    await this.loadQuestions(bookId)
  },

  async loadQuestions(bookId) {
    wx.showLoading({ title: '加载中...' })
    try {
      const auth = require('../../utils/auth')
      const currentChild = auth.getCurrentChild()
      const childId = (currentChild && currentChild.id) || this._urlChildId || null
      const quiz = await api.startQuiz(bookId, childId)
      const quizId = quiz.id || quiz.quiz_id || 0

      // Fetch book title
      let bookTitle = ''
      try {
        const bookDetail = await api.getBookDetail(bookId)
        bookTitle = bookDetail.title || bookDetail.name || ''
      } catch (e) { /* silent */ }

      const questions = await api.getQuizQuestions(bookId)
      if (!questions || questions.length === 0) {
        // MP-009: 题库为空 — 友好占位页
        wx.hideLoading()
        this.setData({ questions: [], noQuestions: true, bookId, loading: false })
        return
      }

      // F-057：后端取题已剥离 correct_answer/explanation，前端不保存任何答案字段
      const sanitizedQuestions = questions

      this.setData({
        quizId,
        bookTitle,
        questions: sanitizedQuestions,
        totalQ: questions.length,
        question: sanitizedQuestions[0],
        currentQ: 0,
        selected: '',
        answers: {},
        noQuestions: false,
        loading: false,
      })

      // MP-007: 检查本地缓存的未完成答题
      const cached = storage.getQuizProgress(quizId)
      if (cached && cached.answers && Object.keys(cached.answers).length > 0) {
        wx.showModal({
          title: '继续答题',
          content: '上次答题未完成，是否继续？',
          confirmText: '继续',
          cancelText: '重新开始',
          success: (res) => {
            if (res.confirm) {
              // 题库变更时缓存索引可能越界，夹紧到有效范围
              const safeQuestions = this.data.questions
              const safeQ = Math.min(cached.currentQ || 0, safeQuestions.length - 1)
              this.setData({
                answers: cached.answers,
                currentQ: safeQ,
                question: safeQuestions[safeQ],
                selected: cached.answers[safeQuestions[safeQ].id] || '',
              })
            }
          },
        })
      }
    } catch (e) {
      wx.hideLoading()
      const msg = (e.message || e.errMsg || '').toLowerCase()
      if (msg.includes('暂无测验题目')) {
        this.setData({ questions: [], noQuestions: true, bookId, loading: false, loadError: false })
        return
      }
      this.setData({ loadError: true, loading: false })
      wx.showModal({
        title: '测评暂时不可用',
        content: '请稍后重试',
        showCancel: false,
      })
    } finally {
      wx.hideLoading()
    }
  },

  onRetry() {
    if (this._retrying) return
    this._retrying = true
    this.setData({ loadError: false, loading: true })
    this.loadQuestions(this.data.bookId).finally(() => { this._retrying = false })
  },

  selectOption(e) {
    if (this.data.selected) return  // 已作答，防连击跳题
    const ans = e.currentTarget.dataset.ans
    // F-057：不在客户端判分（答案仅提交后由服务端权威返回），只记录选择
    this.setData({
      selected: ans,
      feedbackType: 'selected',
      feedbackText: '已选择，提交后可查看对错与解析',
    })
    // MP-007: 每次选择后缓存进度
    this._saveProgress()
    // 触觉反馈
    wx.vibrateShort({ type: 'light' })
    // 自动进入下一题
    if (this.data.currentQ < this.data.totalQ - 1) {
      this._nextTimer = setTimeout(() => { this.nextQuestion(); }, 1200)
    }
  },

  // C2 家长辅助模式：题目语音朗读（英文 TTS，低龄孩子家长播给孩子听）
  playQuestionAudio() {
    const text = this.data.question && this.data.question.question_text
    if (!text) return
    if (this._ttsCtx) {
      this._ttsCtx.destroy()
      this._ttsCtx = null
    }
    const ctx = wx.createInnerAudioContext()
    ctx.src = 'https://dict.youdao.com/dictvoice?audio=' + encodeURIComponent(text) + '&type=1'
    ctx.onError((err) => {
      console.warn('TTS播放失败', err)
      wx.showToast({ title: '语音播放失败，请重试', icon: 'none' })
    })
    ctx.play()
    this._ttsCtx = ctx
  },

  nextQuestion() {
    const { selected, answers, currentQ, totalQ, questions } = this.data
    if (!selected) return

    const questionId = questions[currentQ].id
    const newAnswers = Object.assign({}, answers)
    newAnswers[questionId] = selected

    if (currentQ < totalQ - 1) {
      const nextQ = currentQ + 1
      const nextQuestionId = questions[nextQ].id
      const savedAnswer = newAnswers[nextQuestionId] || ''
      this.setData({
        currentQ: nextQ,
        question: questions[nextQ],
        selected: savedAnswer,
        answers: newAnswers,
        resultA: null,
        resultB: null,
        resultC: null,
        resultD: null,
        feedbackType: '',
        feedbackText: '',
      })
    } else {
      this.setData({ answers: newAnswers, showConfirm: true })
    }
    this._saveProgress()
  },

  prevQuestion() {
    const { currentQ, answers, questions } = this.data
    if (currentQ <= 0) return

    const questionId = questions[currentQ].id
    const newAnswers = Object.assign({}, this.data.answers)
    if (this.data.selected) {
      newAnswers[questionId] = this.data.selected
    }

    const prevQ = currentQ - 1
    const prevQuestionId = questions[prevQ].id
    const savedAnswer = newAnswers[prevQuestionId] || ''
    this.setData({
      currentQ: prevQ,
      question: questions[prevQ],
      selected: savedAnswer,
      answers: newAnswers
    })
  },

  hideConfirm() {
    this.setData({ showConfirm: false })
  },

  // MP-007: 缓存答题进度
  _saveProgress() {
    const { quizId, answers, currentQ } = this.data
    if (quizId) {
      storage.saveQuizProgress(quizId, { answers, currentQ })
    }
  },

  // MP-008: 提交失败保留答案 + 重试
  async doSubmit() {
    this.setData({ showConfirm: false, submitting: true })

    const { quizId, questions, answers } = this.data

    const answerArray = questions.map(q => ({
      quiz_id: quizId,
      question_id: q.id,
      selected_answer: answers[q.id] || ''
    }))

    wx.showLoading({ title: '提交中...' })
    try {
      const result = await api.submitQuizAnswers(quizId, answerArray)
      wx.hideLoading()

      // MP-007: 提交成功后清除缓存
      storage.clearQuizProgress(quizId)

      // 错题回顾：以服务端提交响应为准（F-057，不依赖取题接口泄露的答案）
      try {
        var review = (result && result.question_review) || []
        var wrongQuestions = review.filter(function(item) {
          return !item.is_correct
        }).map(function(item) {
          return {
            question_text: item.question_text || '',
            option_a: item.option_a || '',
            option_b: item.option_b || '',
            option_c: item.option_c || '',
            option_d: item.option_d || '',
            correct_answer: item.correct_answer || '',
            user_answer: item.selected_answer || '',
            explanation: item.explanation || ''
          }
        })
        const cacheData = { questions: wrongQuestions, _ts: Date.now() }
        wx.setStorageSync('quiz_wrong_' + quizId, cacheData)
      } catch (e) { /* 静默 */ }

      const params = [
        `quizId=${quizId}`,
        `total=${result.total}`,
        `correct=${result.correct}`,
        `score=${result.score}`,
        `passed=${result.passed ? 1 : 0}`,
        `wordsRead=${result.word_count || 0}`,
      ]
      if (this.data.bookId) {
        params.push(`bookId=${this.data.bookId}`)
      }
      wx.redirectTo({
        url: `/pages/reading-pkg/quiz-result/quiz-result?${params.join('&')}`
      })
    } catch (e) {
      wx.hideLoading()
      console.error('submitQuiz failed', e)

      // MP-008: 重试机制
      const retries = this.data.submitRetries + 1
      this.setData({ submitting: false, submitRetries: retries })

      if (retries >= 3) {
        wx.showModal({
          title: '提交失败',
          content: '网络似乎有问题，答案已保存，稍后可以在阅读历史中补考',
          showCancel: false,
        })
      } else {
        wx.showModal({
          title: '提交失败',
          content: '是否重试提交？',
          confirmText: '重试',
          cancelText: '稍后',
          success: (res) => {
            if (res.confirm) this.doSubmit()
          },
        })
      }
    }
  },

  goBack() {
    wx.showModal({
      title: '确认退出？',
      content: '退出后答题进度已自动保存',
      confirmText: '退出',
      confirmColor: '#ef4444',
      success: (res) => {
        if (res.confirm) {
          // MP-007: 退出前确保进度已保存
          this._saveProgress()
          wx.navigateBack()
        }
      }
    })
  },

  // MP-009: 题库为空时的导航
  goBookshelf() {
    wx.switchTab({ url: '/pages/shelf/shelf' })
  },

  onUnload() {
    if (this._navTimer) { clearTimeout(this._navTimer); this._navTimer = null; }
    if (this._nextTimer) { clearTimeout(this._nextTimer); this._nextTimer = null; }
    if (this._timerInterval) { clearInterval(this._timerInterval); this._timerInterval = null; }
    // F-011：销毁 TTS 音频上下文，防止页面卸载后继续播放/泄漏
    if (this._ttsCtx) {
      try { this._ttsCtx.destroy() } catch (e) { /* 静默 */ }
      this._ttsCtx = null
    }
  },
})
