// frontend/pages/reading-pkg/vocabulary/vocabulary.js
const api = require('../../utils/api');
const auth = require('../../utils/auth');

Page({
  data: {
    activeTab: 0,
    tabs: ['全部', '学习中', '已掌握'],
    learning: [],
    mastered: [],
    currentList: [],
    learningCount: 0,
    masteredCount: 0,
    loading: true,
    loadError: false,
    child: null,
    sortIndex: 0,
    sortOptions: [
      { label: '按时间', value: 'time' },
      { label: '按书籍', value: 'book' },
      { label: '按字母', value: 'alpha' },
    ],
    showFlashcard: false,
    flashcard: {
      word: '',
      phonetic: '',
      def: '',
      flipped: false,
    },
    reviewIndex: 0,
    reviewWords: [],
    reviewProgress: 0,
    reviewTotal: 0,
    showReviewComplete: false,
  },

  onLoad() {
    const app = getApp()
    if (app.globalData.isTestMode) {
      this._loadTestModeData()
      return
    }
    if (!auth.requireAuth()) return;
  },

  onShow() {
    const app = getApp()

    const child = auth.getCurrentChild();
    if (!child) return;
    this.setData({ child });
    this.loadTabData(this.data.activeTab);
  },

  _loadTestModeData() {
    const learning = [
      { id: '1', word: 'ax', phonetic: '/æks/', chinese_meaning: '斧头', part_of_speech: 'n.', status: 'learning', lookup_count: 3 },
      { id: '2', word: 'runt', phonetic: '/rʌnt/', chinese_meaning: '一窝中最小的动物', part_of_speech: 'n.', status: 'learning', lookup_count: 2 },
      { id: '3', word: 'sobbed', phonetic: '/sɑbd/', chinese_meaning: '哭泣，呜咽（sob 的过去式）', part_of_speech: 'v.', status: 'learning', lookup_count: 5 },
    ]
    const mastered = [
      { id: '4', word: 'caterpillar', phonetic: '/ˈkætərpɪlər/', chinese_meaning: '毛毛虫', part_of_speech: 'n.', status: 'mastered', lookup_count: 8 },
      { id: '5', word: 'burrow', phonetic: '/ˈbɜːroʊ/', chinese_meaning: '洞穴 v. 挖掘', part_of_speech: 'n.', status: 'mastered', lookup_count: 4 },
    ]

    this.setData({
      learning,
      mastered,
      learningCount: learning.length,
      masteredCount: mastered.length,
      currentList: learning.concat(mastered),
      loading: false,
    })
  },

  onPullDownRefresh() {
    this.loadTabData(this.data.activeTab).then(function () {
      wx.stopPullDownRefresh();
    }).catch(function () {
      wx.stopPullDownRefresh();
    });
  },

  onTabChange(e) {
    const index = Number(e.currentTarget.dataset.index);
    if (index === this.data.activeTab) return;
    this.setData({ activeTab: index });
    this._updateCurrentList(index);
    this.loadTabData(index);
  },

  _updateCurrentList(tabIndex) {
    let list = []
    if (tabIndex === 0) {
      list = this.data.learning.concat(this.data.mastered)
    } else if (tabIndex === 1) {
      list = this.data.learning
    } else {
      list = this.data.mastered
    }
    this.setData({ currentList: list })
  },

  async loadTabData(tabIndex) {
    if (!this.data.child) return;
    this.setData({ loading: true });
    const childId = this.data.child.id;

    try {
      // 并行获取两个列表，避免重复请求
      const [learning, mastered] = await Promise.all([
        api.getVocabList(childId, 'learning').catch(() => []),
        api.getVocabList(childId, 'mastered').catch(() => []),
      ])
      const learningArr = learning || []
      const masteredArr = mastered || []

      if (tabIndex === 0) {
        this.setData({
          learning: learningArr,
          mastered: masteredArr,
          learningCount: learningArr.length,
          masteredCount: masteredArr.length,
          currentList: learningArr.concat(masteredArr),
          loading: false,
        });
      } else if (tabIndex === 1) {
        this.setData({
          learning: learningArr,
          learningCount: learningArr.length,
          masteredCount: masteredArr.length,
          currentList: learningArr,
          loading: false,
        });
      } else {
        this.setData({
          mastered: masteredArr,
          learningCount: learningArr.length,
          masteredCount: masteredArr.length,
          currentList: masteredArr,
          loading: false,
        });
      }
    } catch (e) {
      console.error('load vocab data failed:', e);
      this.setData({ loading: false, loadError: true });
    }
  },

  onRetry() {
    this.setData({ loadError: false });
    this.loadTabData(this.data.activeTab);
  },

  onWordTap(e) {
    const word = e.currentTarget.dataset.word;
    wx.navigateTo({
      url: '/pages/reading-pkg/word-detail/word-detail?word=' + encodeURIComponent(word),
    });
  },

  async onMarkMastered(e) {
    const vocabId = e.currentTarget.dataset.id;
    const index = e.currentTarget.dataset.index;

    try {
      await api.markMastered(vocabId);
      // Move item from learning to mastered
      const item = this.data.learning[index];
      const learning = this.data.learning.filter(function (_, i) {
        return i !== index;
      });
      item.status = 'mastered';
      const mastered = this.data.mastered.concat([item]);
      this.setData({
        learning: learning,
        mastered: mastered,
        learningCount: learning.length,
        masteredCount: mastered.length,
      });
      // Update current list based on active tab
      this._updateCurrentList(this.data.activeTab);
      wx.showToast({ title: '已掌握', icon: 'success' });
    } catch (e) {
      console.error('mark mastered failed:', e);
      wx.showToast({ title: '操作失败', icon: 'none' });
    }
  },

  onSortChange(e) {
    const sortIndex = Number(e.detail.value)
    this.setData({ sortIndex })
  },

  startReview() {
    const allWords = this.data.learning.concat(this.data.mastered)
    if (allWords.length === 0) {
      wx.showToast({ title: '暂无单词可复习', icon: 'none' })
      return
    }
    const reviewWords = allWords
    this.setData({
      showFlashcard: true,
      reviewWords,
      reviewIndex: 0,
      reviewProgress: 0,
      reviewTotal: reviewWords.length,
      showReviewComplete: false,
      flashcard: {
        word: reviewWords[0].word,
        phonetic: reviewWords[0].phonetic || '',
        def: (reviewWords[0].part_of_speech || '') + ' ' + (reviewWords[0].chinese_meaning || ''),
        flipped: false,
      },
    })
  },

  flipCard() {
    if (this.data.flashcard.flipped) return
    this.setData({
      'flashcard.flipped': true,
    })
  },

  reviewResult(e) {
    let reviewIndex = this.data.reviewIndex + 1
    if (reviewIndex >= this.data.reviewWords.length) {
      this.setData({
        showReviewComplete: true,
        showFlashcard: false,
        reviewProgress: this.data.reviewTotal,
      })
      return
    }
    const word = this.data.reviewWords[reviewIndex]
    this.setData({
      reviewIndex,
      reviewProgress: reviewIndex,
      flashcard: {
        word: word.word,
        phonetic: word.phonetic || '',
        def: (word.part_of_speech || '') + ' ' + (word.chinese_meaning || ''),
        flipped: false,
      },
    })
  },

  closeReview() {
    this.setData({
      showFlashcard: false,
      reviewIndex: 0,
      reviewWords: [],
      reviewProgress: 0,
      reviewTotal: 0,
      showReviewComplete: false,
    })
  },

  closeReviewComplete() {
    this.closeReview()
  },
});
