Component({
  properties: {
    amount: { type: Number, value: 0 },
    buttonText: { type: String, value: '立即支付' },
    disabled: { type: Boolean, value: false },
  },
  data: {
    isIOS: false,
  },
  lifetimes: {
    attached() {
      try {
        var sysInfo = wx.getSystemInfoSync();
        this.setData({ isIOS: sysInfo.platform === 'ios' });
      } catch (e) {}
    }
  },
  methods: {
    onTap() {
      if (this.data.disabled) return;
      if (this.data.isIOS) {
        this.triggerEvent('iosfallback');
      } else {
        this.triggerEvent('pay');
      }
    }
  }
});
