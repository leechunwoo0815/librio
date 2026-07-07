Component({
  properties: {
    tabs: { type: Array, value: [] },
    current: { type: Number, value: 0 },
  },
  methods: {
    onTab(e) {
      const index = e.currentTarget.dataset.index
      if (index !== this.data.current) {
        this.triggerEvent('change', { index, tab: this.data.tabs[index] })
      }
    },
  },
})
