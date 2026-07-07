// frontend/app.js
App({
  globalData: {
    // 本地开发环境使用 localhost，生产环境替换为 HTTPS 域名
    // 可通过 wx.setStorageSync('baseURL', 'https://your-domain.com') 动态配置
    baseURL: wx.getStorageSync('baseURL') || 'http://localhost:8002',
    token: '',
    userInfo: null,
    currentChild: null,
    isTestMode: false,
  },

  onLaunch() {
    // 版本更新检测
    if (wx.getUpdateManager) {
      const updateManager = wx.getUpdateManager()
      updateManager.onUpdateReady(function () {
        wx.showModal({
          title: '更新提示',
          content: '新版本已准备好，是否重启应用？',
          success(res) { if (res.confirm) updateManager.applyUpdate() }
        })
      })
    }

    // 网络状态检测
    wx.onNetworkStatusChange(function (res) {
      if (!res.isConnected) {
        wx.showToast({ title: '网络已断开，请检查网络连接', icon: 'none', duration: 3000 })
      }
    })

    const token = wx.getStorageSync('token')
    if (token) {
      this.globalData.token = token
    }

    // 检测测试模式（多重判断）
    let isTest = false
    try {
      const accountInfo = wx.getAccountInfoSync()
      const appId = accountInfo.miniProgram.appId || ''
      console.log('[MegaWords] appId:', appId)
      isTest = appId === 'touristappid' || appId === 'wxdevappid' || appId === '' || appId.startsWith('wx0000')
    } catch (e) {
      console.log('[MegaWords] getAccountInfoSync failed, assume test mode')
      isTest = true
    }

    if (isTest) {
      console.log('[MegaWords] 测试模式已启用')
      this.globalData.isTestMode = true
      if (!this.globalData.token) {
        this.globalData.token = 'test-token-mock'
        wx.setStorageSync('token', 'test-token-mock')
      }
      this.globalData.currentChild = {
        id: 1, name: '小明', english_name: 'Tom', age: 7, grade: '二年级',
        status: 2, total_words_read: 42000, total_books_finished: 15, current_streak_days: 7,
      }
      this.globalData.userInfo = { nickname: '家长' }
    }
  },
})
