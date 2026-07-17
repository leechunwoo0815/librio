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

  goBack: function () {
    wx.navigateBack({ delta: 1 });
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
      var levelList = levels || []
      var names = ['全部级别']
      for (var i = 0; i < levelList.length; i++) {
        names.push(levelList[i].name || '级别' + (i + 1))
      }
      that.setData({ levels: levelList, levelNames: names })
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

})
