(function() {
  var typeNames = {1:'系统通知', 2:'活动通知', 3:'借阅通知', 4:'老师消息', 5:'阅读提醒'};
  var priorityNames = {0:'低', 1:'中', 2:'高'};
  var currentPage = 1;
  var pageSize = 20;

  var groupNameMap = {'trial':'体验课', 'observation':'观察期', 'member':'正式会员'};

  window.toggleTargetUser = function() {
    var sel = document.getElementById('msgTarget').value;
    var userInp = document.getElementById('msgTargetUserId');
    var teacherInp = document.getElementById('msgTargetTeacherId');
    var groupRow = document.getElementById('roleGroupRow');
    userInp.style.display = sel === 'user' ? 'block' : 'none';
    teacherInp.style.display = sel === 'teacher_single' ? 'block' : 'none';
    userInp.required = sel === 'user';
    teacherInp.required = sel === 'teacher_single';
    groupRow.style.display = sel === 'all' ? 'flex' : 'none';
    if (sel !== 'user') userInp.value = '';
    if (sel !== 'teacher_single') teacherInp.value = '';
  };

  window.sendMessage = function(e) {
    e.preventDefault();
    var title = document.getElementById('msgTitle').value.trim();
    var content = document.getElementById('msgContent').value.trim();
    var msgType = parseInt(document.getElementById('msgType').value);
    var priority = parseInt(document.getElementById('msgPriority').value);
    var target = document.getElementById('msgTarget').value;
    var targetUserId = document.getElementById('msgTargetUserId').value;
    var targetTeacherId = document.getElementById('msgTargetTeacherId').value;

    if (!title || !content) { showToast('请填写标题和内容', 'error'); return false; }
    if (target === 'user' && !targetUserId) { showToast('请输入用户ID', 'error'); return false; }
    if (target === 'teacher_single' && !targetTeacherId) { showToast('请输入老师ID', 'error'); return false; }

    // 前端选项映射到后端 target 枚举
    var apiTarget = target === 'teacher_single' ? 'teacher' : target;

    var btn = document.getElementById('btnSend');
    btn.disabled = true;
    btn.textContent = '发送中...';

    var body = {
      title: title,
      content: content,
      msg_type: msgType,
      priority: priority,
      target: apiTarget,
    };
    if (target === 'user') body.target_user_id = parseInt(targetUserId);
    if (target === 'teacher_single') body.target_teacher_id = parseInt(targetTeacherId);
    if (target === 'all') {
      var groups = [];
      document.querySelectorAll('.role-group-cb:checked').forEach(function(cb) { groups.push(cb.value); });
      if (groups.length > 0) body.target_role_groups = groups;
    }

    api.post('/admin/api/messages/send', body).then(function(data) {
      btn.disabled = false;
      btn.textContent = '发送';
      if (data.success) {
        showToast('发送成功，共 ' + data.sent_count + ' 条', 'success');
        document.getElementById('msgTitle').value = '';
        document.getElementById('msgContent').value = '';
        document.getElementById('msgTargetUserId').value = '';
        loadMessages();
      } else {
        showToast(data.detail || '发送失败', 'error');
      }
    }).catch(function(err) {
      btn.disabled = false;
      btn.textContent = '发送';
      showToast('发送失败: ' + (err.message || '网络错误'), 'error');
    });

    return false;
  };

  function loadMessages() {
    showSkeleton('msgSkeleton', 8);
    document.getElementById('msgTable').style.display = 'none';
    document.getElementById('msgEmpty').style.display = 'none';

    api.get('/admin/api/messages?page=' + currentPage + '&page_size=' + pageSize)
      .then(function(data) {
        hideSkeleton('msgSkeleton');
        var items = data.items || [];
        var tbody = document.getElementById('msgTableBody');
        tbody.innerHTML = '';

        if (items.length === 0) {
          document.getElementById('msgEmpty').style.display = 'block';
          document.getElementById('msgPagination').innerHTML = '';
          return;
        }

        document.getElementById('msgTable').style.display = '';

        items.forEach(function(m) {
          var tr = document.createElement('tr');
          var shortContent = m.content.length > 40 ? m.content.substring(0, 40) + '...' : m.content;
          var time = m.create_time ? m.create_time.replace('T', ' ').substring(0, 19) : '-';
          var groups = '';
          if (m.target_groups && m.target_groups.length > 0) {
            groups = m.target_groups.map(function(g) { return groupNameMap[g] || escHtml(g); }).join(', ');
          } else if (m.user_id) {
            groups = '个人';
          } else {
            groups = '全部';
          }
          tr.innerHTML =
            '<td>' + m.id + '</td>' +
            '<td>' + escHtml(m.title) + '</td>' +
            '<td title="' + escHtml(m.content) + '">' + escHtml(shortContent) + '</td>' +
            '<td><span class="msg-type-badge type-' + m.msg_type + '">' + (typeNames[m.msg_type] || m.msg_type) + '</span></td>' +
            '<td><span class="priority-badge priority-' + m.priority + '">' + (priorityNames[m.priority] || m.priority) + '</span></td>' +
            '<td>' + (m.user_id || '-') + '</td>' +
            '<td class="text-xs">' + groups + '</td>' +
            '<td>' + (m.is_read ? '已读' : '未读') + '</td>' +
            '<td>' + time + '</td>';
          tbody.appendChild(tr);
        });

        renderPagination('msgPagination', data.total, data.page, data.page_size, 'goPage');
      })
      .catch(function() {
        hideSkeleton('msgSkeleton');
        document.getElementById('msgEmpty').style.display = 'block';
        showToast('加载消息列表失败', 'error');
      });
  }

  window.goPage = function(p) {
    currentPage = p;
    loadMessages();
  };

  function escHtml(s) {
    if (!s) return '';
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  // Initial load
  loadMessages();
})();