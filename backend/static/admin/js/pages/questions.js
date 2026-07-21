(function() {
  'use strict';

let isSubmitting = false;
let selectedBookId = null;

function escapeHtml(str) {
  var div = document.createElement('div');
  div.textContent = str || '';
  return div.innerHTML;
}

function jsEscape(str) {
  return (str || '').replace(/\\/g, '\\\\').replace(/'/g, "\\'");
}

// Search books
document.getElementById('bookSearch').addEventListener('keydown', function(e) {
  if (e.key === 'Enter') searchBooks();
});
document.getElementById('bookSearch').addEventListener('input', function() {
  clearTimeout(this._debounce);
  this._debounce = setTimeout(searchBooks, 300);
});

async function searchBooks() {
  var keyword = document.getElementById('bookSearch').value.trim();
  if (!keyword) return;
  try {
    var data = await api.get('/admin/api/books?keyword=' + encodeURIComponent(keyword));
    var items = data.items || [];
    var el = document.getElementById('bookList');
    if (!items.length) {
      el.innerHTML = '<div class="p-20 text-center text-muted">未找到图书</div>';
      return;
    }
    el.innerHTML = items.map(function(b) {
      return '<div class="book-item" onclick="selectBook(' + b.id + ',\'' + jsEscape(b.title) + '\',' + (b.ar_value||0) + ')">' +
        '<div class="book-title">' + escapeHtml(b.title) + '</div>' +
        '<div class="book-meta">AR ' + (b.ar_value||'-') + '</div>' +
      '</div>';
    }).join('');
  } catch (e) {
    showToast('搜索失败: ' + e.message, 'error');
  }
}

async function selectBook(bookId, title, arLevel) {
  selectedBookId = bookId;
  document.getElementById('selectedBookTitle').textContent = title;
  document.getElementById('selectedBookMeta').textContent = 'AR ' + arLevel;
  try {
    var data = await api.get('/admin/api/advancement/questions/search?keyword=' + encodeURIComponent(title));
    var items = data.items || [];
    document.getElementById('selectedBookMeta').textContent = 'AR ' + arLevel + ' · 共 ' + items.length + ' 道题';
    renderQuestions(items);
  } catch (e) {
    showToast('加载题目失败', 'error');
  }
}

function renderQuestions(items) {
  var el = document.getElementById('questionsList');
  if (!items.length) {
    el.innerHTML = '<div class="text-center p-24 text-muted">暂无题目</div>';
    return;
  }
  el.innerHTML = items.map(function(q, i) {
    var options = [
      { key: 'A', val: q.option_a },
      { key: 'B', val: q.option_b },
      { key: 'C', val: q.option_c },
      { key: 'D', val: q.option_d },
    ].filter(function(o) { return o.val; });
    return '<div class="question-card">' +
      '<div class="question-card-header">' +
        '<div class="question-card-body">' +
          '<div class="question-text">' + (i+1) + '. ' + escapeHtml(q.question_text) + '</div>' +
          '<div class="question-options">' +
            options.map(function(o) {
              var cls = o.key === q.correct_answer ? 'option correct' : 'option';
              return '<div class="' + cls + '">' + o.key + '. ' + escapeHtml(o.val) + '</div>';
            }).join('') +
          '</div>' +
          '<div class="question-answer">✓ 正确答案：' + q.correct_answer + '</div>' +
        '</div>' +
        '<div class="question-actions">' +
          '<button class="btn btn-outline btn-sm" onclick=\'editQuestion(' + JSON.stringify(q).replace(/'/g, "&#39;") + ')\'>编辑</button>' +
          '<button class="btn btn-danger btn-sm" onclick="deleteQuestion(' + q.id + ')">删除</button>' +
        '</div>' +
      '</div>' +
    '</div>';
  }).join('');
}

// Book search in add modal
(function() {
  var searchEl = document.getElementById('fBookSearch');
  var resultsEl = document.getElementById('fBookSearchResults');
  var bookIdEl = document.getElementById('fBookId');
  if (!searchEl) return;

  var debounceTimer = null;
  searchEl.addEventListener('input', function() {
    clearTimeout(debounceTimer);
    var kw = searchEl.value.trim();
    if (!kw) { resultsEl.style.display = 'none'; return; }
    debounceTimer = setTimeout(async function() {
      try {
        var data = await api.get('/admin/api/books?keyword=' + encodeURIComponent(kw));
        var items = data.items || [];
        if (!items.length) {
          resultsEl.innerHTML = '<div class="book-search-noresult">未找到图书</div>';
          resultsEl.style.display = 'block';
          return;
        }
        resultsEl.innerHTML = items.map(function(b) {
          return '<div class="book-search-result-item" ' +
            'onclick="selectAddBook(' + b.id + ', \'' + jsEscape(b.title) + '\')">' +
            escapeHtml(b.title) + ' <span class="text-muted">ISBN: ' + escapeHtml(b.isbn || '-') + '</span>' +
          '</div>';
        }).join('');
        resultsEl.style.display = 'block';
      } catch (e) {
        resultsEl.style.display = 'none';
      }
    }, 250);
  });

  document.addEventListener('click', function(e) {
    if (!searchEl.contains(e.target) && !resultsEl.contains(e.target)) {
      resultsEl.style.display = 'none';
    }
  });
})();

window.selectAddBook = function(bookId, title) {
  document.getElementById('fBookId').value = bookId;
  document.getElementById('fBookSearch').value = title;
  document.getElementById('fBookSearchResults').style.display = 'none';
};

// Add question
document.getElementById('addQBtn').addEventListener('click', async function() {
  if (isSubmitting) return;
  isSubmitting = true;
  this.disabled = true;
  this.textContent = '保存中...';
  try {
    var bookId = document.getElementById('fBookId').value;
    if (!bookId) { showToast('请先选择关联图书', 'error'); return; }
    await api.post('/admin/api/advancement/questions', {
      book_id: parseInt(bookId, 10),
      question_text: document.getElementById('fQuestion').value,
      option_a: document.getElementById('fA').value,
      option_b: document.getElementById('fB').value,
      option_c: document.getElementById('fC').value || null,
      option_d: document.getElementById('fD').value || null,
      correct_answer: document.getElementById('fAnswer').value,
      difficulty: parseInt(document.getElementById('fDiff').value),
      explanation: document.getElementById('fExplanation').value || null,
    });
    showToast('题目添加成功');
    closeModal('addQModal');
    document.getElementById('fBookId').value = '';
    document.getElementById('fBookSearch').value = '';
    document.getElementById('fQuestion').value = '';
    document.getElementById('fA').value = '';
    document.getElementById('fB').value = '';
    document.getElementById('fC').value = '';
    document.getElementById('fD').value = '';
    document.getElementById('fAnswer').value = 'A';
    document.getElementById('fDiff').value = '1';
    document.getElementById('fExplanation').value = '';
  } catch (e) {
    showToast('添加失败: ' + e.message, 'error');
  } finally {
    isSubmitting = false;
    this.disabled = false;
    this.textContent = '保存';
  }
});

// Edit question
function editQuestion(q) {
  document.getElementById('editId').value = q.id;
  document.getElementById('editQuestion').value = q.question_text || '';
  document.getElementById('editA').value = q.option_a || '';
  document.getElementById('editB').value = q.option_b || '';
  document.getElementById('editC').value = q.option_c || '';
  document.getElementById('editD').value = q.option_d || '';
  document.getElementById('editAnswer').value = q.correct_answer || 'A';
  document.getElementById('editDiff').value = q.difficulty || 1;
  document.getElementById('editExplanation').value = q.explanation || '';
  showModal('editQModal');
}

document.getElementById('saveEditBtn').addEventListener('click', async function() {
  if (isSubmitting) return;
  isSubmitting = true;
  this.disabled = true;
  this.textContent = '保存中...';
  var id = document.getElementById('editId').value;
  try {
    await api.put('/admin/api/advancement/questions/' + id, {
      question_text: document.getElementById('editQuestion').value,
      option_a: document.getElementById('editA').value,
      option_b: document.getElementById('editB').value,
      option_c: document.getElementById('editC').value || null,
      option_d: document.getElementById('editD').value || null,
      correct_answer: document.getElementById('editAnswer').value,
      difficulty: parseInt(document.getElementById('editDiff').value),
      explanation: document.getElementById('editExplanation').value || null,
    });
    showToast('题目更新成功');
    closeModal('editQModal');
    if (selectedBookId) selectBook(selectedBookId, document.getElementById('selectedBookTitle').textContent, '');
  } catch (e) {
    showToast('更新失败: ' + e.message, 'error');
  } finally {
    isSubmitting = false;
    this.disabled = false;
    this.textContent = '保存';
  }
});

function showConfirmDialog(title, msg, onConfirm) {
  document.querySelector('#confirmDialog h2').textContent = title;
  document.getElementById('confirmMsg').textContent = msg;
  document.getElementById('confirmBtn').onclick = function() {
    closeModal('confirmDialog');
    onConfirm();
  };
  showModal('confirmDialog');
}

async function deleteQuestion(id) {
  showConfirmDialog('确认删除', '确认删除此题目？', async function() {
    try {
      await api.del('/admin/api/advancement/questions/' + id);
      showToast('删除成功');
      if (selectedBookId) selectBook(selectedBookId, document.getElementById('selectedBookTitle').textContent, '');
    } catch (e) {
      showToast('删除失败: ' + e.message, 'error');
    }
  });
}

  window.questionsPage = { isSubmitting, selectedBookId, searchBooks, selectBook, renderQuestions, editQuestion, showConfirmDialog, deleteQuestion, selectAddBook };
  for (var k in window.questionsPage) window[k] = window.questionsPage[k];

})();
