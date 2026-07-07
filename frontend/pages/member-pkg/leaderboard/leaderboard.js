// frontend/pages/member-pkg/leaderboard/leaderboard.js
const api = require('../../utils/api')
const auth = require('../../utils/auth')

var PERIODS = [
  { label: '7天', value: '7d' },
  { label: '15天', value: '15d' },
  { label: '30天', value: '30d' },
  { label: '本月', value: 'month' },
  { label: '本年', value: 'year' },
  { label: '总榜', value: 'total' },
]

Page({
  data: {
    tabs: PERIODS,
    period: 'total',
    levelIndex: 0,
    levelNames: ['全部级别'],
    levels: [],
    list: [],
    loading: false,
    myChildId: 0,
    myRank: 0,
    myTotalWords: 0,
    myName: '',
  },

  onLoad() {
    const app = getApp()
    if (app.globalData.isTestMode) {
      this._loadDemoData()
      return
    }
    if (!auth.requireAuth()) return
    this._loadLevels()
    this._loadLeaderboard()
  },

  onShow() {
    this._updateMyInfo()
  },

  onPullDownRefresh() {
    this._loadLeaderboard(function () {
      wx.stopPullDownRefresh()
    })
  },

  onPeriodChange: function (e) {
    var value = e.currentTarget.dataset.value
    if (value === this.data.period) return
    this.setData({ period: value })
    this._loadLeaderboard()
  },

  onLevelChange: function (e) {
    var idx = parseInt(e.detail.value)
    this.setData({ levelIndex: idx })
    this._loadLeaderboard()
  },

  onItemTap: function (e) {
    // Could navigate to profile card in the future
  },

  _updateMyInfo: function () {
    var child = auth.getCurrentChild()
    if (child) {
      this.setData({ myChildId: child.id, myName: child.name || '' })
    }
  },

  _loadLevels: function () {
    var that = this
    require('../../utils/api').getLevels().then(function (levels) {
      that.setData({ levels: levels || [] })
    }).catch(function () { /* silent */ })
  },

  _loadLeaderboard: function (cb) {
    var that = this
    this.setData({ loading: true })

    var levelId = this.data.levelIndex > 0 ? this.data.levels[this.data.levelIndex - 1].id : ''
    api.getLeaderboard(this.data.period, levelId, 50)
      .then(function (data) {
        var list = data || []
        var myChildId = that.data.myChildId
        var myRank = 0
        var myTotalWords = 0

        for (var i = 0; i < list.length; i++) {
          if (list[i].child_id === myChildId) {
            myRank = list[i].rank || (i + 1)
            myTotalWords = list[i].total_words || 0
            break
          }
        }

        that.setData({
          list: list,
          loading: false,
          myRank: myRank,
          myTotalWords: myTotalWords,
        })
        if (typeof cb === 'function') cb()
      })
      .catch(function () {
        that.setData({ list: [], loading: false })
        if (typeof cb === 'function') cb()
      })
  },

  _loadDemoData() {
    this.setData({
      list: [
        { rank: 1, child_id: 10, display_name: 'Lucy', total_words: 128000, medal: '🥇', streak_days: 45 },
        { rank: 2, child_id: 20, display_name: 'Tom', total_words: 96000, medal: '🥈', streak_days: 30 },
        { rank: 3, child_id: 30, display_name: 'Mia', total_words: 72000, medal: '🥉', streak_days: 22 },
        { rank: 4, child_id: 40, display_name: 'Leo', total_words: 58000, medal: null, streak_days: 15 },
        { rank: 5, child_id: 50, display_name: 'Emma', total_words: 45000, medal: null, streak_days: 10 },
        { rank: 6, child_id: 60, display_name: 'Noah', total_words: 38000, medal: null, streak_days: 8 },
        { rank: 7, child_id: 70, display_name: 'Lily', total_words: 31000, medal: null, streak_days: 5 },
      ],
      myChildId: 1,
      myRank: 5,
      myTotalWords: 42000,
      myName: '小明',
      loading: false,
    })
  },
})
