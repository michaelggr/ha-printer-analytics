/**
 * 打印机历史记录页面 - 独立版 v1.2
 * 基于Printer Analytics插件的print_history数据
 *
 * 功能：
 * - 📋 完整历史记录列表展示
 * - 🔍 多维度搜索和筛选
 * - 📊 统计摘要面板
 * - 🖼️ 记录详情弹窗
 * - 🎨 Bambu Lab APP风格UI
 * - 🌙 v1.2 暗色主题（Dark Mode）
 * - 🔐 支持两种访问模式：HA内部 / 独立访问（REST API）
 */

class PrinterHistoryPage {
  constructor() {
    this.hass = null;
    this.historyData = [];
    this.filteredData = [];
    this.apiBaseUrl = 'http://192.168.0.130:8123';
    this.accessToken = '';
    this.useRestApi = false;  // 是否使用REST API模式
    
    // 从URL参数读取配置
    const urlParams = new URLSearchParams(location.search);
    
    this.config = {
      print_history: urlParams.get('sensor') || 'sensor.p2s_p2s_da_yin_li_shi',
      printer_name: urlParams.get('printer') || 'P2S'
    };
    
    console.log('[Printer History] v1.2 初始化完成（暗色主题版）');
  }

  async init() {
    try {
      // 模式1：尝试获取Home Assistant实例（HA内部模式）
      await this._waitForHass();
      
      if (this.hass) {
        console.log('[Printer History] ✅ 使用HA内部模式 (window.hass)');
      } else if (this.accessToken) {
        // 模式2：使用REST API（独立访问模式）
        this.useRestApi = true;
        console.log('[Printer History] ✅ 使用REST API独立模式');
      } else {
        throw new Error('请通过Home Assistant访问或在URL中提供认证Token');
      }
      
      // 加载历史数据
      await this.loadHistoryData();
      
      // 渲染页面
      this.render();
      
      // 绑定事件
      this.bindEvents();
      
      // 定时刷新（每30秒）
      setInterval(() => this.refreshData(), 30000);
      
    } catch (error) {
      console.error('[Printer History] 初始化失败:', error);
      
      // 显示错误信息和使用说明
      document.getElementById('app').innerHTML = `
        <div class="error-container">
          <div class="error-icon">⚠️</div>
          <h2>加载失败</h2>
          <p>${error.message}</p>
          
          <div style="margin-top:24px;padding:20px;background:#f5f5f5;border-radius:12px;text-align:left;">
            <strong style="color:#333;font-size:14px;">📖 访问方式：</strong>
            <ol style="margin-top:12px;padding-left:20px;color:#666;line-height:1.8;font-size:13px;">
              <li><strong>方式1 - HA面板内访问</strong><br>
                在Home Assistant Dashboard中配置此页面为Panel或卡片
              </li>
              <li style="margin-top:8px;"><strong>方式2 - 独立URL访问（需Token）</strong><br>
                <code style="background:#e3f2fd;padding:4px 8px;border-radius:4px;font-size:11px;display:inline-block;margin-top:4px;">
                  /local/printer-history.html?authToken=你的长期访问令牌
                </code><br>
                <span style="font-size:11px;color:#999;">获取路径：HA → 个人资料 → 长期访问令牌 → 创建令牌</span>
              </li>
            </ol>
          </div>
          
          <button onclick="location.reload()" class="retry-btn" style="margin-top:20px;">🔄 重试</button>
        </div>
      `;
    }
  }

  async _waitForHass() {
    return new Promise((resolve, reject) => {
      let attempts = 0;
      const maxAttempts = 30;  // 3秒超时
      
      // 首先检查URL参数是否有token
      const urlParams = new URLSearchParams(location.search);
      this.accessToken = urlParams.get('authToken') || '';
      
      const checkHass = () => {
        // 优先使用window.hass
        if (window.hass) {
          this.hass = window.hass;
          resolve();
        } else if (this.accessToken) {
          // 有token但无hass，稍后等待一下看是否延迟加载
          if (attempts++ > maxAttempts) {
            resolve();  // 有token就允许继续，后续用REST API
          } else {
            setTimeout(checkHass, 100);
          }
        } else if (attempts++ > maxAttempts) {
          reject(new Error('未检测到Home Assistant环境且未提供认证Token'));
        } else {
          setTimeout(checkHass, 100);
        }
      };
      
      checkHass();
    });
  }

  async loadHistoryData() {
    try {
      let history = [];
      
      if (this.useRestApi || !this.hass) {
        // ========== REST API模式 ==========
        console.log(`[Printer History] 通过REST API获取数据: ${this.config.print_history}`);
        
        const response = await fetch(
          `${this.apiBaseUrl}/api/states/${this.config.print_history}`,
          {
            headers: {
              'Authorization': `Bearer ${this.accessToken}`,
              'Content-Type': 'application/json'
            }
          }
        );
        
        if (!response.ok) {
          throw new Error(`API请求失败 (${response.status}): ${response.statusText}`);
        }
        
        const state = await response.json();
        history = state.attributes?.history || [];
        
        console.log(`[Printer History] ✅ REST API成功获取 ${history.length} 条记录`);
        
      } else {
        // ========== HA内部模式 ==========
        const state = this.hass.states[this.config.print_history];
        if (!state) {
          throw new Error(`未找到传感器: ${this.config.print_history}`);
        }
        
        history = state.attributes?.history || [];
        console.log(`[Printer History] ✅ HA内部模式获取 ${history.length} 条记录`);
      }
      
      // 排序（最新在前）
      this.historyData = history.sort((a, b) => 
        new Date(b.end_time || b.start_time) - new Date(a.end_time || a.start_time)
      );
      this.filteredData = [...this.historyData];
      
      console.log(`[Printer History] 数据处理完成 - 总计${this.historyData.length}条`);
      
    } catch (error) {
      console.error('[Printer History] 数据加载失败:', error);
      throw error;
    }
  }

