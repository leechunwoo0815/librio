// frontend/pages/order-pkg/child-manage/child-manage.js
const api = require('../../utils/api')
const auth = require('../../utils/auth')
const security = require('../../utils/security')

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
    currentChildItem: null,
    otherChildren: [],
    editingChild: null,
  },

  onLoad() {
    if (!auth.requireAuth()) return
    const ages = []
    for (let i = 3; i <= 15; i++) ages.push(i + '岁')
    this.setData({ ageOptions: ages })
  },

  async onShow() {
    await this.loadChildren()
  },

  async loadChildren() {
    this.setData({ loading: true })
    try {
      const children = await api.getChildren()
      const safeChildren = children || []
      const currentChild = auth.getCurrentChild()
      const currentChildItem = currentChild ? safeChildren.find(c => c.id === currentChild.id) || null : null
      const otherChildren = currentChildItem ? safeChildren.filter(c => c.id !== currentChildItem.id) : safeChildren
      this.setData({
        children: safeChildren,
        currentChildId: currentChild ? currentChild.id : 0,
        currentChildItem,
        otherChildren,
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
    this.setData({ showAddForm: false, editingChild: null })
  },

  onEditChild(e) {
    const child = e.currentTarget.dataset.child
    const ageIndex = this.data.ageOptions.findIndex(a => parseInt(a) === child.age)
    this.setData({
      editingChild: child,
      showAddForm: true,
      formName: child.name || '',
      formAgeIndex: ageIndex >= 0 ? ageIndex : 4,
      formGradeIndex: this.data.gradeOptions.indexOf(child.grade) >= 0 ? this.data.gradeOptions.indexOf(child.grade) : 6,
    })
  },

  async onDeleteChild(e) {
    const childId = e.currentTarget.dataset.childid
    const res = await wx.showModal({
      title: '确认删除',
      content: '确定要删除该孩子吗？此操作不可恢复。',
      confirmText: '删除',
      confirmColor: '#ef4444',
    })
    if (!res.confirm) return
    try {
      await api.deleteChild(childId)
      wx.showToast({ title: '删除成功', icon: 'success' })
      await this.loadChildren()
    } catch (e) {
      wx.showToast({ title: e.message || '删除失败', icon: 'none' })
    }
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
    const { formName, formAgeIndex, formGradeIndex, ageOptions, gradeOptions, editingChild } = this.data
    if (!formName.trim()) {
      wx.showToast({ title: '请输入孩子姓名', icon: 'none' })
      return
    }

    const age = parseInt(ageOptions[formAgeIndex])
    const grade = gradeOptions[formGradeIndex]

    // 内容安全校验
    try {
      await security.checkText(formName.trim())
    } catch (e) {
      wx.showToast({ title: e.message || '孩子姓名包含违规内容', icon: 'none' })
      return
    }

    wx.showLoading({ title: editingChild ? '更新中...' : '添加中...' })
    try {
      if (editingChild) {
        await api.updateChild(editingChild.id, {
          name: formName.trim(),
          age,
          grade,
        })
      } else {
        await api.createChild({
          name: formName.trim(),
          age,
          grade,
        })
      }
      wx.hideLoading()
      wx.showToast({ title: editingChild ? '更新成功' : '添加成功', icon: 'success' })
      this.setData({ showAddForm: false, editingChild: null })
      await this.loadChildren()
    } catch (e) {
      wx.hideLoading()
      wx.showToast({ title: e.message || (editingChild ? '更新失败' : '添加失败'), icon: 'none' })
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
