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
  },

  async onLoad(options) {
    const app = getApp()
    const id = options.id;
    if (!id) return;

    try {
      const book = await api.getBookDetail(id);
      const readingTime = this._calcReadingTime(book.word_count);
      this.setData({ book, readingTime, loading: false });
      wx.setNavigationBarTitle({ title: book.title });
      await this._loadChildAndStatus(book.id);
    } catch (e) {
      console.error('load book detail failed', e);
      // API失败时显示示例数据
      this.setData({
        book: {
          id: id, title: "Charlotte's Web", author: "E.B. White",
          ar_value: "4.4", word_count: 31836, age_min: 7, age_max: 11,
          summary: "经典英文儿童文学作品，讲述了一只名叫Charlotte的蜘蛛和一只名叫Wilbur的小猪之间的友谊故事。",
        },
        readingTime: "约5小时",
        loading: false,
      });
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

  async startReading() {
    const { book, child } = this.data;
    if (!child) {
      wx.showToast({ title: '请先选择孩子', icon: 'none' });
      return;
    }
    try {
      const session = await api.startSession(child.id, book.id);
      wx.navigateTo({
        url: '/pages/reading-pkg/reader/reader?bookId=' + book.id + '&sessionId=' + session.session_id + '&childId=' + child.id,
      });
    } catch (e) {
      console.error('start reading failed', e);
      wx.showToast({ title: '启动阅读失败', icon: 'none' });
    }
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
});
