/**
 * 打印历史列表卡片 - v1.0
 * 功能：打印历史列表视图，支持筛选、搜索、预览图展示
 *
 * 配置项：
 *   print_history    - 必填，打印历史传感器实体ID
 *   title            - 标题，默认"打印历史"
 *   printer_name     - 打印机名称，用于显示
 *   max_items        - 最大显示条数，默认50
 */
class PrinterHistoryListCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    // 内部状态：筛选条件
    this._filterStatus = 'all';
    this._searchKeyword = '';
    this._dateFilter = 'all';
    this._page = 0;
    this._pageSize = 20;
  }

  setConfig(config) {
    this.config = config;
    this._filterStatus = config.default_status_filter || 'all';
    this._dateFilter = config.default_date_filter || 'all';
    this._pageSize = config.max_items || 20;
    this.render();
  }

  set hass(hass) {
    this._hass = hass;
    if (hass && this.config) {
      this.updateData();
    }
  }

  _getState(entityId) {
    const entity = this._hass?.states[entityId];
    return entity?.state || '0';
  }

  _getAttr(entityId) {
    const entity = this._hass?.states[entityId];
    return entity?.attributes || {};
  }

  _getHistory() {
    const historyEntity = this._hass?.states[this.config.print_history];
    return historyEntity?.attributes?.history || [];
  }

  _getCurrentPrint() {
    const historyEntity = this._hass?.states[this.config.print_history];
    return historyEntity?.attributes?.current_print || null;
  }

  _escapeHtml(str) {
    if (str === null || str === undefined) return '';
    const div = document.createElement('div');
    div.textContent = String(str);
    return div.innerHTML;
  }

  _formatDuration(hours) {
    if (!hours || hours <= 0) return '--';
    if (hours < 1) return `${Math.round(hours * 60)}min`;
    return `${hours.toFixed(1)}h`;
  }

  _formatDateTime(isoStr) {
    try {
      const d = new Date(isoStr);
      const pad = n => String(n).padStart(2, '0');
      return `${d.getFullYear()}/${pad(d.getMonth()+1)}/${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
    } catch { return isoStr || '--'; }
  }

  _getStatusInfo(status) {
    const map = {
      running:  { text: '正在打印', color: '#03a9f4', bg: '#e3f2fd' },
      finish:   { text: '成功',    color: '#4caf50', bg: '#e8f5e9' },
      fail:     { text: '失败',    color: '#f44336', bg: '#ffebee' },
      cancelled:{ text: '已取消',  color: '#ff9800', bg: '#fff3e0' },
    };
    return map[status] || { text: status || '未知', color: '#999', bg: '#f5f5f5' };
  }

  _buildSpecsLine(item) {
    const parts = [];
    if (item.nozzle_size) parts.push(this._escapeHtml(item.nozzle_size));
    if (item.total_layer_count) parts.push(`${this._escapeHtml(String(item.total_layer_count))}层`);
    if (item.progress && item.status !== 'finish') parts.push(`${item.progress}%`);
    if (parts.length === 0) parts.push('标准参数');
    return parts.join(', ');
  }

  _getImageUrl(item) {
    // 优先使用本地路径（/local/开头），其次使用URL
    if (item.cover_image_local) return item.cover_image_local;
    if (item.cover_image_url && !item.cover_image_url.startsWith('/local')) {
      // 拼接HA基础URL
      const baseUrl = this._hass?.hassUrl?.() || '';
      return `${baseUrl}${item.cover_image_url}`;
    }
    return '';
  }

  _applyFilters(history) {
    let result = [...history];

    // 状态筛选
    if (this._filterStatus !== 'all') {
      result = result.filter(item => item.status === this._filterStatus);
    }

    // 关键词搜索
    if (this._searchKeyword.trim()) {
      const kw = this._searchKeyword.toLowerCase().trim();
      result = result.filter(item =>
        (item.task_name || '').toLowerCase().includes(kw) ||
        (item.filament_type || '').toLowerCase().includes(kw) ||
        (item.filament_color || '').toLowerCase().includes(kw)
      );
    }

    // 日期筛选
    if (this._dateFilter !== 'all') {
      const now = new Date();
      let cutoff;
      switch (this._dateFilter) {
        case '7d':  cutoff = new Date(now - 7 * 86400000); break;
        case '30d': cutoff = new Date(now - 30 * 86400000); break;
        case '90d': cutoff = new Date(now - 90 * 86400000); break;
        default: cutoff = null;
      }
      if (cutoff) {
        result = result.filter(item => {
          try { return new Date(item.end_time || item.start_time) >= cutoff; }
          catch { return false; }
        });
      }
    }

    // 按时间倒序排列（最新的在前）
    result.sort((a, b) => new Date(b.end_time || b.start_time || 0) - new Date(a.end_time || a.start_time || 0));

    return result;
  }

  render() {
    const container = this.shadowRoot;
    if (!container) return;

    container.innerHTML = `
      <style>
        :host { display: block; }
        .card {
          background: var(--card-background-color, #fff);
          border-radius: var(--border-radius, 12px);
          box-shadow: var(--box-shadow, 0 2px 8px rgba(0,0,0,0.08));
          padding: 16px;
          color: var(--primary-text-color, #333);
          font-family: var(--paper-font-body1_-_font-family), sans-serif;
          overflow: hidden;
        }
        /* ====== 顶部栏 ====== */
        .header-bar {
          display: flex; align-items: center; justify-content: space-between;
          margin-bottom: 12px; padding-bottom: 10px;
          border-bottom: 1px solid var(--divider-color, #e0e0e0);
        }
        .header-left {
          display: flex; align-items: center; gap: 10px;
        }
        .back-btn {
          cursor: pointer; font-size: 20px; padding: 4px 6px;
          border-radius: 6px; transition: background 0.2s;
          color: var(--primary-text-color, #333);
        }
        .back-btn:hover { background: var(--secondary-background-color, #f5f5f5); }
        .header-title {
          font-size: 18px; font-weight: 700;
        }
        .header-actions { display: flex; align-items: center; gap: 8px; }
        .icon-btn {
          cursor: pointer; font-size: 18px; padding: 6px 8px;
          border-radius: 6px; transition: background 0.2s;
          color: var(--secondary-text-color, #666); border: none; background: none;
        }
        .icon-btn:hover { background: var(--secondary-background-color, #f5f5f5); }
        /* ====== 筛选栏 ====== */
        .filter-bar {
          display: flex; align-items: center; gap: 8px; margin-bottom: 14px;
          flex-wrap: wrap;
        }
        .filter-select {
          padding: 7px 28px 7px 12px; border-radius: 8px;
          border: 1.5px solid var(--divider-color, #ddd);
          background: var(--card-background-color, #fff);
          color: var(--primary-text-color, #333);
          font-size: 13px; cursor: pointer;
          appearance: none; -webkit-appearance: none;
          background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6'%3E%3Cpath d='M0 0l5 6 5-6z' fill='%23999'/%3E%3C/svg%3E");
          background-repeat: no-repeat; background-position: right 10px center;
          outline: none; transition: border-color 0.2s;
        }
        .filter-select:focus { border-color: var(--primary-color, #03a9f4); }
        .search-box {
          flex: 1; min-width: 120px;
          padding: 7px 12px; border-radius: 8px;
          border: 1.5px solid var(--divider-color, #ddd);
          background: var(--card-background-color, #fff);
          color: var(--primary-text-color, #333);
          font-size: 13px; outline: none;
          transition: border-color 0.2s;
        }
        .search-box:focus { border-color: var(--primary-color, #03a9f4); }
        .search-box::placeholder { color: var(--secondary-text-color, #aaa); }
        .result-count {
          font-size: 12px; color: var(--secondary-text-color, #888);
          white-space: nowrap;
        }
        /* ====== 列表项 ====== */
        .list-container { display: flex; flex-direction: column; gap: 10px; }
        .list-item {
          display: flex; gap: 12px; padding: 12px;
          background: var(--secondary-background-color, #fafafa);
          border-radius: 10px; cursor: pointer;
          transition: transform 0.15s, box-shadow 0.15s;
          border: 1px solid transparent;
        }
        .list-item:hover {
          transform: translateY(-1px);
          box-shadow: 0 3px 10px rgba(0,0,0,0.08);
          border-color: var(--primary-color, #03a9f4);
        }
        /* 预览图 */
        .item-thumb {
          width: 72px; height: 72px; min-width: 72px;
          border-radius: 10px; overflow: hidden;
          background: linear-gradient(135deg, #eee 0%, #ddd 100%);
          display: flex; align-items: center; justify-content: center;
        }
        .item-thumb img {
          width: 100%; height: 100%; object-fit: cover;
        }
        .thumb-placeholder {
          font-size: 28px; opacity: 0.35;
        }
        /* 内容区 */
        .item-body { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 3px; }
        .item-status-row {
          display: flex; align-items: center; justify-content: space-between;
        }
        .status-badge {
          font-size: 12px; font-weight: 600; padding: 2px 8px;
          border-radius: 4px; display: inline-block;
        }
        .gcode-badge {
          font-size: 10px; padding: 1px 6px; border-radius: 4px;
          background: #e8eaf6; color: #3f51b5; font-weight: 500;
        }
        .item-name {
          font-size: 14px; font-weight: 600;
          white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
          line-height: 1.3;
        }
        .item-specs {
          font-size: 11.5px; color: var(--secondary-text-color, #777);
          white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
        }
        .item-meta {
          display: flex; align-items: center; gap: 12px;
          font-size: 11.5px; color: var(--secondary-text-color, #888);
          margin-top: 2px;
        }
        .meta-item { display: flex; align-items: center; gap: 3px; }
        .meta-icon { font-size: 13px; }
        /* ====== 分页 ====== */
        .pagination {
          display: flex; align-items: center; justify-content: center;
          gap: 10px; margin-top: 14px; padding-top: 12px;
          border-top: 1px solid var(--divider-color, #e0e0e0);
        }
        .page-btn {
          padding: 6px 14px; border-radius: 6px; border: 1.5px solid var(--divider-color, #ddd);
          background: var(--card-background-color, #fff);
          color: var(--primary-text-color, #333); font-size: 13px;
          cursor: pointer; transition: all 0.2s;
        }
        .page-btn:hover:not(:disabled) {
          border-color: var(--primary-color, #03a9f4);
          color: var(--primary-color, #03a9f4);
        }
        .page-btn:disabled { opacity: 0.4; cursor: not-allowed; }
        .page-info { font-size: 12px; color: var(--secondary-text-color, #888); }
        /* ====== 空状态 / 错误 ====== */
        .no-data {
          text-align: center; color: var(--secondary-text-color, #888);
          padding: 40px 20px; font-style: italic;
        }
        .error {
          background: #fce4ec; color: #c62828; padding: 15px;
          border-radius: 8px; border-left: 4px solid #c62828;
          word-break: break-all; font-size: 13px;
        }
        /* ====== 详情弹窗 ====== */
        .modal-overlay {
          position: fixed; top: 0; left: 0; right: 0; bottom: 0;
          background: rgba(0,0,0,0.45); z-index: 999;
          display: flex; align-items: center; justify-content: center;
          backdrop-filter: blur(2px);
        }
        .modal-card {
          background: var(--card-background-color, #fff);
          border-radius: 14px; padding: 20px; max-width: 420px;
          width: 90%; max-height: 85vh; overflow-y: auto;
          box-shadow: 0 10px 40px rgba(0,0,0,0.2);
        }
        .modal-header {
          display: flex; align-items: center; justify-content: space-between;
          margin-bottom: 14px; padding-bottom: 10px;
          border-bottom: 1px solid var(--divider-color, #e0e0e0);
        }
        .modal-title { font-size: 17px; font-weight: 700; }
        .close-btn {
          cursor: pointer; font-size: 22px; color: var(--secondary-text-color, #888);
          background: none; border: none; padding: 0 4px; line-height: 1;
        }
        .close-btn:hover { color: var(--primary-text-color, #333); }
        .detail-row {
          display: flex; justify-content: space-between; padding: 8px 0;
          border-bottom: 1px solid var(--divider-color, #eee);
          font-size: 13px;
        }
        .detail-label { color: var(--secondary-text-color, #777); }
        .detail-value { font-weight: 500; text-align: right; max-width: 60%; word-break: break-all; }
        .modal-img {
          width: 100%; border-radius: 10px; margin-bottom: 14px;
          max-height: 280px; object-fit: cover;
          background: #f0f0f0;
        }
        @media (max-width: 480px) {
          .item-thumb { width: 60px; height: 60px; min-width: 60px; }
          .item-name { font-size: 13px; }
          .item-specs, .item-meta { font-size: 11px; }
        }
      </style>
      <div class="card" id="card-content">
        <div class="no-data">加载中...</div>
      </div>
    `;

    // 绑定事件委托（筛选、搜索、点击）
    setTimeout(() => this._bindEvents(), 0);
  }

  _bindEvents() {
    const root = this.shadowRoot;
    if (!root) return;

    // 状态筛选
    root.querySelectorAll('.filter-status').forEach(el => {
      el.addEventListener('change', e => {
        this._filterStatus = e.target.value;
        this._page = 0;
        this.updateData();
      });
    });

    // 日期筛选
    root.querySelectorAll('.filter-date').forEach(el => {
      el.addEventListener('change', e => {
        this._dateFilter = e.target.value;
        this._page = 0;
        this.updateData();
      });
    });

    // 搜索框
    root.querySelectorAll('.search-box').forEach(el => {
      let timer;
      el.addEventListener('input', e => {
        clearTimeout(timer);
        timer = setTimeout(() => {
          this._searchKeyword = e.target.value;
          this._page = 0;
          this.updateData();
        }, 300);
      });
    });

    // 分页按钮
    root.querySelectorAll('.btn-prev').forEach(el => {
      el.addEventListener('click', () => { this._page = Math.max(0, this._page - 1); this.updateData(); });
    });
    root.querySelectorAll('.btn-next').forEach(el => {
      el.addEventListener('click', () => { this._page++; this.updateData(); });
    });

    // 列表项点击 → 弹出详情
    root.querySelectorAll('.list-item').forEach(el => {
      el.addEventListener('click', () => {
        const idx = parseInt(el.dataset.idx, 10);
        if (!isNaN(idx)) this._showDetailModal(idx);
      });
    });

    // 弹窗关闭
    root.querySelectorAll('.close-modal, .modal-overlay').forEach(el => {
      el.addEventListener('click', e => {
        if (e.target === el || e.target.classList.contains('close-modal')) {
          const modal = root.querySelector('.modal-overlay');
          if (modal) modal.remove();
        }
      });
    });
  }

  updateData() {
    const container = this.shadowRoot.getElementById('card-content');
    if (!container) return;

    try {
      if (!this._hass) {
        container.innerHTML = `<div class="error"><b>错误：</b>未连接到 Home Assistant</div>`;
        return;
      }
      if (!this.config?.print_history) {
        container.innerHTML = `<div class="error"><b>配置错误！</b>缺少 print_history</div>`;
        return;
      }

      const rawHistory = this._getHistory();
      const currentPrint = this._getCurrentPrint();

      // 合并当前正在打印的任务到列表最前面
      let allItems = [];
      if (currentPrint) {
        allItems.push({
          ...currentPrint,
          status: 'running',
          end_time: null,
          duration_hours: currentPrint.start_time
            ? ((Date.now() - new Date(currentPrint.start_time).getTime()) / 3600000).toFixed(1)
            : 0,
        });
      }
      allItems = allItems.concat(rawHistory);

      // 应用筛选和排序
      const filtered = this._applyFilters(allItems);

      // 分页
      const totalFiltered = filtered.length;
      const startIdx = this._page * this._pageSize;
      const pageItems = filtered.slice(startIdx, startIdx + this._pageSize);
      const totalPages = Math.ceil(totalFiltered / this._pageSize);

      const title = this._escapeHtml(this.config.title || '打印历史');
      const printerName = this._escapeHtml(this.config.printer_name || '');

      container.innerHTML = `
        ${this._renderHeader(title)}
        ${this._renderFilterBar(totalFiltered)}
        ${pageItems.length > 0 ? this._renderList(pageItems, printerName) : this._renderEmpty(filtered, allItems)}
        ${totalFiltered > this._pageSize ? this._renderPagination(totalPages, totalFiltered) : ''}
      `;

      this._bindEvents();

    } catch (error) {
      console.error('打印机历史列表错误:', error);
      container.innerHTML = `<div class="error"><b>渲染错误！</b>${this._escapeHtml(error.message)}</div>`;
    }
  }

  _renderHeader(title) {
    return `
      <div class="header-bar">
        <div class="header-left">
          <span class="back-btn">←</span>
          <span class="header-title">${title}</span>
        </div>
        <div class="header-actions">
          <button class="icon-btn" title="搜索">🔍</button>
        </div>
      </div>
    `;
  }

  _renderFilterBar(totalCount) {
    return `
      <div class="filter-bar">
        <select class="filter-select filter-date">
          <option value="all" ${this._dateFilter === 'all' ? 'selected' : ''}>日期筛选 ▾</option>
          <option value="7d" ${this._dateFilter === '7d' ? 'selected' : ''}>最近7天</option>
          <option value="30d" ${this._dateFilter === '30d' ? 'selected' : ''}>最近30天</option>
          <option value="90d" ${this._dateFilter === '90d' ? 'selected' : ''}>最近90天</option>
        </select>
        <select class="filter-select filter-status">
          <option value="all" ${this._filterStatus === 'all' ? 'selected' : ''}>状态 ▾</option>
          <option value="running" ${this._filterStatus === 'running' ? 'selected' : ''}>正在打印</option>
          <option value="finish" ${this._filterStatus === 'finish' ? 'selected' : ''}>成功</option>
          <option value="fail" ${this._filterStatus === 'fail' ? 'selected' : ''}>失败</option>
          <option value="cancelled" ${this._filterStatus === 'cancelled' ? 'selected' : ''}>已取消</option>
        </select>
        <input type="text" class="search-box" placeholder="搜索任务名/耗材..." value="${this._escapeHtml(this._searchKeyword)}">
        <span class="result-count">${totalCount} 条记录</span>
      </div>
    `;
  }

  _renderList(items, printerName) {
    const cards = items.map((item, i) => {
      const statusInfo = this._getStatusInfo(item.status);
      const imgUrl = this._getImageUrl(item);
      const name = this._escapeHtml(item.task_name || '未命名任务');
      const specs = this._buildSpecsLine(item);
      const dur = this._formatDuration(parseFloat(item.duration_hours));
      const timeStr = item.end_time
        ? this._formatDateTime(item.end_time)
        : (item.start_time ? this._formatDateTime(item.start_time) : '--');

      const thumbHtml = imgUrl
        ? `<img src="${imgUrl}" alt="${name}" loading="lazy" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'"><span class="thumb-placeholder">🖨️</span>`
        : `<span class="thumb-placeholder">🖨️</span>`;

      const gcodeBadge = item.gcode_filename
        ? `<span class="gcode-badge">Gcode</span>` : '';

      return `
        <div class="list-item" data-idx="${i}">
          <div class="item-thumb">${thumbHtml}</div>
          <div class="item-body">
            <div class="item-status-row">
              <span class="status-badge" style="color:${statusInfo.color};background:${statusInfo.bg}">${statusInfo.text}</span>
              ${gcodeBadge}
            </div>
            <div class="item-name" title="${name}">${name}</div>
            <div class="item-specs">${specs}</div>
            <div class="item-meta">
              <span class="meta-item"><span class="meta-icon">⏱</span>${dur}</span>
              <span class="meta-item"><span class="meta-icon">🖨</span>${printerName || '打印机'}</span>
            </div>
            <div class="item-meta" style="margin-top:0">
              第${i + 1 + this._page * this._pageSize}盘 (${timeStr})
            </div>
          </div>
        </div>`;
    }).join('');

    return `<div class="list-container">${cards}</div>`;
  }

  _renderEmpty(filtered, allItems) {
    const hasData = allItems.length > 0;
    const msg = !hasData
      ? '暂无打印历史记录'
      : (filtered.length === 0 ? '没有匹配的记录，请调整筛选条件' : '暂无数据');
    return `<div class="no-data">${msg}</div>`;
  }

  _renderPagination(totalPages, totalCount) {
    const cur = this._page + 1;
    const disablePrev = this._page <= 0;
    const disableNext = cur >= totalPages;

    return `
      <div class="pagination">
        <button class="page-btn btn-prev" ${disablePrev ? 'disabled' : ''}>上一页</button>
        <span class="page-info">${cur} / ${totalPages} 页（共 ${totalCount} 条）</span>
        <button class="page-btn btn-next" ${disableNext ? 'disabled' : ''}>下一页</button>
      </div>
    `;
  }

  _showDetailModal(idx) {
    const rawHistory = this._getHistory();
    const currentPrint = this._getCurrentPrint();
    let allItems = currentPrint ? [{ ...currentPrint, status: 'running', end_time: null }].concat(rawHistory) : rawHistory;
    const filtered = this._applyFilters(allItems);
    const item = filtered[idx];
    if (!item) return;

    const statusInfo = this._getStatusInfo(item.status);
    const imgUrl = this._getImageUrl(item);
    const imgHtml = imgUrl ? `<img class="modal-img" src="${imgUrl}" alt="预览图" onerror="this.style.display='none'">` : '';

    const fields = [
      ['状态', `<span style="color:${statusInfo.color};font-weight:600">${statusInfo.text}</span>`],
      ['任务名', this._escapeHtml(item.task_name || '--')],
      ['喷嘴类型', this._escapeHtml(item.nozzle_type || '--')],
      ['喷嘴尺寸', this._escapeHtml(item.nozzle_size || '--')],
      ['热床类型', this._escapeHtml(item.print_bed_type || '--')],
      ['总层数', this._escapeHtml(String(item.total_layer_count || '--'))],
      ['进度', item.status === 'finish' ? '100%' : `${item.progress || 0}%`],
      ['时长', this._formatDuration(parseFloat(item.duration_hours))],
      ['耗材重量', item.total_weight != null ? `${item.total_weight} g` : '--'],
      ['耗材长度', item.total_length != null ? `${item.total_length} m` : '--'],
      ['耗材类型', this._escapeHtml(item.filament_type || '--')],
      ['耗材颜色', this._escapeHtml(item.filament_color || '--')],
      ['能耗', item.energy_kwh != null ? `${item.energy_kwh} kWh` : '--'],
      ['开始时间', this._formatDateTime(item.start_time)],
      ['结束时间', item.end_time ? this._formatDateTime(item.end_time) : '进行中...'],
    ];

    const rowsHtml = fields.map(([label, val]) =>
      `<div class="detail-row"><span class="detail-label">${label}</span><span class="detail-value">${val}</span></div>`
    ).join('');

    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.innerHTML = `
      <div class="modal-card">
        <div class="modal-header">
          <span class="modal-title">${this._escapeHtml(item.task_name || '打印详情')}</span>
          <button class="close-btn close-modal">×</button>
        </div>
        ${imgHtml}
        <div>${rowsHtml}</div>
      </div>
    `;

    this.shadowRoot.appendChild(overlay);
    this._bindEvents();
  }

  getCardSize() {
    const h = this._getHistory();
    return Math.min(6, Math.max(3, Math.ceil((h.length || 0) / 5)));
  }

  static getStubConfig() {
    return {
      type: 'printer-history-list-card',
      print_history: '',
      title: '打印历史',
      printer_name: '',
      max_items: 20,
    };
  }
}

customElements.define('printer-history-list-card', PrinterHistoryListCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: 'printer-history-list-card',
  name: '打印历史列表',
  description: '打印机历史记录列表视图 - 支持筛选、搜索、预览图'
});
