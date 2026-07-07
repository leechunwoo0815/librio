// frontend/pages/order-pkg/child-manage/child-manage.js
const api = require('../../utils/api')
const auth = require('../../utils/auth')

const gradeOptions = [
  '幼儿园小班', '幼儿园中班', '幼儿园大班',
  '一年级', '二年级', '三年级', '四年级', '五年级', '六年级'
]

Page({
  data: {
    children: [],
    currentChildId: 0,
    showAddForm: false,
    formName: '',
    formAgeIndex: 0,
    formGradeIndex: 0,
    ageOptions: [],
    gradeOptions: gradeOptions,
    loading: true,
    testMode: false,
  },

  onLoad() {
    const app = getApp()
    if (app.globalData.isTestMode) {
      this.setData({ testMode: true, loading: false })
      this.loadTestData()
      return
    }
    if (!auth.requireAuth()) return
    const ages = []
    for (let i = 3; i <= 15; i++) ages.push(i + '岁')
    this.setData({ ageOptions: ages })
  },

  async onShow() {
    if (this.data.testMode) return
    await this.loadChildren()
  },

  loadTestData() {
    const testChildren = [
      {
        id: 1,
        name: 'Mega',
        age: 8,
        grade: '二年级',
        avatar: '👦',
        level: '⭐ Level 3 · 故事探索者',
        levelClass: 'level-g1',
        avatarClass: 'g1',
        total_books_finished: 12,
        current_streak_days: 7,
        isCurrent: true,
      },
      {
        id: 2,
        name: 'Mini',
        age: 5,
        grade: '幼儿园大班',
        avatar: '👧',
        level: '🌟 Level 1 · 字母小达人',
        levelClass: 'level-g2',
        avatarClass: 'g2',
        total_books_finished: 3,
        current_streak_days: 3,
        isCurrent: false,
      },
      {
        id: 3,
        name: '小明',
        age: 10,
        grade: '四年级',
        avatar: '👦',
        level: '⭐ Level 5 · 阅读先锋',
        levelClass: 'level-g1',
        avatarClass: 'g1',
        total_books_finished: 28,
        current_streak_days: 21,
        isCurrent: false,
      },
    ]
    this.setData({
      children: testChildren,
      currentChildId: 1,
    })
  },

  async loadChildren() {
    this.setData({ loading: true })
    try {
      const children = await api.getChildren()
      const currentChild = auth.getCurrentChild()
      this.setData({
        children,
        currentChildId: currentChild ? currentChild.id : 0,
        loading: false,
      })
    } catch (e) {
      console.error(e)
      this.setData({ loading: false })
    }
  },

  async onTapChild(e) {
    const child = e.currentTarget.dataset.child
    const res = await wx.showModal({
      title: '切换孩子',
      content: `确定切换到 ${child.name} 吗？`,
      confirmText: '切换',
    })
    if (!res.confirm) return

    try {
      auth.selectChild([child])
      this.setData({ currentChildId: child.id })
      wx.showToast({ title: `已切换到${child.name}`, icon: 'success' })
    } catch (e) {
      wx.showToast({ title: '切换失败', icon: 'none' })
    }
  },

  onShowAddForm() {
    this.setData({
      showAddForm: true,
      formName: '',
      formAgeIndex: 4,
      formGradeIndex: 6,
    })
  },

  onCloseAddForm() {
    this.setData({ showAddForm: false })
  },

  onFormNameInput(e) {
    this.setData({ formName: e.detail.value })
  },

  onFormAgeChange(e) {
    this.setData({ formAgeIndex: e.detail.value })
  },

  onFormGradeChange(e) {
    this.setData({ formGradeIndex: e.detail.value })
  },

  async onSubmitChild() {
    const { formName, formAgeIndex, formGradeIndex, ageOptions, gradeOptions } = this.data
    if (!formName.trim()) {
      wx.showToast({ title: '请输入孩子姓名', icon: 'none' })
      return
    }

    const age = parseInt(ageOptions[formAgeIndex])
    const grade = gradeOptions[formGradeIndex]

    wx.showLoading({ title: '添加中...' })
    try {
      await api.createChild({
        name: formName.trim(),
        age,
        grade,
      })
      wx.hideLoading()
      wx.showToast({ title: '添加成功', icon: 'success' })
      this.setData({ showAddForm: false })
      await this.loadChildren()
    } catch (e) {
      wx.hideLoading()
      wx.showToast({ title: e.message || '添加失败', icon: 'none' })
    }
  },

  onNavigateToStats(e) {
    const childId = e.currentTarget.dataset.childid
    wx.navigateTo({ url: `/pages/member-pkg/reading-stats/reading-stats?childId=${childId}` })
  },

  onNavigateToAchievement(e) {
    const childId = e.currentTarget.dataset.childid
    wx.navigateTo({ url: `/pages/member-pkg/achievement/achievement?childId=${childId}` })
  },

  onPreventBubble() {},
})