  async refreshData() {
    console.log('[Printer History] 刷新数据...');
    await this.loadHistoryData();
    this.renderList();
    this.updateStats();
  }

  render() {
    const app = document.getElementById('app') || document.body;
    app.innerHTML = `
      <header class="page-header">
        <div class="header-left">
          <button class="back-btn" onclick="history.back()">← 返回</button>
          <h1 class="page-title">🖨️ 打印历史记录</h1>
        </div>
        <div class="header-right">
          <span class="printer-badge">${this.config.printer_name}</span>
          <button class="refresh-btn" onclick="window.pageInstance?.refreshData()">🔄</button>
        </div>
      </header>

      <section class="filter-section" id="filter-section">
        <div class="filter-row">
          <div class="search-container">
            <span class="search-icon">🔍</span>
            <input type="text" id="search-input" class="search-input"
                   placeholder="搜索任务名称、耗材类型..."
                   autocomplete="off">
          </div>

          <select id="status-filter" class="filter-select">
            <option value="">全部状态</option>
            <option value="finish">✅ 成功完成</option>
            <option value="failed">❌ 打印失败</option>
            <option value="printing">🔵 正在打印</option>
            <option value="cancelled">⚠️ 已取消</option>
          </select>

          <select id="date-filter" class="filter-select">
            <option value="">全部时间</option>
            <option value="today">今天</option>
            <option value="week">最近7天</option>
            <option value="month">最近30天</option>
            <option value="quarter">最近3个月</option>
            <option value="year">今年</option>
          </select>

          <select id="sort-filter" class="filter-select">
            <option value="newest">最新优先</option>
            <option value="oldest">最早优先</option>
            <option value="duration-asc">时长短→长</option>
            <option value="duration-desc">时长长→短</option>
            <option value="weight-asc">耗材少→多</option>
            <option value="weight-desc">耗材多→少</option>
          </select>
        </div>

        <details class="advanced-filters">
          <summary class="advanced-toggle">高级筛选 ⌄</summary>
          <div class="advanced-content">
            <div class="filter-group">
              <label>耗材类型：</label>
              <div id="type-tags" class="tag-list"></div>
            </div>
            <div class="filter-group">
              <label>颜色范围：</label>
              <div id="color-tags" class="tag-list color-tag-list"></div>
            </div>
            <div class="filter-range">
              <label>重量范围：</label>
              <input type="number" id="weight-min" placeholder="最小(g)" class="range-input">
              <span>~</span>
              <input type="number" id="weight-max" placeholder="最大(g)" class="range-input">
            </div>
            <div class="filter-range">
              <label>时长范围：</label>
              <input type="number" id="duration-min" placeholder="最小(min)" class="range-input">
              <span>~</span>
              <input type="number" id="duration-max" placeholder="最大(min)" class="range-input">
            </div>
          </div>
        </details>
      </section>

      <section class="stats-section" id="stats-section">
        ${this.renderStats()}
      </section>

      <main class="history-main" id="history-list">
        ${this.renderList()}
      </main>

      <div id="detail-modal" class="modal hidden">
        <div class="modal-backdrop" onclick="window.pageInstance?.closeModal()"></div>
        <div class="modal-content">
          <button class="modal-close" onclick="window.pageInstance?.closeModal()">✕</button>
          <div id="modal-body"></div>
        </div>
      </div>

      <div id="empty-state" class="empty-state hidden">
        <div class="empty-icon">📭</div>
        <h3>暂无符合条件的记录</h3>
        <p>尝试调整筛选条件或清空搜索关键词</p>
        <button class="clear-btn" onclick="window.pageInstance?.clearFilters()">清除所有筛选</button>
      </div>
    `;

    // 渲染高级筛选标签
    this.renderFilterTags();
  }

  renderStats() {
    const total = this.filteredData.length;
    const success = this.filteredData.filter(h => h.status === 'finish').length;
    const failed = this.filteredData.filter(h => h.status === 'failed').length;
    const successRate = total > 0 ? ((success / total) * 100).toFixed(1) : '0';
    
    const totalWeight = this.filteredData.reduce((sum, h) => sum + (h.total_weight || 0), 0);
    const totalLength = this.filteredData.reduce((sum, h) => sum + (h.total_length || 0), 0);
    
    let totalMinutes = 0;
    this.filteredData.forEach(item => {
      if (item.start_time && item.end_time) {
        const diff = new Date(item.end_time) - new Date(item.start_time);
        totalMinutes += diff / (1000 * 60);
      }
    });

    return `
      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-value">${total}</div>
          <div class="stat-label">总记录数</div>
        </div>
        <div class="stat-card success">
          <div class="stat-value">${success}</div>
          <div class="stat-label">✅ 成功</div>
        </div>
        <div class="stat-card failed">
          <div class="stat-value">${failed}</div>
          <div class="stat-label">❌ 失败</div>
        </div>
        <div class="stat-card rate">
          <div class="stat-value" style="color: ${successRate >= 80 ? '#4caf50' : '#ff9800'}">${successRate}%</div>
          <div class="stat-label">成功率</div>
        </div>
        <div class="stat-card weight">
          <div class="stat-value">${totalWeight.toFixed(1)}g</div>
          <div class="stat-label">总耗材重</div>
        </div>
        <div class="stat-card length">
          <div class="stat-value">${totalLength.toFixed(1)}m</div>
          <div class="stat-label">总耗材长</div>
        </div>
        <div class="stat-card duration">
          <div class="stat-value">${this.formatTotalDuration(totalMinutes)}</div>
          <div class="stat-label">总打印时长</div>
        </div>
      </div>
    `;
  }

