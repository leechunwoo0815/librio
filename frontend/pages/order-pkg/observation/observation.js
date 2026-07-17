// frontend/pages/order-pkg/observation/observation.js
const api = require('../../utils/api')
const auth = require('../../utils/auth')

Page({
  data: {
    child: null,
    loading: false,
    price: '',
    isIOS: false,
    faqList: [
      {
        q: '观察期和正式会员有什么区别？',
        a: '观察期为30天体验，可在线阅读全量图书、每日打卡、查看阅读统计和老师评估报告。正式会员为年卡，额外享有A-Z晋级体系、排行榜、成就系统等完整功能。',
        open: false,
      },
      {
        q: '观察期到期后会自动扣费吗？',
        a: '不会。观察期为一次性付费，到期后不会自动续费。您可以在到期前选择升级为正式会员。',
        open: false,
      },
      {
        q: '观察期内可以申请退款吗？',
        a: '观察期开始7天内可申请全额退款，超过7天按剩余天数比例退款。',
        open: false,
      },
      {
        q: '第二个孩子报名有优惠吗？',
        a: '正式会员第2个孩子起享受9折优惠。观察期暂无折扣。',
        open: false,
      },
    ],
  },

  onLoad() {
    const app = getApp()
    if (!auth.requireAuth()) return
    const deviceInfo = wx.getDeviceInfo()
    this.setData({ isIOS: deviceInfo.platform === 'ios' })
    this.loadChild()
  },

  async loadChild() {
    try {
      const children = await api.getChildren()
      if (children && children.length > 0) {
        const child = auth.selectChild(children)

        let price = this.data.price
        try {
          const tierData = await api.getTiers()
          const obs = (tierData.tiers || []).find(t => t.type === 2)
          if (obs) price = obs.price
        } catch (e) {
          console.error('Load tier price failed:', e)
        }

        this.setData({ child, price })
      }
    } catch (e) {
      console.error(e)
    }
  },

  toggleFaq(e) {
    const idx = e.currentTarget.dataset.index
    const key = `faqList[${idx}].open`
    this.setData({ [key]: !this.data.faqList[idx].open })
  },

  async handleOrder() {
    if (this.data.isIOS) {
      wx.showModal({
        title: '暂不支持 iOS 开通',
        content: '当前暂不支持 iOS 端开通，请使用安卓设备或联系客服办理',
        showCancel: false,
      })
      return
    }
    const child = this.data.child
    if (!child) {
      wx.showToast({ title: '请先添加孩子信息', icon: 'none' })
      return
    }

    this.setData({ loading: true })
    try {
      const order = await api.createOrder(child.id, 2)
      const payParams = await api.getPayParams(order.id)
      if (!payParams || !payParams.timeStamp || !payParams.nonceStr || !payParams.package || !payParams.signType || !payParams.paySign) {
        throw new Error('支付参数异常，请稍后重试')
      }
      await new Promise((resolve, reject) => {
        wx.requestPayment({
          ...payParams,
          success: resolve,
          fail: reject,
        })
      })
      wx.showToast({ title: '支付成功', icon: 'success' })
      this._navTimer = setTimeout(() => {
        wx.navigateBack()
      }, 1500)
    } catch (e) {
      if (e.errMsg && e.errMsg.indexOf('cancel') > -1) {
        wx.showToast({ title: '已取消支付', icon: 'none' })
      } else {
        wx.showToast({ title: '支付失败，请重试', icon: 'none' })
      }
    } finally {
      this.setData({ loading: false })
    }
  },

  onUnload() {
    if (this._navTimer) { clearTimeout(this._navTimer); this._navTimer = null }
  },
})
