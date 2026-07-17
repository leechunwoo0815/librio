Component({
  properties: {
    src: { type: String, value: '' },
    title: { type: String, value: '' },
    playing: { type: Boolean, value: false },
  },
  data: {
    currentTime: '0:00',
    duration: '0:00',
    progress: 0,
    loading: false,
  },
  lifetimes: {
    attached() {
      this._manager = wx.getBackgroundAudioManager()
      this._bindEvents()
    },
    detached() {
      this._unbindEvents()
      if (this._manager) { this._manager.stop() }
    },
  },
  observers: {
    'src': function (src) {
      if (src && this._manager) {
        this._manager.src = src
        this._manager.title = this.data.title || 'DmkWords'
      }
    },
    'playing': function (playing) {
      if (!this._manager || !this.data.src) return
      playing ? this._manager.play() : this._manager.pause()
    },
  },
  methods: {
    _bindEvents() {
      if (!this._manager) return
      this._manager.onTimeUpdate(() => { this._updateTime() })
      this._manager.onPlay(() => { this.setData({ loading: false }); if (!this.data.playing) this.triggerEvent('play') })
      this._manager.onPause(() => { this.setData({ loading: false }); if (this.data.playing) this.triggerEvent('pause') })
      this._manager.onWaiting(() => { this.setData({ loading: true }) })
      this._manager.onCanplay(() => { this.setData({ loading: false }) })
      this._manager.onError(() => { this.setData({ loading: false }); wx.showToast({ title: '音频加载失败', icon: 'none' }) })
    },
    _unbindEvents() {
      if (!this._manager) return
      this._manager.offTimeUpdate(); this._manager.offPlay(); this._manager.offPause()
      this._manager.offWaiting(); this._manager.offCanplay(); this._manager.offError()
    },
    _updateTime() {
      if (!this._manager || !this._manager.duration) return
      this.setData({
        currentTime: this._fmt(this._manager.currentTime),
        duration: this._fmt(this._manager.duration),
        progress: Math.floor((this._manager.currentTime / this._manager.duration) * 100),
      })
    },
    togglePlay() {
      if (!this.data.src) return
      this.data.playing ? this._manager.pause() : this._manager.play()
    },
    seek(e) {
      const pos = (e.detail.value / 100) * this._manager.duration
      this._manager.seek(pos)
    },
    _fmt(s) {
      if (!s || isNaN(s)) return '0:00'
      const m = Math.floor(s / 60)
      const sec = Math.floor(s % 60)
      return m + ':' + (sec < 10 ? '0' : '') + sec
    },
  },
})