  formatTotalDuration(minutes) {
    if (!minutes || minutes <= 0) return '0分钟';
    
    const hours = Math.floor(minutes / 60);
    const mins = Math.round(minutes % 60);
    
    if (hours === 0) return `${mins}分钟`;
    if (mins === 0) return `${hours}小时`;
    return `${hours}小时${mins}分`;
  }

  renderList() {
    if (this.filteredData.length === 0) {
      document.getElementById('empty-state')?.classList.remove('hidden');
      document.getElementById('history-list').innerHTML = '';
      return '';
    }
    
    document.getElementById('empty-state')?.classList.add('hidden');

    return this.filteredData.map((item, index) => this.renderItem(item, index)).join('');
  }

  renderItem(item, index) {
    const taskName = this.escapeHtml(item.task_name || '未命名任务');
    const status = item.status || 'unknown';
    
    // 状态配置
    const statusMap = {
      'finish': { text: '成功', class: 'badge-success', icon: '✅' },
      'failed': { text: '失败', class: 'badge-failed', icon: '❌' },
      'printing': { text: '进行中', class: 'badge-printing', icon: '🔄' },
      'cancelled': { text: '已取消', class: 'badge-cancelled', icon: '⚠️' }
    };
    const statusInfo = statusMap[status] || { text: '未知', class: '', icon: '❓' };

    // 打印参数
    const layerHeight = item.layer_height || '-';
    const layers = item.layers || item.total_layers || '-';
    const infill = item.infill ? `${item.infill}%` : '-';

    // 时间信息
    const endTime = this.formatDateTime(item.end_time || item.start_time);
    const duration = this.calculateDuration(item);

    // 耗材信息
    const filamentType = this.escapeHtml(item.filament_type || '未知');
    const weight = item.total_weight ? `${item.total_weight.toFixed(1)}g` : '-';
    const length = item.total_length ? `${item.total_length.toFixed(1)}m` : '-';
    const colorsUsed = item.colors_used || [];

    // 缩略图
    const thumbnailBg = colorsUsed.length > 0 
      ? `linear-gradient(135deg, ${colorsUsed[0]}, ${colorsUsed[1] || colorsUsed[0]})`
      : 'linear-gradient(135deg, #e3f2fd, #bbdefb)';
    
    const colorBar = colorsUsed.length > 0 
      ? `<div class="color-bar">${colorsUsed.map(c => `<span style="background:${c}"></span>`).join('')}</div>`
      : '';

    // 多色标识
    const multiColorBadge = colorsUsed.length > 1 
      ? `<span class="multi-color-badge">🎨 ${colorsUsed.length}色</span>` 
      : '';

    return `
      <article class="history-item" data-index="${index}" onclick="window.pageInstance?.showDetail(${index})">
        <div class="status-badge ${statusInfo.class}">${statusInfo.icon} ${statusInfo.text}</div>

        <div class="thumbnail" style="background: ${thumbnailBg}">
          <span class="thumbnail-icon">${statusInfo.icon}</span>
          ${colorBar}
        </div>

        <div class="item-content">
          <h3 class="task-name">${taskName} ${multiColorBadge}</h3>
          
          <div class="params-row">
            <span class="param">层高 ${layerHeight}</span>
            <span class="param">${layers}层</span>
            <span class="param">填充 ${infill}</span>
            ${weight !== '-' ? `<span class="param weight-param">⚖️ ${weight}</span>` : ''}
          </div>

          <div class="meta-row">
            <span class="meta">⏱️ ${duration}</span>
            <span class="meta">🧵 ${filamentType}</span>
            ${length !== '-' ? `<span class="meta">📏 ${length}</span>` : ''}
          </div>

          <div class="datetime-row">
            <span>📅 ${endTime}</span>
            ${item.tray_id ? `<span>💿 第${item.tray_id}盘</span>` : ''}
          </div>
        </div>

        <div class="arrow-indicator">›</div>
      </article>
    `;
  }

