Component({
  properties: {
    book: { type: Object, value: {} },
    showAction: { type: Boolean, value: false },
  },
  methods: {
    onTap() {
      this.triggerEvent('tap', { book: this.data.book })
    },
    onAction() {
      this.triggerEvent('action', { book: this.data.book })
    },
  },
})
