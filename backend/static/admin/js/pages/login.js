(function() {
  'use strict';

    // 清除旧 token
    localStorage.removeItem('mw_admin_token');
    localStorage.removeItem('mw_admin_name');
    localStorage.removeItem('mw_admin_role');
    localStorage.removeItem('admin_info');

    function togglePassword() {
      var input = document.getElementById('password');
      var btn = document.querySelector('.password-toggle');
      if (input.type === 'password') {
        input.type = 'text';
        btn.textContent = '🙈';
      } else {
        input.type = 'password';
        btn.textContent = '👁';
      }
    }

    function doLogin() {
      var btn = document.getElementById('loginBtn');
      var errEl = document.getElementById('errorMsg');
      var username = document.getElementById('username').value;
      var password = document.getElementById('password').value;

      if (!username || !password) {
        errEl.textContent = '请输入用户名和密码';
        errEl.style.display = 'block';
        return;
      }
      errEl.style.display = 'none';
      btn.disabled = true;
      btn.textContent = '登录中...';

      var xhr = new XMLHttpRequest();
      xhr.open('POST', '/admin/login', true);
      xhr.setRequestHeader('Content-Type', 'application/json');

      xhr.onreadystatechange = function() {};

      xhr.onload = function() {
        if (xhr.status === 200) {
          try {
            var data = JSON.parse(xhr.responseText);
            localStorage.setItem('mw_admin_token', data.token);
            localStorage.setItem('mw_admin_name', data.name);
            localStorage.setItem('mw_admin_role', data.role);
            localStorage.setItem('admin_info', JSON.stringify({
              permissions: data.permissions || [],
              role_code: data.role_code || '',
              name: data.name || '',
              data_scope: data.data_scope || 'none'
            }));
            localStorage.setItem('perms_loaded_at', Date.now().toString());
            {# Cookie is redundant — API uses Authorization: Bearer header exclusively.
               Kept only for login page initial token sync. #}
            document.cookie = 'mw_admin_token=' + data.token + '; path=/; max-age=86400; Secure; HttpOnly; SameSite=Strict';
            window.location.href = '/admin/view/dashboard';
          } catch (err) {
            console.error('解析响应失败:', err);
            errEl.textContent = '登录失败，请重试';
            errEl.style.display = 'block';
            btn.disabled = false;
            btn.textContent = '登 录';
          }
        } else {
          try {
            var err = JSON.parse(xhr.responseText);
            errEl.textContent = err.detail || '登录失败';
          } catch (e) {
            console.error('解析错误响应失败:', e);
            errEl.textContent = '登录失败 (' + xhr.status + ')';
          }
          errEl.style.display = 'block';
          btn.disabled = false;
          btn.textContent = '登 录';
        }
      };

      xhr.onerror = function() {
        console.error('=== 网络错误 ===');
        errEl.textContent = '网络错误，请检查网络连接';
        errEl.style.display = 'block';
        btn.disabled = false;
        btn.textContent = '登 录';
      };

      var requestData = JSON.stringify({ username: username, password: password });
      xhr.send(requestData);
    }

    // 回车键提交
    document.addEventListener('DOMContentLoaded', function() {
      document.getElementById('password').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
          doLogin();
        }
      });
    });

  window.loginPage = { togglePassword, doLogin };
  for (var k in window.loginPage) window[k] = window.loginPage[k];
})();