  formatDateTime(dateStr) {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    const pad = n => String(n).padStart(2, '0');
    return `${date.getFullYear()}/${pad(date.getMonth()+1)}/${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
  }

  calculateDuration(item) {
    if (!item.start_time || !item.end_time) {
      if (item.duration_minutes) {
        return this.formatDuration(item.duration_minutes);
      }
      return '-';
    }
    
    const diffMs = new Date(item.end_time) - new Date(item.start_time);
    const minutes = diffMs / (1000 * 60);
    return this.formatDuration(minutes);
  }

  formatDuration(minutes) {
    if (!minutes || minutes <= 0) return '-';
    minutes = parseFloat(minutes);
    
    if (minutes < 60) return `${Math.round(minutes)}分钟`;
    const hours = Math.floor(minutes / 60);
    const mins = Math.round(minutes % 60);
    return mins > 0 ? `${hours}h${mins}m` : `${hours}小时`;
  }

  showDetail(index) {
    const item = this.filteredData[index];
    if (!item) return;

    const modal = document.getElementById('detail-modal');
    const body = document.getElementById('modal-body');
    
    const statusMap = {
      'finish': { text: '成功完成', class: 'detail-success', icon: '✅' },
      'failed': { text: '打印失败', class: 'detail-failed', icon: '❌' },
      'printing': { text: '正在打印', class: 'detail-printing', icon: '🔄' },
      'cancelled': { text: '已取消', class: 'detail-cancelled', icon: '⚠️' }
    };
    const statusInfo = statusMap[item.status] || { text: '未知', class: '', icon: '❓' };

    const colorsUsed = item.colors_used || [];
    const colorDetailsHtml = colorsUsed.length > 0 ? `
      <div class="detail-section">
        <h4>🎨 颜色使用明细</h4>
        <div class="color-detail-list">
          ${colorsUsed.map((color, i) => `
            <div class="color-detail-item">
              <span class="color-dot" style="background:${color}"></span>
              <span>${this.formatColorName(color)}</span>
              ${item.color_usage && item.color_usage[i] ? `<span class="color-weight">${item.color_usage[i].weight_g}g</span>` : ''}
            </div>
          `).join('')}
        </div>
      </div>
    ` : '';

    body.innerHTML = `
      <div class="detail-header ${statusInfo.class}">
        <span class="detail-status-icon">${statusInfo.icon}</span>
        <h2>${this.escapeHtml(item.task_name || '未命名任务')}</h2>
        <span class="detail-status-text">${statusInfo.text}</span>
      </div>

      <div class="detail-body">
        <div class="detail-grid">
          <div class="detail-item">
            <span class="detail-label">开始时间</span>
            <span class="detail-value">${this.formatDateTime(item.start_time)}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">结束时间</span>
            <span class="detail-value">${this.formatDateTime(item.end_time)}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">打印时长</span>
            <span class="detail-value highlight">${this.calculateDuration(item)}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">耗材重量</span>
            <span class="detail-value highlight">${item.total_weight ? item.total_weight.toFixed(1) + 'g' : '-'}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">耗材长度</span>
            <span class="detail-value">${item.total_length ? item.total_length.toFixed(1) + 'm' : '-'}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">耗材类型</span>
            <span class="detail-value">${this.escapeHtml(item.filament_type || '-')}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">层高</span>
            <span class="detail-value">${item.layer_height || '-'}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">层数</span>
            <span class="detail-value">${item.layers || item.total_layers || '-'}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">填充率</span>
            <span class="detail-value">${item.infill ? item.infill + '%' : '-'}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">盘号</span>
            <span class="detail-value">${item.tray_id || '-'}</span>
          </div>
        </div>

        ${colorDetailsHtml}

        ${item.multi_color_summary ? `
          <div class="detail-section">
            <h4>📊 多色打印统计</h4>
            <div class="multi-stat">
              <div class="multi-stat-item">
                <span>颜色切换次数</span>
                <strong>${item.multi_color_summary.color_changes_count || item.color_changes_count || 0}</strong>
              </div>
              <div class="multi-stat-item">
                <span>使用的颜色数</span>
                <strong>${item.total_colors || colorsUsed.length}</strong>
              </div>
            </div>
          </div>
        ` : ''}

        ${item.error_message ? `
          <div class="detail-section error-section">
            <h4>⚠️ 错误信息</h4>
            <p class="error-text">${this.escapeHtml(item.error_message)}</p>
          </div>
        ` : ''}
      </div>

      <div class="detail-footer">
        <button class="action-btn" onclick="window.pageInstance?.closeModal()">关闭</button>
      </div>
    `;

    modal.classList.remove('hidden');
    document.body.style.overflow = 'hidden';
  }

  closeModal() {
    document.getElementById('detail-modal')?.classList.add('hidden');
    document.body.style.overflow = '';
  }

  formatColorName(colorCode) {
    if (!colorCode) return '未知';
    const code = colorCode.replace('#', '').substring(0, 6).toUpperCase();
    
    const names = {
      'FFFFFF': '纯白', '000000': '纯黑', '808080': '灰色', '898989': '中性灰',
      'F72323': '正红', 'FF0000': '亮红', '23C160': '翠绿', '00FF00': '荧光绿',
      'FFF144': '柠檬黄', 'FFFF00': '纯黄', '1AD2FF': '天蓝', '0000FF': '纯蓝',
      '9B59B6': '紫罗兰', 'FF69B4': '热粉红'
    };
    
    return names[code] || `#${code}`;
  }

