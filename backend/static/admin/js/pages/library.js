(function() {
  'use strict';

var currentPage = 1;
var pageSize = 20;
var coverColors = ['bc1', 'bc2', 'bc3', 'bc4', 'bc5'];

function toggleModal() {
  document.getElementById('bookModal').classList.toggle('show');
}

function getContentStatusClass(configured) {
  if (configured === 'configured') return 'content-configured';
  if (configured === 'pending') return 'content-pending';
  if (configured === 'partial') return 'content-partial';
  return 'content-unconfigured';
}

function getContentStatusLabel(configured) {
  if (configured === 'configured') return '已配置';
  if (configured === 'pending') return '待配置';
  if (configured === 'partial') return '部分配置';
  return '未配置';
}

function getDifficultyLabel(ar) {
  if (!ar) return '-';
  var val = parseFloat(ar);
  if (val < 2) return '入门';
  if (val < 4) return '初级';
  if (val < 6) return '中级';
  return '高级';
}

function getInitials(title) {
  if (!title) return '??';
  var words = title.split(/\s+/);
  if (words.length >= 2) return (words[0][0] + words[1][0]).toUpperCase();
  return title.substring(0, 2).toUpperCase();
}

async function loadBooks() {
  var keyword = document.getElementById('searchInput').value.trim();
  var tbody = document.getElementById('bookBody');
  try {
    var params = '?page=' + currentPage + '&page_size=' + pageSize;
    if (keyword) params += '&keyword=' + encodeURIComponent(keyword);
    var r = await api.get('/admin/api/books' + params);
    var items = r.items || r || [];
    var total = r.total || items.length;
    document.getElementById('paginationInfo').textContent = '共 ' + total + ' 册 · 显示 ' + Math.min((currentPage - 1) * pageSize + 1, total) + '-' + Math.min(currentPage * pageSize, total);

    if (items.length === 0) {
      tbody.innerHTML = '<tr><td colspan="12" class="text-center text-muted p-32">暂无图书</td></tr>';
      return;
    }

    tbody.innerHTML = items.map(function(b, i) {
      var colorCls = coverColors[i % coverColors.length];
      var hasAudio = b.audio_url ? '✓' : '—';
      var contentStatus = (b.total_stock > 0 || b.has_audio) ? 'configured' : 'unconfigured';
      return '<tr>' +
        '<td><div class="book-cell"><div class="book-cover ' + colorCls + '">' + escapeHtml(getInitials(b.title)) + '</div><div><div class="book-title-text">' + escapeHtml(b.title || '') + '</div><div class="book-author">' + escapeHtml(b.author || '') + '</div></div></div></td>' +
        '<td class="font-mono text-sm">' + escapeHtml(b.isbn || '-') + '</td>' +
        '<td><span class="ar-badge">' + (b.ar_value || '-') + '</span></td>' +
        '<td>' + (b.word_count ? b.word_count.toLocaleString() : '-') + '</td>' +
        '<td>' + (b.total_pages ? Math.round(b.total_pages * 2) + '分钟' : '-') + '</td>' +
        '<td>' + hasAudio + '</td>' +
        '<td>' + escapeHtml(b.theme || '-') + '</td>' +
        '<td>' + getDifficultyLabel(b.ar_value) + '</td>' +
        '<td>' + (b.total_stock || 0) + '</td>' +
        '<td><span class="' + getContentStatusClass(contentStatus) + '">' + getContentStatusLabel(contentStatus) + '</span></td>' +
        '<td>' + (b.available_stock || 0) + '</td>' +
        '<td><div class="action-btns"><button class="action-btn" onclick="editBook(' + b.id + ')">编辑</button><button class="action-btn" onclick="viewBook(' + b.id + ')">详情</button></div></td>' +
      '</tr>';
    }).join('');

    // pagination
    var totalPages = Math.ceil(total / pageSize);
    var btnHtml = '';
    for (var p = 1; p <= Math.min(totalPages, 5); p++) {
      btnHtml += '<button class="page-btn ' + (p === currentPage ? 'active' : '') + '" onclick="goPage(' + p + ')">' + p + '</button>';
    }
    if (totalPages > 5) btnHtml += '<button class="page-btn">...</button><button class="page-btn" onclick="goPage(' + totalPages + ')">' + totalPages + '</button>';
    document.getElementById('paginationBtns').innerHTML = btnHtml;
  } catch (e) {
    tbody.innerHTML = '<tr><td colspan="12" class="text-center text-error p-32">加载失败: ' + escapeHtml(e.message) + '</td></tr>';
  }
}

function goPage(p) { currentPage = p; loadBooks(); }
function editBook(id) { showToast('编辑图书 #' + id, 'error'); }
function viewBook(id) { showToast('图书详情 #' + id, 'error'); }

async function addBook() {
  var title = document.getElementById('titleInput').value.trim();
  if (!title) { showToast('请输入书名', 'error'); return; }
  var ageMin = parseInt(document.getElementById('ageMinInput').value);
  var ageMax = parseInt(document.getElementById('ageMaxInput').value);
  if (isNaN(ageMin) || isNaN(ageMax) || ageMin < 3 || ageMax > 15 || ageMin > ageMax) {
    showToast('请填写正确的适读年龄（3-15岁）', 'error'); return;
  }
  try {
    await api.post('/admin/api/books', {
      title: title,
      author: document.getElementById('authorInput').value.trim(),
      isbn: document.getElementById('isbnInput').value.trim(),
      ar_value: parseFloat(document.getElementById('arInput').value) || null,
      total_stock: parseInt(document.getElementById('stockInput').value) || 0,
      age_min: ageMin,
      age_max: ageMax
    });
    toggleModal();
    showToast('图书添加成功');
    loadBooks();
  } catch (e) {
    showToast('添加失败: ' + e.message, 'error');
  }
}

loadBooks();

  window.libraryPage = { currentPage, pageSize, coverColors, toggleModal, getContentStatusClass, getContentStatusLabel, getDifficultyLabel, getInitials, loadBooks, goPage, editBook, viewBook, addBook };
  for (var k in window.libraryPage) window[k] = window.libraryPage[k];
})();
