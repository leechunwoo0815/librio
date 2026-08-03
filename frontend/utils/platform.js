// frontend/utils/platform.js — 平台判断与 iOS 支付引导（P1-1：统一各页重复判定）
const req = require('./request')

/** 是否 iOS 平台（统一封装，各页不再重复 wx.getWindowInfo/getDeviceInfo） */
function isIOS() {
  try {
    return wx.getWindowInfo().platform === 'ios'
  } catch (e) {
    return false
  }
}

/**
 * iOS 虚拟服务支付引导弹窗（A5/P1-1）
 * 虚拟服务（观察期/会员）iOS 禁付是苹果政策，给出门店收款码/对公转账替代路径
 * 及人工兜底联系方式（G2：/venue/contact）。
 * @param {string} productName 产品名（如 观察期/正式会员）
 */
async function showIOSPaymentGuide(productName) {
  let contact = {}
  try {
    contact = await req.get('/venue/contact', null, { auth: false })
  } catch (e) { /* 联系信息获取失败不阻塞引导 */ }
  const lines = [
    `因苹果规则限制，iOS 端暂不支持在线支付${productName || '虚拟服务'}。`,
    '可前往门店扫码办理，或通过对公转账后联系客服开通。',
  ]
  if (contact.venue_name) lines.push(`办理门店：${contact.venue_name}`)
  if (contact.phone) lines.push(`门店电话：${contact.phone}`)
  if (contact.wechat) lines.push(`客服微信：${contact.wechat}`)
  wx.showModal({
    title: 'iOS 端办理指引',
    content: lines.join('\n'),
    showCancel: false,
    confirmText: '我知道了',
  })
}

module.exports = { isIOS, showIOSPaymentGuide }
