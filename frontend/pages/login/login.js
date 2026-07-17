// frontend/pages/login/login.js

Page({
  data: {
    loading: false,
    redirect: '',
    error: '',
    retryCount: 0,
    showPhoneForm: false,
    phone: '',
    smsCode: '',
    smsDisabled: false,
    smsBtnText: '获取验证码',
    countdown: 0,
    privacyChecked: false,
  },

  onTogglePrivacy() {
    const checked = !this.data.privacyChecked
    this.setData({ privacyChecked: checked })
    wx.setStorageSync('privacy_agreed', checked)
  },

  handleLogin(e) {
    if (!this.data.privacyChecked) {
      wx.showToast({ title: '请先勾选同意隐私协议后再登录', icon: 'none' })
      return
    }
    const phoneCode = e.detail ? e.detail.code : null
    this._doLogin(phoneCode)
  },

  _doLogin(phoneCode) {
    this.setData({ loading: true, error: '' })
    const self = this
    wx.login({
      success(loginRes) {
        if (!loginRes.code) {
          self.setData({ loading: false })
          wx.showToast({ title: '登录失败', icon: 'none' })
          return
        }
        const data = { code: loginRes.code }
        if (phoneCode) data.phone_code = phoneCode
        const request = require('../../utils/request')
        request.post('/user/wx-login', data, { auth: false })
          .then(res => {
            const app = getApp()
            app.globalData.token = res.token
            app.globalData.userInfo = res.user
            wx.setStorageSync('token', res.token)
            wx.setStorageSync('userInfo', res.user)
            self.setData({ loading: false, retryCount: 0 })
            const targetUrl = self.data.redirect || '/pages/index/index'
            const tabBarPages = ['/pages/index/index', '/pages/books/books', '/pages/shelf/shelf', '/pages/member/member']
            if (tabBarPages.includes(targetUrl)) {
              wx.switchTab({ url: targetUrl })
            } else {
              wx.redirectTo({ url: targetUrl })
            }
          })
          .catch(err => {
            const retryCount = self.data.retryCount + 1
            const errorMsg = retryCount >= 3
              ? '多次登录失败，请检查网络或联系客服'
              : '登录失败，请重试'
            self.setData({ loading: false, error: errorMsg, retryCount })
            wx.showToast({ title: errorMsg, icon: 'none' })
          })
      },
      fail() {
        self.setData({ loading: false })
        wx.showToast({ title: '登录失败', icon: 'none' })
      }
    })
  },

  togglePhoneForm() {
    this.setData({ showPhoneForm: !this.data.showPhoneForm })
  },

  onPhoneInput(e) {
    this.setData({ phone: e.detail.value })
  },

  onSmsCodeInput(e) {
    this.setData({ smsCode: e.detail.value })
  },

  onSendSms() {
    const phone = this.data.phone
    if (!/^1\d{10}$/.test(phone)) {
      wx.showToast({ title: '请输入正确的手机号', icon: 'none' })
      return
    }
    const request = require('../../utils/request')
    request.post('/user/send-sms', { phone }, { auth: false })
      .then(() => {
        wx.showToast({ title: '验证码已发送', icon: 'success' })
        this._startCountdown()
      })
      .catch(() => {
        wx.showToast({ title: '发送失败，请重试', icon: 'none' })
      })
  },

  _startCountdown() {
    this.setData({ smsDisabled: true, countdown: 60, smsBtnText: '60s' })
    if (this._countdownTimer) clearInterval(this._countdownTimer)
    this._countdownTimer = setInterval(() => {
      let count = this.data.countdown - 1
      if (count <= 0) {
        clearInterval(this._countdownTimer)
        this._countdownTimer = null
        this.setData({ smsDisabled: false, smsBtnText: '获取验证码' })
      } else {
        this.setData({ countdown: count, smsBtnText: count + 's' })
      }
    }, 1000)
  },

  onUnload() {
    if (this._countdownTimer) {
      clearInterval(this._countdownTimer)
      this._countdownTimer = null
    }
  },

  onPhoneLogin() {
    const phone = this.data.phone
    const smsCode = this.data.smsCode
    if (!/^1\d{10}$/.test(phone)) {
      wx.showToast({ title: '请输入正确的手机号', icon: 'none' })
      return
    }
    if (!smsCode) {
      wx.showToast({ title: '请输入验证码', icon: 'none' })
      return
    }
    this._doPhoneLogin(phone, smsCode)
  },

  _doPhoneLogin(phone, smsCode) {
    this.setData({ loading: true, error: '' })
    const self = this
    // 手机号登录仍需 wx.login 获取 code，后端通过 code 拿到 openid 后再用手机号+验证码匹配用户
    wx.login({
      success(loginRes) {
        if (!loginRes.code) {
          self.setData({ loading: false })
          wx.showToast({ title: '登录失败', icon: 'none' })
          return
        }
        const request = require('../../utils/request')
        request.post('/user/phone-login', {
          code: loginRes.code,
          phone: phone,
          sms_code: smsCode,
        }, { auth: false })
          .then(res => {
            const app = getApp()
            app.globalData.token = res.token
            app.globalData.userInfo = res.user
            wx.setStorageSync('token', res.token)
            wx.setStorageSync('userInfo', res.user)
            self.setData({ loading: false, retryCount: 0 })
            const targetUrl = self.data.redirect || '/pages/index/index'
            const tabBarPages = ['/pages/index/index', '/pages/books/books', '/pages/shelf/shelf', '/pages/member/member']
            if (tabBarPages.includes(targetUrl)) {
              wx.switchTab({ url: targetUrl })
            } else {
              wx.redirectTo({ url: targetUrl })
            }
          })
          .catch(err => {
            const retryCount = self.data.retryCount + 1
            const errorMsg = retryCount >= 3
              ? '多次登录失败，请检查网络或联系客服'
              : (err && err.message) ? err.message : '登录失败，请重试'
            self.setData({ loading: false, error: errorMsg, retryCount })
            wx.showToast({ title: errorMsg, icon: 'none' })
          })
      },
      fail() {
        self.setData({ loading: false })
        wx.showToast({ title: '登录失败', icon: 'none' })
      }
    })
  },

  onTapService() {
    wx.navigateTo({ url: '/pages/agreement/service-agreement/service-agreement' })
  },

  onTapPrivacy() {
    wx.navigateTo({ url: '/pages/agreement/privacy-policy/privacy-policy' })
  },

  onLoad(options) {
    const app = getApp()
    if (options.redirect) {
      this.setData({ redirect: decodeURIComponent(options.redirect) })
    }
    if (app.globalData.token) {
      wx.switchTab({ url: '/pages/index/index' })
    }
  },
})
