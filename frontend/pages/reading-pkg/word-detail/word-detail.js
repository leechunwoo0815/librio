// frontend/pages/reading-pkg/word-detail/word-detail.js
const api = require('../../utils/api');
const auth = require('../../utils/auth');

Page({
  _audio: null,

  data: {
    word: '',
    wordData: null,
    inVocab: false,
    vocabId: null,
    vocabStatus: null,
    loading: true,
    child: null,
    audioPlaying: false,
    loadError: false,
  },

  async onLoad(options) {
    const app = getApp()
    if (!auth.requireAuth()) return;

    const word = decodeURIComponent(options.word || '');
    if (!word) {
      wx.showToast({ title: '参数错误', icon: 'none' });
      return;
    }

    const child = auth.getCurrentChild();
    this.setData({ word, child: child });

    await this.loadWordData(word);
    if (child) {
      await this.checkVocabStatus(word, child.id);
    }
  },

  async loadWordData(word) {
    try {
      const data = await api.lookupWord(word);
      if (data && data.word) {
        this.setData({ wordData: data, loading: false, loadError: false });
      } else {
        // MP-012: 查词未收录 — 友好提示
        this.setData({
          wordData: { word: word, chinese_meaning: '该词暂未收录', found: false },
          loading: false,
          loadError: false,
          notFound: true,
        });
      }
    } catch (e) {
      // MP-012: 网络异常 — 友好提示 + 重试
      console.error('lookup word failed:', e);
      this.setData({ loading: false, loadError: true });
    }
  },

  // MP-012: 重试查词
  retryLookup() {
    this.setData({ loading: true, loadError: false });
    this.loadWordData(this.data.word);
  },

  onRetry() {
    this.retryLookup();
  },

  async checkVocabStatus(word, childId) {
    try {
      // 并行获取两个列表
      const [learning, mastered] = await Promise.all([
        api.getVocabList(childId, 'learning').catch(() => []),
        api.getVocabList(childId, 'mastered').catch(() => []),
      ]);
      const allVocab = (learning || []).concat(mastered || []);
      const found = allVocab.find(function (item) {
        return item.word.toLowerCase() === word.toLowerCase();
      });
      if (found) {
        this.setData({
          inVocab: true,
          vocabId: found.id,
          vocabStatus: found.status,
        });
      }
    } catch (e) {
      // ignore - treat as not in vocab
    }
  },

  playAudio() {
    const audioUrl = this.data.wordData && this.data.wordData.audio_url;
    if (!audioUrl) {
      wx.showToast({ title: '暂无发音', icon: 'none' });
      return;
    }

    // 复用单个 InnerAudioContext 实例
    if (!this._audio) {
      this._audio = wx.createInnerAudioContext();
      var self = this;
      this._audio.onPlay(function () { self.setData({ audioPlaying: true }); });
      this._audio.onEnded(function () { self.setData({ audioPlaying: false }); });
      this._audio.onError(function () { self.setData({ audioPlaying: false }); });
    }
    this._audio.src = audioUrl;
    this._audio.play();
  },

  onUnload() {
    if (this._audio) { this._audio.stop(); this._audio.destroy(); this._audio = null; }
  },

  async addToVocab() {
    const { word, child, wordData } = this.data;
    if (!child) {
      wx.showToast({ title: '请先选择孩子', icon: 'none' });
      return;
    }

    try {
      const extraData = this.data.extraData || {}
      const bookId = wordData && wordData.book_id ? wordData.book_id : (extraData.bookId || '')
      await api.addToVocab(child.id, word, bookId);
      this.setData({ inVocab: true, vocabStatus: 'learning' });
      wx.showToast({ title: '已加入生词本', icon: 'success' });
    } catch (e) {
      console.error('add to vocab failed:', e);
      wx.showToast({ title: '添加失败', icon: 'none' });
    }
  },

  async markMastered() {
    const { vocabId } = this.data;
    if (!vocabId) return;

    try {
      await api.markMastered(vocabId);
      this.setData({ vocabStatus: 'mastered' });
      wx.showToast({ title: '已掌握', icon: 'success' });
    } catch (e) {
      console.error('mark mastered failed:', e);
      wx.showToast({ title: '操作失败', icon: 'none' });
    }
  },

  async removeFromVocab() {
    const { vocabId, child, word } = this.data;
    if (!vocabId || !child) return;

    try {
      await api.removeVocab(vocabId);
      this.setData({
        inVocab: false,
        vocabId: null,
        vocabStatus: null,
      });
      wx.showToast({ title: '已移除', icon: 'success' });
    } catch (e) {
      console.error('remove from vocab failed:', e);
      wx.showToast({ title: '操作失败', icon: 'none' });
    }
  },
});
