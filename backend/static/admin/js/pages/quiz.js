(function() {
  'use strict';

document.addEventListener('DOMContentLoaded', function() {
  loadStats();
  loadRecentQuizzes();
});

async function loadStats() {
  try {
    // 获取题库统计
    const questions = await api.get('/admin/api/advancement/questions');
    const questionList = Array.isArray(questions) ? questions : (questions.items || []);
    document.getElementById('statTotalQuestions').textContent = (questions.total !== undefined) ? questions.total : questionList.length;

    // 测验记录统计
    const quizData = await api.get('/admin/api/advancement/quizzes');
    const quizzes = quizData.items || [];
    const completed = quizzes.filter(function(q) { return q.status === 1; });
    document.getElementById('statTodayQuiz').textContent = completed.length;

    if (completed.length) {
      const avgScore = completed.reduce(function(sum, q) { return sum + (q.score || 0); }, 0) / completed.length;
      document.getElementById('statAvgScore').textContent = avgScore.toFixed(1) + '%';
      const passed = completed.filter(function(q) { return q.passed; }).length;
      document.getElementById('statPassRate').textContent = Math.round(passed / completed.length * 100) + '%';
    } else {
      document.getElementById('statAvgScore').textContent = '--';
      document.getElementById('statPassRate').textContent = '--';
    }
  } catch (err) {
    console.error('加载统计失败', err);
  }
}

async function loadRecentQuizzes() {
  try {
    const data = await api.get('/admin/api/advancement/quizzes');
    const quizzes = data.items || [];
    if (quizzes.length === 0) {
      document.getElementById('recentQuizzes').innerHTML = '<p>暂无测验记录</p>';
      return;
    }
    let html = '<table class="quiz-table">';
    html += '<thead><tr><th>孩子</th><th>图书</th><th>正确率</th><th>结果</th><th>时间</th></tr></thead>';
    html += '<tbody>';
    quizzes.slice(0, 20).forEach(function(q) {
      var result = '';
      if (q.status === 0) {
        result = '<span class="text-warning">进行中</span>';
      } else if (q.passed) {
        result = '<span class="text-success">通过</span>';
      } else {
        result = '<span class="text-error">未通过</span>';
      }
      html += '<tr>';
      html += '<td>' + escapeHtml(q.child_name || '-') + '</td>';
      html += '<td>' + escapeHtml(q.book_title || '-') + '</td>';
      html += '<td>' + (q.score != null ? q.score + '%' : '-') + '</td>';
      html += '<td>' + result + '</td>';
      html += '<td class="text-muted text-sm">' + (q.create_time ? formatDateTime(q.create_time) : '-') + '</td>';
      html += '</tr>';
    });
    html += '</tbody></table>';
    document.getElementById('recentQuizzes').innerHTML = html;
  } catch (err) {
    document.getElementById('recentQuizzes').innerHTML = '<p class="text-error">加载失败</p>';
  }
}

async function generateQuiz() {
  showToast('测验由系统自动生成，无需手动触发', 'info');
}

async function exportQuizResults() {
  try {
    const data = await api.get('/admin/api/advancement/quizzes');
    const quizzes = data.items || [];
    if (quizzes.length === 0) {
      showToast('没有可导出的数据', 'error');
      return;
    }
    const headers = ['孩子', '图书', '正确率', '结果', '时间'];
    const rows = quizzes.map(function(q) {
      return [
        q.child_name,
        q.book_title,
        q.score != null ? q.score + '%' : '-',
        q.passed ? '通过' : (q.status === 0 ? '进行中' : '未通过'),
        q.create_time
      ];
    });
    exportCSV('quiz_results.csv', headers, rows);
    showToast('已导出 ' + rows.length + ' 条记录');
  } catch (err) {
    showToast('导出失败: ' + err.message, 'error');
  }
}

function exportCSV(filename, headers, rows) {
  let csv = headers.join(',') + '\n';
  rows.forEach(function(row) {
    csv += row.map(cell => '"' + (cell != null ? String(cell).replace(/"/g, '""') : '') + '"').join(',') + '\n';
  });
  const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8;' });
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = filename;
  link.click();
}

function formatDateTime(isoStr) {
  if (!isoStr) return '-';
  const d = new Date(isoStr);
  return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0') + ' ' + String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0');
}

  window.quizPage = { loadStats, loadRecentQuizzes, generateQuiz, exportQuizResults };
  for (var k in window.quizPage) window[k] = window.quizPage[k];
})();
