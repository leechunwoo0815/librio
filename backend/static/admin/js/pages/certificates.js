(function() {
  'use strict';

  var certsData = [];

  (function() {
    loadCertificates();
  })();

  async function loadCertificates() {
    try {
      var resp = await api.get('/admin/api/advancement/certificates');
      var list = resp.items || resp || [];
      certsData = list;
      renderStats(resp.stats || {});
      renderTable(list);
      populateFilters(list);
    } catch (err) {
      showToast(err.message || '加载证书数据失败', 'error');
      document.getElementById('certBody').innerHTML =
        '<tr><td colspan="7" class="text-center p-40 text-error">加载失败</td></tr>';
    }
  }

  function renderStats(stats) {
    document.getElementById('statTotal').textContent = stats.total != null ? stats.total : '--';
    document.getElementById('statMonth').textContent = stats.month_new != null ? stats.month_new : '--';
    var changeEl = document.getElementById('statMonthChange');
    if (stats.month_change != null) {
      changeEl.textContent = '较上月 ' + (stats.month_change >= 0 ? '+' : '') + stats.month_change;
      changeEl.className = 'stat-change ' + (stats.month_change >= 0 ? 'up' : 'down');
    }
    document.getElementById('statLevels').textContent = stats.level_count != null ? stats.level_count : '--';
    var rangeEl = document.getElementById('statLevelsRange');
    if (stats.level_min != null && stats.level_max != null) {
      rangeEl.textContent = 'Level ' + stats.level_min + ' - ' + stats.level_max;
    }
    document.getElementById('statRegenerate').textContent = stats.pending_regen != null ? stats.pending_regen : '--';
  }

  function formatPeriod(dt) {
    if (!dt) return '';
    var s = dt.slice(0, 7); // YYYY-MM
    return s;
  }

  function renderTable(list) {
    var body = document.getElementById('certBody');
    if (!list.length) {
      body.innerHTML = '<tr><td colspan="6" class="text-center p-40 text-muted">暂无证书记录</td></tr>';
      return;
    }
    body.innerHTML = list.map(function(cert, idx) {
      var levelCls = 'level-1';
      var period = formatPeriod(cert.create_time);
      return '<tr data-level="' + escapeAttr(cert.level_name || '') + '" data-period="' + escapeAttr(period) + '">' +
        '<td><strong>' + escapeHtml(cert.child_name || '-') + '</strong>' +
        (cert.child_id ? '<br><span class="text-muted text-sm">ID: ' + escapeHtml(cert.child_id) + '</span>' : '') +
        '</td>' +
        '<td><span class="level-badge ' + levelCls + '">Level ' + (cert.level_name || '-') + '</span></td>' +
        '<td><span class="cert-id">' + escapeHtml(cert.certificate_no || '-') + '</span></td>' +
        '<td>' + escapeHtml((cert.issued_at || '-').slice(0,10)) + '</td>' +
        '<td>' + escapeHtml((cert.create_time || '-').slice(0,10)) + '</td>' +
        '<td>' +
        '<button class="btn btn-primary btn-sm" onclick="openCert(' + idx + ')">查看</button>' +
        '<button class="btn btn-outline btn-sm ml-4" onclick="regenerate(\'' + escapeAttr(cert.child_name || '') + '\', ' + cert.id + ')">重新生成</button>' +
        '</td>' +
        '</tr>';
    }).join('');
  }

  function populateFilters(list) {
    // 级别过滤
    var levels = {};
    list.forEach(function(c) { if (c.level_name) levels[c.level_name] = true; });
    var levelSel = document.getElementById('levelFilter');
    // 保留第一个"全部级别"选项
    levelSel.innerHTML = '<option value="">全部级别</option>';
    Object.keys(levels).sort().forEach(function(lvl) {
      var opt = document.createElement('option');
      opt.value = lvl;
      opt.textContent = lvl;
      levelSel.appendChild(opt);
    });

    // 时间段过滤
    var periods = {};
    list.forEach(function(c) {
      var p = formatPeriod(c.create_time);
      if (p) periods[p] = true;
    });
    var periodSel = document.getElementById('periodFilter');
    periodSel.innerHTML = '<option value="">全部时间段</option>';
    Object.keys(periods).sort().reverse().forEach(function(p) {
      var opt = document.createElement('option');
      opt.value = p;
      opt.textContent = p.replace(/-(\d{2})$/, '年$1月');
      periodSel.appendChild(opt);
    });
  }

  function openCert(idx) {
    var c = certsData[idx];
    if (!c) return;
    // 后端返回字段：level_name / certificate_no / issued_at / create_time，无 book_count/word_count/prev_level
    var levelName = c.level_name || c.level || '-';
    var certNo = c.certificate_no || c.cert_number || '-';
    var issuedAt = c.issued_at || c.create_time || '-';
    var html = '<div class="cert-inner">';
    html += '<div class="cert-corner-bl"></div>';
    html += '<div class="cert-corner-tr"></div>';
    html += '<div class="cert-logo">&#128218;</div>';
    html += '<div class="cert-brand">DmkWords</div>';
    html += '<div class="cert-title">晋级证书</div>';
    html += '<div class="cert-subtitle">Certificate of Level Advancement</div>';
    html += '<div class="cert-name">' + escapeHtml(c.child_name || '-') + '</div>';
    html += '<div class="cert-desc">';
    html += '恭喜通过 Level ' + levelName + ' 的阅读晋级考核！';
    html += '特此证明该学员在 DmkWords 英语阅读计划中的优异表现。';
    html += '</div>';
    html += '<div class="cert-level">Level ' + levelName + '</div>';
    html += '<div class="cert-stats">';
    html += '<div class="cs"><div class="cs-val">' + (c.book_count || 0) + '</div><div class="cs-lbl">阅读本数</div></div>';
    html += '<div class="cs"><div class="cs-val">' + (c.word_count >= 1000 ? (c.word_count / 1000).toFixed(1) + 'K' : (c.word_count || 0)) + '</div><div class="cs-lbl">累计词数</div></div>';
    html += '<div class="cs"><div class="cs-val">Level ' + levelName + '</div><div class="cs-lbl">晋级至</div></div>';
    html += '</div>';
    html += '<div class="cert-seal"><div class="cert-seal-inner">&#127942;</div></div>';
    html += '<div class="cert-date">签发日期：' + escapeHtml(issuedAt.slice(0, 10)) + '</div>';
    html += '<div class="cert-number">' + escapeHtml(certNo) + '</div>';
    html += '</div>';
    document.getElementById('certContent').innerHTML = html;
    document.getElementById('certModal').classList.add('show');
  }

  function closeCert() {
    document.getElementById('certModal').classList.remove('show');
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

  function regenerate(name, id) {
    showConfirmDialog('重新生成证书', '确定为 ' + name + ' 重新生成证书？', function() {
      api.post('/admin/api/advancement/certificates/' + id + '/regenerate').then(function() {
        showToast('证书已重新生成');
        loadCertificates();
      }).catch(function(err) {
        showToast(err.message || '重新生成失败', 'error');
      });
    });
  }

  function filterTable() {
    var search = document.getElementById('searchInput').value.toLowerCase();
    var level = document.getElementById('levelFilter').value;
    var period = document.getElementById('periodFilter').value;
    var rows = document.querySelectorAll('#certBody tr');
    rows.forEach(function(row) {
      if (!row.dataset.level && !row.dataset.period) return;
      var name = (row.querySelector('td strong') || {}).textContent || '';
      var certId = (row.querySelector('.cert-id') || {}).textContent || '';
      var matchSearch = !search || name.toLowerCase().indexOf(search) >= 0 || certId.toLowerCase().indexOf(search) >= 0;
      var matchLevel = !level || row.dataset.level === level;
      var matchPeriod = !period || row.dataset.period === period;
      row.style.display = (matchSearch && matchLevel && matchPeriod) ? '' : 'none';
    });
  }

  function escapeHtml(str) {
    var div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }
  function escapeAttr(str) {
    return str.replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/'/g,'&#39;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }

  window.certificatesPage = { certsData, loadCertificates, renderStats, formatPeriod, renderTable, populateFilters, openCert, closeCert, showConfirmDialog, regenerate, filterTable, escapeAttr };
  for (var k in window.certificatesPage) window[k] = window.certificatesPage[k];

})();
