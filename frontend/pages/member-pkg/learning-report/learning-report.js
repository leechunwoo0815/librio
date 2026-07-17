// frontend/pages/member-pkg/learning-report/learning-report.js
const api = require('../../utils/api')
const auth = require('../../utils/auth')

Page({
  data: {
    loading: true,
    child: null,
    period: 'week',
    summary: null,
    trendData: [],
    maxMinutes: 1,
    suggestion: '',
    barLabels: [],
    trendTitle: '阅读时长趋势',
    reportTitle: '',
    reportPeriod: '',
  },

  onLoad(options) {
    if (!auth.requireAuth()) return

    // 从二维码扫码进入：解析 scene
    if (options && options.scene) {
      var scene = decodeURIComponent(options.scene)
      if (scene.indexOf('report_') === 0) {
        var parts = scene.split('_')
        if (parts.length >= 3) {
          var childId = parseInt(parts[1])
          var period = parts[2]
          if (childId && (period === 'week' || period === 'month')) {
            this.setData({ period: period })
          }
        }
      }
    }
  },

  onShow() {
    this.loadReport()
  },

  async loadReport() {
    this.setData({ loading: true })
    try {
      const child = auth.getCurrentChild()
      if (!child) {
        const children = await api.getChildren()
        if (!children || children.length === 0) {
          this.setData({ loading: false })
          return
        }
        this.setData({ child: children[0] })
        await this.fetchData(children[0].id)
      } else {
        this.setData({ child })
        await this.fetchData(child.id)
      }
    } catch (e) {
      console.error('Load learning report failed:', e)
      this.setData({ loading: false })
    }
  },

  async fetchData(childId) {
    const { period } = this.data
    const days = period === 'week' ? 7 : 30

    try {
      const [summary, trend, learningReport] = await Promise.all([
        api.getStatsSummary(childId).catch(() => ({})),
        api.getTrend(childId, days).catch(() => []),
        api.getLearningReport(childId).catch(() => null),
      ])

      const recentTrend = Array.isArray(trend) ? trend.slice(-7) : []
      const maxVal = Math.max(1, ...recentTrend.map(d => d.reading_minutes || d.minutes || 0))
      const barData = recentTrend.map((d, i) => ({
        ...d,
        minutes: d.reading_minutes || d.minutes || 0,
        barHeight: Math.round(((d.reading_minutes || d.minutes || 0) / maxVal) * 100),
        label: this.formatBarLabel(d.date),
        isToday: i === recentTrend.length - 1,
      }))
      const barLabels = barData.map(d => d.label)

      const now = new Date()
      const reportPeriod = period === 'week'
        ? `${now.getFullYear()}年${now.getMonth() + 1}月 · 第${Math.ceil(now.getDate() / 7)}周`
        : `${now.getFullYear()}年${now.getMonth() + 1}月`

      const mergedSummary = {
        total_minutes: summary.total_reading_minutes || summary.total_minutes || 0,
        total_words: summary.total_words_read || summary.total_words || 0,
        books_finished: summary.total_books_read || summary.books_finished || 0,
        checkin_days: summary.checkin_days || summary.total_checkin_days || 0,
      }
      if (learningReport) {
        mergedSummary.total_minutes = learningReport.total_minutes || mergedSummary.total_minutes
        mergedSummary.total_words = learningReport.total_words || mergedSummary.total_words
        mergedSummary.books_finished = learningReport.books_finished || mergedSummary.books_finished
        mergedSummary.checkin_days = learningReport.checkin_days || mergedSummary.checkin_days
      }

      this.setData({
        summary: mergedSummary,
        trendData: barData,
        maxMinutes: maxVal,
        suggestion: summary.suggestion || '',
        barLabels,
        reportTitle: period === 'week' ? '本周学习报告' : '本月学习报告',
        reportPeriod,
        loading: false,
      })
    } catch (e) {
      console.error('Fetch report data failed:', e)
      this.setData({ loading: false })
    }
  },

  switchPeriod(e) {
    const period = e.currentTarget.dataset.period
    if (period === this.data.period) return
    this.setData({ period })
    if (this.data.child) {
      this.fetchData(this.data.child.id)
    }
  },

  formatBarLabel(dateStr) {
    if (!dateStr) return ''
    const d = new Date(dateStr)
    const days = ['日', '一', '二', '三', '四', '五', '六']
    return days[d.getDay()]
  },

  onShareAppMessage() {
    const child = this.data.child
    const period = this.data.period || 'week'
    const name = child ? child.name : '小朋友'
    const scene = child ? 'report_' + child.id + '_' + period : ''
    const path = scene
      ? '/pages/member-pkg/learning-report/learning-report?scene=' + scene
      : '/pages/member-pkg/learning-report/learning-report'
    return {
      title: `${name}的学习报告 - DmkWords`,
      path: path,
    }
  },

  onShareTap() {
    this.generateShareImage()
  },

  async generateShareImage() {
    const query = wx.createSelectorQuery()
    query.select('#shareCanvas')
      .fields({ node: true, size: true })
      .exec(async (res) => {
        const canvas = res[0].node
        const ctx = canvas.getContext('2d')

        const dpr = wx.getWindowInfo().pixelRatio || 2
        const W = 1080, H = 1080
        canvas.width = W * dpr
        canvas.height = H * dpr
        ctx.scale(dpr, dpr)

        // 1. 背景渐变
        const gradient = ctx.createLinearGradient(0, 0, 0, H)
        gradient.addColorStop(0, '#667eea')
        gradient.addColorStop(1, '#764ba2')
        ctx.fillStyle = gradient
        ctx.fillRect(0, 0, W, H)

        // 2. 标题
        ctx.fillStyle = '#ffffff'
        ctx.font = 'bold 48px sans-serif'
        ctx.textAlign = 'center'
        ctx.fillText('DmkWords 学习报告', W / 2, 100)

        // 3. 白色卡片背景
        ctx.fillStyle = 'rgba(255,255,255,0.95)'
        const cardX = 60, cardY = 160, cardW = 960, cardH = 760
        this.roundRect(ctx, cardX, cardY, cardW, cardH, 24)
        ctx.fill()

        // 4. 孩子名 + 周期
        ctx.fillStyle = '#333333'
        ctx.font = 'bold 40px sans-serif'
        ctx.textAlign = 'left'
        const childName = (this.data.child && this.data.child.name) || '小朋友'
        ctx.fillText(childName, cardX + 40, cardY + 60)

        ctx.fillStyle = '#888888'
        ctx.font = '28px sans-serif'
        const periodText = this.data.reportTitle || '本周学习报告'
        ctx.fillText(periodText, cardX + 40, cardY + 105)

        // 5. 四个数据块
        const summary = this.data.summary || {}
        const dataBlocks = [
          { label: '阅读时长', value: this.formatMinutes(summary.total_minutes || 0) },
          { label: '读完本书', value: String(summary.books_finished || 0) },
          { label: '阅读词数', value: String(summary.total_words || 0) },
          { label: '打卡天数', value: String(summary.checkin_days || 0) },
        ]

        const blockW = 200, blockH = 160
        const blockGap = 24
        const totalBlocksW = blockW * 4 + blockGap * 3
        const startX = cardX + (cardW - totalBlocksW) / 2
        const blockY = cardY + 150

        dataBlocks.forEach((block, i) => {
          const bx = startX + i * (blockW + blockGap)
          ctx.fillStyle = '#f0f4ff'
          this.roundRect(ctx, bx, blockY, blockW, blockH, 16)
          ctx.fill()

          ctx.fillStyle = '#667eea'
          ctx.font = 'bold 48px sans-serif'
          ctx.textAlign = 'center'
          ctx.fillText(block.value, bx + blockW / 2, blockY + 80)

          ctx.fillStyle = '#888888'
          ctx.font = '24px sans-serif'
          ctx.fillText(block.label, bx + blockW / 2, blockY + 130)
        })

        // 6. 底部提示
        ctx.fillStyle = '#999999'
        ctx.font = '24px sans-serif'
        ctx.textAlign = 'center'
        ctx.fillText('长按查看完整报告', W / 2, cardY + cardH - 40)

        // 7. 小程序码 — 等待加载完成
        try {
          await this.loadQrCodeOntoCanvas(canvas, ctx, cardX + cardW - 180, cardY + cardH - 180, 160, 160)
        } catch (e) {
          console.warn('QR code load failed, continue without it', e)
        }

        // 8. 转临时文件并分享
        wx.canvasToTempFilePath({
          canvas,
          success: (res) => {
            wx.shareImageMenu({
              path: res.tempFilePath,
              fail: () => {
                wx.showToast({ title: '分享已取消', icon: 'none' })
              }
            })
          },
          fail: () => {
            wx.showToast({ title: '生成图片失败', icon: 'none' })
          }
        }, this)
      })
  },

  roundRect(ctx, x, y, w, h, r) {
    ctx.beginPath()
    ctx.moveTo(x + r, y)
    ctx.lineTo(x + w - r, y)
    ctx.quadraticCurveTo(x + w, y, x + w, y + r)
    ctx.lineTo(x + w, y + h - r)
    ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h)
    ctx.lineTo(x + r, y + h)
    ctx.quadraticCurveTo(x, y + h, x, y + h - r)
    ctx.lineTo(x, y + r)
    ctx.quadraticCurveTo(x, y, x + r, y)
    ctx.closePath()
  },

  loadQrCodeOntoCanvas(canvas, ctx, x, y, w, h) {
    return new Promise(function (resolve, reject) {
      const childId = (this.data.child && this.data.child.id) || ''
      const period = this.data.period || 'week'
      const scene = 'report_' + childId + '_' + period
      const page = 'pages/member-pkg/learning-report/learning-report'
      const baseURL = getApp().globalData.baseURL || 'https://api.dmkwords.cn'
      const url = baseURL + '/wechat/qr-code?scene=' + scene + '&page=' + page

      wx.downloadFile({
        url: url,
        success: function (res) {
          var img = canvas.createImage()
          img.src = res.tempFilePath
          img.onload = function () {
            ctx.drawImage(img, x, y, w, h)
            resolve()
          }
          img.onerror = function () {
            reject(new Error('QR image decode failed'))
          }
        },
        fail: function () {
          reject(new Error('QR code download failed'))
        }
      })
    }.bind(this))
  },

  formatMinutes(minutes) {
    if (minutes >= 60) {
      const h = Math.floor(minutes / 60)
      const m = minutes % 60
      return m > 0 ? `${h}h${m}m` : `${h}h`
    }
    return `${minutes}min`
  },
})
