// frontend/pages/order-pkg/borrow-history/borrow-history.js
const api = require('../../utils/api')
const auth = require('../../utils/auth')

const STATUS_TEXT = { borrowed: '借出', returned: '已还', overdue: '逾期', lost: '丢失' }
const STATUS_CLASS = { borrowed: 'st-borrowed', returned: 'st-returned', overdue: 'st-overdue', lost: 'st-lost' }

Page({
  data: {
    activeTab: 'borrowing',
    borrowingRecords: [],
    returnedRecords: [],
    allRecords: [],
    borrowingDisplay: [],
    returnedDisplay: [],
    allDisplay: [],
    summary: { current: 0, total: 0, overdue: 0 },
    loading: true,
  },

  onLoad() {
    if (!auth.requireAuth()) return
    this.loadRecords()
  },

  async loadRecords() {
    this.setData({ loading: true })
    try {
      const child = auth.getCurrentChild()
      if (!child) {
        this.setData({ loading: false })
        return
      }
      const res = await api.getChildBorrows(child.id)
      const rawList = res.list || res || []
      const records = rawList.map(r => this._formatRecord(r))

      const borrowing = records.filter(r => r.status === 'borrowed' || r.status === 'overdue')
      const returned = records.filter(r => r.status === 'returned' || r.status === 'lost')

      this.setData({
        borrowingRecords: borrowing,
        returnedRecords: returned,
        allRecords: records,
        borrowingDisplay: this._buildDisplayList(borrowing),
        returnedDisplay: this._buildDisplayList(returned),
        allDisplay: this._buildDisplayList(records),
        summary: {
          current: borrowing.length,
          total: records.length,
          overdue: records.filter(r => r.status === 'overdue').length,
        },
      })
    } catch (e) {
      console.error('Load borrow history failed:', e)
      wx.showToast({ title: '加载失败', icon: 'none' })
    } finally {
      this.setData({ loading: false })
    }
  },

  _formatRecord(r) {
    const status = r.status || 'borrowed'
    return {
      id: r.id,
      title: r.book_title || r.title || '',
      author: r.book_author || r.author || '',
      cover: r.cover || '',
      borrowedAt: (r.borrowed_at || r.borrow_time || '').slice(0, 10),
      dueAt: (r.due_at || r.due_time || '').slice(0, 10),
      returnedAt: (r.returned_at || r.return_time || '').slice(0, 10),
      status,
      statusText: STATUS_TEXT[status] || '借出',
      statusClass: STATUS_CLASS[status] || 'st-borrowed',
      testPassed: !!r.test_passed,
      fine: r.fine || 0,
      overdueDays: r.overdue_days || 0,
    }
  },

  _buildDisplayList(records) {
    if (!records || records.length === 0) return []
    const groups = {}
    records.forEach(r => {
      const d = r.returnedAt || r.borrowedAt
      const month = d ? d.slice(0, 7) : ''
      if (!groups[month]) groups[month] = []
      groups[month].push(r)
    })
    const months = Object.keys(groups).sort((a, b) => b.localeCompare(a))
    const list = []
    months.forEach(m => {
      if (m) list.push({ _type: 'divider', text: m.replace('-', '年') + '月' })
      groups[m].forEach(r => list.push({ _type: 'record', ...r }))
    })
    return list
  },

  switchTab(e) {
    const tab = e.currentTarget.dataset.tab
    this.setData({ activeTab: tab })
  },

  goBack() {
    wx.navigateBack()
  },
})
