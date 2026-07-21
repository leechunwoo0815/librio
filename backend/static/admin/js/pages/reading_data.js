(function() {
  'use strict';

  var currentPeriod = 'today';

  document.addEventListener('DOMContentLoaded', function() {
    loadData('today');
    loadTrends();
  });

  async function loadData(period, btn) {
    currentPeriod = period;
    if (btn) {
      document.querySelectorAll('.period-tabs button').forEach(function(b) { b.classList.remove('active'); });
      btn.classList.add('active');
    }

    try {
      var data = await api.get('/admin/api/reading-data/stats?period=' + period);
      var stats = data.stats || {};
      document.getElementById('statOnline').textContent = stats.online_today || 0;
      document.getElementById('statDuration').textContent = stats.total_hours || '0m';
      document.getElementById('statActive').textContent = stats.active_children || 0;
      document.getElementById('statAvg').textContent = (stats.avg_minutes || 0) + 'm';
      document.getElementById('statCheckin').textContent = (stats.checkin_rate || 0) + '%';

      // 渲染排行
      var readers = data.top_readers || [];
      var chartEl = document.getElementById('topReadersChart');
      if (!readers.length) {
        chartEl.innerHTML = '<div class="chart-loading">暂无数据</div>';
        return;
      }
      var maxMinutes = readers[0].minutes || 1;
      chartEl.innerHTML = readers.map(function(r, i) {
        var pct = Math.round(r.minutes / maxMinutes * 100);
        return '<div class="bar-col"><div class="bar-fill" style="height:' + pct + '%"></div><div class="bar-label">' + escapeHtml(r.child_name) + '</div></div>';
      }).join('');
    } catch (e) {
      showToast('加载数据失败: ' + e.message, 'error');
    }
  }

  async function loadTrends() {
    try {
      var data = await api.get('/admin/api/reading-data/trends?days=14');
      var trends = data.trends || [];
      var chartEl = document.getElementById('trendChart');
      if (!trends.length) {
        chartEl.innerHTML = '<div class="chart-loading">暂无数据</div>';
        return;
      }

      // 简单 SVG 折线图
      var maxOnline = Math.max(...trends.map(function(t) { return t.online; }), 1);
      var points = trends.map(function(t, i) {
        var x = (i / (trends.length - 1)) * 800;
        var y = 180 - (t.online / maxOnline * 160);
        return x + ',' + y;
      }).join(' ');

      var labels = trends.map(function(t, i) {
        if (i % 2 === 0) {
          var x = (i / (trends.length - 1)) * 800;
          return '<text x="' + x + '" y="195" font-size="11" text-anchor="middle" class="chart-label">' + t.date + '</text>';
        }
        return '';
      }).join('');

      chartEl.innerHTML = '<svg viewBox="0 0 800 200" class="w-full" style="height:200px">' +
        '<polyline points="' + points + '" fill="none" stroke="var(--accent)" stroke-width="2.5" stroke-linecap="round"/>' +
        labels +
        '</svg>';
    } catch (e) {
      // silent
    }
  }

  function escapeHtml(str) {
    var div = document.createElement('div');
    div.textContent = str || '';
    return div.innerHTML;
  }

  window.readingDataPage = { currentPeriod, loadData, loadTrends };
  for (var k in window.readingDataPage) window[k] = window.readingDataPage[k];
})();
