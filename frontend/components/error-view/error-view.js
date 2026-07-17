// frontend/components/error-view/error-view.js
Component({
  properties: {
    type: { type: String, value: 'error' }, // error | network | empty | permission
    title: { type: String, value: '' },
    desc: { type: String, value: '' },
    showRetry: { type: Boolean, value: true },
    showBack: { type: Boolean, value: false },
    retryText: { type: String, value: '重试' },
    backText: { type: String, value: '返回' },
  },
  data: {
    visible: true,
    icon: '😔',
  },
  observers: {
    'type': function(type) {
      const icons = { error: '😔', network: '📡', empty: '📭', permission: '🔒' };
      this.setData({ icon: icons[type] || '😔' });
    }
  },
  methods: {
    onRetry() { this.triggerEvent('retry'); },
    onBack() {
      try {
        var pages = getCurrentPages()
        if (pages.length > 1) {
          wx.navigateBack()
        } else {
          wx.switchTab({ url: '/pages/index/index' })
        }
      } catch (e) {
        wx.switchTab({ url: '/pages/index/index' })
      }
    },
  }
});
