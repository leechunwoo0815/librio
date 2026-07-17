Component({
  properties: {
    percent: { type: Number, value: 0 },
    showLabel: { type: Boolean, value: true },
    color: { type: String, value: '#4CAF50' },
  },
  data: {
    _clampedPercent: 0,
  },
  observers: {
    'percent': function (pct) {
      this.setData({ _clampedPercent: Math.max(0, Math.min(100, Number(pct) || 0)) })
    },
  },
})
