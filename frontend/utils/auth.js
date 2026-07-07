// frontend/utils/auth.js — 登录鉴权

const request = require('./request')

function wxLogin() {
  return new Promise((resolve, reject) => {
    wx.login({
      success(loginRes) {
        if (!loginRes.code) {
          reject(new Error('wx.login 获取 code 失败'))
          return
        }
        request.post('/user/wx-login', { code: loginRes.code }, { auth: false })
          .then(data => {
            const app = getApp()
            app.globalData.token = data.token
            app.globalData.userInfo = data.user
            wx.setStorageSync('token', data.token)
            resolve(data)
          })
          .catch(reject)
      },
      fail: reject
    })
  })
}

function checkSession() {
  return new Promise((resolve) => {
    wx.checkSession({
      success() { resolve(true) },
      fail() { resolve(false) }
    })
  })
}

async function ensureLogin() {
  const app = getApp()
  if (app.globalData.token) {
    const valid = await checkSession()
    if (valid) return true
  }
  await wxLogin()
  return true
}

function selectChild(children) {
  if (!children || children.length === 0) return null
  const app = getApp()
  // 优先用上次选中的孩子
  const lastId = wx.getStorageSync('currentChildId')
  const found = children.find(c => c.id === lastId)
  const child = found || children[0]
  app.globalData.currentChild = child
  wx.setStorageSync('currentChildId', child.id)
  return child
}

function getCurrentChild() {
  const app = getApp()
  return app.globalData.currentChild
}

function requireAuth(redirectUrl) {
  const app = getApp()
  // 测试模式直接放行
  if (app.globalData.isTestMode) return true
  if (!app.globalData.token) {
    wx.redirectTo({ url: `/pages/login/login?redirect=${encodeURIComponent(redirectUrl || '/pages/index/index')}` })
    return false
  }
  return true
}

module.exports = { wxLogin, checkSession, ensureLogin, selectChild, getCurrentChild, requireAuth }
