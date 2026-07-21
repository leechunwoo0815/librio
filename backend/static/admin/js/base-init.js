    // 认证检查（登录页跳过）
    if (!location.pathname.includes('/login')) {
      auth.requireAuth();
    }

    // 侧边栏滚动位置保持
    (function() {
      var sidebarNav = document.querySelector('.sidebar-nav');
      if (sidebarNav) {
        // 页面加载时恢复滚动位置
        var savedScroll = sessionStorage.getItem('sidebar_scroll');
        if (savedScroll) {
          sidebarNav.scrollTop = parseInt(savedScroll, 10);
        }
        // 页面卸载时保存滚动位置
        window.addEventListener('beforeunload', function() {
          sessionStorage.setItem('sidebar_scroll', sidebarNav.scrollTop);
        });
      }
    })();


    // 审核队列待审核数量角标
    (function() {
      var badge = document.getElementById('pendingSubCount');
      if (!badge) return;
      fetch('/admin/api/advancement/submissions?page=1&page_size=1&status=0', {
        headers: { 'Authorization': 'Bearer ' + (localStorage.getItem('mw_admin_token') || '') }
      })
      .then(function(r) { return r.json(); })
      .then(function(data) {
        var count = data && data.total;
        if (count && count > 0) {
          badge.textContent = count > 99 ? '99+' : count;
          badge.classList.remove('hidden');
        }
      })
      .catch(function() {});
    })();

    // PC-029: 骨架屏函数
    function showSkeleton(containerId, colCount) {
      var container = document.getElementById(containerId);
      if (!container) return;
      var cols = colCount || 6;
      var rows = 7;
      var html = '';
      for (var r = 0; r < rows; r++) {
        html += '<div class="skeleton-row">';
        for (var c = 0; c < cols; c++) {
          var cls = 'skeleton-cell';
          if (c === 0) cls += ' long';
          else if (c === cols - 1) cls += ' short';
          html += '<div class="' + cls + '"></div>';
        }
        html += '</div>';
      }
      container.innerHTML = html;
    }
    function hideSkeleton(containerId) {
      var container = document.getElementById(containerId);
      if (container) container.innerHTML = '';
    }

    // 通用 CSV 导出工具
    function exportCSV(filename, headers, rows) {
      var csv = [headers.join(',')].concat(
        rows.map(function(r) {
          return r.map(function(cell) {
            var s = String(cell == null ? '' : cell);
            return '"' + s.replace(/"/g, '""') + '"';
          }).join(',');
        })
      ).join('\n');
      var blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' });
      var link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    }

    // JS 字符串转义 — 用于 onclick 内嵌用户数据
    function jsEscape(str) {
      return (str == null ? '' : String(str)).replace(/\\/g, '\\\\').replace(/'/g, "\\'");
    }

    // 全局弹窗显隐 — 配合 modal-overlay + show/hide class
    function showModal(id) {
      var el = document.getElementById(id);
      if (el) el.classList.add('show');
    }
    function closeModal(id) {
      var el = document.getElementById(id);
      if (el) el.classList.remove('show');
    }

    // 委托处理 data-close-modal 点击关闭 + ESC 键关闭
    document.addEventListener('click', function(e) {
      var target = e.target.closest('[data-close-modal]');
      if (target) { closeModal(target.getAttribute('data-close-modal')); return; }
      var overlay = e.target.closest('.modal-overlay');
      if (overlay && overlay === e.target) { closeModal(overlay.id); }
    });
    document.addEventListener('keydown', function(e) {
      if (e.key === 'Escape') {
        var open = document.querySelector('.modal-overlay.show');
        if (open) closeModal(open.id);
      }
    });

    // 通用分页器渲染
    function renderPagination(containerId, total, page, pageSize, onPageChange, onPageSizeChange) {
      var totalPages = Math.ceil(total / pageSize);
      var el = document.getElementById(containerId);
      if (!el) return;
      var html = '<div class="flex-center gap-8">';
      html += '<span class="text-muted">共 ' + total + ' 条</span>';
      if (onPageSizeChange) {
        html += '<span class="text-xs text-muted">每页</span><select class="page-size-select" onchange="' + onPageSizeChange + '(this.value)">';
        var sizes = [15, 30, 50, 100];
        for (var si = 0; si < sizes.length; si++) {
          html += '<option value="' + sizes[si] + '"' + (sizes[si] === pageSize ? ' selected' : '') + '>' + sizes[si] + '</option>';
        }
        html += '</select><span class="text-xs text-muted">条</span>';
      }
      html += '</div>';
      if (totalPages > 1) {
        if (page > 1) html += '<button class="btn-outline btn-sm" onclick="' + onPageChange + '(' + (page-1) + ')">上一页</button>';
        var start = Math.max(1, page - 2);
        var end = Math.min(totalPages, page + 2);
        for (var i = start; i <= end; i++) {
          html += '<button class="' + (i===page?'btn-primary':'btn-outline') + ' btn-sm" onclick="' + onPageChange + '(' + i + ')"' + (i===page?' disabled':'') + '>' + i + '</button>';
        }
        if (page < totalPages) html += '<button class="btn-outline btn-sm" onclick="' + onPageChange + '(' + (page+1) + ')">下一页</button>';
      }
      el.innerHTML = html;
    }