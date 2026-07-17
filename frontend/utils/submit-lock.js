// frontend/utils/submit-lock.js
// MP-019: 全局提交防重复 — 防止网络慢时重复点击
const locks = new Map()

module.exports = {
  /**
   * 带锁提交 — 按钮点击后立即 lock，完成后 unlock
   * @param {string} key - 锁的 key（如 'createOrder', 'submitQuiz'）
   * @param {Function} fn - 异步函数
   * @returns {Promise} fn 的返回值
   */
  async submitWithLock(key, fn) {
    if (locks.get(key)) {
      wx.showToast({ title: '请勿重复提交', icon: 'none' })
      return
    }
    locks.set(key, true)
    try {
      return await fn()
    } finally {
      locks.delete(key)
    }
  },

  isLocked(key) {
    return !!locks.get(key)
  },
}
