// frontend/pages/order-pkg/messages/messages.js
const api = require('../../utils/api')
const auth = require('../../utils/auth')

const CATEGORIES = [
  { key: 'all', label: '全部' },
  { key: 'system', label: '系统通知' },
  { key: 'reading', label: '阅读提醒' },
  { key: 'activity', label: '活动通知' },
  { key: 'teacher', label: '老师消息' },
]

const CATEGORY_ICONS = {
  system: '🔔',
  reading: '📖',
  activity: '🎉',
  teacher: '👩‍🏫',
}

Page({
  data: {
    categories: CATEGORIES,
    activeTab: 'all',
    messages: [],
    filteredMessages: [],
    expandedId: null,
    loading: true,
    emptyText: '暂无消息',
    page: 1,
    hasMore: true,
  },

  onLoad() {
    const app = getApp()
    if (!auth.requireAuth()) return
    this.loadMessages()
  },

  onShow() {
    this.setData({ page: 1, hasMore: true })
    this.loadMessages()
  },

  onPullDownRefresh() {
    this.setData({ page: 1, hasMore: true })
    this.loadMessages().then(() => {
      wx.stopPullDownRefresh()
    })
  },

  onReachBottom() {
    if (this.data.hasMore && !this.data.loading) {
      this.loadMessages(this.data.page + 1)
    }
  },

  async loadMessages(page) {
    page = page || 1
    this.setData({ loading: true })
    try {
      const res = await api.getMessages(null, page)
      const items = res.items || res || []
      const enriched = items.map(msg => ({
        ...msg,
        icon: CATEGORY_ICONS[this._typeToCategory(msg.msg_type)] || '📢',
        category: this._typeToCategory(msg.msg_type),
        timeText: this.formatTime(msg.create_time),
        dateText: this.formatDate(msg.create_time),
        is_read: msg.is_read === 1,
        showDate: false,
      }))
      // Mark first message of each date group to show date separator
      let lastDate = ''
      for (let i = 0; i < enriched.length; i++) {
        if (enriched[i].dateText !== lastDate) {
          enriched[i].showDate = true
          lastDate = enriched[i].dateText
        }
      }
      const allMessages = page === 1 ? enriched : [...this.data.messages, ...enriched]
      const hasMore = allMessages.length < (res.total || 0)
      this.setData({
        messages: allMessages,
        page,
        hasMore,
        loading: false,
        unreadCount: res.unread_count || 0,
      })
      this.filterMessages()
    } catch (e) {
      console.error('Load messages failed:', e)
      this.setData({ loading: false, messages: [], filteredMessages: [] })
    }
  },

  _typeToCategory(type) {
    const map = { 1: 'system', 2: 'activity', 3: 'reading', 4: 'teacher', 5: 'reading' }
    return map[type] || 'system'
  },

  switchTab(e) {
    const tab = e.currentTarget.dataset.tab
    const emptyMap = {
      all: '暂无消息', system: '暂无系统通知', reading: '暂无阅读提醒',
      activity: '暂无活动通知', teacher: '暂无老师消息',
    }
    this.setData({ activeTab: tab, expandedId: null, emptyText: emptyMap[tab] || '暂无消息' })
    this.filterMessages()
  },

  filterMessages() {
    const { messages, activeTab } = this.data
    const filtered = activeTab === 'all'
      ? messages
      : messages.filter(m => m.category === activeTab)
    this.setData({ filteredMessages: filtered })
  },

  toggleMessage(e) {
    const id = e.currentTarget.dataset.id
    const current = this.data.expandedId
    this.setData({ expandedId: current === id ? null : id })
  },

  formatDate(dateStr) {
    if (!dateStr) return ''
    const d = new Date(dateStr)
    const now = new Date()
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
    const target = new Date(d.getFullYear(), d.getMonth(), d.getDate())
    const diffDay = Math.floor((today - target) / 86400000)

    if (diffDay === 0) return '今天'
    if (diffDay === 1) return '昨天'

    const m = d.getMonth() + 1
    const day = d.getDate()
    if (d.getFullYear() === now.getFullYear()) {
      return `${m}月${day}日`
    }
    return `${d.getFullYear()}-${String(m).padStart(2, '0')}-${String(day).padStart(2, '0')}`
  },

  formatTime(dateStr) {
    if (!dateStr) return ''
    const d = new Date(dateStr)
    const now = new Date()
    const diffMs = now - d
    const diffMin = Math.floor(diffMs / 60000)
    const diffHour = Math.floor(diffMs / 3600000)
    const diffDay = Math.floor(diffMs / 86400000)

    if (diffMin < 1) return '刚刚'
    if (diffMin < 60) return `${diffMin}分钟前`
    if (diffHour < 24) return `${diffHour}小时前`
    if (diffDay < 7) return `${diffDay}天前`

    const m = String(d.getMonth() + 1).padStart(2, '0')
    const day = String(d.getDate()).padStart(2, '0')
    return `${m}-${day}`
  },

  getEmptyText() {
    const tab = this.data.activeTab
    const map = {
      all: '暂无消息',
      system: '暂无系统通知',
      reading: '暂无阅读提醒',
      activity: '暂无活动通知',
      teacher: '暂无老师消息',
    }
    return map[tab] || '暂无消息'
  },

  async markAllRead() {
    try {
      await api.markAllMessagesRead()
      const msgs = this.data.messages.map(function (m) {
        return Object.assign({}, m, { is_read: 1, read: true })
      })
      this.setData({ messages: msgs, unreadCount: 0 })
      wx.showToast({ title: '已全部标记为已读', icon: 'success' })
    } catch (e) {
      wx.showToast({ title: '操作失败', icon: 'none' })
    }
  },

  async toggleMessage(e) {
    const id = e.currentTarget.dataset.id
    const msg = this.data.messages.find(m => m.id === id)
    if (msg && !msg.is_read) {
      try {
        await api.markMessageRead(id)
        msg.is_read = 1
        this.setData({ messages: this.data.messages, unreadCount: Math.max(0, (this.data.unreadCount || 1) - 1) })
      } catch (e) { /* silent */ }
    }
  },
})
