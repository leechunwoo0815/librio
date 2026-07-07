// frontend/pages/login/login.js
const auth = require('../../utils/auth')

Page({
  data: {
    loading: false,
    redirect: '',
    error: '',
    retryCount: 0,
    phone: '',
    smsCode: '',
    smsDisabled: false,
    countdown: 0,
  },

  handleLogin() {
    this.setData({ loading: true, error: '' })
    const self = this
    auth.wxLogin()
      .then(() => {
        self.setData({ loading: false, retryCount: 0 })
        wx.switchTab({ url: self.data.redirect || '/pages/index/index' })
      })
      .catch((err) => {
        const retryCount = self.data.retryCount + 1
        const errorMsg = retryCount >= 3
          ? '多次登录失败，请检查网络或联系客服'
          : '登录失败，请重试'
        self.setData({ loading: false, error: errorMsg, retryCount })
        wx.showToast({ title: errorMsg, icon: 'none' })
      })
  },

  handlePhoneInput(e) {
    this.setData({ phone: e.detail.value })
  },

  handleSmsCodeInput(e) {
    this.setData({ smsCode: e.detail.value })
  },

  handleSendSms() {
    const { phone, countdown } = this.data
    if (countdown > 0) return
    if (!phone || phone.length !== 11) {
      wx.showToast({ title: '请输入正确的手机号', icon: 'none' })
      return
    }
    this.setData({ smsDisabled: true, countdown: 60 })
    this._startCountdown()
    // TODO: call backend SMS API
  },

  _startCountdown() {
    const self = this
    if (this._countdownTimer) clearInterval(this._countdownTimer)
    this._countdownTimer = setInterval(() => {
      const s = self.data.countdown - 1
      if (s <= 0) {
        clearInterval(self._countdownTimer)
        self.setData({ countdown: 0, smsDisabled: false })
      } else {
        self.setData({ countdown: s })
      }
    }, 1000)
  },

  handlePhoneLogin() {
    const { phone, smsCode } = this.data
    if (!phone || phone.length !== 11) {
      wx.showToast({ title: '请输入正确的手机号', icon: 'none' })
      return
    }
    if (!smsCode || smsCode.length < 4) {
      wx.showToast({ title: '请输入验证码', icon: 'none' })
      return
    }
    // TODO: call backend phone login API
    wx.showToast({ title: '手机号登录功能开发中', icon: 'none' })
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

  onUnload() {
    if (this._countdownTimer) {
      clearInterval(this._countdownTimer)
    }
  },
})
