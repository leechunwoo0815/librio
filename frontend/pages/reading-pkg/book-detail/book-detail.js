// frontend/pages/reading-pkg/book-detail/book-detail.js
const api = require('../../utils/api');
const auth = require('../../utils/auth');

Page({
  data: {
    book: null,
    child: null,
    progress: null,
    onShelf: false,
    onFavorite: false,
    readingTime: '',
    loading: true,
    descExpanded: false,
    shelfLoading: false,
    favLoading: false,
    loadError: false,
    relatedBooks: [],
  },

  async onLoad(options) {
    const app = getApp()
    const id = parseInt(options.id) || parseInt(options.bookId);
    if (!id) return;

    try {
      const book = await api.getBookDetail(id);
      const readingTime = this._calcReadingTime(book.word_count);
      this.setData({ book, readingTime, loading: false });
      wx.setNavigationBarTitle({ title: book.title });
      this._loadRelatedBooks(book.id);
      await this._loadChildAndStatus(book.id);
    } catch (e) {
      console.error('load book detail failed', e);
      this.setData({ loadError: true, loading: false });
    }
  },

  async _loadChildAndStatus(bookId) {
    const child = auth.getCurrentChild();
    if (!child) return;
    this.setData({ child });

    try {
      // 并行查询书架、收藏、进度，避免串行 N+1
      const [shelfBooks, favBooks, progress] = await Promise.all([
        api.getBookshelf(child.id).catch(() => []),
        api.getFavorites(child.id).catch(() => []),
        api.getProgress(bookId, child.id).catch(() => null),
      ]);

      const onShelf = (shelfBooks || []).some(function (item) {
        return item.book_id === bookId || item.id === bookId;
      });
      const onFavorite = (favBooks || []).some(function (item) {
        return item.book_id === bookId || item.id === bookId;
      });

      this.setData({ onShelf, onFavorite, progress: onShelf ? progress : null });
    } catch (e) {
      console.error('load child status failed', e);
    }
  },

  _calcReadingTime(wordCount) {
    if (!wordCount) return '';
    // Average reading speed for children: ~100 words/min
    const minutes = Math.ceil(wordCount / 100);
    if (minutes < 1) return '不到 1 分钟';
    if (minutes < 60) return minutes + ' 分钟';
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return hours + ' 小时' + (mins > 0 ? mins + ' 分钟' : '');
  },

  async addToShelf() {
    const { book, child } = this.data;
    if (!child) {
      wx.showToast({ title: '请先选择孩子', icon: 'none' });
      return;
    }
    if (this.data.shelfLoading) return;
    this.setData({ shelfLoading: true });
    try {
      await api.addToShelf(book.id, child.id);
      this.setData({ onShelf: true });
      wx.showToast({ title: '已加入书架', icon: 'success' });
    } catch (e) {
      console.error('add to shelf failed', e);
      wx.showToast({ title: '加入书架失败', icon: 'none' });
    }
    this.setData({ shelfLoading: false });
  },

  async addFavorite() {
    const { book, child } = this.data;
    if (!child) {
      wx.showToast({ title: '请先选择孩子', icon: 'none' });
      return;
    }
    if (this.data.favLoading) return;
    this.setData({ favLoading: true });
    try {
      await api.addFavorite(book.id, child.id);
      this.setData({ onFavorite: true });
      wx.showToast({ title: '已收藏', icon: 'success' });
    } catch (e) {
      console.error('add favorite failed', e);
      wx.showToast({ title: '收藏失败', icon: 'none' });
    }
    this.setData({ favLoading: false });
  },

  toggleDesc() {
    this.setData({ descExpanded: !this.data.descExpanded });
  },

  async reserveBook(e) {
    const { book, child } = this.data;
    if (!child) { wx.showToast({ title: '请先选择孩子', icon: 'none' }); return; }
    try {
      wx.showLoading({ title: '预约中...' });
      await api.createReservation(child.id, book.id);
      wx.hideLoading();
      wx.showToast({ title: '预约成功', icon: 'success' });
    } catch (err) {
      wx.hideLoading();
      wx.showModal({ title: '预约失败', content: err.errMsg || '请稍后重试', showCancel: false });
    }
  },

  async _loadRelatedBooks(bookId) {
    try {
      const related = await api.getRelatedBooks(bookId);
      this.setData({ relatedBooks: related || [] });
    } catch (e) {
      console.error('load related books failed', e);
      this.setData({ relatedBooks: [] });
    }
  },
});
