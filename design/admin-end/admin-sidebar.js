/**
 * DmkWords Admin — 全局侧边栏组件
 * 版本: 1.0.0
 *
 * 使用方式:
 *   1. 在 <head> 中引入:  <link rel="stylesheet" href="admin-sidebar.css">
 *   2. 在 <body> 顶部放: <div id="sidebar-root"></div>
 *   3. 在 </body> 前放:  <script src="admin-sidebar.js"></script>
 *
 * 新增/修改导航项: 只需修改下方 NAV_CONFIG 即可，所有页面自动更新。
 */
(function () {
  'use strict';

  // ============================================================
  //  导航配置 — 唯一需要维护的地方
  //  新增页面时，只需在此处添加一条记录
  // ============================================================
  var NAV_CONFIG = [
    {
      group: '运营',
      items: [
        { href: 'admin-dashboard.html',    label: '数据概览', icon: '<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>' },
        { href: 'admin-users.html',         label: '用户管理', icon: '<path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75"/>' },
        { href: 'admin-orders.html',        label: '订单管理', icon: '<path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><path d="M14 2v6h6"/><path d="M16 13H8"/><path d="M16 17H8"/><path d="M10 9H8"/>' },
        { href: 'admin-submissions.html',   label: '审核队列', icon: '<path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"/>' },
        { href: 'admin-activities.html',    label: '活动管理', icon: '<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>' }
      ]
    },
    {
      group: '场馆',
      items: [
        { href: 'admin-venues.html',        label: '场馆管理', icon: '<path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/>' },
        { href: 'admin-teachers.html',      label: '老师管理', icon: '<path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/>' }
      ]
    },
    {
      group: '内容',
      items: [
        { href: 'admin-library.html',       label: '图书管理', icon: '<path d="M4 19.5A2.5 2.5 0 016.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z"/>' },
        { href: 'admin-content.html',       label: '图书内容', icon: '<path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><path d="M14 2v6h6"/><path d="M16 13H8"/><path d="M16 17H8"/><path d="M10 9H8"/>' },
        { href: 'admin-audio.html',         label: '音频管理', icon: '<polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M19.07 4.93a10 10 0 010 14.14M15.54 8.46a5 5 0 010 7.07"/>' },
        { href: 'admin-dictionary.html',    label: '词库管理', icon: '<path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/>' },
        { href: 'admin-questions.html',     label: '题库管理', icon: '<circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 015.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/>' },
        { href: 'admin-quiz.html',          label: '出卷管理', icon: '<path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><path d="M14 2v6h6"/><path d="M16 13H8"/><path d="M16 17H8"/><path d="M10 9H8"/>' },
        { href: 'admin-reports.html',       label: '观察期报告', icon: '<path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><path d="M14 2v6h6"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>' }
      ]
    },
    {
      group: '数据',
      items: [
        { href: 'admin-reading-data.html',  label: '阅读数据', icon: '<path d="M18 20V10M12 20V4M6 20v-6"/>' },
        { href: 'admin-assessments.html',   label: '评估管理', icon: '<path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"/>' },
        { href: 'admin-booklist.html',      label: '推荐书单', icon: '<line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/>' }
      ]
    },
    {
      group: '系统',
      items: [
        { href: 'admin-levels.html',        label: '级别配置', icon: '<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>' },
        { href: 'admin-achievements.html',  label: '成就管理', icon: '<circle cx="12" cy="8" r="7"/><polyline points="8.21 13.89 7 23 12 20 17 23 15.79 13.88"/>' },
        { href: 'admin-profile.html',       label: '个人名片', icon: '<rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/>' },
        { href: 'admin-certificates.html',  label: '证书管理', icon: '<circle cx="12" cy="8" r="7"/><polyline points="8.21 13.89 7 23 12 20 17 23 15.79 13.88"/>' },
        { href: 'admin-settings.html',      label: '系统设置', icon: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/>' }
      ]
    }
  ];

  // ============================================================
  //  渲染逻辑 — 一般不需要修改
  // ============================================================

  /**
   * 生成 SVG 图标 HTML
   */
  function makeIcon(paths) {
    return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">'
      + paths + '</svg>';
  }

  /**
   * 获取当前页面文件名（去除 hash 和 query）
   */
  function getCurrentPage() {
    var path = location.pathname;
    var name = path.split('/').pop().split('?')[0].split('#')[0];
    return name || 'admin-dashboard.html';
  }

  /**
   * 从 URL 读取侧边栏滚动位置
   */
  function getSavedScroll() {
    var m = location.search.match(/_ss=(\d+)/);
    return m ? parseInt(m[1], 10) : 0;
  }

  /**
   * 根据 NAV_CONFIG 生成完整侧边栏 HTML
   */
  function renderSidebar() {
    var current = getCurrentPage();
    var scrollPos = getSavedScroll();
    var html = '';

    html += '<aside class="sidebar">';
    html += '<div class="sidebar-logo">';
    html += '<div class="logo-icon">M</div>';
    html += '<div><div class="logo-text">DmkWords</div>';
    html += '<div class="logo-sub">管理后台</div></div>';
    html += '</div>';
    html += '<nav class="sidebar-nav" data-scroll="' + scrollPos + '">';

    for (var g = 0; g < NAV_CONFIG.length; g++) {
      var section = NAV_CONFIG[g];
      html += '<div class="nav-group-label">' + section.group + '</div>';

      for (var i = 0; i < section.items.length; i++) {
        var item = section.items[i];
        var isActive = item.href === current;
        html += '<a class="nav-link' + (isActive ? ' active' : '') + '"'
             + ' href="' + item.href + '">'
             + makeIcon(item.icon)
             + item.label
             + '</a>';
      }
    }

    html += '</nav></aside>';
    return html;
  }

  /**
   * 注入侧边栏 DOM，恢复滚动位置，并拦截链接点击
   */
  function mount() {
    var root = document.getElementById('sidebar-root');
    if (!root) {
      console.warn('[admin-sidebar] 未找到 #sidebar-root 容器，侧边栏未渲染。');
      return;
    }
    root.outerHTML = renderSidebar();

    var nav = document.querySelector('.sidebar-nav');
    if (!nav) return;

    // 恢复滚动位置
    var saved = parseInt(nav.getAttribute('data-scroll') || '0', 10);
    if (saved > 0) {
      nav.scrollTop = saved;
      // 保险：下一帧再设一次（等布局完成）
      requestAnimationFrame(function () { nav.scrollTop = saved; });
    }

    // 拦截所有导航链接：点击时把当前滚动位置写进目标 URL
    nav.addEventListener('click', function (e) {
      var link = e.target.closest('.nav-link');
      if (!link) return;
      e.preventDefault();
      var href = link.getAttribute('href');
      // 清除旧的 _ss 参数，追加当前滚动位置
      href = href.split('?')[0].split('#')[0];
      href += '?_ss=' + nav.scrollTop;
      location.href = href;
    });
  }

  // DOM ready 后执行
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', mount);
  } else {
    mount();
  }

  // 暴露配置，方便调试 / 外部动态追加
  window.AdminSidebar = {
    config: NAV_CONFIG,
    render: renderSidebar,
    mount: mount
  };

})();
