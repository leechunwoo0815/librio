(function() {
  'use strict';

var currentPage = 1;
var pageSize = 15;

function safeEl(id) { return document.getElementById(id); }
function setText(id, val) { var el = safeEl(id); if (el) el.textContent = val; }
function setVal(id, val) { var el = safeEl(id); if (el) el.value = val; }
function setHtml(id, val) { var el = safeEl(id); if (el) el.innerHTML = val; }
function showModal(id) { var el = safeEl(id); if (el) el.classList.add('show'); }
function hideModal(id) { var el = safeEl(id); if (el) el.classList.remove('show'); }
function setOnClick(id, fn) { var el = safeEl(id); if (el) el.onclick = fn; }

function getTagClass(level) {
  if (!level) return 'tag-ar2';
  var val = parseFloat(level);
  if (val < 2) return 'tag-ar1';
  if (val < 4) return 'tag-ar2';
  if (val < 6) return 'tag-ar3';
  return 'tag-ar4';
}

function getTagLabel(level) {
  if (!level) return 'AR ?';
  var val = parseFloat(level);
  if (val < 2) return 'AR 0-2';
  if (val < 4) return 'AR 2-4';
  if (val < 6) return 'AR 4-6';
  return 'AR 6+';
}

async function loadWords() {
  var keywordEl = safeEl('searchInput');
  var levelEl = safeEl('levelFilter');
  var keyword = keywordEl ? keywordEl.value.trim() : '';
  var level = levelEl ? levelEl.value : '';
  var tbody = safeEl('wordBody'); if (!tbody) return;
  try {
    var params = '?page=' + currentPage + '&page_size=' + pageSize;
    if (keyword) params += '&keyword=' + encodeURIComponent(keyword);
    if (level) params += '&level=' + encodeURIComponent(level);
    var r = await api.get('/admin/api/dictionary/search' + params);
    var items = r.items || r || [];
    setText('totalCount', '共 ' + (r.total || items.length) + ' 个词条');
    if (items.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted p-24">暂无词条</td></tr>';
      return;
    }
    tbody.innerHTML = items.map(function(w) {
      return '<tr>' +
        '<td class="fw-600">' + escapeHtml(w.word) + '</td>' +
        '<td class="font-mono text-sm">' + escapeHtml(w.phonetic || '-') + '</td>' +
        '<td>' + escapeHtml(w.cn_definition || '-') + '</td>' +
        '<td>' + escapeHtml(w.pos || '-') + '</td>' +
        '<td><span class="tag ' + getTagClass(w.ar_level) + '">' + getTagLabel(w.ar_level) + '</span></td>' +
        '<td>' +
          '<button class="action-sm" onclick="editWord(' + w.id + ', \'' + jsEscape(w.word) + '\', \'' + jsEscape(w.phonetic || '') + '\', \'' + jsEscape(w.cn_definition || '') + '\', \'' + jsEscape(w.pos || '') + '\', ' + (w.ar_level || 0) + ')">编辑</button> ' +
          '<button class="action-sm" onclick="deleteWord(' + w.id + ')">删除</button>' +
        '</td>' +
      '</tr>';
    }).join('');
    var total = r.total || items.length;
    setText('paginationInfo', Math.min((currentPage - 1) * pageSize + 1, total) + '-' + Math.min(currentPage * pageSize, total) + ' / ' + total);
    pageUi(total, pageSize);
  } catch (e) {
    tbody.innerHTML = '<tr><td colspan="6" class="text-center text-error p-24">加载失败: ' + escapeHtml(e.message) + '</td></tr>';
    setHtml('paginationBtns', '');
  }
}

function pageUi(total, pageSize) {
  var pages = Math.ceil(total / pageSize) || 1;
  var html = '<div class="flex-center gap-8"><span class="text-muted">共 ' + total + ' 条</span><span class="text-xs text-muted">每页</span><select class="page-size-select" onchange="changePageSize(this.value)"><option value="15"'+(pageSize===15?' selected':'')+'>15</option><option value="30"'+(pageSize===30?' selected':'')+'>30</option><option value="50"'+(pageSize===50?' selected':'')+'>50</option><option value="100"'+(pageSize===100?' selected':'')+'>100</option></select><span class="text-xs text-muted">条</span></div>';
  html += '<button class="action-sm" ' + (currentPage <= 1 ? 'disabled' : 'onclick="goPage(1)"') + '>首页</button>';
  html += '<button class="action-sm" ' + (currentPage <= 1 ? 'disabled' : 'onclick="goPage(' + (currentPage - 1) + ')"') + '>上一页</button>';
  var start = Math.max(1, currentPage - 2);
  var end = Math.min(pages, currentPage + 2);
  for (var p = start; p <= end; p++) {
    html += '<button class="action-sm" ' + (p === currentPage ? 'disabled class="fw-600"' : 'onclick="goPage(' + p + ')"') + '>' + p + '</button>';
  }
  html += '<button class="action-sm" ' + (currentPage >= pages ? 'disabled' : 'onclick="goPage(' + (currentPage + 1) + ')"') + '>下一页</button>';
  html += '<button class="action-sm" ' + (currentPage >= pages ? 'disabled' : 'onclick="goPage(' + pages + ')"') + '>末页</button>';
  setHtml('paginationBtns', html);
}

function goPage(p) {
  currentPage = p;
  loadWords();
}

function changePageSize(newSize) {
  pageSize = parseInt(newSize);
  goPage(1);
}

  function showConfirmDialog(title, msg, onConfirm) {
    var titleEl = document.querySelector('#confirmDialog h2'); if (titleEl) titleEl.textContent = title;
    setText('confirmMsg', msg);
    setOnClick('confirmBtn', function() {
      closeModal('confirmDialog');
      onConfirm();
    };
    showModal('confirmDialog');
  }

  function deleteWord(id) {
    showConfirmDialog('删除单词', '确定删除该单词？', function() {
      api.del('/admin/api/dictionary/' + id).then(function() {
        showToast('删除成功');
        loadWords();
      }).catch(function(e) {
        showToast('删除失败: ' + e.message, 'error');
      });
    });
  }

function openAddModal() {
  setVal('editId', '');
  setText('modalTitle', '添加单词');
  setText('submitBtn', '保存');
  var wf = safeEl('wordForm'); if (wf) wf.reset();
  showModal('wordModal');
}

function editWord(id, word, phonetic, cnDef, pos, arLevel) {
  setVal('editId', id);
  setText('modalTitle', '编辑单词');
  setText('submitBtn', '保存修改');
  var form = safeEl('wordForm');
  if (form) {
    form.elements['word'].value = word;
    form.elements['phonetic'].value = phonetic;
    form.elements['cn_definition'].value = cnDef;
    form.elements['pos'].value = pos;
    form.elements['ar_level'].value = arLevel || '';
  }
  showModal('wordModal');
}

function closeWordModal() {
  hideModal('wordModal');
}

async function submitWord(e) {
  e.preventDefault();
  var form = safeEl('wordForm');
  var fd = new FormData(form);
  var body = {};
  for (var [k, v] of fd.entries()) {
    if (k === 'editId') continue;
    if (v === '') continue;
    if (k === 'ar_level') {
      body[k] = Number(v);
    } else {
      body[k] = v;
    }
  }
  var editIdEl = safeEl('editId');
  var editId = editIdEl ? editIdEl.value : '';
  try {
    if (editId) {
      await api.put('/admin/api/dictionary/' + editId, body);
      showToast('单词更新成功');
    } else {
      await api.post('/admin/api/dictionary/', body);
      showToast('单词添加成功');
    }
    closeWordModal();
    loadWords();
  } catch (e) {
    showToast('操作失败: ' + e.message, 'error');
  }
}

loadWords();

  window.dictionaryPage = { currentPage, pageSize, safeEl, setText, setVal, setHtml, hideModal, setOnClick, getTagClass, getTagLabel, loadWords, pageUi, goPage, changePageSize, showConfirmDialog, deleteWord, openAddModal, editWord, closeWordModal, submitWord };
  for (var k in window.dictionaryPage) window[k] = window.dictionaryPage[k];

})();
