// frontend/pages/member-pkg/profile-card/profile-card.js
const api = require('../../utils/api')
const auth = require('../../utils/auth')

Page({
  data: {
    child: null,
    profile: {},
    currentLevel: {},
    achievements: [],
    todayDate: '',
    qrUrl: '',
  },

  async onLoad() {
    const now = new Date()
    const dateStr = `${now.getFullYear()}.${String(now.getMonth() + 1).padStart(2, '0')}.${String(now.getDate()).padStart(2, '0')}`
    this.setData({ todayDate: dateStr })

    if (!auth.requireAuth()) return
    await this.loadProfile()
  },

  async loadProfile() {
    try {
      const children = await api.getChildren()
      if (!children || children.length === 0) return

      const child = auth.selectChild(children)
      if (!child) return
      this.setData({ child })

      const [profile, level, earned] = await Promise.all([
        api.getProfile(child.id).catch(() => ({})),
        api.getCurrentLevel(child.id).catch(() => ({})),
        api.getChildAchievements(child.id).catch(() => []),
      ])

      const achievements = (Array.isArray(earned) ? earned : []).slice(0, 3)

      this.setData({
        profile: profile || {},
        currentLevel: level || {},
        achievements,
      })
    } catch (e) {
      console.error('loadProfile failed:', e)
    }
  },

  savePoster() {
    const query = wx.createSelectorQuery()
    query.select('#posterCanvas')
      .fields({ node: true, size: true })
      .exec(async (res) => {
        if (!res || !res[0] || !res[0].node) {
          wx.showToast({ title: '暂不支持保存', icon: 'none' })
          return
        }
        const canvas = res[0].node
        const ctx = canvas.getContext('2d')
        const dpr = wx.getSystemInfoSync().pixelRatio
        const width = 600
        const height = 900
        canvas.width = width * dpr
        canvas.height = height * dpr
        ctx.scale(dpr, dpr)

        const { profile, currentLevel, achievements, todayDate } = this.data

        ctx.fillStyle = '#ffffff'
        ctx.fillRect(0, 0, width, height)

        ctx.fillStyle = '#f0f4ff'
        ctx.beginPath()
        ctx.arc(width - 60, 40, 80, 0, Math.PI * 2)
        ctx.fill()
        ctx.beginPath()
        ctx.arc(width - 20, 80, 40, 0, Math.PI * 2)
        ctx.fill()

        let y = 60
        const avatarText = (profile.avatar_emoji || (profile.chinese_name || '?')[0])
        ctx.fillStyle = '#5560cf'
        ctx.beginPath()
        ctx.arc(60, y, 34, 0, Math.PI * 2)
        ctx.fill()
        ctx.fillStyle = '#ffffff'
        ctx.font = 'bold 28px sans-serif'
        ctx.textAlign = 'center'
        ctx.textBaseline = 'middle'
        ctx.fillText(avatarText, 60, y)

        ctx.fillStyle = '#1a1a2e'
        ctx.font = 'bold 26px sans-serif'
        ctx.textAlign = 'left'
        ctx.textBaseline = 'top'
        ctx.fillText(profile.chinese_name || '未知', 110, y - 12)

        ctx.fillStyle = '#888888'
        ctx.font = '16px sans-serif'
        ctx.fillText(profile.english_name || '', 110, y + 20)

        y = 140
        const badgeText = currentLevel.level_badge || currentLevel.badge_emoji || 'B'
        ctx.fillStyle = '#5560cf'
        ctx.beginPath()
        ctx.arc(60, y, 22, 0, Math.PI * 2)
        ctx.fill()
        ctx.fillStyle = '#ffffff'
        ctx.font = '18px sans-serif'
        ctx.textAlign = 'center'
        ctx.textBaseline = 'middle'
        ctx.fillText(badgeText, 60, y)

        ctx.fillStyle = '#1a1a2e'
        ctx.font = 'bold 20px sans-serif'
        ctx.textAlign = 'left'
        ctx.textBaseline = 'top'
        ctx.fillText(currentLevel.level_name || '未评级', 95, y - 8)

        ctx.fillStyle = '#888888'
        ctx.font = '14px sans-serif'
        ctx.fillText(currentLevel.level_subtitle || '', 95, y + 16)

        y = 200
        ctx.fillStyle = '#eeeeee'
        ctx.fillRect(30, y, width - 60, 1)

        y = 230
        const stats = [
          { val: profile.books_finished || 0, label: '读完本书' },
          { val: profile.total_words_read || 0, label: '累计词数' },
          { val: profile.current_streak || 0, label: '连续打卡' },
        ]
        const statWidth = (width - 80) / 3
        stats.forEach((stat) => {
          const sx = 40 + statWidth * (stats.indexOf(stat)) + statWidth / 2
          ctx.fillStyle = '#1a1a2e'
          ctx.font = 'bold 22px sans-serif'
          ctx.textAlign = 'center'
          ctx.textBaseline = 'top'
          ctx.fillText(String(stat.val), sx, y)
          ctx.fillStyle = '#888888'
          ctx.font = '12px sans-serif'
          ctx.fillText(stat.label, sx, y + 30)
        })

        y = 310
        if (achievements && achievements.length > 0) {
          ctx.fillStyle = '#eeeeee'
          ctx.fillRect(30, y, width - 60, 1)
          y += 20
          achievements.forEach((ach) => {
            ctx.fillStyle = '#1a1a2e'
            ctx.font = '16px sans-serif'
            ctx.textAlign = 'left'
            ctx.textBaseline = 'top'
            ctx.fillText((ach.badge_emoji || '🏆') + ' ' + (ach.name || ''), 40, y)
            y += 36
          })
        }

        y = Math.max(y + 10, 370)
        ctx.fillStyle = '#eeeeee'
        ctx.fillRect(30, y, width - 60, 1)
        y += 30

        ctx.fillStyle = '#1a1a2e'
        ctx.font = 'bold 16px sans-serif'
        ctx.textAlign = 'left'
        ctx.textBaseline = 'top'
        ctx.fillText('扫码加入 DmkWords', 135, y + 10)

        ctx.fillStyle = '#888888'
        ctx.font = '12px sans-serif'
        ctx.fillText('让孩子爱上阅读，轻松掌握英文词汇', 135, y + 36)

        try {
          await this.loadQrCodeOntoCanvas(canvas, ctx, 40, y, 80, 80)
        } catch (e) {
          console.error('QR code load failed, skipping:', e)
        }

        y += 110
        ctx.fillStyle = '#eeeeee'
        ctx.fillRect(30, y, width - 60, 1)
        y += 20

        ctx.fillStyle = '#5560cf'
        ctx.font = 'bold 18px sans-serif'
        ctx.textAlign = 'left'
        ctx.textBaseline = 'top'
        ctx.fillText('DmkWords', 40, y)

        ctx.fillStyle = '#aaaaaa'
        ctx.font = '12px sans-serif'
        ctx.textAlign = 'right'
        ctx.textBaseline = 'top'
        ctx.fillText(todayDate || '', width - 40, y + 4)

        wx.canvasToTempFilePath({
          canvas,
          success(imgRes) {
            wx.saveImageToPhotosAlbum({
              filePath: imgRes.tempFilePath,
              success() {
                wx.showToast({ title: '已保存到相册', icon: 'success' })
              },
              fail(err) {
                if (err && err.errMsg && (err.errMsg.indexOf('auth deny') >= 0 || err.errMsg.indexOf('fail auth') >= 0)) {
                  wx.showModal({
                    title: '需要权限',
                    content: '保存图片到相册需要您的授权',
                    confirmText: '去授权',
                    success(modalRes) {
                      if (modalRes.confirm) { wx.openSetting() }
                    }
                  })
                } else {
                  wx.showToast({ title: '保存失败，请重试', icon: 'none' })
                }
              },
            })
          },
          fail() {
            wx.showToast({ title: '生成图片失败', icon: 'none' })
          },
        })
      })
  },

  loadQrCodeOntoCanvas(canvas, ctx, x, y, w, h) {
    return new Promise(function (resolve, reject) {
      const childId = (this.data.child && this.data.child.id) || ''
      const scene = 'profile_' + childId
      const page = 'pages/member-pkg/profile-card/profile-card'
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
          this.setData({ qrUrl: res.tempFilePath })
        }.bind(this),
        fail: function () {
          reject(new Error('QR code download failed'))
        }
      })
    }.bind(this))
  },

  onShareAppMessage() {
    const { profile } = this.data
    const name = profile.chinese_name || '小朋友'
    return {
      title: `${name}的学习名片 - DmkWords`,
      path: '/pages/index/index',
    }
  },
})
