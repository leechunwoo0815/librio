// frontend/pages/shelf/shelf.js
const api = require('../../utils/api');
const auth = require('../../utils/auth');

Page({
  data: {
    activeTab: 0,
    tabs: ['书架', '收藏夹', '已读完'],
    books: [],
    favorites: [],
    finished: [],
    shelfLimit: 20,
    loading: true,
    loadError: false,
    child: null,
    showRemoveDialog: false,
    removeTarget: null,
    removeBookId: null,
  },

  onShow() {
    const app = getApp();
    // 测试模式或mock token都直接加载示例数据
    if (app.globalData.isTestMode || app.globalData.token === 'test-token-mock') {
      this.setData({ child: app.globalData.currentChild });
      this._loadDemoData();
      return;
    }
    if (!auth.requireAuth()) return;
    const child = auth.getCurrentChild();
    if (!child) return;
    this.setData({ child });
    this.loadTabData(this.data.activeTab);
  },

  onPullDownRefresh() {
    this.loadTabData(this.data.activeTab).then(() => {
      wx.stopPullDownRefresh();
    }).catch(() => {
      wx.stopPullDownRefresh();
    });
  },

  onTabChange(e) {
    const index = Number(e.currentTarget.dataset.index);
    if (index === this.data.activeTab) return;
    this.setData({ activeTab: index });
    this.loadTabData(index);
  },

  async loadTabData(tabIndex) {
    if (!this.data.child) return;
    this.setData({ loading: true });
    const childId = this.data.child.id;

    try {
      if (tabIndex === 0) {
        const books = await api.getBookshelf(childId);
        this.setData({ books: books || [], loading: false });
      } else if (tabIndex === 1) {
        const favorites = await api.getFavorites(childId);
        this.setData({ favorites: favorites || [], loading: false });
      } else {
        // 已读完 — 从书架中过滤已完成状态
        const books = await api.getBookshelf(childId);
        const finished = (books || []).filter(function (item) {
          return item.status === 'finished' || item.status === 3;
        });
        this.setData({ finished: finished, loading: false });
      }
    } catch (e) {
      console.error('load shelf data failed:', e);
      this.setData({ loading: false, loadError: true });
    }
  },

  // --- 书架 Tab ---
  goReader(e) {
    const bookId = e.currentTarget.dataset.bookid;
    wx.navigateTo({ url: '/pages/reading-pkg/book-detail/book-detail?id=' + bookId });
  },

  onShelfLongPress(e) {
    const bookId = e.currentTarget.dataset.bookid;
    const bookTitle = e.currentTarget.dataset.title || '这本书';
    const that = this;
    wx.showModal({
      title: '移出书架',
      content: `确定要从书架移除《${bookTitle}》吗？`,
      success(res) {
        if (res.confirm) {
          that.removeFromShelf(bookId);
        }
      },
    });
  },

  async removeFromShelf(bookId) {
    const childId = this.data.child.id;
    try {
      await api.removeFromShelf(bookId, childId);
      const books = this.data.books.filter(function (item) {
        return (item.book_id || item.id) !== bookId;
      });
      this.setData({ books });
      wx.showToast({ title: '已移出书架', icon: 'success' });
    } catch (e) {
      console.error('remove from shelf failed:', e);
      wx.showToast({ title: '操作失败', icon: 'none' });
    }
  },

  confirmRemoveFromShelf() {
    const bookId = this.data.removeBookId;
    if (bookId) {
      this.removeFromShelf(bookId);
    }
    this.setData({ showRemoveDialog: false, removeTarget: null, removeBookId: null });
  },

  hideRemove() {
    this.setData({ showRemoveDialog: false, removeTarget: null, removeBookId: null });
  },

  // --- 收藏夹 Tab ---
  goFavDetail(e) {
    const bookId = e.currentTarget.dataset.bookid;
    wx.navigateTo({ url: '/pages/reading-pkg/book-detail/book-detail?id=' + bookId });
  },

  async onAddToShelf(e) {
    const bookId = e.currentTarget.dataset.bookid;
    const childId = this.data.child.id;
    const favs = this.data.favorites;
    const idx = favs.findIndex(function (item) {
      return (item.book_id || item.id) === bookId;
    });
    if (idx === -1 || favs[idx]._adding) return;

    this.setData({ ['favorites[' + idx + ']._adding']: true });
    try {
      await api.addToShelf(bookId, childId);
      wx.showToast({ title: '已加入书架', icon: 'success' });
    } catch (e) {
      const msg = e.message || '添加失败';
      wx.showToast({ title: msg, icon: 'none' });
    } finally {
      this.setData({ ['favorites[' + idx + ']._adding']: false });
    }
  },

  async addToShelfFromFav(e) {
    const bookId = e.currentTarget.dataset.bookid;
    const childId = this.data.child.id;
    try {
      await api.addToShelf(bookId, childId);
      wx.showToast({ title: '已加入书架', icon: 'success' });
    } catch (err) {
      wx.showToast({ title: err.message || '添加失败', icon: 'none' });
    }
  },

  // --- 已读完 Tab ---
  goFinishedDetail(e) {
    const bookId = e.currentTarget.dataset.bookid;
    wx.navigateTo({ url: '/pages/reading-pkg/book-detail/book-detail?id=' + bookId });
  },

  onRetry() {
    this.setData({ loadError: false });
    this.loadTabData(this.data.activeTab);
  },

  _loadDemoData() {
    this.setData({
      loading: false,
      books: [
        { id: 1, title: "Charlotte's Web", author: 'E.B. White', ar_value: 4.4, word_count: 31836, _progress: 65 },
        { id: 7, title: 'Diary of a Wimpy Kid', author: 'Jeff Kinney', ar_value: 5.2, word_count: 19784, _progress: 30 },
        { id: 9, title: 'Matilda', author: 'Roald Dahl', ar_value: 5.0, word_count: 30833, _progress: 10 },
      ],
      favorites: [
        { id: 8, title: "Harry Potter and the Sorcerer's Stone", author: 'J.K. Rowling', ar_value: 5.5 },
        { id: 10, title: 'The BFG', author: 'Roald Dahl', ar_value: 4.8 },
      ],
      finished: [
        { id: 2, title: 'The Cat in the Hat', author: 'Dr. Seuss', word_count: 1624, finish_date: '2026-05-20' },
        { id: 3, title: 'Green Eggs and Ham', author: 'Dr. Seuss', word_count: 820, finish_date: '2026-05-15' },
        { id: 5, title: 'Where the Wild Things Are', author: 'Maurice Sendak', word_count: 1018, finish_date: '2026-05-10' },
      ],
    });
  },
});
