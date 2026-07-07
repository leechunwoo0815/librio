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

Page({
  data: {
    books: [],
    keyword: '',
    arLevelIndex: 0,
    ageRangeIndex: 0,
    arLevels: AR_LEVELS,
    ageRanges: AGE_RANGES,
    hasActiveFilter: false,
    page: 1,
    pageSize: 10,
    hasMore: true,
    loading: false,
    loadError: false,
  },

  onLoad() {
    const app = getApp()
    if (app.globalData.isTestMode || app.globalData.token === 'test-token-mock') {
      this._loadDemoBooks()
    } else {
      this.search()
    }
  },

  onShow() {
    // tabBar 页面每次显示时刷新（从其他页面返回时）
  },

  onPullDownRefresh() {
    this.search().then(() => {
      wx.stopPullDownRefresh()
    }).catch(() => {
      wx.stopPullDownRefresh()
    })
  },

  onReachBottom() {
    if (this.data.hasMore && !this.data.loading) {
      this.setData({ page: this.data.page + 1 })
      this.search(false)
    }
  },

  buildParams() {
    const { keyword, arLevelIndex, ageRangeIndex, arLevels, ageRanges, page, pageSize } = this.data
    const params = { page, page_size: pageSize }
    if (keyword) params.keyword = keyword
    if (arLevelIndex > 0) params.ar_level = arLevels[arLevelIndex].value
    if (ageRangeIndex > 0) params.age_range = ageRanges[ageRangeIndex].value
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
      hasActiveFilter: index > 0,
    })
    this.search()
  },

  onResetFilter() {
    this.setData({
      arLevelIndex: 0,
      ageRangeIndex: 0,
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

  onRetry() {
    this.setData({ loadError: false })
    this.search()
  },

  _loadDemoBooks() {
    const demoBooks = [
      { id: 1, title: "Charlotte's Web", author: 'E.B. White', ar_value: 4.4, word_count: 31836, age_min: 7, age_max: 11 },
      { id: 2, title: 'The Cat in the Hat', author: 'Dr. Seuss', ar_value: 2.1, word_count: 1624, age_min: 4, age_max: 8 },
      { id: 3, title: 'Green Eggs and Ham', author: 'Dr. Seuss', ar_value: 1.5, word_count: 820, age_min: 3, age_max: 7 },
      { id: 4, title: 'Goodnight Moon', author: 'Margaret Wise Brown', ar_value: 1.8, word_count: 131, age_min: 2, age_max: 5 },
      { id: 5, title: 'Where the Wild Things Are', author: 'Maurice Sendak', ar_value: 3.2, word_count: 1018, age_min: 4, age_max: 8 },
      { id: 6, title: 'The Very Hungry Caterpillar', author: 'Eric Carle', ar_value: 2.9, word_count: 224, age_min: 2, age_max: 6 },
      { id: 7, title: 'Diary of a Wimpy Kid', author: 'Jeff Kinney', ar_value: 5.2, word_count: 19784, age_min: 8, age_max: 12 },
      { id: 8, title: 'Harry Potter and the Sorcerer\'s Stone', author: 'J.K. Rowling', ar_value: 5.5, word_count: 77508, age_min: 9, age_max: 15 },
      { id: 9, title: 'Matilda', author: 'Roald Dahl', ar_value: 5.0, word_count: 30833, age_min: 8, age_max: 12 },
      { id: 10, title: 'The BFG', author: 'Roald Dahl', ar_value: 4.8, word_count: 25837, age_min: 8, age_max: 12 },
    ]
    this.setData({ books: demoBooks, loading: false, hasMore: false })
  },

  onUnload() {
    if (this._searchTimer) {
      clearTimeout(this._searchTimer)
      this._searchTimer = null
    }
  },
})
