Component({
  properties: {
    src: { type: String, value: '' },
    title: { type: String, value: '' },
    playing: { type: Boolean, value: false },
  },
  methods: {
    togglePlay() {
      this.triggerEvent(this.data.playing ? 'pause' : 'play')
    },
  },
})
