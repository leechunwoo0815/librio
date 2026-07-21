(function() {
  'use strict';

  const dataBody = document.getElementById('dataBody');
  const searchInput = document.getElementById('searchInput');
  const statusFilter = document.getElementById('statusFilter');

  document.addEventListener('DOMContentLoaded', () => {
    loadData();
    searchInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') loadData();
    });
    statusFilter.addEventListener('change', () => loadData());
  });

  async function loadData() {
    try {
      const result = await api.get('/admin/api/venues');
      const list = result.items || result || [];
      renderVenues(list);
      updateStats(list);
    } catch (err) {
      showToast(err.message || '加载场馆列表失败', 'error');
      dataBody.innerHTML = '<tr><td colspan="7" class="text-center text-error p-40">加载失败</td></tr>';
    }
  }

  function updateStats(venues) {
    document.getElementById('statTotal').textContent = venues.length;
    const activeCount = venues.filter(v => v.status === 'active' || !v.status).length;
    document.getElementById('statActive').textContent = activeCount;
    const totalStations = venues.reduce((sum, v) => sum + (v.station_count || 0), 0);
    document.getElementById('statStations').textContent = totalStations.toLocaleString();
    const totalVisits = venues.reduce((sum, v) => sum + (v.monthly_visits || 0), 0);
    document.getElementById('statVisits').textContent = totalVisits.toLocaleString();
  }

  function getStatusBadge(status) {
    if (status === 'active' || !status) {
      return '<span class="status-badge status-active"><span class="status-dot"></span>运营中</span>';
    }
    if (status === 'maintenance') {
      return '<span class="status-badge status-maintenance"><span class="status-dot"></span>维护中</span>';
    }
    if (status === 'inactive') {
      return '<span class="status-badge status-inactive"><span class="status-dot"></span>已关闭</span>';
    }
    return '<span class="status-badge status-active"><span class="status-dot"></span>' + escapeHtml(status) + '</span>';
  }

  function renderVenues(venues) {
    const kw = searchInput.value.trim().toLowerCase();
    const st = statusFilter.value;
    let filtered = venues;
    if (kw) {
      filtered = filtered.filter(v =>
        (v.name || '').toLowerCase().includes(kw) ||
        (v.address || '').toLowerCase().includes(kw)
      );
    }
    if (st) {
      filtered = filtered.filter(v => (v.status || 'active') === st);
    }
    if (!filtered.length) {
      dataBody.innerHTML = '<tr><td colspan="7" class="text-center text-muted p-40">暂无场馆数据</td></tr>';
      document.getElementById('venuePagination').innerHTML = '';
      return;
    }
    dataBody.innerHTML = filtered.map(v => `
      <tr>
        <td>
          <div class="venue-name-cell">
            <div class="venue-icon-sm"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/></svg></div>
            <div>
              <div class="venue-name-text">${escapeHtml(v.name || '-')}</div>
              <div class="venue-addr-text">${escapeHtml(v.address || '-')}</div>
            </div>
          </div>
        </td>
        <td>${escapeHtml(v.phone || '-')}</td>
        <td>${v.capacity != null ? v.capacity.toLocaleString() : '-'}</td>
        <td>${v.book_count != null ? v.book_count.toLocaleString() : '-'}</td>
        <td>${v.borrowed_count != null ? v.borrowed_count.toLocaleString() : '-'}</td>
        <td>${getStatusBadge(v.status)}</td>
        <td>
          <div class="action-btns">
            <button class="action-btn" onclick="editVenue(${v.id}, '${jsEscape(v.name || '')}', '${jsEscape(v.address || '')}', '${jsEscape(v.phone || '')}', '${jsEscape(v.status || 'active')}', ${v.capacity || 0}, '${jsEscape(v.business_hours || '')}')">编辑</button>
            <button class="action-btn action-btn-danger" onclick="deleteVenue(${v.id}, '${jsEscape(v.name || '')}')">删除</button>
          </div>
        </td>
      </tr>
    `).join('');
    document.getElementById('venuePagination').innerHTML =
      '<span class="info">共 ' + filtered.length + ' 个场馆</span><div class="pages"><button class="page-btn active">1</button></div>';
  }

  function openAddModal() {
    document.getElementById('editId').value = '';
    document.querySelector('#venueModal h2').textContent = '新建场馆';
    document.getElementById('submitBtn').textContent = '确认创建';
    document.getElementById('addForm').reset();
    showModal('venueModal');
  }

  function editVenue(id, name, address, phone, status, capacity, businessHours) {
    document.getElementById('editId').value = id;
    document.querySelector('#venueModal h2').textContent = '编辑场馆';
    document.getElementById('submitBtn').textContent = '保存修改';
    const form = document.getElementById('addForm');
    form.elements['name'].value = name;
    form.elements['address'].value = address;
    form.elements['phone'].value = phone;
    // 后端 status 是 int (1=active, 0=inactive)，前端 select 用字符串
    var statusStr = status === 1 || status === '1' || status === 'active' ? 'active'
      : status === 0 || status === '0' || status === 'inactive' ? 'inactive'
      : status === 'maintenance' ? 'maintenance'
      : 'active';
    form.elements['status'].value = statusStr;
    form.elements['capacity'].value = capacity != null ? capacity : '';
    form.elements['business_hours'].value = businessHours || '';
    showModal('venueModal');
  }

  function closeAddModal() {
    closeModal('venueModal');
  }

  async function submitVenue(e) {
    e.preventDefault();
    const form = document.getElementById('addForm');
    const fd = new FormData(form);
    const body = {};
    for (const [k, v] of fd.entries()) {
      if (k === 'editId') continue;
      if (v === '') continue;
      if (k === 'capacity') {
        body[k] = Number(v);
      } else {
        body[k] = v;
      }
    }
    const editId = document.getElementById('editId').value;
    try {
      if (editId) {
        await api.put('/admin/api/venues/' + editId, body);
        showToast('场馆更新成功');
      } else {
        await api.post('/admin/api/venues', body);
        showToast('场馆创建成功');
      }
      closeAddModal();
      loadData();
    } catch (err) {
      showToast(err.message || '操作失败', 'error');
    }
  }

  async function deleteVenue(id, name) {
    showConfirm('删除场馆', '确定删除场馆"' + name + '"？此操作不可撤销。', async function() {
      try {
        await api.del('/admin/api/venues/' + id);
        showToast('场馆已删除');
        loadData();
      } catch (err) {
        showToast(err.message || '删除失败', 'error');
      }
    });
  }

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  window.venuesPage = { dataBody, searchInput, statusFilter, loadData, updateStats, getStatusBadge, renderVenues, openAddModal, editVenue, closeAddModal, submitVenue, deleteVenue };
  for (var k in window.venuesPage) window[k] = window.venuesPage[k];
})();
