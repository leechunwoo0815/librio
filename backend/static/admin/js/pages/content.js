(function() {
  'use strict';

  var books = [];
  var currentBookId = null;
  var pages = [];
  var audios = [];

  function switchTab(name, el) {
    document.querySelectorAll('.tab-item').forEach(function(t) { t.classList.remove('active'); });
    document.querySelectorAll('.tab-panel').forEach(function(p) { p.classList.remove('active'); });
    el.classList.add('active');
    document.getElementById('panel-' + name).classList.add('active');
  }
  window.switchTab = switchTab;

  async function loadBooks() {
    try {
      var data = await api.get('/admin/api/books?page=1&page_size=100');
      books = data.items || [];
      var opts = '<option value="">-- 请选择图书 --</option>';
      books.forEach(function(b) {
        opts += '<option value="' + b.id + '">' + escapeHtml(b.title) + '</option>';
      });
      document.getElementById('bookSelect').innerHTML = opts;
      document.getElementById('pageEditBookSelect').innerHTML = opts;
      document.getElementById('uploadBookSelect').innerHTML = opts;
    } catch (e) {
      showToast('加载图书失败: ' + e.message, 'error');
    }
  }

  async function selectBook(bookId) {
    currentBookId = bookId ? parseInt(bookId, 10) : null;
    if (!currentBookId) {
      document.getElementById('pageGrid').innerHTML = '<div class="p-40 text-center text-muted full-span">请先选择一本图书</div>';
      document.getElementById('audioBody').innerHTML = '<tr><td colspan="7" class="text-center text-muted p-24">请先选择一本图书</td></tr>';
      document.getElementById('pageCount').textContent = '共 0 页';
      document.getElementById('audioCount').textContent = '共 0 个音频文件';
      return;
    }
    var book = books.find(function(b) { return b.id === currentBookId; }) || {};
    document.getElementById('audioBookId').value = currentBookId;
    loadPages(currentBookId);
    loadAudios(currentBookId, book.title);
  }

  async function loadPages(bookId) {
    try {
      var data = await api.get('/admin/api/books/' + bookId + '/pages');
      pages = data.items || [];
      document.getElementById('pageCount').textContent = '共 ' + pages.length + ' 页';
      renderPages();
    } catch (e) {
      showToast('加载页面失败: ' + e.message, 'error');
    }
  }

  function renderPages() {
    var grid = document.getElementById('pageGrid');
    if (!pages.length) {
      grid.innerHTML = '<div class="p-40 text-center text-muted full-span">暂无页面，点击“新增页面”添加</div>';
      return;
    }
    grid.innerHTML = pages.map(function(p) {
      return '<div class="page-card p-16" onclick="editPage(' + p.page_number + ')">' +
        '<div class="page-num">P' + p.page_number + '</div>' +
        '<div class="page-status text-sm text-muted">' + (p.text_content ? '有文本' : '无文本') + ' · ' + (p.image_url ? '有图片' : '无图片') + ' · ' + (p.audio_url ? '有音频' : '无音频') + '</div>' +
      '</div>';
    }).join('');
  }

  async function loadAudios(bookId, bookTitle) {
    try {
      var data = await api.get('/admin/api/audio/list?keyword=' + encodeURIComponent(bookTitle || ''));
      audios = data.items || [];
      // 如果按书名没搜到，兜底显示该书已关联的音频
      if (!audios.length) {
        var all = await api.get('/admin/api/audio/list');
        var allItems = all.items || [];
        audios = allItems.filter(function(a) { return a.book_id === bookId; });
      }
      document.getElementById('audioCount').textContent = '共 ' + audios.length + ' 个音频文件';
      renderAudios();
    } catch (e) {
      showToast('加载音频失败: ' + e.message, 'error');
    }
  }

  function renderAudios() {
    var body = document.getElementById('audioBody');
    if (!audios.length) {
      body.innerHTML = '<tr><td colspan="7" class="text-center text-muted p-24">暂无音频</td></tr>';
      return;
    }
    body.innerHTML = audios.map(function(a) {
      return '<tr>' +
        '<td><button class="action-sm" onclick="playAudioContent(\'' + jsEscape(a.file_url || '') + '\')">▶</button></td>' +
        '<td>' + escapeHtml(a.filename || '-') + '</td>' +
        '<td>' + escapeHtml(a.duration || '-') + '</td>' +
        '<td>' + escapeHtml(a.page_label || '全文') + '</td>' +
        '<td>' + (a.file_size || '-') + '</td>' +
        '<td class="text-sm text-muted">' + (a.create_time ? a.create_time.slice(0, 10) : '-') + '</td>' +
        '<td><button class="action-sm" onclick="deleteAudioContent(' + a.id + ')">删除</button></td>' +
      '</tr>';
    }).join('');
  }

  function openUploadModal() { document.getElementById('uploadModal').classList.add('show'); }
  function closeUploadModal() { document.getElementById('uploadModal').classList.remove('show'); }

  function openPageModal() {
    if (!currentBookId) { showToast('请先选择图书', 'warning'); return; }
    document.getElementById('pageEditBookId').value = currentBookId;
    document.getElementById('pageEditPageId').value = '';
    document.getElementById('pageEditBookSelect').value = currentBookId;
    document.getElementById('pageEditNumber').value = pages.length + 1;
    document.getElementById('pageEditImageUrl').value = '';
    document.getElementById('pageEditAudioUrl').value = '';
    document.getElementById('pageEditText').value = '';
    document.getElementById('pageModal').classList.add('show');
  }

  function closePageModal() { document.getElementById('pageModal').classList.remove('show'); }

  window.editPage = function(pageNumber) {
    if (!currentBookId) return;
    var p = pages.find(function(x) { return x.page_number === pageNumber; }) || {};
    document.getElementById('pageEditBookId').value = currentBookId;
    document.getElementById('pageEditPageId').value = p.id || '';
    document.getElementById('pageEditBookSelect').value = currentBookId;
    document.getElementById('pageEditNumber').value = pageNumber;
    document.getElementById('pageEditImageUrl').value = p.image_url || '';
    document.getElementById('pageEditAudioUrl').value = p.audio_url || '';
    document.getElementById('pageEditText').value = p.text_content || '';
    document.getElementById('pageModal').classList.add('show');
  };

  async function savePage() {
    if (!currentBookId) return;
    var pageNumber = parseInt(document.getElementById('pageEditNumber').value, 10);
    if (!pageNumber || pageNumber < 1) { showToast('请输入有效页码', 'error'); return; }
    try {
      await api.put('/admin/api/books/' + currentBookId + '/pages/' + pageNumber, {
        text_content: document.getElementById('pageEditText').value,
        image_url: document.getElementById('pageEditImageUrl').value || null,
        audio_url: document.getElementById('pageEditAudioUrl').value || null,
      });
      showToast('页面保存成功');
      closePageModal();
      loadPages(currentBookId);
    } catch (e) {
      showToast('保存失败: ' + e.message, 'error');
    }
  }

  function openAudioModal() {
    if (!currentBookId) { showToast('请先选择图书', 'warning'); return; }
    document.getElementById('audioBookId').value = currentBookId;
    document.getElementById('audioFileUrl').value = '';
    document.getElementById('audioFilename').value = '';
    document.getElementById('audioDuration').value = '';
    document.getElementById('audioPageNumber').value = '';
    document.getElementById('audioModal').classList.add('show');
  }

  function closeAudioModal() { document.getElementById('audioModal').classList.remove('show'); }

  async function saveAudio() {
    if (!currentBookId) return;
    var body = {
      book_id: currentBookId,
      file_url: document.getElementById('audioFileUrl').value.trim(),
      filename: document.getElementById('audioFilename').value.trim(),
      duration: document.getElementById('audioDuration').value.trim() || null,
      page_number: document.getElementById('audioPageNumber').value ? parseInt(document.getElementById('audioPageNumber').value, 10) : null,
    };
    if (!body.file_url || !body.filename) { showToast('请填写音频 URL 和文件名', 'error'); return; }
    try {
      await api.post('/admin/api/audio/', body);
      showToast('音频关联成功');
      closeAudioModal();
      var book = books.find(function(b) { return b.id === currentBookId; }) || {};
      loadAudios(currentBookId, book.title);
    } catch (e) {
      showToast('保存失败: ' + e.message, 'error');
    }
  }

  window.playAudioContent = function(url) {
    if (!url) return;
    var audio = new Audio(url);
    audio.play().catch(function() { showToast('播放失败', 'error'); });
  };

  window.showConfirmDialog = function(title, msg, onConfirm) {
    document.querySelector('#confirmDialog h2').textContent = title;
    document.getElementById('confirmMsg').textContent = msg;
    document.getElementById('confirmBtn').onclick = function() {
      closeModal('confirmDialog');
      onConfirm();
    };
    showModal('confirmDialog');
  };

  window.deleteAudioContent = async function(id) {
    showConfirmDialog('确认删除', '确认删除该音频？', async function() {
      try {
        await api.del('/admin/api/audio/' + id);
        showToast('删除成功');
        var book = books.find(function(b) { return b.id === currentBookId; }) || {};
        loadAudios(currentBookId, book.title);
      } catch (e) {
        showToast('删除失败: ' + e.message, 'error');
      }
    });
  };

  // PDF 上传占位：使用通用上传接口
  document.getElementById('pdfFileInput').addEventListener('change', async function(e) {
    var file = e.target.files[0];
    if (!file) return;
    var formData = new FormData();
    formData.append('file', file);
    try {
      var resp = await fetch('/admin/api/upload?filename=' + encodeURIComponent(file.name), {
        method: 'POST',
        headers: { 'Authorization': 'Bearer ' + (localStorage.getItem('mw_admin_token') || '') },
        body: formData,
      });
      var result = await resp.json();
      if (resp.ok) {
        showToast('PDF 已上传，路径: ' + result.url);
      } else {
        showToast(result.detail || '上传失败', 'error');
      }
    } catch (err) {
      showToast('上传失败', 'error');
    }
  });

  document.getElementById('bookSelect').addEventListener('change', function(e) {
    selectBook(e.target.value);
  });

  document.addEventListener('DOMContentLoaded', function() {
    loadBooks();
  });

  window.openUploadModal = openUploadModal;
  window.closeUploadModal = closeUploadModal;
  window.openPageModal = openPageModal;
  window.closePageModal = closePageModal;
  window.openAudioModal = openAudioModal;
  window.closeAudioModal = closeAudioModal;
  window.savePage = savePage;
  window.saveAudio = saveAudio;

  window.startUploadPdf = function() {
    var bookId = document.getElementById('uploadBookSelect').value;
    if (!bookId) {
      showToast('请先选择图书', 'warning');
      return;
    }
    var fileInput = document.getElementById('pdfFileInput');
    if (!fileInput.files || !fileInput.files[0]) {
      showToast('请先选择 PDF 文件', 'warning');
      return;
    }
    showToast('PDF 处理任务已提交，请稍后刷新查看');
    closeUploadModal();
  };
})();