// frontend/pages/books/books.js
const api = require('../../utils/api')
const auth = require('../../utils/auth')

const AR_LEVELS = [
  { label: 'AR级别', value: '' },
  { label: 'AR 0.5-2.0', value: '0.5-2.0' },
  { label: 'AR 2.0-4.0', value: '2.0-4.0' },
  { label: 'AR 4.0-6.0', value: '4.0-6.0' },
  { label: 'AR 6.0+', value: '6.0+' },
]

const AGE_RANGES = [
  { label: '年龄段', value: '' },
  { label: '3-5岁', value: '3-5' },
  { label: '6-8岁', value: '6-8' },
  { label: '9-11岁', value: '9-11' },
  { label: '12-15岁', value: '12-15' },
]

const CATEGORIES = [
  { label: '故事', value: 'story' },
  { label: '科普', value: 'science' },
  { label: '有声书', value: 'audio' },
]

Page({
  data: {
    books: [],
    keyword: '',
    arLevelIndex: 0,
    ageRangeIndex: 0,
    categoryIndex: -1,
    arLevels: AR_LEVELS,
    ageRanges: AGE_RANGES,
    hasActiveFilter: false,
    page: 1,
    pageSize: 10,
    hasMore: true,
    loading: false,
    loadError: false,
    showNavBar: true,
    categories: CATEGORIES,
  },

  onLoad() {
    this.search()
  },

  onShow() {
    // tabBar 页面每次显示时刷新（从其他页面返回时）
  },

  onPullDownRefresh() {
    this.search().then(() => {
      wx.stopPullDownRefresh()
    }).catch((err) => {
      console.error('[books search failed]', err)
      wx.stopPullDownRefresh()
    })
  },

  onReachBottom() {
    if (this.data.loading) return
    if (this.data.hasMore) {
      this.setData({ page: this.data.page + 1 })
      this.search(false)
    }
  },

  buildParams() {
    const { keyword, arLevelIndex, ageRangeIndex, categoryIndex, arLevels, ageRanges, categories, page, pageSize } = this.data
    const params = { page, page_size: pageSize }
    if (keyword) params.keyword = keyword
    if (arLevelIndex > 0) params.ar_level = arLevels[arLevelIndex].value
    if (ageRangeIndex > 0) params.age_range = ageRanges[ageRangeIndex].value
    if (categoryIndex >= 0) params.category = categories[categoryIndex].value
    return params
  },

  async search(reset = true) {
    if (this.data.loading) return

    if (reset) {
      this.setData({ page: 1, books: [], hasMore: true })
    }

    this.setData({ loading: true })

    try {
      const params = this.buildParams()
      const result = await api.searchBooks(params)
      const newList = result.list || []
      const books = reset ? newList : [...this.data.books, ...newList]
      this.setData({
        books,
        hasMore: books.length < (result.total || 0),
        loading: false,
      })
    } catch (e) {
      console.error('Search books failed:', e)
      this.setData({ loading: false, loadError: true })
    }
  },

  _searchTimer: null,

  onSearchInput(e) {
    this.setData({ keyword: e.detail.value })
    // 防抖：300ms 后自动搜索
    if (this._searchTimer) clearTimeout(this._searchTimer)
    this._searchTimer = setTimeout(() => { this.search() }, 300)
  },

  onSearch() {
    this.search()
  },

  onClearKeyword() {
    this.setData({ keyword: '' })
    this.search()
  },

  onFilterAR(e) {
    const index = Number(e.detail.value)
    this.setData({
      arLevelIndex: index,
      hasActiveFilter: index > 0 || this.data.ageRangeIndex > 0,
    })
    this.search()
  },

  onFilterAge(e) {
    const index = Number(e.detail.value)
    this.setData({
      ageRangeIndex: index,
      hasActiveFilter: this.data.arLevelIndex > 0 || index > 0,
    })
    this.search()
  },

  onTapAR(e) {
    const index = Number(e.currentTarget.dataset.index)
    this.setData({
      arLevelIndex: index,
      ageRangeIndex: 0,
      hasActiveFilter: index > 0,
    })
    this.search()
  },

  onTapAge(e) {
    const index = Number(e.currentTarget.dataset.index)
    this.setData({
      ageRangeIndex: index,
      arLevelIndex: 0,
      categoryIndex: -1,
      hasActiveFilter: index > 0,
    })
    this.search()
  },

  onTapCategory(e) {
    const index = Number(e.currentTarget.dataset.index)
    this.setData({
      categoryIndex: index,
      arLevelIndex: 0,
      ageRangeIndex: 0,
      hasActiveFilter: index >= 0,
    })
    this.search()
  },

  onResetFilter() {
    this.setData({
      arLevelIndex: 0,
      ageRangeIndex: 0,
      categoryIndex: -1,
      hasActiveFilter: false,
    })
    this.search()
  },

  goDetail(e) {
    const id = e.currentTarget.dataset.id
    wx.navigateTo({ url: `/pages/reading-pkg/book-detail/book-detail?id=${id}` })
  },

  async onAddToShelf(e) {
    const bookId = e.currentTarget.dataset.id
    const child = auth.getCurrentChild()

    if (!child) {
      wx.showToast({ title: '请先选择孩子', icon: 'none' })
      return
    }

    // Set adding state on the specific book
    const books = this.data.books
    const idx = books.findIndex(b => b.id === bookId)
    if (idx === -1 || books[idx]._adding) return

    this.setData({ [`books[${idx}]._adding`]: true })

    try {
      await api.addToShelf(bookId, child.id)
      wx.showToast({ title: '已加入书架', icon: 'success' })
    } catch (e) {
      const msg = e.message || '添加失败'
      wx.showToast({ title: msg, icon: 'none' })
    } finally {
      this.setData({ [`books[${idx}]._adding`]: false })
    }
  },

  goBack() {
    wx.navigateBack()
  },

  async onReserve(e) {
    const bookId = e.currentTarget.dataset.id
    const child = auth.getCurrentChild()

    if (!child) {
      wx.showToast({ title: '请先选择孩子', icon: 'none' })
      return
    }

    try {
      await api.createReservation(child.id, bookId)
      wx.showToast({ title: '预约成功', icon: 'success' })
    } catch (e) {
      wx.showToast({ title: e.message || '预约失败', icon: 'none' })
    }
  },

  onRetry() {
    this.setData({ loadError: false })
    this.search()
  },

  onUnload() {
    if (this._searchTimer) {
      clearTimeout(this._searchTimer)
      this._searchTimer = null
    }
  },
})