  bindEvents() {
    // 搜索框输入事件（防抖）
    const searchInput = document.getElementById('search-input');
    let searchTimeout;
    searchInput?.addEventListener('input', () => {
      clearTimeout(searchTimeout);
      searchTimeout = setTimeout(() => this.applyFilters(), 300);
    });

    // 筛选下拉框变化事件
    ['status-filter', 'date-filter', 'sort-filter'].forEach(id => {
      document.getElementById(id)?.addEventListener('change', () => this.applyFilters());
    });

    // 高级筛选数值输入
    ['weight-min', 'weight-max', 'duration-min', 'duration-max'].forEach(id => {
      document.getElementById(id)?.addEventListener('input', () => this.applyFilters());
    });

    // ESC键关闭弹窗
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') this.closeModal();
    });
  }

  applyFilters() {
    const searchValue = (document.getElementById('search-input')?.value || '').toLowerCase().trim();
    const statusValue = document.getElementById('status-filter')?.value || '';
    const dateValue = document.getElementById('date-filter')?.value || '';
    const sortValue = document.getElementById('sort-filter')?.value || 'newest';
    
    const weightMin = parseFloat(document.getElementById('weight-min')?.value) || 0;
    const weightMax = parseFloat(document.getElementById('weight-max')?.value) || Infinity;
    const durationMin = parseFloat(document.getElementById('duration-min')?.value) || 0;
    const durationMax = parseFloat(document.getElementById('duration-max')?.value) || Infinity;

    // 开始过滤
    let filtered = [...this.historyData];

    // 1. 关键词搜索
    if (searchValue) {
      filtered = filtered.filter(item => {
        const name = (item.task_name || '').toLowerCase();
        const type = (item.filament_type || '').toLowerCase();
        return name.includes(searchValue) || type.includes(searchValue);
      });
    }

    // 2. 状态筛选
    if (statusValue) {
      filtered = filtered.filter(item => item.status === statusValue);
    }

    // 3. 日期范围筛选
    if (dateValue) {
      const now = new Date();
      filtered = filtered.filter(item => {
        const itemDate = new Date(item.end_time || item.start_time);
        const diffDays = (now - itemDate) / (1000 * 60 * 60 * 24);
        
        switch (dateValue) {
          case 'today': return diffDays <= 1;
          case 'week': return diffDays <= 7;
          case 'month': return diffDays <= 30;
          case 'quarter': return diffDays <= 90;
          case 'year': return diffDays <= 365;
          default: return true;
        }
      });
    }

    // 4. 重量范围筛选
    filtered = filtered.filter(item => {
      const weight = item.total_weight || 0;
      return weight >= weightMin && weight <= weightMax;
    });

    // 5. 时长范围筛选
    filtered = filtered.filter(item => {
      let duration = 0;
      if (item.duration_minutes) {
        duration = parseFloat(item.duration_minutes);
      } else if (item.start_time && item.end_time) {
        duration = (new Date(item.end_time) - new Date(item.start_time)) / (1000 * 60);
      }
      return duration >= durationMin && duration <= durationMax;
    });

    // 6. 排序
    switch (sortValue) {
      case 'oldest':
        filtered.sort((a, b) => new Date(a.end_time) - new Date(b.end_time));
        break;
      case 'duration-asc':
        filtered.sort((a, b) => (a.duration_minutes || 0) - (b.duration_minutes || 0));
        break;
      case 'duration-desc':
        filtered.sort((a, b) => (b.duration_minutes || 0) - (a.duration_minutes || 0));
        break;
      case 'weight-asc':
        filtered.sort((a, b) => (a.total_weight || 0) - (b.total_weight || 0));
        break;
      case 'weight-desc':
        filtered.sort((a, b) => (b.total_weight || 0) - (a.total_weight || 0));
        break;
      case 'newest':
      default:
        filtered.sort((a, b) => new Date(b.end_time) - new Date(a.end_time));
    }

    this.filteredData = filtered;
    
    // 更新UI
    this.renderList();
    this.updateStats();
  }

  updateStats() {
    const statsSection = document.getElementById('stats-section');
    if (statsSection) {
      statsSection.innerHTML = this.renderStats();
    }
  }

  clearFilters() {
    document.getElementById('search-input').value = '';
    document.getElementById('status-filter').value = '';
    document.getElementById('date-filter').value = '';
    document.getElementById('sort-filter').value = 'newest';
    document.getElementById('weight-min').value = '';
    document.getElementById('weight-max').value = '';
    document.getElementById('duration-min').value = '';
    document.getElementById('duration-max').value = '';
    
    this.applyFilters();
  }

  renderFilterTags() {
    // 提取所有唯一的耗材类型
    const types = [...new Set(this.historyData.map(h => h.filament_type).filter(Boolean))];
    const typesContainer = document.getElementById('type-tags');
    if (typesContainer) {
      typesContainer.innerHTML = types.map(type => `
        <label class="tag-label">
          <input type="checkbox" name="filament_type" value="${this.escapeHtml(type)}"
                 onchange="window.pageInstance?.applyFilters()">
          <span class="tag">${this.escapeHtml(type)}</span>
        </label>
      `).join('');
    }

    // 提取所有唯一的颜色
    const allColors = this.historyData.flatMap(h => h.colors_used || []);
    const uniqueColors = [...new Set(allColors)];
    const colorsContainer = document.getElementById('color-tags');
    if (colorsContainer) {
      colorsContainer.innerHTML = uniqueColors.slice(0, 20).map(color => `
        <label class="tag-label color-tag-label">
          <input type="checkbox" name="color" value="${color}"
                 onchange="window.pageInstance?.applyFilters()">
          <span class="tag color-tag" style="background:${color}; border-color:${color}"></span>
        </label>
      `).join('');
    }
  }

  escapeHtml(str) {
    if (str === null || str === undefined) return '';
    const div = document.createElement('div');
    div.textContent = String(str);
    return div.innerHTML;
  }
}

