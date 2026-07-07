// frontend/pages/order-pkg/official/official.js
const api = require('../../utils/api')
const auth = require('../../utils/auth')

Page({
  data: {
    child: null,
    children: [],
    loading: false,
    isSecondChild: false,
    actualPrice: 5400,
    features: [
      { icon: '📚', title: '全量图书无限阅读', desc: '平台所有图书随时在线阅读' },
      { icon: '🎯', title: 'A-Z 26级晋级体系', desc: '科学分级，循序渐进提升阅读能力' },
      { icon: '🏆', title: '排行榜竞技', desc: '与同龄小伙伴比拼阅读量，激发阅读兴趣' },
      { icon: '📜', title: '晋级证书', desc: '每通过一个级别即可获得专属晋级证书' },
      { icon: '⭐', title: '成就系统', desc: '丰富的成就徽章，记录每一个阅读里程碑' },
    ],
    comparisons: [
      { feature: '在线阅读图书', observation: true, official: true },
      { feature: '每日打卡', observation: true, official: true },
      { feature: '阅读统计', observation: true, official: true },
      { feature: '老师定期评估', observation: true, official: true },
      { feature: '观察期结束报告', observation: true, official: false },
      { feature: 'A-Z晋级体系', observation: false, official: true },
      { feature: '排行榜', observation: false, official: true },
      { feature: '晋级证书', observation: false, official: true },
      { feature: '成就系统', observation: false, official: true },
      { feature: '有效期', observation: '30天', official: '365天' },
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
      if (!children || children.length === 0) return

      const child = auth.selectChild(children)
      if (!child) return

      const detail = await api.getChild(child.id).catch(() => child)
      // 二孩优惠：已有其他孩子是观察期/正式会员
      const activeSiblings = children.filter(c =>
        c.id !== child.id && (c.status === 1 || c.status === 2)
      )
      const isSecondChild = activeSiblings.length >= 1
      const actualPrice = isSecondChild ? 4860 : 5400

      this.setData({ child: detail, children, isSecondChild, actualPrice })
    } catch (e) {
      console.error(e)
    }
  },

  async handleOrder() {
    // iOS 虚拟支付拦截（Apple 审核红线）
    const sysInfo = wx.getSystemInfoSync()
    if (sysInfo.platform === 'ios') {
      this.showIOSNotice()
      return
    }

    const child = this.data.child
    if (!child) {
      wx.showToast({ title: '请先添加孩子信息', icon: 'none' })
      return
    }

    this.setData({ loading: true })
    try {
      const order = await api.createOrder(child.id, 3)
      const payParams = await api.getPayParams(order.id)
      await new Promise((resolve, reject) => {
        wx.requestPayment({
          ...payParams,
          success: resolve,
          fail: reject,
        })
      })
      wx.showToast({ title: '开通成功', icon: 'success' })
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
