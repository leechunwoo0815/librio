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
    const app = getApp()
    if (app.globalData.isTestMode) {
      this._loadDemoData()
      return
    }
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

    // Load level, achievements in parallel
    Promise.all([
      api.getCurrentLevel(childId).catch(function () { return null }),
      api.getAchievements().catch(function () { return [] }),
      api.getChildAchievements(childId).catch(function () { return [] }),
    ]).then(function (results) {
      var level = results[0]
      var adv = null  // 晋级由后端自动触发
      var allDefs = results[1] || []
      var earned = results[2] || []

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

      // Progress
      var progressPercent = 0
      if (adv && adv.books_required > 0) {
        progressPercent = Math.min(100, Math.round(adv.books_read / adv.books_required * 100))
      }

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

  _loadDemoData: function () {
    this.setData({
      currentLevel: {
        level_name: 'Level 3 · 故事探索者',
        level_number: 3,
        books_read: 12,
        quizzes_passed: 10,
        streak_days: 7,
      },
      advancement: {
        books_read: 12,
        books_required: 20,
        can_advance: false,
      },
      progressPercent: 60,
      myName: 'Mega',
      achievements: [
        { id: 1, name: '初读启航', badge_emoji: '📖', description: '完成第一本书的阅读', trigger_desc: '阅读完任意 1 本书', earned: true, dateStr: '2025-05-10' },
        { id: 2, name: '连续 7 天', badge_emoji: '🔥', description: '连续阅读打卡 7 天', trigger_desc: '连续 7 天每天阅读满 10 分钟', earned: true, dateStr: '2025-05-20' },
        { id: 3, name: '满分达人', badge_emoji: '💯', description: '测验获得 100 分', trigger_desc: '任意一次测验得 100 分', earned: true, dateStr: '2025-05-25' },
        { id: 4, name: '读完 10 本', badge_emoji: '📚', description: '累计阅读 10 本书', trigger_desc: '累计阅读完 10 本书', earned: true, dateStr: '2025-06-01' },
        { id: 5, name: '朗读之星', badge_emoji: '🎙️', description: '完成 10 次朗读录音', trigger_desc: '累计完成 10 次朗读录音', earned: true, dateStr: '2025-06-03' },
        { id: 6, name: '词汇先锋', badge_emoji: '📝', description: '积累 100 个生词', trigger_desc: '生词本累计收录 100 个单词', earned: true, dateStr: '2025-06-04' },
        { id: 7, name: '晋级达人', badge_emoji: '🏆', description: '成功晋级 3 次', trigger_desc: '累计成功晋级 3 次', earned: false, dateStr: '' },
        { id: 8, name: '速度之王', badge_emoji: '⚡', description: '5 分钟内完成测验满分', trigger_desc: '5 分钟内完成测验并得满分', earned: false, dateStr: '' },
        { id: 9, name: '阅读大师', badge_emoji: '🌟', description: '累计阅读 100 本书', trigger_desc: '累计阅读完 100 本书', earned: false, dateStr: '' },
      ],
      earnedCount: 6,
      recentEarned: [
        { id: 6, name: '词汇先锋', badge_emoji: '📝', description: '生词本累计收录 100 个单词', dateStr: '2025-06-04' },
        { id: 5, name: '朗读之星', badge_emoji: '🎙️', description: '累计完成 10 次朗读录音', dateStr: '2025-06-03' },
        { id: 4, name: '读完 10 本', badge_emoji: '📚', description: '累计阅读完 10 本书', dateStr: '2025-06-01' },
        { id: 3, name: '满分达人', badge_emoji: '💯', description: '任意一次测验得 100 分', dateStr: '2025-05-25' },
        { id: 2, name: '连续 7 天', badge_emoji: '🔥', description: '连续 7 天每天阅读满 10 分钟', dateStr: '2025-05-20' },
        { id: 1, name: '初读启航', badge_emoji: '📖', description: '阅读完任意 1 本书', dateStr: '2025-05-10' },
      ],
      leaderboardData: [
        { name: '小月', avatar_emoji: '👧', level_name: 'Level 5', books_read: 38 },
        { name: '小明', avatar_emoji: '👦', level_name: 'Level 5', books_read: 28 },
        { name: 'Lily', avatar_emoji: '👧', level_name: 'Level 4', books_read: 22 },
        { name: 'Tom', avatar_emoji: '👦', level_name: 'Level 3', books_read: 18 },
      ],
      myRank: 5,
    })
  },
})