// ==================== CSS样式 ====================
const styles = `
/* ========== v1.2 暗色主题（Dark Mode）========== */
:root {
  --bg-primary: #0d1117;
  --bg-secondary: #161b22;
  --bg-tertiary: #21262d;
  --bg-card: rgba(255,255,255,0.04);
  --bg-card-hover: rgba(255,255,255,0.08);
  --border-color: rgba(255,255,255,0.1);
  --border-color-light: rgba(255,255,255,0.06);
  --text-primary: #e6edf3;
  --text-secondary: #8b949e;
  --text-muted: #6e7681;
  --accent-primary: #58a6ff;
  --accent-gradient: linear-gradient(135deg, #238636, #2ea043);
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Noto Sans SC', sans-serif;
  background: var(--bg-primary);
  color: var(--text-primary);
  line-height: 1.6;
}

/* 页面头部 - 深蓝渐变 */
.page-header {
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
  color: var(--text-primary);
  padding: 16px 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  position: sticky;
  top: 0;
  z-index: 100;
  box-shadow: 0 4px 20px rgba(0,0,0,0.4), 0 0 40px rgba(88,166,255,0.05);
  border-bottom: 1px solid var(--border-color);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.back-btn {
  background: rgba(255,255,255,0.08);
  border: 1px solid var(--border-color);
  color: var(--text-primary);
  padding: 8px 16px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 600;
  transition: all 0.3s;
}

.back-btn:hover {
  background: rgba(88,166,255,0.15);
  border-color: var(--accent-primary);
  transform: translateX(-2px);
}

.page-title {
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.5px;
  background: linear-gradient(135deg, #58a6ff, #79c0ff);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.printer-badge {
  background: linear-gradient(135deg, rgba(35,134,54,0.2), rgba(46,160,67,0.15));
  border: 1px solid rgba(35,134,54,0.3);
  color: #3fb950;
  padding: 6px 14px;
  border-radius: 20px;
  font-size: 13px;
  font-weight: 600;
}

.refresh-btn {
  background: rgba(255,255,255,0.08);
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
  width: 40px;
  height: 40px;
  border-radius: 50%;
  cursor: pointer;
  font-size: 18px;
  transition: all 0.3s;
}

.refresh-btn:hover {
  background: rgba(88,166,255,0.15);
  border-color: var(--accent-primary);
  color: var(--accent-primary);
  transform: rotate(180deg);
}

/* 筛选区域 - 半透明深色卡片 */
.filter-section {
  background: var(--bg-secondary);
  padding: 20px 24px;
  border-bottom: 1px solid var(--border-color);
  backdrop-filter: blur(10px);
}

.filter-row {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.search-container {
  flex: 1;
  min-width: 280px;
  position: relative;
}

.search-icon {
  position: absolute;
  left: 14px;
  top: 50%;
  transform: translateY(-50%);
  font-size: 16px;
  color: var(--text-muted);
}

.search-input {
  width: 100%;
  padding: 12px 16px 12px 42px;
  border: 1px solid var(--border-color);
  border-radius: 10px;
  font-size: 14px;
  background: var(--bg-tertiary);
  color: var(--text-primary);
  transition: all 0.3s;
}

.search-input::placeholder {
  color: var(--text-muted);
}

.search-input:focus {
  outline: none;
  border-color: var(--accent-primary);
  box-shadow: 0 0 0 3px rgba(88,166,255,0.15);
  background: var(--bg-primary);
}

.filter-select {
  padding: 12px 16px;
  border: 1px solid var(--border-color);
  border-radius: 10px;
  font-size: 14px;
  background: var(--bg-tertiary);
  color: var(--text-primary);
  cursor: pointer;
  min-width: 150px;
  transition: all 0.3s;
}

.filter-select:focus {
  outline: none;
  border-color: var(--accent-primary);
  box-shadow: 0 0 0 3px rgba(88,166,255,0.15);
}

/* 高级筛选 */
.advanced-filters {
  margin-top: 16px;
}

.advanced-toggle {
  cursor: pointer;
  font-weight: 600;
  color: var(--accent-primary);
  padding: 8px 0;
  user-select: none;
  transition: opacity 0.3s;
}

.advanced-toggle:hover {
  opacity: 0.8;
}

.advanced-content {
  margin-top: 12px;
  padding-top: 16px;
  border-top: 1px dashed var(--border-color);
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 16px;
}

.filter-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.filter-group label {
  font-weight: 600;
  font-size: 13px;
  color: var(--text-secondary);
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.tag-label {
  cursor: pointer;
}

.tag-label input {
  display: none;
}

.tag-label input:checked + .tag {
  background: var(--accent-primary);
  color: white;
  border-color: var(--accent-primary);
  transform: scale(1.05);
  box-shadow: 0 4px 12px rgba(88,166,255,0.3);
}

.tag {
  display: inline-block;
  padding: 6px 14px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  transition: all 0.3s;
}

.color-tag {
  width: 28px;
  height: 28px;
  padding: 0;
  border-radius: 50%;
  border-width: 2px;
}

.filter-range {
  display: flex;
  align-items: center;
  gap: 8px;
}

.range-input {
  width: 90px;
  padding: 8px 12px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  font-size: 13px;
  background: var(--bg-tertiary);
  color: var(--text-primary);
}

.range-input::placeholder {
  color: var(--text-muted);
}

/* 统计区域 - 玻璃态卡片 */
.stats-section {
  padding: 20px 24px;
  background: var(--bg-secondary);
  border-bottom: 1px solid var(--border-color);
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 16px;
}

.stat-card {
  background: var(--bg-card);
  backdrop-filter: blur(10px);
  padding: 18px;
  border-radius: 12px;
  text-align: center;
  border: 1px solid var(--border-color-light);
  transition: all 0.3s cubic-bezier(0.25, 0.46, 0.45, 0.94);
}

.stat-card:hover {
  transform: translateY(-4px);
  background: var(--bg-card-hover);
  box-shadow: 0 8px 24px rgba(0,0,0,0.3);
  border-color: var(--border-color);
}

.stat-card.success { 
  border-left: 4px solid #3fb950; 
}
.stat-card.success:hover { 
  box-shadow: 0 8px 24px rgba(63,185,80,0.15); 
}

.stat-card.failed { 
  border-left: 4px solid #f85149; 
}
.stat-card.failed:hover { 
  box-shadow: 0 8px 24px rgba(248,81,73,0.15); 
}

.stat-card.rate { 
  border-left: 4px solid var(--accent-primary); 
}
.stat-card.rate:hover { 
  box-shadow: 0 8px 24px rgba(88,166,255,0.15); 
}

.stat-card.weight { 
  border-left: 4px solid #d29922; 
}
.stat-card.length { 
  border-left: 4px solid #a371f7; 
}
.stat-card.duration { 
  border-left: 4px solid #39d353; 
}

.stat-value {
  font-size: 26px;
  font-weight: 800;
  color: var(--text-primary);
  margin-bottom: 4px;
}

.stat-label {
  font-size: 12px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  font-weight: 600;
}

/* 历史列表 */
.history-main {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
}

.history-item {
  display: flex;
  gap: 18px;
  background: var(--bg-card);
  backdrop-filter: blur(10px);
  padding: 20px;
  border-radius: 16px;
  margin-bottom: 16px;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.25, 0.46, 0.45, 0.94);
  border: 1px solid var(--border-color-light);
  position: relative;
  overflow: hidden;
}

.history-item::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 4px;
  background: linear-gradient(180deg, var(--accent-primary), #79c0ff);
  opacity: 0;
  transition: opacity 0.3s;
}

.history-item:hover {
  transform: translateX(8px);
  background: var(--bg-card-hover);
  border-color: rgba(88,166,255,0.25);
  box-shadow: 0 8px 32px rgba(0,0,0,0.3), 0 0 48px rgba(88,166,255,0.08);
}

.history-item:hover::before {
  opacity: 1;
}

.status-badge {
  position: absolute;
  top: 14px;
  right: 14px;
  padding: 6px 16px;
  border-radius: 20px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.5px;
  backdrop-filter: blur(10px);
}

.badge-success { 
  background: rgba(63,185,80,0.15); 
  color: #3fb950; 
  border: 1px solid rgba(63,185,80,0.3); 
}
.badge-failed { 
  background: rgba(248,81,73,0.15); 
  color: #f85149; 
  border: 1px solid rgba(248,81,73,0.3); 
}
.badge-printing { 
  background: rgba(88,166,255,0.15); 
  color: #58a6ff; 
  border: 1px solid rgba(88,166,255,0.3); 
  animation: pulse-dark 2s infinite; 
}
.badge-cancelled { 
  background: rgba(210,153,34,0.15); 
  color: #d29922; 
  border: 1px solid rgba(210,153,34,0.3); 
}

@keyframes pulse-dark {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

.thumbnail {
  width: 88px;
  height: 88px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  position: relative;
  overflow: hidden;
  box-shadow: 0 4px 16px rgba(0,0,0,0.3);
  border: 1px solid var(--border-color);
}

.thumbnail-icon {
  font-size: 32px;
  filter: drop-shadow(0 2px 8px rgba(0,0,0,0.4));
}

.color-bar {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 7px;
  display: flex;
}

.color-bar span {
  flex: 1;
}

.item-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
}

.task-name {
  font-size: 17px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.3;
  padding-right: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.multi-color-badge {
  display: inline-block;
  background: linear-gradient(135deg, rgba(163,113,247,0.2), rgba(188,118,226,0.15));
  color: #a371f7;
  padding: 3px 10px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 700;
  vertical-align: middle;
  margin-left: 8px;
  border: 1px solid rgba(163,113,247,0.3);
}

.params-row {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.param {
  background: rgba(88,166,255,0.1);
  color: var(--accent-primary);
  padding: 4px 12px;
  border-radius: 14px;
  font-size: 12px;
  font-weight: 600;
  border: 1px solid rgba(88,166,255,0.15);
}

.weight-param {
  background: rgba(210,153,34,0.1);
  color: #d29922;
  border-color: rgba(210,153,34,0.15);
}

.meta-row {
  display: flex;
  gap: 16px;
  font-size: 13px;
  color: var(--text-secondary);
}

.meta {
  display: flex;
  align-items: center;
  gap: 4px;
}

.datetime-row {
  font-size: 12px;
  color: var(--text-muted);
  padding-top: 8px;
  border-top: 1px dashed var(--border-color-light);
  display: flex;
  gap: 16px;
}

.arrow-indicator {
  align-self: center;
  font-size: 28px;
  color: var(--text-muted);
  transition: all 0.3s;
}

.history-item:hover .arrow-indicator {
  color: var(--accent-primary);
  transform: translateX(4px);
}

/* 弹窗 - 深色玻璃态 */
.modal {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.modal.hidden {
  display: none;
}

.modal-backdrop {
  position: absolute;
  inset: 0;
  background: rgba(0,0,0,0.75);
  backdrop-filter: blur(8px);
}

.modal-content {
  position: relative;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 20px;
  max-width: 600px;
  width: 100%;
  max-height: 85vh;
  overflow-y: auto;
  box-shadow: 0 24px 64px rgba(0,0,0,0.5), 0 0 80px rgba(88,166,255,0.1);
  animation: modalIn 0.3s ease;
}

@keyframes modalIn {
  from { opacity: 0; transform: scale(0.95) translateY(20px); }
  to { opacity: 1; transform: scale(1) translateY(0); }
}

.modal-close {
  position: absolute;
  top: 16px;
  right: 16px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
  width: 36px;
  height: 36px;
  border-radius: 50%;
  cursor: pointer;
  font-size: 18px;
  transition: all 0.3s;
  z-index: 1;
}

.modal-close:hover {
  background: #f85149;
  color: white;
  border-color: #f85149;
  transform: rotate(90deg);
}

.detail-header {
  padding: 32px 28px 24px;
  text-align: center;
  color: white;
}

.detail-header.detail-success { background: linear-gradient(135deg, #238636, #2ea043); }
.detail-header.detail-failed { background: linear-gradient(135deg, #da3633, #f85149); }
.detail-header.detail-printing { background: linear-gradient(135deg, #1f6feb, #388bfd); }
.detail-header.detail-cancelled { background: linear-gradient(135deg, #9e6a03, #bb8009); }

.detail-status-icon {
  font-size: 48px;
  display: block;
  margin-bottom: 12px;
  filter: drop-shadow(0 4px 8px rgba(0,0,0,0.3));
}

.detail-header h2 {
  font-size: 22px;
  font-weight: 700;
  margin-bottom: 8px;
}

.detail-status-text {
  font-size: 14px;
  opacity: 0.9;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.detail-body {
  padding: 24px 28px;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}

.detail-item {
  background: var(--bg-tertiary);
  padding: 14px;
  border-radius: 10px;
  border: 1px solid var(--border-color-light);
}

.detail-label {
  display: block;
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 6px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.detail-value {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
}

.detail-value.highlight {
  color: var(--accent-primary);
  font-size: 18px;
}

.detail-section {
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid var(--border-color);
}

.detail-section h4 {
  font-size: 15px;
  font-weight: 700;
  margin-bottom: 14px;
  color: var(--text-primary);
}

.color-detail-list {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.color-detail-item {
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--bg-tertiary);
  padding: 8px 14px;
  border-radius: 20px;
  font-size: 13px;
  color: var(--text-secondary);
  border: 1px solid var(--border-color-light);
}

.color-dot {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: 2px solid rgba(255,255,255,0.3);
  box-shadow: 0 2px 6px rgba(0,0,0,0.3);
}

.color-weight {
  font-weight: 700;
  color: var(--accent-primary);
}

.multi-stat {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.multi-stat-item {
  background: var(--bg-tertiary);
  padding: 14px;
  border-radius: 10px;
  text-align: center;
  border: 1px solid var(--border-color-light);
}

.multi-stat-item span {
  display: block;
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 6px;
}

.multi-stat-item strong {
  font-size: 20px;
  color: var(--accent-primary);
}

.error-section {
  background: rgba(248,81,73,0.1);
  border: 1px solid rgba(248,81,73,0.2);
  border-radius: 10px;
  padding: 14px;
}

.error-text {
  color: #f85149;
  font-size: 13px;
  line-height: 1.6;
}

.detail-footer {
  padding: 20px 28px;
  border-top: 1px solid var(--border-color);
  text-align: center;
}

.action-btn {
  background: linear-gradient(135deg, #238636, #2ea043);
  color: white;
  border: none;
  padding: 12px 40px;
  border-radius: 10px;
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.3s;
}

.action-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(35,134,54,0.4);
}

/* 空状态 */
.empty-state {
  text-align: center;
  padding: 80px 24px;
  color: var(--text-muted);
}

.empty-state.hidden {
  display: none;
}

.empty-icon {
  font-size: 72px;
  margin-bottom: 20px;
  opacity: 0.3;
}

.empty-state h3 {
  font-size: 20px;
  margin-bottom: 10px;
  color: var(--text-secondary);
}

.clear-btn {
  margin-top: 20px;
  background: var(--accent-primary);
  color: white;
  border: none;
  padding: 10px 28px;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s;
}

.clear-btn:hover {
  background: #1f6feb;
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(88,166,255,0.3);
}

/* 错误容器 */
.error-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  text-align: center;
  padding: 40px;
  background: var(--bg-primary);
}

.error-icon {
  font-size: 64px;
  margin-bottom: 20px;
  opacity: 0.5;
}

.error-container h2 {
  font-size: 24px;
  color: var(--text-primary);
  margin-bottom: 12px;
}

.error-container p {
  color: var(--text-secondary);
  margin-bottom: 24px;
}

.retry-btn {
  background: var(--accent-primary);
  color: white;
  border: none;
  padding: 12px 32px;
  border-radius: 10px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s;
}

.retry-btn:hover {
  background: #1f6feb;
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(88,166,255,0.3);
}

/* 加载屏幕 - 暗色版本 */
.loading-screen {
  background: linear-gradient(135deg, #0d1117 0%, #161b22 50%, #1a1a2e 100%);
}

/* 响应式 */
@media (max-width: 768px) {
  .page-header {
    padding: 12px 16px;
  }
  
  .page-title {
    font-size: 18px;
  }
  
  .filter-row {
    flex-direction: column;
  }
  
  .search-container {
    min-width: auto;
  }
  
  .filter-select {
    width: 100%;
  }
  
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  
  .history-item {
    flex-direction: column;
  }
  
  .thumbnail {
    width: 100%;
    height: 140px;
  }
  
  .status-badge {
    position: static;
    align-self: flex-start;
  }
  
  .task-name {
    padding-right: 0;
  }
  
  .arrow-indicator {
    display: none;
  }
  
  .detail-grid {
    grid-template-columns: 1fr;
  }
}
`;

// 注入样式
const styleSheet = document.createElement('style');
styleSheet.textContent = styles;
document.head.appendChild(styleSheet);

// 创建应用容器
const appDiv = document.createElement('div');
appDiv.id = 'app';
document.body.appendChild(appDiv);

// 全局暴露实例
window.pageInstance = new PrinterHistoryPage();

// 启动应用
window.pageInstance.init();

console.log('[Printer History] 独立历史记录页面v1.0 已启动');
