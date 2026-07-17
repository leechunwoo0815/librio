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
    if (!auth.requireAuth()) return;
  },

  onShow() {
    const app = getApp()

    const child = auth.getCurrentChild();
    if (!child) return;
    this.setData({ child });
    this.loadTabData(this.data.activeTab);
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
    this._sortCurrentList(this.data.sortIndex)
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
      this._sortCurrentList(this.data.sortIndex);
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
    const { activeTab, learning, mastered, currentList } = this.data;
    const item = currentList[index];
    if (!item || item.status === 'mastered') return;

    try {
      await api.markMastered(vocabId);
      // Move item from learning to mastered
      const newLearning = learning.filter(function (v) { return v.id !== vocabId; });
      item.status = 'mastered';
      const newMastered = mastered.concat([item]);
      this.setData({
        learning: newLearning,
        mastered: newMastered,
        learningCount: newLearning.length,
        masteredCount: newMastered.length,
      });
      // Update current list based on active tab
      this._updateCurrentList(activeTab);
      wx.showToast({ title: '已掌握', icon: 'success' });
    } catch (e) {
      console.error('mark mastered failed:', e);
      wx.showToast({ title: '操作失败', icon: 'none' });
    }
  },

  onPlayAudio(e) {
    const audioUrl = e.currentTarget.dataset.audio
    if (!audioUrl) return
    const audio = wx.createInnerAudioContext()
    audio.src = audioUrl
    audio.play()
  },

  onSortChange(e) {
    const sortIndex = Number(e.detail.value)
    this.setData({ sortIndex })
    this._sortCurrentList(sortIndex)
  },

  _sortCurrentList(sortOption) {
    const { currentList } = this.data
    if (!currentList || currentList.length === 0) return
    const sortValue = this.data.sortOptions[sortOption]?.value || 'time'
    let sorted = [...currentList]
    switch (sortValue) {
      case 'time': sorted.sort((a, b) => (b.created_at || '').localeCompare(a.created_at || '')); break
      case 'book': sorted.sort((a, b) => (a.source_book || '').localeCompare(b.source_book || '')); break
      case 'alpha': sorted.sort((a, b) => (a.word || '').localeCompare(b.word || '')); break
    }
    this.setData({ currentList: sorted })
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

  async reviewResult(e) {
    const result = e.currentTarget.dataset.result
    if (result === 'got') {
      const currentWord = this.data.reviewWords[this.data.reviewIndex]
      if (currentWord && currentWord.id) {
        try {
          await api.markMastered(currentWord.id)
          const newLearning = this.data.learning.filter(v => v.id !== currentWord.id)
          if (newLearning.length < this.data.learning.length) {
            currentWord.status = 'mastered'
            this.setData({
              learning: newLearning,
              mastered: this.data.mastered.concat([currentWord]),
              learningCount: newLearning.length,
              masteredCount: this.data.mastered.length + 1,
            })
          }
        } catch (e) { console.error(e) }
      }
    }
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
