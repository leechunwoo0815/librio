Component({
  properties: {
    title: { type: String, value: '' },
    value: { type: String, value: '0' },
    unit: { type: String, value: '' },
    icon: { type: String, value: '' },
  },
  methods: {
    onTap() {
      this.triggerEvent('tap')
    },
  },
})
