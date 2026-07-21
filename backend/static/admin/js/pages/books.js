// backend/static/admin/js/pages/books.js
// 图书管理页面逻辑

(function() {
  'use strict';

  const searchInput = document.getElementById('searchInput');
  const booksTable = document.getElementById('booksTable');
  var pageSize = 15;
  let isSubmitting = false;
  let booksData = [];
  let currentKeyword = '';
  let currentPage = 1;

  document.addEventListener('DOMContentLoaded', () => {
    loadBooks();
    if (searchInput) {
      searchInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') searchBooks();
      });
    }

    const addForm = document.getElementById('addForm');
    if (addForm) {
      addForm.addEventListener('input', saveDraft);
      addForm.addEventListener('submit', submitBook);
    }

    const dropZone = document.getElementById('uploadDropZone');
    if (dropZone) {
      dropZone.addEventListener('click', () => document.getElementById('uploadFileInput').click());
    }

    const fileInput = document.getElementById('uploadFileInput');
    if (fileInput) {
      fileInput.addEventListener('change', function() { handleFileSelect(this); });
    }

    BatchSelect.init('#booksTable', (ids) => {
      const countEl = document.getElementById('selectedCount');
      const bar = document.getElementById('batchBar');
      if (countEl) countEl.textContent = ids.length;
      if (bar) bar.classList.toggle('hidden', ids.length === 0);
    });

    // Delegated handler for data-pg buttons
    document.body.addEventListener('click', function(e) {
      const el = e.target.closest('[data-pg]');
      if (!el) return;
      const fn = window.booksPage[el.getAttribute('data-pg')];
      if (typeof fn === 'function') {
        e.preventDefault();
        fn();
      }
    });
  });

  async function loadBooks(keyword, page) {
    currentKeyword = keyword !== undefined ? keyword : currentKeyword;
    currentPage = page !== undefined ? page : currentPage;
    try {
      const url = `/admin/api/books?keyword=${encodeURIComponent(currentKeyword || '')}&page=${currentPage}&page_size=${pageSize}`;
      const data = await api.get(url);
      booksData = data.items || data || [];
      renderBooks(booksData, data.total || booksData.length, data.stats || null);
    } catch (err) {
      showToast(err.message || '加载图书失败', 'error');
      booksTable.innerHTML = '<tr><td colspan="14" class="text-center p-40 text-error">加载失败</td></tr>';
    }
  }

  function searchBooks() {
    const keyword = searchInput ? searchInput.value.trim() : '';
    loadBooks(keyword, 1);
  }

  function goToPage(page) {
    loadBooks(currentKeyword, page);
  }

  function changePageSize(newSize) {
    pageSize = parseInt(newSize);
    currentPage = 1;
    loadBooks();
  }

  function renderBooks(books, total, stats) {
    const pageTotal = total || books.length;
    document.getElementById('statTotal').textContent = pageTotal;
    document.getElementById('statAudio').textContent = stats ? stats.audio_books : books.filter(b => b.has_audio).length;
    document.getElementById('statQuiz').textContent = stats ? stats.quiz_books : books.filter(b => b.question_count && b.question_count > 0).length;
    document.getElementById('paginationInfo').textContent = '共 ' + pageTotal + ' 条';

    if (!books.length) {
      booksTable.innerHTML = '<tr><td colspan="14" style="text-align:center;padding:40px;color:var(--muted);">暂无图书数据</td></tr>';
      document.getElementById('paginationPages').innerHTML = '';
      return;
    }

    booksTable.innerHTML = books.map(b => {
      const hasAudio = b.has_audio;
      const series = b.theme || '';
      const arVal = b.ar_value !== null && b.ar_value !== undefined ? b.ar_value : '-';
      const wc = b.word_count !== null && b.word_count !== undefined ? Number(b.word_count).toLocaleString() : '-';
      const qCount = b.difficulty_level || '-';
      const totalStock = b.total_stock || 0;
      const availStock = b.available_stock !== null && b.available_stock !== undefined ? b.available_stock : totalStock;
      const published = b.is_published !== 0;
      const statusText = published ? '上架' : '下架';
      const statusCls = published ? 'badge-success' : 'badge-muted';
      const barcode = b.barcode || (b.copies && b.copies.length ? b.copies[0].barcode : '-');
      const publishAction = published ? '下架' : '上架';
      return '<tr>' +
        '<td><input type="checkbox" class="row-check" value="' + b.id + '"></td>' +
        '<td style="font-family:var(--font-mono);font-size:12px;color:var(--muted)">' + escapeHtml(b.isbn || '-') + '</td>' +
        '<td><div class="cover-thumb">' + (b.cover ? '<img src="' + escapeHtml(b.cover) + '" />' : '&#x1F4D5;') + '</div></td>' +
        '<td><strong>' + escapeHtml(b.title || '-') + '</strong></td>' +
        '<td>' + escapeHtml(b.author || '-') + '</td>' +
        '<td><span class="badge badge-accent">' + arVal + '</span></td>' +
        '<td>' + wc + '</td>' +
        '<td>' + (series ? '<span class="badge badge-accent">' + escapeHtml(series) + '</span>' : '<span class="badge badge-muted">-</span>') + '</td>' +
        '<td>' + (hasAudio ? '<span class="badge badge-success">有</span>' : '<span class="badge badge-muted">无</span>') + '</td>' +
        '<td>' + qCount + '</td>' +
        '<td><span class="badge ' + statusCls + '">' + statusText + '</span></td>' +
        '<td style="font-family:var(--font-mono);font-size:12px;">' + escapeHtml(barcode) + '</td>' +
        '<td>' + totalStock + ' / ' + availStock + '</td>' +
        '<td><div class="ops">' +
          '<a href="#" onclick="window.booksPage.viewBook(\'' + b.id + '\')">查看</a>' +
          '<span class="sep">|</span>' +
          '<a href="#" onclick="window.booksPage.togglePublish(\'' + b.id + '\',\'' + jsEscape(b.title) + '\',' + totalStock + ',' + availStock + ')">' + publishAction + '</a>' +
          '<span class="sep">|</span>' +
          '<a href="#" style="color:var(--error)" onclick="window.booksPage.deleteBook(\'' + b.id + '\')">删除</a>' +
        '</div></td>' +
      '</tr>';
    }).join('');

    // 重新绑定批量选择事件
    BatchSelect.init('#booksTable', (ids) => {
      document.getElementById('selectedCount').textContent = ids.length;
      document.getElementById('batchBar').classList.toggle('hidden', ids.length === 0);
    });

    // 渲染分页
    renderPagination('paginationPages', pageTotal, currentPage, pageSize, 'window.booksPage.goToPage', 'window.booksPage.changePageSize');
  }

  function openAddModal() {
    const form = document.getElementById('addForm');
    if (form) form.reset();
    document.getElementById('addModal').classList.add('show');
    restoreDraft();
  }

  function closeAddModal() {
    document.getElementById('addModal').classList.remove('show');
  }

  async function submitBook(e) {
    e.preventDefault();
    if (isSubmitting) return;
    isSubmitting = true;
    const submitBtn = document.querySelector('#addForm button[type="submit"]');
    submitBtn.disabled = true;
    submitBtn.textContent = '提交中...';
    const form = document.getElementById('addForm');
    const fd = new FormData(form);
    const body = {};
    for (const [k, v] of fd.entries()) {
      if (v === '') continue;
      if (['ar_value', 'age_min', 'age_max', 'word_count'].includes(k)) {
        body[k] = Number(v);
      } else {
        body[k] = v;
      }
    }
    try {
      await api.post('/admin/api/books', body);
      showToast('图书添加成功');
      clearDraft();
      closeAddModal();
      loadBooks(currentKeyword, 1);
    } catch (err) {
      showToast(err.message || '添加失败', 'error');
    } finally {
      isSubmitting = false;
      submitBtn.disabled = false;
      submitBtn.textContent = '确认添加';
    }
  }

  // PC-003: 表单草稿缓存
  const DRAFT_KEY = 'book_form_draft';
  const formFields = ['isbn', 'title', 'author', 'ar_value', 'age_min', 'age_max', 'word_count'];

  function saveDraft() {
    const form = document.getElementById('addForm');
    if (!form) return;
    const data = {};
    formFields.forEach(name => {
      const el = form.elements[name];
      if (el && el.value) data[name] = el.value;
    });
    if (Object.keys(data).length > 0) {
      localStorage.setItem(DRAFT_KEY, JSON.stringify(data));
    }
  }

  function restoreDraft() {
    const raw = localStorage.getItem(DRAFT_KEY);
    if (!raw) return;
    try {
      const data = JSON.parse(raw);
      if (Object.keys(data).length === 0) return;
      AdminConfirm.show('恢复草稿', '检测到未提交的草稿，是否恢复？', function() {
        const form = document.getElementById('addForm');
        formFields.forEach(name => {
          if (data[name] && form.elements[name]) {
            form.elements[name].value = data[name];
          }
        });
      });
    } catch (e) {
      clearDraft();
    }
  }

  function clearDraft() {
    localStorage.removeItem(DRAFT_KEY);
  }

  async function viewBook(id) {
    const book = booksData.find(b => String(b.id) === String(id));
    if (!book) {
      showToast('图书信息加载失败', 'error');
      return;
    }
    const html = `
      <div style="padding:20px">
        <h3 style="margin-bottom:16px">图书详情</h3>
        <table style="width:100%;border-collapse:collapse">
          <tr><td style="padding:8px;color:var(--muted);width:80px">书名</td><td>${escapeHtml(book.title || '-')}</td></tr>
          <tr><td style="padding:8px;color:var(--muted)">ISBN</td><td style="font-family:var(--font-mono)">${escapeHtml(book.isbn || '-')}</td></tr>
          <tr><td style="padding:8px;color:var(--muted)">作者</td><td>${escapeHtml(book.author || '-')}</td></tr>
          <tr><td style="padding:8px;color:var(--muted)">AR等级</td><td>${escapeHtml(book.ar_value !== undefined ? book.ar_value : '-')}</td></tr>
          <tr><td style="padding:8px;color:var(--muted)">适读年龄</td><td>${escapeHtml(book.age_min !== undefined ? book.age_min + '-' + (book.age_max || '') : '-')}</td></tr>
          <tr><td style="padding:8px;color:var(--muted)">库存</td><td>${escapeHtml((book.total_stock || 0) + ' / ' + (book.offline_available !== undefined ? book.offline_available : book.total_stock || 0))}</td></tr>
        </table>
      </div>`;
    AdminConfirm.show('图书详情', html);
  }

  async function togglePublish(bookId, title, totalStock, availableStock) {
    const borrowedCount = totalStock - availableStock;
    const message = `该书"${title}"当前有 ${totalStock} 本库存、${borrowedCount} 本借出，确认切换上下架状态？`;
    AdminConfirm.show('上下架操作', message, async function() {
      try {
        await api.put('/admin/api/books/' + bookId + '/toggle-publish');
        showToast('操作成功');
        loadBooks(currentKeyword, currentPage);
      } catch (err) {
        showToast(err.message || '操作失败', 'error');
      }
    });
  }

  async function deleteBook(bookId) {
    AdminConfirm.show('删除图书', '确定删除该图书？此操作不可撤销。', async function() {
      try {
        await api.del('/admin/api/books/' + bookId);
        showToast('已删除');
        loadBooks(currentKeyword, currentPage);
      } catch (err) {
        showToast(err.message || '删除失败', 'error');
      }
    });
  }

  // 批量操作
  function getSelectedBookIds() {
    return BatchSelect.getSelectedIds('#booksTable');
  }

  async function batchDelete() {
    const ids = getSelectedBookIds();
    if (!ids.length) return;
    AdminConfirm.show('批量删除', '确定删除选中的 ' + ids.length + ' 本图书？', async function() {
      try {
        for (const id of ids) {
          await api.del('/admin/api/books/' + id);
        }
        showToast('已删除 ' + ids.length + ' 本图书');
        loadBooks(currentKeyword, 1);
      } catch (err) {
        showToast(err.message || '批量删除失败', 'error');
      }
    });
  }

  function batchExport() {
    const ids = getSelectedBookIds();
    if (!ids.length) return;
    const headers = ['ID', '书名', '作者', 'ISBN', 'AR值', '词数'];
    const rows = [];
    document.querySelectorAll('#booksTable .row-check:checked').forEach(cb => {
      const row = cb.closest('tr');
      const cells = row.querySelectorAll('td');
      rows.push([
        cb.value,
        cells[3].textContent.trim(),
        cells[4].textContent.trim(),
        cells[1].textContent.trim(),
        cells[5].textContent.trim(),
        cells[6].textContent.trim(),
      ]);
    });
    exportCSV('books_export.csv', headers, rows);
    showToast('已导出 ' + rows.length + ' 条记录');
  }

  // ==================== File Upload (PC-010) ====================
  let uploadFile = null;
  const CHUNK_SIZE = 2 * 1024 * 1024;

  function openUploadModal() {
    document.getElementById('uploadModal').style.display = 'flex';
    document.getElementById('uploadFileInput').value = '';
    document.getElementById('uploadFileInfo').style.display = 'none';
    document.getElementById('uploadProgress').style.display = 'none';
    document.getElementById('uploadResult').innerHTML = '';
    document.getElementById('uploadBtn').disabled = true;
    uploadFile = null;
  }

  function closeUploadModal() {
    document.getElementById('uploadModal').style.display = 'none';
  }

  function handleFileSelect(input) {
    if (!input.files[0]) return;
    uploadFile = input.files[0];
    const ext = uploadFile.name.split('.').pop().toLowerCase();
    const allowed = ['jpg','jpeg','png','gif','mp3','m4a','wav','pdf'];
    if (allowed.indexOf(ext) === -1) {
      showToast('不支持的文件格式: .' + ext, 'error');
      uploadFile = null;
      return;
    }
    const sizeMB = (uploadFile.size / 1024 / 1024).toFixed(1);
    document.getElementById('uploadFileInfo').classList.remove('hidden');
    document.getElementById('uploadFileInfo').innerHTML =
      '<div style="padding:12px;background:var(--success-soft);border:1px solid var(--success);border-radius:var(--radius-sm);font-size:13px;">' +
      '&#x1F4C4; <strong>' + escapeHtml(uploadFile.name) + '</strong> (' + sizeMB + ' MB)</div>';
    document.getElementById('uploadBtn').disabled = false;
  }

  async function startUpload() {
    if (!uploadFile) return;
    const btn = document.getElementById('uploadBtn');
    btn.disabled = true;
    btn.textContent = '上传中...';
    document.getElementById('uploadProgress').classList.remove('hidden');
    document.getElementById('uploadFileName').textContent = uploadFile.name;

    if (uploadFile.size <= CHUNK_SIZE) {
      await uploadSmallFile();
    } else {
      await uploadLargeFile();
    }
  }

  async function uploadSmallFile() {
    try {
      const formData = new FormData();
      formData.append('file', uploadFile);
      const xhr = new XMLHttpRequest();
      xhr.open('POST', '/admin/api/upload?filename=' + encodeURIComponent(uploadFile.name));
      xhr.setRequestHeader('Authorization', 'Bearer ' + (localStorage.getItem('mw_admin_token') || ''));
      xhr.upload.onprogress = function(e) {
        if (e.lengthComputable) {
          const pct = Math.round(e.loaded / e.total * 100);
          document.getElementById('uploadProgressBar').style.width = pct + '%';
          document.getElementById('uploadPercent').textContent = pct + '%';
          document.getElementById('uploadStatus').textContent = formatBytes(e.loaded) + ' / ' + formatBytes(e.total);
        }
      };
      xhr.onload = function() {
        if (xhr.status === 200) {
          showUploadSuccess(JSON.parse(xhr.responseText));
        } else {
          showUploadError('上传失败: ' + xhr.statusText);
        }
      };
      xhr.onerror = function() { showUploadError('网络错误'); };
      xhr.send(formData);
    } catch (e) { showUploadError(e.message); }
  }

  async function uploadLargeFile() {
    const totalChunks = Math.ceil(uploadFile.size / CHUNK_SIZE);
    const uploadId = 'upload_' + Date.now() + '_' + Math.random().toString(36).substr(2, 8);
    document.getElementById('uploadStatus').textContent = '分片上传: 0/' + totalChunks;

    for (let i = 0; i < totalChunks; i++) {
      const start = i * CHUNK_SIZE;
      const end = Math.min(start + CHUNK_SIZE, uploadFile.size);
      const chunk = uploadFile.slice(start, end);
      const formData = new FormData();
      formData.append('file', chunk, uploadFile.name);

      try {
        const resp = await fetch('/admin/api/upload/chunk?upload_id=' + uploadId +
          '&chunk_index=' + i + '&total_chunks=' + totalChunks +
          '&filename=' + encodeURIComponent(uploadFile.name), {
          method: 'POST',
          headers: { 'Authorization': 'Bearer ' + (localStorage.getItem('mw_admin_token') || '') },
          body: formData,
        });
        if (!resp.ok) {
          const err = await resp.json();
          showUploadError('分片 ' + (i+1) + ' 上传失败: ' + (err.detail || '未知错误'));
          return;
        }
        const pct = Math.round((i + 1) / totalChunks * 100);
        document.getElementById('uploadProgressBar').style.width = pct + '%';
        document.getElementById('uploadPercent').textContent = pct + '%';
        document.getElementById('uploadStatus').textContent = '分片上传: ' + (i + 1) + '/' + totalChunks;
      } catch (e) {
        showUploadError('分片 ' + (i+1) + ' 网络错误，可重新上传');
        return;
      }
    }

    try {
      const completeResp = await fetch('/admin/api/upload/complete?upload_id=' + uploadId, {
        method: 'POST',
        headers: { 'Authorization': 'Bearer ' + (localStorage.getItem('mw_admin_token') || '') },
      });
      if (completeResp.ok) {
        showUploadSuccess(await completeResp.json());
      } else {
        const err = await completeResp.json();
        showUploadError('合并失败: ' + (err.detail || '未知错误'));
      }
    } catch (e) { showUploadError('合并失败: ' + e.message); }
  }

  function showUploadSuccess(result) {
    document.getElementById('uploadResult').innerHTML =
      '<div style="padding:12px;background:var(--success-soft);border:1px solid var(--success);border-radius:var(--radius-sm);">' +
      '上传成功！<br>文件: ' + escapeHtml(result.original_name) +
      '<br>大小: ' + formatBytes(result.size) + '</div>';
    document.getElementById('uploadBtn').textContent = '上传完成';
  }

  function showUploadError(msg) {
    document.getElementById('uploadResult').innerHTML =
      '<div style="padding:12px;background:var(--error-soft);border:1px solid var(--error);border-radius:var(--radius-sm);color:var(--error);">' + escapeHtml(msg) + '</div>';
    document.getElementById('uploadBtn').disabled = false;
    document.getElementById('uploadBtn').textContent = '重新上传';
  }

  function formatBytes(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / 1024 / 1024).toFixed(1) + ' MB';
  }

  // 暴露到全局供 HTML onclick 调用
  window.booksPage = {
    openAddModal,
    closeAddModal,
    submitBook,
    viewBook,
    togglePublish,
    deleteBook,
    batchDelete,
    batchExport,
    openUploadModal,
    closeUploadModal,
    handleFileSelect,
    startUpload,
    searchBooks,
    loadBooks,
    goToPage,
    changePageSize
  };
})();
