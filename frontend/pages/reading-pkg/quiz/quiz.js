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

    this.setData({ bookId })

    // Start timer
    this._timerInterval = setInterval(() => {
      this.setData({ elapsedSeconds: this.data.elapsedSeconds + 1 })
    }, 1000)

    await this.loadQuestions(bookId)
  },

  async loadQuestions(bookId) {
    wx.showLoading({ title: '加载中...' })
    try {
      const quiz = await api.startQuiz(bookId)
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

      // Strip correct_answer from data sent to WXML
      const sanitizedQuestions = questions.map(q => {
        const { correct_answer, ...rest } = q
        return rest
      })
      this._correctAnswers = {}
      questions.forEach(q => { this._correctAnswers[q.id] = q.correct_answer })

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
              this.setData({
                answers: cached.answers,
                currentQ: cached.currentQ || 0,
                question: questions[cached.currentQ || 0],
                selected: cached.answers[questions[cached.currentQ || 0].id] || '',
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
    const ans = e.currentTarget.dataset.ans
    const questionId = this.data.questions[this.data.currentQ].id
    const correctAns = this._correctAnswers[questionId]
    const isCorrect = ans === correctAns
    const resultData = {}
    resultData['result' + ans] = isCorrect ? 'correct' : 'wrong'
    if (!isCorrect) {
      resultData['result' + correctAns] = 'correct'
    }
    resultData.feedbackType = isCorrect ? 'correct' : 'wrong'
    resultData.feedbackText = isCorrect ? '回答正确！' + this.data.question.explanation : '正确答案是 ' + correctAns + '，' + this.data.question.explanation
    this.setData(Object.assign({ selected: ans }, resultData))
    // MP-007: 每次选择后缓存进度
    this._saveProgress()
    // 触觉反馈
    wx.vibrateShort({ type: 'light' })
    // 自动进入下一题
    if (this.data.currentQ < this.data.totalQ - 1) {
      this._nextTimer = setTimeout(() => { this.nextQuestion(); }, 1200)
    }
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

      // 错题回顾：缓存题目和答案供结果页使用
      try {
        var self = this
        var wrongQuestions = questions.filter(function(q) {
          return answers[q.id] && answers[q.id] !== (self._correctAnswers[q.id] || '')
        }).map(function(q) {
          return {
            question_text: q.question_text,
            option_a: q.option_a, option_b: q.option_b,
            option_c: q.option_c, option_d: q.option_d,
            correct_answer: self._correctAnswers[q.id] || '',
            user_answer: answers[q.id] || '',
            explanation: q.explanation || ''
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
        `wordsRead=${result.words_read || 0}`,
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
  },
})
