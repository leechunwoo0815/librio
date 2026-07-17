// frontend/pages/member-pkg/achievement/achievement.js
const api = require('../../utils/api')
const auth = require('../../utils/auth')

function formatDate(dateStr) {
  if (!dateStr) return ''
  var d = new Date(dateStr)
  var y = d.getFullYear()
  var m = ('0' + (d.getMonth() + 1)).slice(-2)
  var day = ('0' + d.getDate()).slice(-2)
  return y + '-' + m + '-' + day
}

Page({
  data: {
    currentLevel: null,
    advancement: null,
    progressPercent: 0,
    achievements: [],
    earnedCount: 0,
    recentEarned: [],
    showDetail: false,
    selectedAchievement: {},
    activeTab: 'badges',
    leaderboardData: [],
    myRank: 0,
    myName: '',
    loading: true,
    loadError: false,
  },

  onLoad() {
    if (!auth.requireAuth()) return
  },

  onShow() {
    var child = auth.getCurrentChild()
    if (child) {
      this.setData({ myName: child.name || '' })
    }
    this._loadData()
  },

  onSwitchTab: function (e) {
    var tab = e.currentTarget.dataset.tab
    if (tab === this.data.activeTab) return
    this.setData({ activeTab: tab })
    if (tab === 'leaderboard' && this.data.leaderboardData.length === 0) {
      this._loadLeaderboard()
    }
  },

  onBadgeTap: function (e) {
    var id = e.currentTarget.dataset.id
    var item = null
    for (var i = 0; i < this.data.achievements.length; i++) {
      if (this.data.achievements[i].id === id) {
        item = this.data.achievements[i]
        break
      }
    }
    if (item) {
      this.setData({
        showDetail: true,
        selectedAchievement: item,
      })
    }
  },

  onCloseDetail: function () {
    this.setData({ showDetail: false, selectedAchievement: {} })
  },

  onPromote: function () {
    // Navigate to promotion flow
    wx.navigateTo({ url: '/pages/member-pkg/reading-stats/reading-stats' })
  },

  _loadData: function () {
    var that = this
    var child = auth.getCurrentChild()
    if (!child) return
    var childId = child.id
    that.setData({ myName: child.name || '', loading: true, loadError: false })

    // Load level, levels, achievements in parallel
    Promise.all([
      api.getCurrentLevel(childId).catch(function () { return null }),
      api.getLevels().catch(function () { return [] }),
      api.getAchievements().catch(function () { return [] }),
      api.getChildAchievements(childId).catch(function () { return [] }),
    ]).then(function (results) {
      var level = results[0]
      var levels = results[1] || []
      var allDefs = results[2] || []
      var earned = results[3] || []

      // Build advancement from current level + next level threshold
      var adv = null
      var progressPercent = 0
      if (level) {
        var levelDef = null
        var nextLevel = null
        for (var k = 0; k < levels.length; k++) {
          if (levels[k].id === level.level_id) {
            levelDef = levels[k]
          }
        }
        var currentSort = levelDef ? levelDef.sort_order : 0
        for (var m = 0; m < levels.length; m++) {
          if (levels[m].sort_order > currentSort) {
            nextLevel = levels[m]
            break
          }
        }
        var booksRead = level.books_read_at_level || 0
        var booksRequired = nextLevel ? nextLevel.required_books : 5
        progressPercent = booksRequired > 0 ? Math.min(100, Math.round(booksRead / booksRequired * 100)) : 0
        adv = {
          books_read: booksRead,
          books_required: booksRequired,
          can_advance: booksRead >= booksRequired && !!nextLevel,
        }
        // Enrich level for WXML template field names
        level.badge_emoji = levelDef ? (levelDef.badge_emoji || '⭐') : '⭐'
        level.books_read = level.books_read_at_level || 0
        level.quizzes_passed = level.quizzes_passed_at_level || 0
        level.streak_days = level.streak_days || 0
        level.level_number = currentSort
      }

      // Build earned lookup
      var earnedMap = {}
      for (var i = 0; i < earned.length; i++) {
        earnedMap[earned[i].achievement_id] = earned[i]
      }

      // Merge definitions with earned status
      var achievements = []
      var recentEarned = []
      var earnedCount = 0
      for (var j = 0; j < allDefs.length; j++) {
        var def = allDefs[j]
        var earnedData = earnedMap[def.id]
        var item = {
          id: def.id,
          name: def.name,
          badge_emoji: def.badge_emoji || '🏅',
          description: def.description || '',
          trigger_desc: def.trigger_desc || '',
          earned: !!earnedData,
          achieved_at: earnedData ? earnedData.achieved_at : '',
          dateStr: earnedData ? formatDate(earnedData.achieved_at) : '',
          progress: earnedData ? 100 : (def.default_progress || 0),
        }
        achievements.push(item)
        if (item.earned) {
          earnedCount++
          recentEarned.push(item)
        }
      }

      // Sort recent earned by date descending, take top 10
      recentEarned.sort(function (a, b) {
        return new Date(b.achieved_at) - new Date(a.achieved_at)
      })
      recentEarned = recentEarned.slice(0, 10)

      that.setData({
        currentLevel: level,
        advancement: adv,
        progressPercent: progressPercent,
        achievements: achievements,
        earnedCount: earnedCount,
        recentEarned: recentEarned,
        loading: false,
        loadError: false,
      })
    }).catch(function (e) {
      console.error('load achievement data failed', e)
      that.setData({ loading: false, loadError: true })
    })
  },

  onRetry: function () {
    this._loadData()
  },

  _loadLeaderboard: function () {
    var that = this
    api.getLeaderboard('total', '', 5)
      .then(function (data) {
        var list = data || []
        var myChildId = that.data.currentLevel ? that.data.currentLevel.child_id : 0
        var myRank = 0

        for (var i = 0; i < list.length; i++) {
          if (list[i].child_id === myChildId) {
            myRank = list[i].rank || (i + 1)
            break
          }
        }

        that.setData({
          leaderboardData: list,
          myRank: myRank,
        })
      })
      .catch(function () {
        that.setData({ leaderboardData: [] })
      })
  },

})
