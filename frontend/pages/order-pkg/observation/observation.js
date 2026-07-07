// frontend/pages/order-pkg/observation/observation.js
const api = require('../../utils/api')
const auth = require('../../utils/auth')

Page({
  data: {
    child: null,
    loading: false,
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
        a: '正式会员第2个孩子起享受9折优惠（4860元/年）。观察期暂无折扣。',
        open: false,
      },
    ],
  },

  onLoad() {
    const app = getApp()
    if (!auth.requireAuth()) return
    this.loadChild()
  },

  async loadChild() {
    try {
      const children = await api.getChildren()
      if (children && children.length > 0) {
        const child = auth.selectChild(children)
        this.setData({ child })
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
    // iOS 虚拟支付拦截（Apple 审核红线）
    const sysInfo = wx.getSystemInfoSync()
    if (sysInfo.platform === 'ios') {
      wx.showModal({
        title: '提示',
        content: '因苹果规则限制，请前往线下门店或使用安卓设备办理',
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
      const order = await api.createOrder(child.id, 2, 500)
      const payParams = await api.getPayParams(order.id)
      await new Promise((resolve, reject) => {
        wx.requestPayment({
          ...payParams,
          success: resolve,
          fail: reject,
        })
      })
      wx.showToast({ title: '支付成功', icon: 'success' })
      setTimeout(() => {
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

  showIOSNotice() {
    wx.showModal({
      title: '提示',
      content: '因苹果规则限制，请前往线下门店或使用安卓设备办理',
      showCancel: false,
    });
  },
})
