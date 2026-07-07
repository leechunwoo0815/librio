Component({
  properties: {
    actions: { type: Array, value: [] },
  },
  methods: {
    onAction(e) {
      const index = e.currentTarget.dataset.index
      const action = this.data.actions[index]
      this.triggerEvent('action', { index, action })
    },
  },
})
