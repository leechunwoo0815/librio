// frontend/pages/member-pkg/profile-card/profile-card.js
const api = require('../../utils/api')
const auth = require('../../utils/auth')

Page({
  data: {
    child: null,
    profile: {},
    currentLevel: {},
    achievements: [],
    testMode: false,
    todayDate: '',
  },

  async onLoad() {
    const now = new Date()
    const dateStr = `${now.getFullYear()}.${String(now.getMonth() + 1).padStart(2, '0')}.${String(now.getDate()).padStart(2, '0')}`
    this.setData({ todayDate: dateStr })

    const app = getApp()
    if (app.globalData.isTestMode) {
      this.setData({ testMode: true })
      this.loadTestData()
      return
    }
    if (!auth.requireAuth()) return
    await this.loadProfile()
  },

  loadTestData() {
    this.setData({
      child: { id: 1, name: '小明' },
      profile: {
        chinese_name: '小明',
        english_name: 'Tom',
        avatar_emoji: '👦',
        books_finished: 23,
        total_words_read: '1,280',
        current_streak: 15,
      },
      currentLevel: {
        level_name: 'B级 · 初学者',
        level_subtitle: 'Beginner Level',
        level_badge: 'B',
      },
      achievements: [
        { id: 1, name: '连续7天', badge_emoji: '🔥' },
        { id: 2, name: '读完20本', badge_emoji: '📚' },
        { id: 3, name: '测验满分', badge_emoji: '⭐' },
      ],
    })
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
    wx.createSelectorQuery()
      .select('#profileCard')
      .fields({ node: true, size: true })
      .exec((res) => {
        if (!res || !res[0] || !res[0].node) {
          wx.showToast({ title: '暂不支持保存', icon: 'none' })
          return
        }
        const canvas = res[0].node
        const ctx = canvas.getContext('2d')
        const dpr = wx.getSystemInfoSync().pixelRatio
        canvas.width = res[0].width * dpr
        canvas.height = res[0].height * dpr
        ctx.scale(dpr, dpr)

        wx.canvasToTempFilePath({
          canvas,
          success(imgRes) {
            wx.saveImageToPhotosAlbum({
              filePath: imgRes.tempFilePath,
              success() {
                wx.showToast({ title: '已保存到相册', icon: 'success' })
              },
              fail() {
                wx.showToast({ title: '保存失败', icon: 'none' })
              },
            })
          },
          fail() {
            wx.showToast({ title: '生成图片失败', icon: 'none' })
          },
        })
      })
  },

  onShareAppMessage() {
    const { profile } = this.data
    const name = profile.chinese_name || '小朋友'
    return {
      title: `${name}的学习名片 - MegaWords`,
      path: '/pages/index/index',
    }
  },
})
