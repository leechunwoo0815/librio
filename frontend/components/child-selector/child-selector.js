Component({
  properties: {
    childList: { type: Array, value: [] },
    currentId: { type: String, value: '' },
  },
  methods: {
    onSelect(e) {
      const id = e.currentTarget.dataset.id
      this.triggerEvent('change', { childId: id })
    },
  },
})
