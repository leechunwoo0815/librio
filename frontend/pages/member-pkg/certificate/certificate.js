// frontend/pages/member-pkg/certificate/certificate.js
const api = require('../../utils/api')
const auth = require('../../utils/auth')

function formatDate(dateStr) {
  if (!dateStr) return ''
  var d = new Date(dateStr)
  var y = d.getFullYear()
  var m = ('0' + (d.getMonth() + 1)).slice(-2)
  var day = ('0' + d.getDate()).slice(-2)
  return y + '年' + parseInt(m) + '月' + parseInt(day) + '日'
}

Page({
  data: {
    mode: 'single',   // 'single' | 'list'
    cert: null,        // single certificate data
    certList: [],      // list of certificates
    loading: false,
    childId: 0,
    showShare: false,
    qrCodeUrl: '',
  },

  onLoad: function (options) {
    if (!auth.requireAuth()) return

    // 从二维码扫码进入：options.scene 包含 scene 值
    if (options.scene) {
      var scene = decodeURIComponent(options.scene)
      if (scene.indexOf('cert_') === 0) {
        var certId = parseInt(scene.substring(5))
        if (certId) {
          this.setData({ mode: 'list' })
          this._loadChildCerts(certId)
          return
        }
      }
    }

    if (options.certId) {
      // Single cert by ID — load from child's certs
      this.setData({ mode: 'list' })
      this._loadChildCerts(options.certId)
    } else if (options.childId) {
      this.setData({ childId: parseInt(options.childId), mode: 'list' })
      this._loadCertList(parseInt(options.childId))
    } else {
      // Default: load current child's certs
      var child = auth.getCurrentChild()
      if (child) {
        this.setData({ childId: child.id, mode: 'list' })
        this._loadCertList(child.id)
      }
    }
  },

  onCertTap: function (e) {
    var idx = e.currentTarget.dataset.index
    var cert = this.data.certList[idx]
    if (cert) {
      this.setData({ mode: 'single', cert: cert })
      wx.setNavigationBarTitle({ title: '晋级证书' })
    }
  },

  _loadCertList: function (childId) {
    var that = this
    this.setData({ loading: true })
    api.getChildCertificates(childId)
      .then(function (list) {
        var certs = (list || []).map(function (c) {
          return {
            id: c.id,
            level_name: c.level_name,
            child_name: c.child_name,
            english_name: c.english_name,
            badge_emoji: c.badge_emoji,
            from_level: c.from_level,
            certificate_no: c.certificate_no,
            created_at: c.created_at,
            dateStr: formatDate(c.created_at),
          }
        })
        that.setData({ certList: certs, loading: false })

        // If only one cert, show it directly
        if (certs.length === 1) {
          that.setData({ mode: 'single', cert: certs[0] })
          wx.setNavigationBarTitle({ title: '晋级证书' })
        }
      })
      .catch(function () {
        that.setData({ certList: [], loading: false })
      })
  },

  _loadChildCerts: function (certId) {
    // Load all certs for the current child and find by certId
    var that = this
    var child = auth.getCurrentChild()
    if (!child) return

    api.getChildCertificates(child.id)
      .then(function (list) {
        var certs = (list || []).map(function (c) {
          return {
            id: c.id,
            level_name: c.level_name,
            child_name: c.child_name,
            english_name: c.english_name,
            badge_emoji: c.badge_emoji,
            from_level: c.from_level,
            certificate_no: c.certificate_no,
            created_at: c.created_at,
            dateStr: formatDate(c.created_at),
          }
        })

        // Find the specific cert
        var found = null
        for (var i = 0; i < certs.length; i++) {
          if (String(certs[i].id) === String(certId)) {
            found = certs[i]
            break
          }
        }

        if (found) {
          that.setData({ mode: 'single', cert: found })
          wx.setNavigationBarTitle({ title: '晋级证书' })
        } else if (certs.length > 0) {
          // CertId not found, show list
          that.setData({ certList: certs })
        }
      })
      .catch(function () {
        that.setData({ certList: [] })
      })
  },

  // 保存到相册
  saveToAlbum: function () {
    var that = this
    var cert = this.data.cert
    if (!cert) return

    wx.showLoading({ title: '生成图片...', mask: true })

    var query = this.createSelectorQuery()
    query.select('#certCanvas')
      .fields({ node: true, size: true })
      .exec(function (res) {
        if (!res || !res[0] || !res[0].node) {
          wx.hideLoading()
          wx.showToast({ title: '无法生成图片', icon: 'none' })
          return
        }

        var canvas = res[0].node
        var ctx = canvas.getContext('2d')

        var dpr = wx.getWindowInfo().pixelRatio || 2
        var width = 600
        var height = 900
        canvas.width = width * dpr
        canvas.height = height * dpr
        ctx.scale(dpr, dpr)

        // 背景
        ctx.fillStyle = '#fffdf5'
        ctx.fillRect(0, 0, width, height)

        // 金色边框
        ctx.strokeStyle = '#daa520'
        ctx.lineWidth = 6
        ctx.strokeRect(12, 12, width - 24, height - 24)

        // 内框
        ctx.strokeStyle = '#f0d060'
        ctx.lineWidth = 2
        ctx.strokeRect(24, 24, width - 48, height - 48)

        var cy = 120

        // Badge emoji
        ctx.font = '64px sans-serif'
        ctx.textAlign = 'center'
        ctx.fillText(cert.badge_emoji || '🎓', width / 2, cy)
        cy += 80

        // 标题
        ctx.font = 'bold 36px "PingFang SC", sans-serif'
        ctx.fillStyle = '#b8860b'
        ctx.fillText('晋级证书', width / 2, cy)
        cy += 60

        // 分割线
        ctx.strokeStyle = '#daa520'
        ctx.lineWidth = 1
        ctx.beginPath()
        ctx.moveTo(150, cy)
        ctx.lineTo(width - 150, cy)
        ctx.stroke()
        cy += 50

        // 名字
        ctx.font = 'bold 32px "PingFang SC", sans-serif'
        ctx.fillStyle = '#333'
        ctx.fillText(cert.child_name || '', width / 2, cy)
        cy += 48

        // 英文名
        if (cert.english_name) {
          ctx.font = '24px "PingFang SC", sans-serif'
          ctx.fillStyle = '#666'
          ctx.fillText(cert.english_name, width / 2, cy)
          cy += 44
        }

        // 晋级信息
        cy += 16
        ctx.font = '26px "PingFang SC", sans-serif'
        ctx.fillStyle = '#555'
        ctx.fillText('成功晋级至', width / 2, cy)
        cy += 48

        ctx.font = 'bold 34px "PingFang SC", sans-serif'
        ctx.fillStyle = '#b8860b'
        ctx.fillText(cert.level_name || '', width / 2, cy)
        cy += 60

        // 日期
        ctx.font = '22px "PingFang SC", sans-serif'
        ctx.fillStyle = '#999'
        ctx.fillText(cert.dateStr || '', width / 2, cy)
        cy += 36

        // 证书编号
        if (cert.certificate_no) {
          ctx.font = '20px "PingFang SC", sans-serif'
          ctx.fillStyle = '#bbb'
          ctx.fillText('证书编号：' + cert.certificate_no, width / 2, cy)
        }

        // 导出图片
        wx.canvasToTempFilePath({
          canvas: canvas,
          x: 0,
          y: 0,
          width: width * dpr,
          height: height * dpr,
          destWidth: width * dpr,
          destHeight: height * dpr,
          success: function (fileRes) {
            wx.saveImageToPhotosAlbum({
              filePath: fileRes.tempFilePath,
              success: function () {
                wx.hideLoading()
                wx.showToast({ title: '已保存到相册', icon: 'success' })
              },
              fail: function (saveErr) {
                wx.hideLoading()
                if (saveErr.errMsg && saveErr.errMsg.indexOf('auth deny') >= 0) {
                  wx.showModal({
                    title: '提示',
                    content: '需要您授权保存图片到相册',
                    confirmText: '去授权',
                    success: function (modalRes) {
                      if (modalRes.confirm) {
                        wx.openSetting()
                      }
                    }
                  })
                } else {
                  wx.showToast({ title: '保存失败', icon: 'none' })
                }
              }
            })
          },
          fail: function () {
            wx.hideLoading()
            wx.showToast({ title: '图片生成失败，请重试', icon: 'none' })
          }
        })
      })
  },

  showShareModal: function () {
    this.setData({ showShare: true, qrCodeUrl: '' })

    var cert = this.data.cert
    if (!cert || !cert.id) return

    var scene = 'cert_' + cert.id
    var page = 'pages/member-pkg/certificate/certificate'
    var baseURL = getApp().globalData.baseURL || 'https://api.dmkwords.cn'
    var url = baseURL + '/wechat/qr-code?scene=' + scene + '&page=' + page
    var retries = 0
    var self = this

    function download() {
      wx.downloadFile({
        url: url,
        success: function (res) {
          self.setData({ qrCodeUrl: res.tempFilePath })
        },
        fail: function () {
          retries++
          if (retries < 2) {
            self._qrTimer = setTimeout(download, 1000)
          } else {
            wx.showToast({ title: '加载小程序码失败', icon: 'none' })
          }
        }
      })
    }

    download()
  },

  closeShare: function () {
    this.setData({ showShare: false });
  },

  // 分享给朋友
  onShareAppMessage: function () {
    var cert = this.data.cert
    var path = '/pages/member-pkg/certificate/certificate?'
    if (cert && cert.id) {
      path += 'certId=' + cert.id
    } else {
      path += 'childId=' + (this.data.childId || 0)
    }
    return {
      title: cert
        ? (cert.child_name + '成功晋级至' + cert.level_name + '！')
        : 'DmkWords 晋级证书',
      path: path,
    }
  },

  onUnload() {
    if (this._qrTimer) { clearTimeout(this._qrTimer); this._qrTimer = null }
  },
})
