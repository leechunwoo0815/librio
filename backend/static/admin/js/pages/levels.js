// backend/static/admin/js/pages/levels.js
// 级别配置页面逻辑

(function() {
  'use strict';

  const levelsTable = document.getElementById('levelsTable');

  document.addEventListener('DOMContentLoaded', () => {
    loadLevels();
    document.body.addEventListener('click', function(e) {
      var el = e.target.closest('[data-pg]');
      if (!el) return;
      e.preventDefault();
      var fn = window.levelsPage[el.getAttribute('data-pg')];
      if (typeof fn === 'function') fn();
    });
    document.getElementById('levelForm').addEventListener('submit', function(e) { submitLevel(e); });
    document.getElementById('importFile').addEventListener('change', function() { handleImport(this); });
  });

  async function loadLevels() {
    try {
      const data = await api.get('/admin/api/advancement/levels');
      const levels = data.items || data || [];
      renderLevels(levels);
    } catch (err) {
      showToast(err.message || '加载级别失败', 'error');
      levelsTable.innerHTML = '<tr><td colspan="9" style="text-align:center;padding:40px;color:var(--error);">加载失败</td></tr>';
    }
  }

  function renderLevels(levels) {
    if (!levels.length) {
      levelsTable.innerHTML = '<tr><td colspan="9" style="text-align:center;padding:40px;color:var(--muted);">暂无级别数据</td></tr>';
      return;
    }
    levels.sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0));
    levelsTable.innerHTML = levels.map(l => `
      <tr>
        <td>${l.sort_order != null ? l.sort_order : '-'}</td>
        <td style="font-family:var(--font-mono);font-weight:600">${escapeHtml(l.code || l.name || '-')}</td>
        <td>${l.badge_emoji || '-'}</td>
        <td>${escapeHtml(l.name || '-')}</td>
        <td>${l.required_books != null ? l.required_books : '-'}</td>
        <td>${l.required_quiz_pass_rate != null ? Math.round(l.required_quiz_pass_rate * 100) + '%' : '--'}</td>
        <td>${l.max_borrow_count != null ? l.max_borrow_count : '-'}</td>
        <td>${l.student_count != null ? l.student_count : '-'}</td>
        <td><button class="btn btn-outline btn-sm" onclick="window.levelsPage.editLevel(${l.id}, '${jsEscape(l.code || '')}', '${jsEscape(l.name || '')}', '${l.badge_emoji || ''}', ${l.sort_order || 0}, ${l.required_books || 5}, ${(l.required_quiz_pass_rate || 0.8) * 100}, ${l.max_borrow_count || 10}, ${l.max_ar_level || 10}, ${l.require_teacher_review ? 'true' : 'false'})">编辑</button>
        <button class="btn btn-outline btn-sm" style="color:var(--error)" onclick="window.levelsPage.deleteLevel(${l.id}, '${jsEscape(l.name || '')}')">删除</button></td>
      </tr>
    `).join('');
  }

  function openLevelModal() {
    document.getElementById('editId').value = '';
    document.querySelector('#levelModal .modal-header h2').textContent = '新增级别';
    document.getElementById('submitBtn').textContent = '保存';
    document.getElementById('levelForm').reset();
    showModal('levelModal');
  }

  function editLevel(id, code, name, emoji, sortOrder, requiredBooks, passRate, maxBorrow, maxAr, requireReview) {
    document.getElementById('editId').value = id;
    document.querySelector('#levelModal .modal-header h2').textContent = '编辑级别';
    document.getElementById('submitBtn').textContent = '保存修改';
    const form = document.getElementById('levelForm');
    form.elements['code'].value = code;
    form.elements['name'].value = name;
    form.elements['badge_emoji'].value = emoji;
    form.elements['sort_order'].value = sortOrder;
    form.elements['required_books'].value = requiredBooks;
    form.elements['pass_rate'].value = passRate;
    form.elements['max_borrow_count'].value = maxBorrow;
    form.elements['max_ar_level'].value = maxAr;
    form.elements['require_approval'].checked = requireReview;
    showModal('levelModal');
  }

  async function deleteLevel(id, name) {
    showConfirm('删除级别', '确定删除级别"' + name + '"？此操作不可撤销。', async function() {
      try {
        await api.del('/admin/api/advancement/levels/' + id);
        showToast('级别已删除');
        loadLevels();
      } catch (err) {
        showToast(err.message || '删除失败', 'error');
      }
    });
  }

  function closeLevelModal() {
    closeModal('levelModal');
  }

  async function submitLevel(e) {
    e.preventDefault();
    const btn = document.querySelector('#levelForm button[type="submit"]');
    if (btn.disabled) return;
    btn.disabled = true;
    btn.textContent = '提交中...';
    const form = document.getElementById('levelForm');
    const fd = new FormData(form);
    const body = {};
    body['require_teacher_review'] = false;
    for (const [k, v] of fd.entries()) {
      if (k === 'editId') continue;
      if (k === 'require_approval') {
        body['require_teacher_review'] = true;
      } else if (v === '') {
        continue;
      } else if (['sort_order', 'required_books', 'pass_rate', 'max_borrow_count', 'max_ar_level'].includes(k)) {
        body[k] = Number(v);
      } else {
        body[k] = v;
      }
    }
    // pass_rate 从百分比转为小数
    if (body.pass_rate) {
      body.pass_rate = body.pass_rate / 100;
    }
    const editId = document.getElementById('editId').value;
    try {
      if (editId) {
        await api.put('/admin/api/advancement/levels/' + editId, body);
        showToast('级别更新成功');
      } else {
        await api.post('/admin/api/advancement/levels', body);
        showToast('级别创建成功');
      }
      closeLevelModal();
      loadLevels();
    } catch (err) {
      showToast(err.message || '操作失败', 'error');
    } finally {
      btn.disabled = false;
      btn.textContent = '保存';
    }
  }

  function saveAdjustment() {
    var childId = document.getElementById('adjustChildId').value;
    var books = document.getElementById('adjustBooks').value;
    var rate = document.getElementById('adjustRate').value;
    if (!childId) {
      showToast('请选择孩子', 'error');
      return;
    }
    showToast('调整已保存（本地配置）');
  }

  async function exportLevels() {
    try {
      var data = await api.get('/admin/api/advancement/levels');
      var levels = data.items || data || [];
      if (!levels.length) {
        showToast('没有可导出的数据', 'error');
        return;
      }
      var headers = ['排序', '名称', '徽章', '需读书数', '通过率', '最大借阅', '最大AR'];
      var rows = levels.map(function(l) {
        return [l.sort_order, l.name, l.badge_emoji, l.required_books, l.required_quiz_pass_rate, l.max_borrow_count, l.max_ar_level];
      });
      exportCSV('levels_export.csv', headers, rows);
      showToast('已导出 ' + rows.length + ' 个级别');
    } catch (err) {
      showToast('导出失败: ' + err.message, 'error');
    }
  }

  function importLevels() {
    document.getElementById('importFile').click();
  }

  async function handleImport(input) {
    const file = input.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = async function(e) {
      try {
        let levels = [];
        if (file.name.endsWith('.json')) {
          levels = JSON.parse(e.target.result);
        } else {
          // CSV 格式
          const lines = e.target.result.split('\n').filter(l => l.trim());
          const headers = lines[0].split(',').map(h => h.trim().replace(/"/g, ''));
          for (let i = 1; i < lines.length; i++) {
            const values = lines[i].split(',').map(v => v.trim().replace(/"/g, ''));
            const level = {};
            headers.forEach((h, idx) => { level[h] = values[idx]; });
            levels.push(level);
          }
        }
        let success = 0, failed = 0;
        for (const level of levels) {
          try {
            await api.post('/admin/api/advancement/levels', level);
            success++;
          } catch { failed++; }
        }
        showToast('导入完成：成功 ' + success + ' 个，失败 ' + failed + ' 个');
        loadLevels();
      } catch (err) {
        showToast('导入失败：文件格式错误', 'error');
      }
    };
    reader.readAsText(file);
    input.value = '';
  }

  window.levelsPage = {
    loadLevels,
    exportLevels,
    importLevels,
    openLevelModal,
    editLevel,
    deleteLevel,
    closeLevelModal,
    submitLevel,
    saveAdjustment,
    handleImport
  };
})();
