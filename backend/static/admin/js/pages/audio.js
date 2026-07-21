(function() {
  'use strict';

  var audioData = [];

  (function() {
    loadAudios();
  })();

  async function loadAudios() {
    try {
      var resp = await api.get('/admin/api/audio/list');
      var list = resp.items || resp || [];
      audioData = list;
      renderStats(resp.stats || {});
      renderTable(list);
      populateReaders(list);
    } catch (err) {
      showToast(err.message || '加载音频数据失败', 'error');
      document.getElementById('audioBody').innerHTML =
        '<tr><td colspan="7" class="text-center p-40 text-error">加载失败</td></tr>';
    }
  }

  function renderStats(stats) {
    document.getElementById('statTotal').textContent = stats.total != null ? stats.total : '--';
    document.getElementById('statBooks').textContent = stats.book_count != null ? stats.book_count : '--';
    document.getElementById('statDuration').textContent = stats.total_duration || '--';
  }

  function renderTable(list) {
    var body = document.getElementById('audioBody');
    if (!list.length) {
      body.innerHTML = '<tr><td colspan="7" class="text-center p-40 text-muted">暂无音频文件</td></tr>';
      return;
    }
    body.innerHTML = list.map(function(item) {
      var statusCls = item.status === 'linked' ? 'tag-done' : 'tag-pending';
      var statusText = item.status === 'linked' ? '已关联' : '待关联';
      var actions = '<button class="action-sm" onclick="playAudio(\'' + escapeAttr(item.file_url || '') + '\',\'' + escapeAttr(item.filename || '') + '\')">播放</button>';
      actions += '<button class="action-sm" onclick="deleteAudio(' + item.id + ')">删除</button>';
      return '<tr>' +
        '<td>' + escapeHtml(item.filename || '-') + '</td>' +
        '<td>' + escapeHtml(item.book_title || '-') + '</td>' +
        '<td>' + escapeHtml(item.page_label || '全文') + '</td>' +
        '<td>' + escapeHtml(item.duration || '-') + '</td>' +
        '<td>' + escapeHtml(item.reader || '-') + '</td>' +
        '<td><span class="tag ' + statusCls + '">' + statusText + '</span></td>' +
        '<td>' + actions + '</td>' +
        '</tr>';
    }).join('');
  }

  function populateReaders(list) {
    var readers = {};
    list.forEach(function(i) { if (i.reader) readers[i.reader] = true; });
    var sel = document.getElementById('readerFilter');
    sel.innerHTML = '<option value="">全部朗读者</option>';
    Object.keys(readers).sort().forEach(function(r) {
      var opt = document.createElement('option');
      opt.value = r; opt.textContent = r;
      sel.appendChild(opt);
    });
  }

  function filterTable() {
    var search = document.getElementById('searchInput').value.toLowerCase();
    var reader = document.getElementById('readerFilter').value;
    var rows = document.querySelectorAll('#audioBody tr');
    rows.forEach(function(row) {
      if (row.children.length < 7) return;
      var filename = row.children[0].textContent.toLowerCase();
      var rowReader = row.children[4].textContent.trim();
      var matchSearch = !search || filename.indexOf(search) >= 0;
      var matchReader = !reader || rowReader === reader;
      row.style.display = (matchSearch && matchReader) ? '' : 'none';
    });
  }

  function showConfirmDialog(title, msg, onConfirm) {
    document.querySelector('#confirmDialog h2').textContent = title;
    document.getElementById('confirmMsg').textContent = msg;
    document.getElementById('confirmBtn').onclick = function() {
      closeModal('confirmDialog');
      onConfirm();
    };
    showModal('confirmDialog');
  }

  function deleteAudio(id) {
    showConfirmDialog('删除音频', '确定删除该音频？', function() {
      api.del('/admin/api/audio/' + id).then(function() {
        showToast('删除成功');
        loadAudios();
      }).catch(function(e) {
        showToast('删除失败: ' + e.message, 'error');
      });
    });
  }

  function playAudio(url, name) {
    if (!url) { showToast('音频地址无效', 'error'); return; }
    var bar = document.getElementById('audioPlayerBar');
    bar.style.display = 'flex';
    document.getElementById('playerFileName').textContent = name;
    var audio = document.getElementById('audioPreview');
    audio.src = url;
    audio.play();
  }

  function closePlayer() {
    var audio = document.getElementById('audioPreview');
    audio.pause();
    audio.src = '';
    document.getElementById('audioPlayerBar').style.display = 'none';
  }

  function escapeHtml(str) {
    var div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }
  function escapeAttr(str) {
    return str.replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/'/g,'&#39;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }

  window.audioPage = { audioData, loadAudios, renderStats, renderTable, populateReaders, filterTable, showConfirmDialog, deleteAudio, playAudio, closePlayer, escapeAttr };
  for (var k in window.audioPage) window[k] = window.audioPage[k];

})();
