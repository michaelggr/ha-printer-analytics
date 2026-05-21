/**
 * 打印机分析卡片 - v5.11.8
 * 版本: 5.11.8 (2026-05-22) - 修复任务名称显示配置参数、完成时间显示00、耗材类型颜色未显示、BOM乱码
 *
 * 设计特点:
 * - 顶部打印机实时监控（多打印机卡片）
 * - 统计分析：含之最内容，支持按打印机切换
 * - 全部历史：多打印机合并显示，支持打印机筛选
 * - 现代化渐变设计 + 玻璃拟态效果
 * - 日期筛选 + 删除功能（二次确认）
 * - 任务封面图 + 详情弹窗（含快照图）
 */

const PRINTER_ICON_URL = 'https://img2.baidu.com/it/u=446945898,2280838356&fm=253&fmt=auto&app=138&f=JPEG?w=500&h=500';

const ICON_3D_PRINTER = (size = 28, inline = false) => {
  const baseStyle = 'object-fit:contain;border-radius:4px;';
  const displayStyle = inline ? 'display:inline-block;vertical-align:middle;' : 'display:block;margin:0 auto;';
  return `<img src="${PRINTER_ICON_URL}" width="${size}" height="${size}" style="${baseStyle}${displayStyle}" alt="3D Printer" />`;
};
class PrinterAnalyticsCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._lastRenderedData = null;
    this._renderDebounce = null;
    this._isRendering = false;
    this._activeTab = 'stats';
    this._mode = '';
    this._selectedPrinter = '全部';
    this._selectedRecords = new Set();
    this._deleteConfirmVisible = false;
    this._detailRecord = null;
    this._dateFrom = '';
    this._dateTo = '';
    this._filterStatus = '';
    this._filterColor = '';
    this._filterPrinter = '';
    this._searchQuery = '';
    this._currentPage = 1;
    this._pageSize = 20;
    this._pendingFilterStatus = '';
    this._pendingFilterColor = '';
    this._pendingDateFrom = '';
    this._pendingDateTo = '';
    this._pendingSearchQuery = '';
  }

  setConfig(config) {
    this.config = config;
    this._mode = config.mode || '';
    if (this._mode === 'history') this._activeTab = 'merged';
    this.render();
  }

  set hass(hass) {
    this._hass = hass;
    if (hass && this.config) {
      if (this._renderDebounce) {
        clearTimeout(this._renderDebounce);
      }
      this._renderDebounce = setTimeout(() => {
        this.updateData();
      }, 300);
    }
  }

  disconnectedCallback() {
    if (this._renderDebounce) {
      clearTimeout(this._renderDebounce);
      this._renderDebounce = null;
    }
    this._selectedRecords.clear();
    this._detailRecord = null;
  }

  // 获取实体属性，"全部"模式下聚合所有打印机同名属性（数值求和）
  _getAggregatedAttr(entityKey) {
    if (this._selectedPrinter !== '全部') {
      const eid = this._getEntityForPrinter(this._selectedPrinter, entityKey);
      return eid ? this._getAttr(eid) : {};
    }
    const printers = this._getPrintersConfig();
    const merged = {};
    for (const p of printers) {
      const eid = p.entities[entityKey];
      if (!eid) continue;
      const attrs = this._getAttr(eid);
      for (const k in attrs) {
        if (k === 'icon' || k === 'friendly_name') continue;
        const v = attrs[k];
        if (typeof v === 'number') {
          merged[k] = (merged[k] || 0) + v;
        } else if (typeof v === 'object' && v !== null) {
          if (!merged[k]) merged[k] = Array.isArray(v) ? [] : {};
          if (Array.isArray(v)) {
            merged[k] = [...(merged[k] || []), ...v];
          } else {
            for (const sk in v) {
              if (typeof v[sk] === 'number') {
                merged[k][sk] = ((merged[k][sk] || 0)) + v[sk];
              } else if (typeof v[sk] === 'object' && v[sk] !== null) {
                if (!merged[k][sk]) merged[k][sk] = {};
                for (const ssk in v[sk]) {
                  if (typeof v[sk][ssk] === 'number') {
                    merged[k][sk][ssk] = (merged[k][sk][ssk] || 0) + v[sk][ssk];
                  }
                }
              }
            }
          }
        }
      }
    }
    return merged;
  }

  /**
   * 获取实体状态值
   * @param {string} entityId 实体ID
   * @returns {string} 状态值
   */
  _getState(entityId) {
    const entity = this._hass?.states[entityId];
    return entity?.state || '0';
  }

  /**
   * 获取实体属性
   * @param {string} entityId 实体ID
   * @returns {object} 属性对象
   */
  _getAttr(entityId) {
    const entity = this._hass?.states[entityId];
    return entity?.attributes || {};
  }

  /**
   * 判断任务名是否是参数描述（如 "0.2mm 2层墙 15%填充"）而非模型名
   * 参数描述特征：包含层高mm、填充%、墙层数等工艺参数关键词
   */
  _isParamDescription(name) {
    if (!name || typeof name !== 'string') return false;
    // 匹配参数描述的典型模式：层高+墙层数+填充率
    return /\d+(\.\d+)?mm.*\d+层.*\d+%/.test(name) || /\d+%.*填充/.test(name);
  }

  _formatWeight(grams) {
    const g = parseFloat(grams) || 0;
    if (g >= 1000000) return `${(g / 1000).toFixed(1)}t`;
    if (g >= 1000) return `${(g / 1000).toFixed(1)}kg`;
    return `${g.toFixed(1)}g`;
  }

  _formatDurationHours(hours) {
    const h = parseFloat(hours) || 0;
    if (h < 100) return `${h.toFixed(1)}h`;
    const d = h / 24;
    if (d < 30) return `${d.toFixed(1)}天`;
    const w = d / 7;
    if (w < 52) return `${w.toFixed(1)}周`;
    const m = d / 30.44;
    return `${m.toFixed(1)}月`;
  }

  _formatDurationMinutes(totalMinutes) {
    const m = totalMinutes || 0;
    if (m < 60) return `${Math.round(m)}分`;
    if (m < 1440) return `${Math.floor(m / 60)}h${Math.round(m % 60)}m`;
    const h = m / 60;
    return this._formatDurationHours(h);
  }

  /**
   * 获取历史记录数据
   * @returns {Array} 历史记录数组
   */
  _getHistory() {
    const historyEntity = this._hass?.states[this.config.print_history];
    return historyEntity?.attributes?.history || [];
  }

  _getPrintersConfig() {
    if (this.config.printers && Array.isArray(this.config.printers)) {
      return this.config.printers.map(p => ({
        printer_name: p.printer_name || '未命名',
        entities: p,
      }));
    }

    const entities = {};
    const knownKeys = [
      'print_history', 'total_prints', 'success_rate', 'average_duration',
      'total_print_duration', 'total_energy', 'material_stats_7d',
      'material_stats_30d', 'material_stats_lifetime', 'duration_distribution',
      'activity_heatmap', 'failure_stage_distribution', 'filament_success_stats',
      'print_status', 'current_task', 'print_progress', 'current_weight',
      'current_length', 'total_usage', 'nozzle_temperature', 'bed_temperature',
      'chamber_temperature', 'active_tray', 'ams_1_tray_1', 'ams_1_tray_2',
      'ams_1_tray_3', 'ams_1_tray_4', 'wifi_signal', 'speed_profile', 'nozzle_size',
    ];
    for (const k of knownKeys) {
      if (this.config[k]) entities[k] = this.config[k];
    }
    return [{
      printer_name: this.config.printer_name || this.config.title?.replace(/[🖨️ ]/g, '') || '本机',
      entities,
    }];
  }

  /**
   * 获取指定打印机的历史记录（支持"全部"聚合）
   */
  _getHistoryForPrinter(printerName) {
    const printers = this._getPrintersConfig();
    if (printerName === '全部') {
      return this._getAllMergedRecords();
    }
    const p = printers.find(x => x.printer_name === printerName);
    if (!p || !p.entities.print_history) return [];
    const entity = this._hass?.states[p.entities.print_history];
    const records = entity?.attributes?.history || [];
    records.forEach(r => { r._printer_name = printerName; });
    return records;
  }

  /**
   * 判断打印记录是否为成功状态（兼容中英文）
   */
  _isSuccessStatus(status) {
    return status === 'finish' || status === '完成' || status === '成功';
  }

  /**
   * 判断打印记录是否为失败状态（兼容中英文）
   */
  _isFailedStatus(status) {
    return status === 'fail' || status === 'failed' || status === '失败';
  }

  /**
   * 判断打印记录是否为取消状态（兼容中英文）
   */
  _isCancelledStatus(status) {
    return status === 'cancelled' || status === '已取消';
  }

  _isStatusMatch(status, filter) {
    if (!filter) return true;
    if (filter === 'finish') return this._isSuccessStatus(status);
    if (filter === 'failed') return this._isFailedStatus(status);
    if (filter === 'cancelled') return this._isCancelledStatus(status);
    return status === filter;
  }

  /**
   * 获取指定打印机的传感器实体ID
   */
  _getEntityForPrinter(printerName, entityKey) {
    const printers = this._getPrintersConfig();
    const p = printers.find(x => x.printer_name === printerName);
    return p?.entities?.[entityKey] || '';
  }

  /**
   * 获取打印机切换器 HTML
   */
  _renderPrinterSelector() {
    const printers = this._getPrintersConfig();
    if (printers.length <= 1) return '';
    const options = ['全部', ...printers.map(p => p.printer_name)];
    const buttons = options.map(name => {
      const active = this._selectedPrinter === name ? 'active' : '';
      return `<button class="printer-selector-btn ${active}" data-printer="${this._escapeHtml(name)}">${this._escapeHtml(name)}</button>`;
    }).join('');
    return `<div class="printer-selector">${buttons}</div>`;
  }

  /**
   * HTML字符转义
   * @param {string} str 输入字符串
   * @returns {string} 转义后的字符串
   */
  _escapeHtml(str) {
    if (str === null || str === undefined) return '';
    const div = document.createElement('div');
    div.textContent = String(str);
    return div.innerHTML;
  }

  _sanitizeColor(color) {
    if (!color || typeof color !== 'string') return 'transparent';
    const c = color.trim();
    if (/^#[0-9a-fA-F]{3,8}$/.test(c)) return c;
    if (/^var\(--[\w-]+\)$/.test(c)) return c;
    if (/^rgba?\(\s*[\d.]+\s*,\s*[\d.]+\s*,\s*[\d.]+\s*(?:,\s*[\d.]+\s*)?\)$/.test(c)) return c;
    if (/^hsla?\(\s*[\d.]+\s*,\s*[\d.]+%\s*,\s*[\d.]+%(?:,\s*[\d.]+\s*)?\)$/.test(c)) return c;
    return 'transparent';
  }

  /**
   * 数据降采样（用于大量数据显示）
   * @param {Array} data 原始数据
   * @param {number} threshold 阈值
   * @returns {Array} 降采样后的数据
   */
  _downsampleData(data, threshold) {
    if (data.length <= threshold) return data;
    const sampled = [];
    const step = (data.length - 2) / (threshold - 2);
    sampled.push(data[0]);
    for (let i = 1; i < threshold - 1; i++) {
      const index = Math.floor(i * step);
      if (index < data.length - 1) {
        sampled.push(data[index]);
      }
    }
    sampled.push(data[data.length - 1]);
    return sampled;
  }

  /**
   * 初始化卡片渲染
   */
  render() {
    const container = this.shadowRoot;
    if (!container) return;

    container.innerHTML = `
      <style>
        /* ==================== 基础样式 ==================== */
        :host {
          display: block;
          /* 主色调系统 */
          --primary: #6366f1;
          --primary-light: #818cf8;
          --primary-dark: #4f46e5;
          --secondary: #06b6d4;
          --accent: #f59e0b;
          --success: #22c55e;
          --danger: #ef4444;
          --warning: #f59e0b;
          
          /* 颜色系统 */
          --surface: rgba(15, 23, 42, 0.95);
          --surface-light: rgba(30, 41, 59, 0.85);
          --surface-card: rgba(51, 65, 85, 0.4);
          --text-primary: #f8fafc;
          --text-secondary: #94a3b8;
          --text-muted: #64748b;
          --border: rgba(148, 163, 184, 0.15);
          --border-light: rgba(148, 163, 184, 0.1);
          
          /* 阴影系统 */
          --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.3);
          --shadow: 0 4px 6px rgba(0, 0, 0, 0.4);
          --shadow-md: 0 10px 15px rgba(0, 0, 0, 0.5);
          --shadow-lg: 0 20px 25px rgba(0, 0, 0, 0.6);
          
          /* 圆角系统 */
          --radius-sm: 6px;
          --radius: 12px;
          --radius-md: 16px;
          --radius-lg: 24px;
          
          /* 玻璃拟态 */
          --glass-bg: rgba(15, 23, 42, 0.85);
          --glass-border: rgba(148, 163, 184, 0.2);
        }

        * {
          box-sizing: border-box;
        }

        .card {
          background: linear-gradient(145deg, var(--glass-bg), rgba(15, 23, 42, 0.95));
          backdrop-filter: blur(20px);
          border: 1px solid var(--glass-border);
          border-radius: var(--radius-lg);
          padding: 28px;
          color: var(--text-primary);
          font-family: 'Inter', 'Noto Sans SC', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
          position: relative;
          overflow: hidden;
        }

        /* 装饰背景 */
        .card::before {
          content: '';
          position: absolute;
          top: -50%;
          left: -50%;
          width: 200%;
          height: 200%;
          background: radial-gradient(ellipse at 30% 20%, rgba(99, 102, 241, 0.08) 0%, transparent 50%),
                      radial-gradient(ellipse at 70% 80%, rgba(6, 182, 212, 0.06) 0%, transparent 50%);
          pointer-events: none;
          z-index: 0;
        }

        .card-content {
          position: relative;
          z-index: 1;
        }

        /* ==================== 头部样式 ==================== */
        .header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 28px;
          padding-bottom: 20px;
          border-bottom: 1px solid var(--border);
        }

        .header-left {
          display: flex;
          align-items: center;
          gap: 16px;
        }

        .header-icon {
          width: 36px;
          height: 36px;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .header-title {
          font-size: 22px;
          font-weight: 700;
          background: linear-gradient(135deg, var(--text-primary), var(--primary-light));
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          background-clip: text;
          letter-spacing: -0.3px;
        }

        .header-badge {
          background: linear-gradient(135deg, rgba(99, 102, 241, 0.2), rgba(6, 182, 212, 0.2));
          color: var(--primary-light);
          padding: 6px 14px;
          border-radius: var(--radius);
          font-size: 12px;
          font-weight: 600;
          border: 1px solid rgba(99, 102, 241, 0.3);
        }

        /* ==================== 标签切换 ==================== */
        .tab-container {
          display: inline-flex;
          gap: 4px;
          background: var(--surface-card);
          padding: 6px;
          border-radius: var(--radius-md);
          margin-bottom: 24px;
          border: 1px solid var(--border-light);
        }

        .tab-button {
          padding: 10px 20px;
          border: none;
          background: transparent;
          color: var(--text-secondary);
          font-size: 14px;
          font-weight: 600;
          border-radius: var(--radius);
          cursor: pointer;
          transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
          position: relative;
        }

        .tab-button:hover {
          color: var(--text-primary);
          background: rgba(99, 102, 241, 0.1);
        }

        .tab-button.active {
          background: linear-gradient(135deg, var(--primary), var(--primary-dark));
          color: white;
          box-shadow: 0 4px 12px rgba(99, 102, 241, 0.4);
        }

        .tab-content {
          display: none;
          animation: fadeIn 0.3s ease-out;
        }

        .tab-content.active {
          display: block;
        }

        /* ==================== 打印机切换器 ==================== */
        .printer-selector {
          display: flex;
          gap: 6px;
          margin-bottom: 16px;
          flex-wrap: wrap;
        }

        .printer-selector-btn {
          padding: 6px 14px;
          border-radius: 20px;
          border: 1px solid var(--border);
          background: var(--surface-card);
          color: var(--text-secondary);
          font-size: 11px;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.2s ease;
        }

        .printer-selector-btn:hover {
          border-color: var(--primary);
          color: var(--primary-light);
        }

        .printer-selector-btn.active {
          background: linear-gradient(135deg, var(--primary), var(--primary-dark));
          color: #fff;
          border-color: transparent;
          box-shadow: 0 2px 8px rgba(99, 102, 241, 0.3);
        }

        /* 实时监控面板打印机切换按钮 */
        .monitor-switch-btn {
          padding: 4px 12px;
          border-radius: 16px;
          border: 1px solid var(--border);
          background: var(--surface-card);
          color: var(--text-secondary);
          font-size: 11px;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.2s ease;
          display: inline-flex;
          align-items: center;
          gap: 5px;
          white-space: nowrap;
        }
        .monitor-switch-btn:hover {
          border-color: var(--primary);
          color: var(--primary-light);
        }
        .monitor-switch-btn.active {
          background: linear-gradient(135deg, var(--primary), var(--primary-dark));
          color: #fff;
          border-color: transparent;
          box-shadow: 0 2px 8px rgba(99, 102, 241, 0.3);
        }
        .monitor-switch-dot {
          width: 6px;
          height: 6px;
          border-radius: 50%;
          flex-shrink: 0;
        }

        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(8px); }
          to { opacity: 1; transform: translateY(0); }
        }

        /* ==================== 统计卡片网格 ==================== */
        .stats-grid {
          display: flex;
          flex-wrap: wrap;
          gap: 6px;
          margin-bottom: 12px;
        }

        .stat-card {
          background: var(--surface-card);
          border-radius: var(--radius);
          padding: 6px 10px;
          text-align: center;
          border: 1px solid var(--border);
          position: relative;
          overflow: hidden;
          flex: 1 1 auto;
          min-width: 0;
        }

        .stat-card::before {
          content: '';
          position: absolute;
          top: 0; left: 0; right: 0;
          height: 2px;
          background: linear-gradient(90deg, var(--primary), var(--secondary));
        }

        .stat-icon {
          font-size: 14px;
          margin-bottom: 1px;
          display: inline-block;
        }

        .stat-value {
          font-size: 15px;
          font-weight: 700;
          line-height: 1.1;
          color: var(--primary-light);
          margin-bottom: 1px;
        }

        .stat-label {
          font-size: 9px;
          color: var(--text-secondary);
          line-height: 1;
          font-weight: 500;
          opacity: 0.8;
        }

        /* ==================== 区域标题 ==================== */
        .section-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin: 28px 0 18px 0;
          padding-bottom: 14px;
          border-bottom: 1px solid var(--border);
        }

        .section-title {
          font-size: 17px;
          font-weight: 700;
          color: var(--text-primary);
          display: flex;
          align-items: center;
          gap: 12px;
        }

        .section-icon {
          width: 36px;
          height: 36px;
          border-radius: var(--radius);
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 18px;
          background: linear-gradient(135deg, rgba(99, 102, 241, 0.2), rgba(6, 182, 212, 0.2));
          border: 1px solid var(--border);
        }

        /* ==================== 图表容器 ==================== */
        .chart-container {
          background: var(--surface-card);
          border-radius: var(--radius-md);
          padding: 24px;
          margin-bottom: 20px;
          border: 1px solid var(--border);
          transition: all 0.3s ease;
        }

        .chart-container:hover {
          box-shadow: var(--shadow);
          border-color: rgba(99, 102, 241, 0.3);
        }

        .heatmap-cell {
          aspect-ratio: 1;
          border-radius: 2px;
          min-height: 2px;
          cursor: default;
          border: 1px solid rgba(255,255,255,0.08);
          transition: all 0.15s ease;
        }

        .heatmap-cell:hover {
          transform: scale(1.3);
          z-index: 1;
        }

        .chart-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 20px;
        }

        .chart-title {
          font-size: 15px;
          font-weight: 600;
          color: var(--text-primary);
        }

        .chart-subtitle {
          font-size: 12px;
          color: var(--text-muted);
        }

        /* ==================== 统计表格 ==================== */
        .stats-table {
          width: 100%;
          border-collapse: separate;
          border-spacing: 0;
          font-size: 14px;
          border-radius: var(--radius);
          overflow: hidden;
          background: var(--surface);
        }

        .stats-table th {
          text-align: left;
          padding: 14px 18px;
          background: linear-gradient(135deg, var(--primary), var(--primary-dark));
          color: white;
          font-weight: 600;
          font-size: 12px;
          letter-spacing: 0.5px;
          text-transform: uppercase;
        }

        .stats-table td {
          padding: 14px 18px;
          border-bottom: 1px solid var(--border-light);
          color: var(--text-secondary);
        }

        .stats-table tr:last-child td { border-bottom: none; }

        .stats-table tr:hover td {
          background: rgba(99, 102, 241, 0.08);
          color: var(--text-primary);
        }

        .table-value {
          font-weight: 700;
          color: var(--primary-light);
          font-size: 15px;
        }

        /* ==================== 多色打印卡片 ==================== */
        .multi-color-card {
          background: var(--surface-card);
          border-radius: var(--radius-md);
          padding: 18px;
          margin-bottom: 14px;
          border-left: 4px solid var(--primary);
          transition: all 0.3s ease;
        }

        .multi-color-card:hover {
          transform: translateX(4px);
          box-shadow: var(--shadow);
        }

        .multi-color-card.success {
          border-left-color: var(--success);
          background: linear-gradient(135deg, rgba(34, 197, 94, 0.1), var(--surface-card));
        }

        .multi-color-card.failed {
          border-left-color: var(--danger);
          background: linear-gradient(135deg, rgba(239, 68, 68, 0.1), var(--surface-card));
        }

        .multi-color-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 12px;
        }

        .multi-color-title {
          font-size: 15px;
          font-weight: 700;
          color: var(--text-primary);
        }

        .color-tag-list {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
          margin-top: 12px;
        }

        .color-tag {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          padding: 6px 14px;
          border-radius: 20px;
          font-size: 12px;
          font-weight: 600;
          border: 1px solid rgba(255, 255, 255, 0.2);
          transition: all 0.2s ease;
        }

        .color-tag:hover {
          transform: scale(1.05);
        }

        .color-dot {
          width: 14px;
          height: 14px;
          border-radius: 50%;
          box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.3);
        }

        /* ==================== 进度条 ==================== */
        .progress-container {
          margin-top: 10px;
        }

        .progress-header {
          display: flex;
          justify-content: space-between;
          font-size: 12px;
          color: var(--text-secondary);
          margin-bottom: 6px;
          font-weight: 600;
        }

        .progress-track {
          background: rgba(15, 23, 42, 0.6);
          border-radius: 10px;
          height: 10px;
          overflow: hidden;
          position: relative;
          box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.3);
        }

        .progress-fill {
          height: 100%;
          border-radius: 10px;
          transition: width 0.8s cubic-bezier(0.4, 0, 0.2, 1);
          background: linear-gradient(90deg, var(--primary), var(--secondary));
          box-shadow: 0 0 12px rgba(99, 102, 241, 0.4);
          position: relative;
        }

        .progress-fill::after {
          content: '';
          position: absolute;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.2), transparent);
          animation: shimmer 2s infinite;
        }

        @keyframes shimmer {
          0% { transform: translateX(-100%); }
          100% { transform: translateX(100%); }
        }

        /* ==================== 无数据/错误状态 ==================== */
        .empty-state {
          text-align: center;
          color: var(--text-muted);
          padding: 60px 24px;
          background: var(--surface-card);
          border-radius: var(--radius-md);
          border: 2px dashed var(--border);
        }

        .empty-state-icon {
          font-size: 56px;
          margin-bottom: 16px;
          opacity: 0.6;
        }

        .empty-state-text {
          font-size: 16px;
          font-weight: 500;
        }

        .error-state {
          background: linear-gradient(135deg, rgba(239, 68, 68, 0.15), rgba(220, 38, 38, 0.1));
          color: #fca5a5;
          padding: 20px 24px;
          border-radius: var(--radius-md);
          border-left: 4px solid var(--danger);
          font-weight: 600;
          word-break: break-all;
          box-shadow: var(--shadow);
        }

        /* ==================== 饼图样式 ==================== */
        .pie-wrapper {
          display: flex;
          align-items: center;
          gap: 32px;
          flex-wrap: wrap;
        }

        .pie-chart {
          width: 160px;
          height: 160px;
          filter: drop-shadow(0 4px 12px rgba(0, 0, 0, 0.3));
        }

        .pie-legend {
          flex: 1;
          min-width: 200px;
        }

        .legend-item {
          display: flex;
          align-items: center;
          gap: 12px;
          padding: 10px 14px;
          margin-bottom: 6px;
          border-radius: var(--radius);
          cursor: default;
          transition: all 0.2s ease;
        }

        .legend-item:hover {
          background: rgba(99, 102, 241, 0.1);
          padding-left: 18px;
        }

        .legend-color {
          width: 18px;
          height: 18px;
          border-radius: 6px;
          flex-shrink: 0;
          box-shadow: var(--shadow-sm);
        }

        .legend-label {
          flex: 1;
          font-size: 14px;
          color: var(--text-secondary);
        }

        .legend-value {
          font-weight: 700;
          color: var(--text-primary);
        }

        /* ==================== 实时监控面板 ==================== */
        .realtime-panel {
          background: linear-gradient(135deg, rgba(30, 41, 59, 0.9), rgba(15, 23, 42, 0.95));
          border-radius: var(--radius-md);
          padding: 24px;
          margin-bottom: 24px;
          border: 1px solid rgba(99, 102, 241, 0.25);
          box-shadow: var(--shadow), inset 0 0 40px rgba(0, 0, 0, 0.4);
        }

        .realtime-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 20px;
          padding-bottom: 16px;
          border-bottom: 1px solid rgba(99, 102, 241, 0.2);
        }

        .realtime-title {
          font-size: 17px;
          font-weight: 700;
          color: var(--primary-light);
          display: flex;
          align-items: center;
          gap: 10px;
        }

        .status-badge {
          padding: 6px 16px;
          border-radius: 20px;
          font-size: 12px;
          font-weight: 600;
        }

        .status-badge.printing {
          background: linear-gradient(135deg, var(--primary), var(--secondary));
          color: white;
          animation: pulse 2s infinite;
        }

        .status-badge.finish {
          background: linear-gradient(135deg, var(--success), #4ade80);
          color: white;
        }

        .status-badge.idle {
          background: linear-gradient(135deg, #64748b, #94a3b8);
          color: white;
        }

        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.7; }
        }

        .realtime-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
          gap: 16px;
        }

        .realtime-item {
          background: linear-gradient(135deg, rgba(51, 65, 85, 0.6), rgba(30, 41, 59, 0.8));
          border-radius: var(--radius);
          padding: 18px;
          border: 1px solid var(--border);
          transition: all 0.3s ease;
        }

        .realtime-item:hover {
          transform: translateY(-2px);
          box-shadow: var(--shadow);
          border-color: var(--primary);
        }

        .realtime-label {
          font-size: 10px;
          color: var(--text-muted);
          text-transform: uppercase;
          letter-spacing: 0.6px;
          margin-bottom: 6px;
          font-weight: 600;
        }

        .realtime-value {
          font-size: 20px;
          font-weight: 800;
          color: var(--text-primary);
        }

        /* ==================== AMS耗材盘 ==================== */
        .ams-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(90px, 1fr));
          gap: 8px;
          margin-top: 10px;
        }

        .ams-tray {
          background: var(--surface-card);
          border-radius: var(--radius);
          padding: 10px;
          text-align: center;
          border: 1px solid var(--border);
          transition: all 0.3s ease;
          position: relative;
        }

        .ams-tray:hover {
          transform: translateY(-3px);
          box-shadow: var(--shadow);
        }

        .ams-tray.active {
          border-color: var(--primary);
          box-shadow: 0 0 20px rgba(99, 102, 241, 0.3);
          background: linear-gradient(135deg, rgba(99, 102, 241, 0.15), var(--surface-card));
        }

        .ams-tray-number {
          font-size: 11px;
          color: var(--text-muted);
          font-weight: 600;
          margin-bottom: 6px;
        }

        .ams-tray-color {
          width: 36px;
          height: 36px;
          border-radius: 50%;
          margin: 0 auto 6px;
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4), inset 0 2px 6px rgba(0, 0, 0, 0.3);
          border: 3px solid rgba(255, 255, 255, 0.15);
        }

        .ams-tray-name {
          font-size: 13px;
          font-weight: 700;
          color: var(--text-primary);
          line-height: 1.3;
        }

        /* ==================== 历史记录列表 ==================== */
        .history-wrapper {
          max-height: 650px;
          overflow-y: auto;
          padding-right: 8px;
        }

        .history-wrapper::-webkit-scrollbar {
          width: 8px;
        }

        .history-wrapper::-webkit-scrollbar-track {
          background: var(--surface);
          border-radius: 4px;
        }

        .history-wrapper::-webkit-scrollbar-thumb {
          background: var(--text-muted);
          border-radius: 4px;
        }

        .history-wrapper::-webkit-scrollbar-thumb:hover {
          background: var(--text-secondary);
        }

        .history-item {
          display: flex;
          gap: 18px;
          padding: 18px;
          background: var(--surface-card);
          border-radius: var(--radius-md);
          margin-bottom: 14px;
          border: 1px solid var(--border);
          cursor: default;
          position: relative;
          transition: all 0.3s ease;
        }

        .history-item:hover {
          transform: translateY(-2px);
          box-shadow: var(--shadow);
          border-color: rgba(99, 102, 241, 0.3);
        }

        .history-thumbnail {
          width: 76px;
          height: 76px;
          border-radius: var(--radius);
          background: linear-gradient(135deg, rgba(99, 102, 241, 0.2), rgba(6, 182, 212, 0.1));
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 36px;
          flex-shrink: 0;
          box-shadow: var(--shadow-sm);
        }

        .history-content {
          flex: 1;
          display: flex;
          flex-direction: column;
          gap: 6px;
        }

        .history-title {
          font-size: 15px;
          font-weight: 700;
          color: var(--text-primary);
          line-height: 1.3;
        }

        .history-tags {
          font-size: 11px;
          color: var(--text-secondary);
          display: flex;
          gap: 10px;
          flex-wrap: wrap;
        }

        .tag {
          background: rgba(99, 102, 241, 0.15);
          padding: 3px 10px;
          border-radius: 12px;
          font-weight: 500;
          color: var(--primary-light);
        }

        .history-meta {
          display: flex;
          align-items: center;
          gap: 16px;
          font-size: 12px;
          color: var(--text-muted);
          margin-top: 8px;
        }

        .history-date {
          font-size: 11px;
          color: var(--text-muted);
          margin-top: auto;
          padding-top: 8px;
          border-top: 1px dashed var(--border);
        }

        .history-status {
          position: absolute;
          top: 12px;
          right: 12px;
          padding: 4px 12px;
          border-radius: 14px;
          font-size: 11px;
          font-weight: 700;
        }

        .history-status.success {
          background: linear-gradient(135deg, rgba(34, 197, 94, 0.2), rgba(34, 197, 94, 0.1));
          color: #86efac;
          border: 1px solid rgba(34, 197, 94, 0.3);
        }

        .history-status.failed {
          background: linear-gradient(135deg, rgba(239, 68, 68, 0.2), rgba(239, 68, 68, 0.1));
          color: #fca5a5;
          border: 1px solid rgba(239, 68, 68, 0.3);
        }

        .history-status.printing {
          background: linear-gradient(135deg, rgba(99, 102, 241, 0.2), rgba(6, 182, 212, 0.1));
          color: var(--primary-light);
          border: 1px solid rgba(99, 102, 241, 0.3);
        }

        /* ==================== 统计摘要 ==================== */
        .summary-bar {
          display: flex;
          flex-wrap: nowrap;
          gap: 6px;
          margin-bottom: 12px;
          padding: 12px 10px;
          background: var(--surface-card);
          border-radius: var(--radius);
          border: 1px solid var(--border);
          overflow: hidden;
          min-height: 56px;
        }

        .summary-item {
          flex: 1 1 0;
          text-align: center;
          min-width: 0;
          display: flex;
          flex-direction: column;
          justify-content: center;
          gap: 2px;
        }

        .summary-number {
          font-size: 15px;
          font-weight: 700;
          color: var(--primary-light);
          line-height: 1.2;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .summary-text {
          font-size: 9px;
          color: var(--text-muted);
          margin-top: 1px;
          line-height: 1;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        /* ==================== 历史记录筛选栏 ==================== */
        .filter-bar {
          display: flex;
          gap: 10px;
          margin-bottom: 16px;
          flex-wrap: wrap;
          align-items: center;
        }

        .filter-select {
          padding: 8px 32px 8px 14px;
          border: 1px solid var(--border);
          border-radius: var(--radius);
          background: var(--surface-card);
          font-size: 13px;
          font-weight: 500;
          color: var(--text-primary);
          cursor: pointer;
          min-width: 120px;
          transition: all 0.2s ease;
          appearance: none;
          position: relative;
          background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%236b7280' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'%3E%3C/polyline%3E%3C/svg%3E");
          background-repeat: no-repeat;
          background-position: right 10px center;
          background-size: 14px;
        }

        .filter-select:hover {
          border-color: var(--primary);
          background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%236366f1' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'%3E%3C/polyline%3E%3C/svg%3E");
        }

        .filter-select:focus {
          outline: none;
          border-color: var(--primary);
          box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.2);
          background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%236366f1' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'%3E%3C/polyline%3E%3C/svg%3E");
        }

        .filter-select option {
          background: var(--surface);
          color: var(--text-primary);
          padding: 8px 12px;
          font-size: 13px;
        }

        .filter-select option:hover {
          background: var(--surface-hover);
        }

        .filter-actions {
          display: flex;
          gap: 8px;
          margin-left: auto;
        }

        .btn-filter {
          padding: 8px 18px;
          border: none;
          border-radius: var(--radius);
          font-size: 13px;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.2s ease;
        }

        .btn-filter-apply {
          background: var(--primary);
          color: white;
        }
        .btn-filter-apply:hover { background: var(--primary-dark); }

        .btn-filter-reset {
          background: var(--surface-card);
          color: var(--text-secondary);
          border: 1px solid var(--border);
        }
        .btn-filter-reset:hover { background: var(--surface-hover); }

        .btn-filter-export {
          background: #16a34a;
          color: white;
        }
        .btn-filter-export:hover { background: #15803d; }

        .color-dot {
          display: inline-block;
          width: 14px;
          height: 14px;
          border-radius: 50%;
          vertical-align: middle;
          margin-right: 4px;
          border: 1px solid rgba(255,255,255,0.3);
        }

        .pagination {
          display: flex;
          justify-content: center;
          align-items: center;
          gap: 6px;
          margin-top: 10px;
          padding: 12px 0;
        }

        .page-btn {
          padding: 6px 14px;
          border: 1px solid var(--border);
          border-radius: var(--radius);
          background: var(--surface-card);
          color: var(--text-primary);
          font-size: 13px;
          cursor: pointer;
          transition: all 0.2s ease;
        }
        .page-btn:hover { background: var(--surface-hover); }
        .page-btn.active {
          background: var(--primary);
          color: white;
          border-color: var(--primary);
        }
        .page-btn:disabled {
          opacity: 0.4;
          cursor: not-allowed;
        }

        .page-info {
          font-size: 13px;
          color: var(--text-muted);
          margin: 0 8px;
        }

        .search-box {
          flex: 1;
          min-width: 200px;
          position: relative;
        }

        .search-input {
          width: 100%;
          padding: 10px 16px 10px 40px;
          border: 1px solid var(--border);
          border-radius: var(--radius);
          font-size: 13px;
          background: var(--surface-card);
          color: var(--text-primary);
          transition: all 0.2s ease;
        }

        .search-input:focus {
          outline: none;
          border-color: var(--primary);
          box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.2);
        }

        .search-icon {
          position: absolute;
          left: 14px;
          top: 50%;
          transform: translateY(-50%);
          color: var(--text-muted);
          font-size: 14px;
        }

        .history-empty-state {
          text-align: center;
          padding: 60px 24px;
          color: var(--text-muted);
        }

        .history-empty-icon {
          font-size: 64px;
          margin-bottom: 16px;
          opacity: 0.5;
        }

        .history-empty-text {
          font-size: 15px;
          font-weight: 500;
        }

        .history-details {
          flex: 1;
          display: flex;
          flex-direction: column;
          gap: 6px;
        }

        .history-task-name {
          font-size: 15px;
          font-weight: 700;
          color: var(--text-primary);
          line-height: 1.3;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
          max-width: calc(100% - 60px);
          display: inline-block;
          vertical-align: middle;
        }

        .history-params {
          font-size: 11px;
          color: var(--text-secondary);
          display: flex;
          gap: 8px;
          flex-wrap: wrap;
        }

        .param-tag {
          background: rgba(99, 102, 241, 0.15);
          padding: 3px 10px;
          border-radius: 12px;
          font-weight: 500;
          color: var(--primary-light);
        }

        .thumbnail-color-bar {
          position: absolute;
          bottom: 0;
          left: 0;
          right: 0;
          height: 6px;
          display: flex;
          border-radius: 0 0 var(--radius) var(--radius);
          overflow: hidden;
        }

        .thumbnail-color-segment {
          flex: 1;
        }

        /* ==================== 详情弹窗 ==================== */
        .modal-overlay {
          position: fixed;
          top: 0; left: 0; right: 0; bottom: 0;
          background: rgba(0, 0, 0, 0.7);
          backdrop-filter: blur(8px);
          z-index: 9999;
          display: flex;
          align-items: center;
          justify-content: center;
          animation: fadeIn 0.2s ease-out;
        }

        .modal-overlay.closing {
          animation: fadeOut 0.15s ease-in forwards;
        }

        @keyframes fadeOut {
          from { opacity: 1; }
          to { opacity: 0; }
        }

        .modal-content {
          background: linear-gradient(145deg, var(--glass-bg), rgba(15, 23, 42, 0.98));
          border: 1px solid var(--glass-border);
          border-radius: var(--radius-lg);
          padding: 10px;
          max-width: 520px;
          width: 94%;
          max-height: 90vh;
          overflow-y: auto;
          box-shadow: var(--shadow-lg);
          position: relative;
        }

        .modal-close {
          position: absolute;
          top: 10px; right: 10px;
          width: 28px; height: 28px;
          border-radius: 50%;
          border: 1px solid var(--border);
          background: var(--surface-card);
          color: var(--text-secondary);
          font-size: 14px;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          transition: all 0.2s ease;
        }

        .modal-close:hover {
          background: var(--danger);
          color: white;
          border-color: var(--danger);
        }

        .detail-cover {
          width: 100%;
          max-height: 180px;
          object-fit: contain;
          border-radius: var(--radius-md);
          margin-bottom: 12px;
          background: var(--surface-card);
        }

        .detail-snapshot {
          width: 100%;
          max-height: 150px;
          object-fit: contain;
          border-radius: var(--radius-md);
          margin-top: 12px;
          background: var(--surface-card);
        }

        .detail-title {
          font-size: 16px;
          font-weight: 700;
          color: var(--text-primary);
          margin-bottom: 10px;
        }

        .detail-grid {
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          gap: 8px;
        }

        .detail-field {
          background: var(--surface-card);
          border-radius: var(--radius);
          padding: 8px 10px;
          border: 1px solid var(--border);
        }

        .detail-field-label {
          font-size: 9px;
          color: var(--text-muted);
          text-transform: uppercase;
          letter-spacing: 0.3px;
          margin-bottom: 2px;
        }

        .detail-field-value {
          font-size: 13px;
          font-weight: 700;
          color: var(--text-primary);
        }

        /* ==================== 删除确认框 ==================== */
        .confirm-overlay {
          position: fixed;
          top: 0; left: 0; right: 0; bottom: 0;
          background: rgba(0, 0, 0, 0.6);
          backdrop-filter: blur(6px);
          z-index: 10000;
          display: flex;
          align-items: center;
          justify-content: center;
          animation: fadeIn 0.2s ease-out;
        }

        .confirm-box {
          background: linear-gradient(145deg, var(--glass-bg), rgba(15, 23, 42, 0.98));
          border: 1px solid rgba(239, 68, 68, 0.3);
          border-radius: var(--radius-lg);
          padding: 18px;
          max-width: 340px;
          width: 90%;
          box-shadow: var(--shadow-lg);
        }

        .confirm-title {
          font-size: 15px;
          font-weight: 700;
          color: var(--danger);
          margin-bottom: 6px;
        }

        .confirm-text {
          font-size: 12px;
          color: var(--text-secondary);
          margin-bottom: 14px;
          line-height: 1.5;
        }

        .confirm-actions {
          display: flex;
          gap: 12px;
          justify-content: flex-end;
        }

        .btn {
          padding: 10px 20px;
          border-radius: var(--radius);
          font-size: 14px;
          font-weight: 600;
          cursor: pointer;
          border: 1px solid var(--border);
          transition: all 0.2s ease;
        }

        .btn-cancel {
          background: var(--surface-card);
          color: var(--text-secondary);
        }

        .btn-cancel:hover { background: rgba(100, 116, 139, 0.3); }

        .btn-danger {
          background: linear-gradient(135deg, var(--danger), #dc2626);
          color: white;
          border-color: var(--danger);
        }

        .btn-danger:hover { box-shadow: 0 4px 12px rgba(239, 68, 68, 0.4); }

        /* ==================== 日期筛选 ==================== */
        .date-filter {
          display: flex;
          gap: 10px;
          align-items: center;
          flex-wrap: wrap;
        }

        .date-input {
          padding: 8px 14px;
          border: 1px solid var(--border);
          border-radius: var(--radius);
          background: var(--surface-card);
          color: var(--text-primary);
          font-size: 13px;
          transition: all 0.2s ease;
        }

        .date-input:focus {
          outline: none;
          border-color: var(--primary);
          box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.2);
        }

        .date-separator {
          color: var(--text-muted);
          font-size: 13px;
        }

        /* ==================== 封面图 ==================== */
        .history-cover-img {
          width: 76px;
          height: 76px;
          border-radius: var(--radius);
          object-fit: cover;
          flex-shrink: 0;
          box-shadow: var(--shadow-sm);
          background: var(--surface-card);
        }

        /* ==================== 选择框 ==================== */
        .record-checkbox {
          width: 20px;
          height: 20px;
          border-radius: 6px;
          border: 2px solid var(--border);
          background: var(--surface-card);
          cursor: pointer;
          appearance: none;
          -webkit-appearance: none;
          flex-shrink: 0;
          transition: all 0.2s ease;
          position: relative;
        }

        .record-checkbox:checked {
          background: var(--primary);
          border-color: var(--primary);
        }

        .record-checkbox:checked::after {
          content: '✓';
          position: absolute;
          top: 50%; left: 50%;
          transform: translate(-50%, -50%);
          color: white;
          font-size: 12px;
          font-weight: 700;
        }

        .delete-bar {
          display: flex;
          align-items: center;
          gap: 12px;
          padding: 12px 20px;
          background: linear-gradient(135deg, rgba(239, 68, 68, 0.15), rgba(220, 38, 38, 0.1));
          border: 1px solid rgba(239, 68, 68, 0.3);
          border-radius: var(--radius-md);
          margin-bottom: 16px;
          animation: fadeIn 0.2s ease-out;
        }

        .delete-bar-text {
          font-size: 13px;
          color: #fca5a5;
          font-weight: 600;
        }

        .printer-tag {
          display: inline-flex;
          padding: 3px 10px;
          border-radius: 12px;
          font-size: 11px;
          font-weight: 600;
          background: rgba(6, 182, 212, 0.15);
          color: var(--secondary);
          border: 1px solid rgba(6, 182, 212, 0.3);
        }

        /* ==================== 响应式设计 ==================== */
        @media (max-width: 768px) {
          .card {
            padding: 20px;
          }

          .header {
            flex-direction: column;
            align-items: flex-start;
            gap: 12px;
          }

          .header-title {
            font-size: 19px;
          }

          .stats-grid {
            grid-template-columns: repeat(2, 1fr);
            gap: 12px;
          }

          .stat-card {
            padding: 16px 12px;
          }

          .stat-value {
            font-size: 28px;
          }

          .realtime-grid {
            grid-template-columns: repeat(2, 1fr);
          }

          .pie-wrapper {
            flex-direction: column;
            align-items: center;
          }

          .history-item {
            flex-direction: column;
            gap: 12px;
          }

          .history-thumbnail {
            width: 100%;
            height: 80px;
          }

          .tab-button {
            padding: 8px 14px;
            font-size: 13px;
          }
        }

        @media (max-width: 480px) {
          .stats-grid {
            grid-template-columns: 1fr;
          }

          .realtime-grid {
            grid-template-columns: 1fr;
          }

          .ams-grid {
            grid-template-columns: repeat(2, 1fr);
          }
        }
      </style>
      <div class="card">
        <div class="card-content">
          <div class="empty-state">
            <div class="empty-state-icon">${ICON_3D_PRINTER()}</div>
            <div class="empty-state-text">加载打印机分析数据...</div>
          </div>
        </div>
      </div>
    `;
  }

  /**
   * 更新数据并重新渲染
   */
  updateData() {
    if (this._isRendering) return;

    const container = this.shadowRoot.querySelector('.card-content');
    if (!container) return;

    try {
      if (!this._hass) {
        container.innerHTML = `<div class="error-state">⚠️ 错误: 未连接到 Home Assistant</div>`;
        return;
      }

      if (!this.config) {
        container.innerHTML = `<div class="error-state">⚠️ 错误: 卡片配置为空</div>`;
        return;
      }

      if (!this.config.print_history && !this.config.printers) {
        container.innerHTML = `<div class="error-state">⚠️ 错误: 缺少 print_history 或 printers 配置项</div>`;
        return;
      }

      const currentDataSnapshot = this._generateDataSnapshot();

      if (this._lastRenderedData && this._isDataEqual(this._lastRenderedData, currentDataSnapshot)) {
        return;
      }

      this._isRendering = true;

      const title = this._escapeHtml(this.config.title || '打印机分析');

      let html = `
        <div class="header">
          <div class="header-left">
            <div class="header-icon">${ICON_3D_PRINTER()}</div>
            <div>
              <div class="header-title">${title}</div>
            </div>
          </div>
        <div class="header-badge">v5.11.8</div>
        </div>
      `;

      if (this._mode !== 'history') {
        try { html += this._renderRealtimeMonitor(); } catch (e) {
          html += `<div class="error-state">实时监控渲染失败: ${this._escapeHtml(e.message)}</div>`;
        }
      }

      // 两页签：统计分析、全部历史
      html += `
        <div class="tab-container">
          <button class="tab-button ${this._activeTab === 'stats' ? 'active' : ''}" data-tab="stats">📊 统计分析</button>
          <button class="tab-button ${this._activeTab === 'merged' ? 'active' : ''}" data-tab="merged">🗂️ 全部历史</button>
        </div>
      `;

      // 统计分析 Tab
      html += `<div class="tab-content ${this._activeTab === 'stats' ? 'active' : ''}" id="tab-stats">`;
      html += this._renderPrinterSelector();
      try {
        html += '<div style="height:1px;background:linear-gradient(90deg,transparent,var(--primary),transparent);margin:20px 0;opacity:0.3;"></div>';
        try { html += this._renderExtremeStats(); } catch (e) {}
        try { html += this._renderRecentPrints(); } catch (e) {}
        html += this._renderPeriodStats();
      } catch (e) {
        html += `<div class="error-state">统计渲染失败: ${this._escapeHtml(e.message)}</div>`;
      }
      try { html += this._renderFilamentBarCharts(); } catch (e) {
        html += `<div class="error-state">耗材使用量对比图渲染失败: ${this._escapeHtml(e.message)}</div>`;
      }
      try { html += this._renderHeatmapWithDuration(); } catch (e) {
        html += `<div class="error-state">热力图/时长分布渲染失败: ${this._escapeHtml(e.message)}</div>`;
      }
      try { html += this._renderFilamentSuccessStats(); } catch (e) {
        html += `<div class="error-state">耗材成功率渲染失败: ${this._escapeHtml(e.message)}</div>`;
      }
      try { html += this._renderRecordsTab(); } catch (e) {
        html += `<div class="error-state">之最渲染失败: ${this._escapeHtml(e.message)}</div>`;
      }
      try { html += this._renderFailureStageDistribution(); } catch (e) {
        html += `<div class="error-state">失败阶段分布渲染失败: ${this._escapeHtml(e.message)}</div>`;
      }
      html += `</div>`;

      // 全部历史 Tab
      html += `<div class="tab-content ${this._activeTab === 'merged' ? 'active' : ''}" id="tab-merged">`;
      html += this._renderMergedHistoryPage();
      html += `</div>`;

      if (this._detailRecord) {
        html += this._renderDetailModal(this._detailRecord);
      }
      if (this._deleteConfirmVisible) {
        html += this._renderDeleteConfirm();
      }

      container.innerHTML = html || `<div class="empty-state"><div class="empty-state-icon">📭</div><div class="empty-state-text">暂无数据</div></div>`;

      this._lastRenderedData = currentDataSnapshot;
      this._isRendering = false;

      this._bindTabEvents();

    } catch (error) {
      console.error('打印机分析卡片错误:', error);
      container.innerHTML = `<div class="error-state">❌ 渲染错误! ${this._escapeHtml(error.message)}</div>`;
      this._isRendering = false;
    }
  }

  /**
   * 绑定标签页切换事件
   */
  _bindTabEvents() {
    const tabs = this.shadowRoot.querySelectorAll('.tab-button');
    tabs.forEach(tab => {
      tab.addEventListener('click', (e) => {
        const tabName = e.target.dataset.tab;
        this._activeTab = tabName;

        this.shadowRoot.querySelectorAll('.tab-content').forEach(content => {
          content.classList.remove('active');
        });
        const tabEl = this.shadowRoot.getElementById(`tab-${tabName}`);
        if (tabEl) tabEl.classList.add('active');

        tabs.forEach(t => t.classList.remove('active'));
        e.target.classList.add('active');
      });
    });

    // 打印机切换器事件
    const printerBtns = this.shadowRoot.querySelectorAll('.printer-selector-btn');
    printerBtns.forEach(btn => {
      btn.addEventListener('click', (e) => {
        this._selectedPrinter = e.target.dataset.printer;
        // 重新渲染当前页签内容
        this.updateData();
      });
    });

    // 实时监控面板打印机切换按钮事件
    const monitorBtns = this.shadowRoot.querySelectorAll('.monitor-switch-btn');
    monitorBtns.forEach(btn => {
      btn.addEventListener('click', (e) => {
        const target = e.target.closest('.monitor-switch-btn');
        if (!target) return;
        this._selectedPrinter = target.dataset.printer;
        this.updateData();
      });
    });

    this._bindHistoryEvents();
    this._restoreFilterValues();
  }

  // 恢复筛选控件的值（render后DOM重建，需要恢复选中状态）
  _restoreFilterValues() {
    const root = this.shadowRoot;
    const statusSel = root.getElementById('filter-status');
    const colorSel = root.getElementById('filter-color');
    const dateFrom = root.getElementById('date-from');
    const dateTo = root.getElementById('date-to');
    const searchInput = root.getElementById('search-input');

    if (statusSel) statusSel.value = this._pendingFilterStatus || this._filterStatus || '';
    if (colorSel) colorSel.value = this._pendingFilterColor || this._filterColor || '';
    const printerSel = root.getElementById('filter-printer');
    if (printerSel) printerSel.value = this._pendingFilterPrinter || this._filterPrinter || '';
    if (dateFrom) dateFrom.value = this._pendingDateFrom || this._dateFrom || '';
    if (dateTo) dateTo.value = this._pendingDateTo || this._dateTo || '';
    if (searchInput) searchInput.value = this._pendingSearchQuery || this._searchQuery || '';
  }

  _bindHistoryEvents() {
    const root = this.shadowRoot;

    root.querySelectorAll('.history-item').forEach(item => {
      item.addEventListener('click', (e) => {
        if (e.target.classList.contains('record-checkbox')) return;
        const recordId = item.dataset.recordId;
        if (!recordId) return;
        const allRecords = this._getAllMergedRecords();
        const record = allRecords.find(r => r.id === recordId);
        if (record) {
          this._detailRecord = record;
          this._showDetailModal(record);
        }
      });
    });

    root.querySelectorAll('.record-checkbox').forEach(cb => {
      cb.addEventListener('change', (e) => {
        const id = e.target.dataset.recordId;
        if (e.target.checked) {
          this._selectedRecords.add(id);
        } else {
          this._selectedRecords.delete(id);
        }
        this._updateDeleteBar();
      });
    });

    // 筛选条件变更时只更新 pending 值，不立即筛选
    root.querySelectorAll('.date-input').forEach(input => {
      input.addEventListener('change', (e) => {
        if (e.target.id === 'date-from') this._pendingDateFrom = e.target.value;
        if (e.target.id === 'date-to') this._pendingDateTo = e.target.value;
      });
    });

    root.querySelectorAll('.filter-select').forEach(sel => {
      sel.addEventListener('change', (e) => {
        if (e.target.id === 'filter-status') this._pendingFilterStatus = e.target.value;
        if (e.target.id === 'filter-color') this._pendingFilterColor = e.target.value;
        if (e.target.id === 'filter-printer') this._pendingFilterPrinter = e.target.value;
      });
    });

    root.querySelectorAll('.search-input').forEach(input => {
      input.addEventListener('input', (e) => {
        this._pendingSearchQuery = e.target.value;
      });
    });

    // 确定筛选按钮
    const applyBtn = root.getElementById('btn-apply-filter');
    if (applyBtn) {
      applyBtn.addEventListener('click', () => {
        this._filterStatus = this._pendingFilterStatus;
        this._filterColor = this._pendingFilterColor;
        this._filterPrinter = this._pendingFilterPrinter;
        this._dateFrom = this._pendingDateFrom;
        this._dateTo = this._pendingDateTo;
        this._searchQuery = this._pendingSearchQuery;
        this._currentPage = 1;
        this._lastRenderedData = null;
        this._refreshContent();
      });
    }

    // 重置筛选按钮
    const resetBtn = root.getElementById('btn-reset-filter');
    if (resetBtn) {
      resetBtn.addEventListener('click', () => {
        this._filterStatus = '';
        this._filterColor = '';
        this._filterPrinter = '';
        this._dateFrom = '';
        this._dateTo = '';
        this._searchQuery = '';
        this._pendingFilterStatus = '';
        this._pendingFilterColor = '';
        this._pendingFilterPrinter = '';
        this._pendingDateFrom = '';
        this._pendingDateTo = '';
        this._pendingSearchQuery = '';
        this._currentPage = 1;
        this._lastRenderedData = null;
        this._refreshContent();
      });
    }

    // 导出CSV按钮
    const exportBtn = root.getElementById('btn-export-csv');
    if (exportBtn) {
      exportBtn.addEventListener('click', () => {
        this._exportHistoryToCSV();
      });
    }

    // 分页按钮
    root.querySelectorAll('.page-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const page = parseInt(e.target.dataset.page);
        if (page && page !== this._currentPage) {
          this._currentPage = page;
          this._lastRenderedData = null;
          this._refreshContent();
          // 滚动到历史记录顶部
          const wrapper = root.querySelector('.history-wrapper');
          if (wrapper) wrapper.scrollTop = 0;
        }
      });
    });

    const deleteBtn = root.getElementById('btn-delete-selected');
    if (deleteBtn) {
      deleteBtn.addEventListener('click', () => {
        if (this._selectedRecords.size > 0) {
          this._deleteConfirmVisible = true;
          this._showDeleteConfirm();
        }
      });
    }

    const confirmDeleteBtn = root.getElementById('btn-confirm-delete');
    if (confirmDeleteBtn) {
      confirmDeleteBtn.addEventListener('click', () => this._executeDelete());
    }

    const cancelDeleteBtn = root.getElementById('btn-cancel-delete');
    if (cancelDeleteBtn) {
      cancelDeleteBtn.addEventListener('click', () => {
        this._closeConfirmModal();
      });
    }

    const closeModal = root.getElementById('btn-close-modal');
    if (closeModal) {
      closeModal.addEventListener('click', () => {
        this._closeDetailModal();
      });
    }

    const modalOverlay = root.querySelector('.modal-overlay');
    if (modalOverlay) {
      modalOverlay.addEventListener('click', (e) => {
        if (e.target === modalOverlay) {
          this._closeDetailModal();
        }
      });
    }

    const confirmOverlay = root.querySelector('.confirm-overlay');
    if (confirmOverlay) {
      confirmOverlay.addEventListener('click', (e) => {
        if (e.target === confirmOverlay) {
          this._closeConfirmModal();
        }
      });
    }
  }

  _showDetailModal(record) {
    const root = this.shadowRoot;
    const cardContent = root.querySelector('.card-content');
    if (!cardContent) return;

    const existingModal = root.querySelector('.modal-overlay');
    if (existingModal) existingModal.remove();

    const modalHtml = this._renderDetailModal(record);
    cardContent.insertAdjacentHTML('beforeend', modalHtml);

    const closeModal = root.getElementById('btn-close-modal');
    if (closeModal) {
      closeModal.addEventListener('click', () => this._closeDetailModal());
    }
    const modalOverlay = root.querySelector('.modal-overlay');
    if (modalOverlay) {
      modalOverlay.addEventListener('click', (e) => {
        if (e.target === modalOverlay) this._closeDetailModal();
      });
    }
  }

  _refreshContent() {
    this._isRendering = false;
    this._lastRenderedData = null;
    this.updateData();
  }

  _showDeleteConfirm() {
    const root = this.shadowRoot;
    const cardContent = root.querySelector('.card-content');
    if (!cardContent) return;

    const existingConfirm = root.querySelector('.confirm-overlay');
    if (existingConfirm) existingConfirm.remove();

    const count = this._selectedRecords.size;
    const confirmHtml = `
      <div class="confirm-overlay">
        <div class="confirm-dialog">
          <div class="confirm-title">⚠️ 确认删除</div>
          <div class="confirm-message">确定要删除选中的 ${count} 条打印记录吗？此操作不可撤销。</div>
          <div class="confirm-buttons">
            <button class="btn btn-danger" id="btn-confirm-delete">确认删除</button>
            <button class="btn" id="btn-cancel-delete">取消</button>
          </div>
        </div>
      </div>`;
    cardContent.insertAdjacentHTML('beforeend', confirmHtml);

    const cancelBtn = root.getElementById('btn-cancel-delete');
    if (cancelBtn) cancelBtn.addEventListener('click', () => this._closeConfirmModal());
    const confirmBtn = root.getElementById('btn-confirm-delete');
    if (confirmBtn) confirmBtn.addEventListener('click', () => this._executeDelete());
  }

  _closeDetailModal() {
    const modal = this.shadowRoot.querySelector('.modal-overlay');
    if (modal) {
      modal.classList.add('closing');
      setTimeout(() => {
        modal.remove();
        this._detailRecord = null;
      }, 150);
    } else {
      this._detailRecord = null;
    }
  }

  _closeConfirmModal() {
    const confirm = this.shadowRoot.querySelector('.confirm-overlay');
    if (confirm) {
      confirm.remove();
      this._deleteConfirmVisible = false;
    } else {
      this._deleteConfirmVisible = false;
    }
  }

  _updateDeleteBar() {
    const bar = this.shadowRoot.getElementById('delete-bar');
    const countEl = this.shadowRoot.getElementById('selected-count');
    if (bar && countEl) {
      countEl.textContent = this._selectedRecords.size;
      bar.style.display = this._selectedRecords.size > 0 ? 'flex' : 'none';
    }
  }

  async _executeDelete() {
    if (this._selectedRecords.size === 0 || !this._hass) return;
    const recordIds = Array.from(this._selectedRecords);

    const printerGroups = this._groupRecordsByPrinter(recordIds);
    for (const [printerEntity, ids] of printerGroups) {
      try {
        await this._hass.callService('printer_analytics', 'delete_history_records', {
          entity_id: printerEntity,
          record_ids: ids.join(',')
        });
      } catch (e) {
        console.error('删除历史记录失败:', e);
      }
    }

    this._selectedRecords.clear();
    this._deleteConfirmVisible = false;
    setTimeout(() => this._refreshContent(), 500);
  }

  _groupRecordsByPrinter(recordIds) {
    const groups = new Map();
    const allRecords = this._getAllMergedRecords();
    for (const id of recordIds) {
      const record = allRecords.find(r => r.id === id);
      if (record && record._printer_entity) {
        if (!groups.has(record._printer_entity)) {
          groups.set(record._printer_entity, []);
        }
        groups.get(record._printer_entity).push(id);
      }
    }
    return groups;
  }

  /**
   * 生成数据快照（用于比较是否需要重渲染）
   */
  _generateDataSnapshot() {
    try {
      const printers = this._getPrintersConfig();
      const firstPrinter = printers[0];
      const e = firstPrinter?.entities || {};
      let historyLen = 0;
      for (const p of printers) {
        if (p.entities.print_history) {
          const entity = this._hass?.states[p.entities.print_history];
          historyLen += entity?.attributes?.history?.length || 0;
        }
      }
      return {
        _selectedPrinter: this._selectedPrinter,
        _activeTab: this._activeTab,
        totalPrints: this._getState(e.total_prints || this.config.total_prints),
        successRate: this._getState(e.success_rate || this.config.success_rate),
        avgDuration: this._getState(e.average_duration || this.config.average_duration),
        totalDuration: this._getState(e.total_print_duration || this.config.total_print_duration),
        totalEnergy: this._getState(e.total_energy || this.config.total_energy),
        printStatus: this._getState(e.print_status || this.config.print_status),
        currentTask: this._getState(e.current_task || this.config.current_task),
        printProgress: this._getState(e.print_progress || this.config.print_progress),
        currentWeight: this._getState(e.current_weight || this.config.current_weight),
        historyLength: historyLen,
        timestamp: Date.now()
      };
    } catch (e) {
      return { timestamp: Date.now(), error: true };
    }
  }

  /**
   * 比较两个数据快照是否相同
   */
  _isDataEqual(data1, data2) {
    if (!data1 || !data2) return false;

    const keys = ['_selectedPrinter', '_activeTab', 'totalPrints', 'successRate', 'avgDuration', 'totalDuration', 'totalEnergy',
                  'printStatus', 'currentTask', 'printProgress', 'currentWeight', 'historyLength'];

    for (const key of keys) {
      if (data1[key] !== data2[key]) return false;
    }

    return true;
  }

  /**
   * 渲染实时统计维度卡片
   */
  _renderTimeDimension() {
    const printerName = this._selectedPrinter;
    const history = this._getHistoryForPrinter(printerName);
    let totalPrints = 0, successCount = 0, failCount = 0;
    let totalWeight = 0, totalLength = 0, totalEnergy = 0;
    let totalDuration = 0, durationCount = 0;

    if (Array.isArray(history)) {
      for (const item of history) {
        totalPrints++;
        const status = (item.status || '').toLowerCase();
        const weight = item.total_weight || 0;
        const length = item.total_length || 0;
        const energy = item.energy_kwh || 0;
        const duration = item.duration_hours || (item.duration_minutes ? item.duration_minutes / 60 : 0);

        if (status === 'finish' || status === '完成' || status === '成功') {
          successCount++;
          totalWeight += weight;
          totalLength += length;
        } else if (status === 'failed' || status === 'fail' || status === '失败') {
          failCount++;
          totalWeight += weight;
          totalLength += length;
        }
        totalEnergy += energy;
        if (duration > 0) {
          totalDuration += duration;
          durationCount++;
        }
      }
    }

    const successRate = totalPrints > 0 ? (successCount / totalPrints * 100).toFixed(1) : '0';
    const avgDuration = durationCount > 0 ? (totalDuration / durationCount).toFixed(2) : '0';
    const weightStr = totalWeight.toFixed(1);
    const lengthStr = totalLength.toFixed(1);
    const totalDurationStr = totalDuration.toFixed(2);
    const totalEnergyStr = totalEnergy.toFixed(2);

    // 打印质量 = 成功率 + 质量等级
    const rateNum = parseFloat(successRate) || 0;
    let qualityLabel, qualityIcon, qualityColor;
    if (rateNum >= 99) { qualityLabel = '优秀'; qualityIcon = '⭐'; qualityColor = '#22c55e'; }
    else if (rateNum >= 95) { qualityLabel = '良好'; qualityIcon = '👍'; qualityColor = '#3b82f6'; }
    else if (rateNum >= 90) { qualityLabel = '一般'; qualityIcon = '📊'; qualityColor = '#f59e0b'; }
    else { qualityLabel = '待改善'; qualityIcon = '⚠️'; qualityColor = '#ef4444'; }

    return `
      <div class="stats-grid">
        <div class="stat-card" style="padding:16px;">
          <div style="display:flex;flex-wrap:wrap;justify-content:space-around;align-items:center;gap:12px 24px;">
            <div style="text-align:center;min-width:70px;">
              <div class="stat-icon">${ICON_3D_PRINTER(18)}</div>
              <div class="stat-value" style="font-size:20px;">${totalPrints}</div>
              <div class="stat-label">打印次数</div>
            </div>
            <div style="text-align:center;min-width:70px;">
              <div class="stat-icon">⚖️</div>
              <div class="stat-value" style="font-size:20px;">${this._formatWeight(weightStr)}</div>
              <div class="stat-label">总重量</div>
            </div>
            <div style="text-align:center;min-width:70px;">
              <div class="stat-icon">📏</div>
              <div class="stat-value" style="font-size:20px;">${lengthStr}m</div>
              <div class="stat-label">总长度</div>
            </div>
            <div style="text-align:center;min-width:70px;">
              <div class="stat-icon">⏱️</div>
              <div class="stat-value" style="font-size:20px;">${avgDuration}</div>
              <div class="stat-label">平均时长</div>
            </div>
            <div style="text-align:center;min-width:70px;">
              <div class="stat-icon">🕐</div>
              <div class="stat-value" style="font-size:20px;">${this._formatDurationHours(totalDurationStr)}</div>
              <div class="stat-label">总时长</div>
            </div>
            <div style="text-align:center;min-width:70px;">
              <div class="stat-icon">⚡</div>
              <div class="stat-value" style="font-size:20px;">${totalEnergyStr}</div>
              <div class="stat-label">能耗</div>
            </div>
            <div style="text-align:center;min-width:70px;">
              <div class="stat-icon">${qualityIcon}</div>
              <div class="stat-value" style="color:${qualityColor};font-size:18px;">${successRate}%<span style="font-size:9px;opacity:0.8;margin-left:2px;display:block;">${qualityLabel}</span></div>
              <div class="stat-label">质量</div>
            </div>
          </div>
        </div>
      </div>
    `;
  }

  /**
   * 渲染周期统计（7天/30天）
   */
  _renderPeriodStats() {
    const printerName = this._selectedPrinter;
    const history = this._getHistoryForPrinter(printerName);
    const now = new Date();
    const sevenDaysAgo = new Date(now.getTime() - 7 * 24 * 3600 * 1000);
    const thirtyDaysAgo = new Date(now.getTime() - 30 * 24 * 3600 * 1000);

    const calcPeriod = (records, since) => {
      let totalPrints = 0, successful = 0, failed = 0;
      let totalWeight = 0, totalLength = 0, totalEnergy = 0;
      let totalDuration = 0, durationCount = 0;
      for (const item of records) {
        const endTime = item.end_time || item.start_time || '';
        const endDt = endTime ? new Date(endTime) : null;
        if (since && endDt && endDt < since) continue;
        totalPrints++;
        const status = (item.status || '').toLowerCase();
        const weight = item.total_weight || 0;
        const length = item.total_length || 0;
        const energy = item.energy_kwh || 0;
        const duration = item.duration_hours || (item.duration_minutes ? item.duration_minutes / 60 : 0);
        if (status === 'finish' || status === '完成' || status === '成功') {
          successful++;
          totalWeight += weight;
          totalLength += length;
        } else if (status === 'failed' || status === 'fail' || status === '失败') {
          failed++;
          totalWeight += weight;
          totalLength += length;
        } else if (status === 'cancelled' || status === '已取消') {
          totalWeight += weight;
          totalLength += length;
        }
        totalEnergy += energy;
        if (duration > 0) { totalDuration += duration; durationCount++; }
      }
      return {
        totalPrints, successful, failed,
        successRate: totalPrints > 0 ? (successful / totalPrints * 100).toFixed(1) : '0',
        totalWeight: totalWeight.toFixed(1),
        totalLength: totalLength.toFixed(1),
        totalEnergy: totalEnergy.toFixed(2),
        avgDuration: durationCount > 0 ? (totalDuration / durationCount).toFixed(2) : '0'
      };
    };

    const periodData = [
      { label: '7天', ...calcPeriod(history, sevenDaysAgo) },
      { label: '30天', ...calcPeriod(history, thirtyDaysAgo) },
      { label: '总', ...calcPeriod(history, null) },
    ];

    const d = periodData;
    const metrics = [
      { key: 'totalPrints', label: '次数', icon: '🖨️', color: '' },
      { key: 'successful', label: '成功', icon: '✅', color: 'color:var(--success);' },
      { key: 'failed', label: '失败', icon: '❌', color: 'color:var(--danger);' },
      { key: 'successRate', label: '成功率', icon: '📈', color: '', suffix: '%' },
      { key: 'totalWeight', label: '重量', icon: '⚖️', color: '', suffix: 'g' },
      { key: 'totalLength', label: '长度', icon: '📏', color: '', suffix: 'm' },
      { key: 'totalEnergy', label: '能耗', icon: '⚡', color: '', suffix: 'kWh' },
      { key: 'avgDuration', label: '均时', icon: '⏱️', color: '', suffix: 'h' },
    ];
    const cellStyle = 'padding:4px 8px;text-align:center;font-size:12px;';
    const labelStyle = 'padding:4px 8px;text-align:left;font-size:12px;font-weight:500;white-space:nowrap;';
    return `
      <div class="section-header">
        <div class="section-title">
          <span class="section-icon">📅</span>
          <span>周期统计</span>
        </div>
      </div>
      <div class="chart-container" style="overflow-x:auto;">
        <table class="stats-table" style="min-width:100%;">
          <thead>
            <tr>
              <th style="${labelStyle}"></th>
              ${d.map(p => `<th style="${cellStyle};font-weight:600;font-size:11px;white-space:nowrap;">${p.label}</th>`).join('')}
            </tr>
          </thead>
          <tbody>
            ${metrics.map(m => `
              <tr>
                <td style="${labelStyle}">${m.icon} ${m.label}</td>
                ${d.map(p => {
                  const val = p[m.key] || 0;
                  return `<td style="${cellStyle}${m.color}">${val}${m.suffix || ''}</td>`;
                }).join('')}
              </tr>`).join('')}
          </tbody>
        </table>
      </div>
    `;
  }

  /**
   * 渲染打印时长分布
   */
  _renderDurationDistribution() {
    const records = this._getHistoryForPrinter(this._selectedPrinter);
    if (!Array.isArray(records) || records.length === 0) {
      return `<div class="section-header"><div class="section-title"><span class="section-icon">📊</span><span>打印时长分布</span></div></div><div class="chart-container"><div class="empty-state"><div class="empty-state-icon">📭</div><div class="empty-state-text">暂无数据</div></div></div>`;
    }

    const buckets = [
      { label: '0-30分钟', min: 0, max: 30 },
      { label: '30-60分钟', min: 30, max: 60 },
      { label: '1-3小时', min: 60, max: 180 },
      { label: '3-6小时', min: 180, max: 360 },
      { label: '6-12小时', min: 360, max: 720 },
      { label: '12小时+', min: 720, max: Infinity },
    ];

    const distribution = {};
    for (const b of buckets) distribution[b.label] = 0;

    for (const r of records) {
      if ((r.duration_hours || 0) <= 0) continue;
      const mins = r.duration_hours * 60;
      for (const b of buckets) {
        if (mins >= b.min && mins < b.max) { distribution[b.label]++; break; }
      }
    }

    const activeBuckets = buckets.filter(b => distribution[b.label] > 0);
    if (activeBuckets.length === 0) {
      return `<div class="section-header"><div class="section-title"><span class="section-icon">📊</span><span>打印时长分布</span></div></div><div class="chart-container"><div class="empty-state"><div class="empty-state-icon">📭</div><div class="empty-state-text">暂无数据</div></div></div>`;
    }

    const maxVal = Math.max(...activeBuckets.map(b => distribution[b.label]), 1);
    const colors = ['#22c55e', '#84cc16', '#eab308', '#f97316', '#ef4444', '#a855f7'];

    let barsHtml = '';
    for (let i = 0; i < activeBuckets.length; i++) {
      const bucket = activeBuckets[i];
      const value = distribution[bucket.label];
      const heightPct = (value / maxVal) * 100;
      barsHtml += `<div style="flex:1;display:flex;flex-direction:column;align-items:center;min-height:110px;">
        <div class="table-value" style="font-size:14px;margin-bottom:8px;">${value}</div>
        <div style="width:100%;background:rgba(15,23,42,0.4);border-radius:8px;height:90px;padding:4px;position:relative;">
          <div style="width:100%;height:${Math.max(heightPct, 5)}%;background:linear-gradient(to top,${colors[i % colors.length]},${colors[(i + 1) % colors.length]});border-radius:6px;transition:height 0.5s ease;"></div>
        </div>
        <div style="font-size:12px;color:var(--text-secondary);margin-top:10px;text-align:center;font-weight:500;">${bucket.label}</div>
      </div>`;
    }

    return `<div class="section-header"><div class="section-title"><span class="section-icon">📊</span><span>打印时长分布</span></div></div><div class="chart-container"><div style="display:flex;gap:16px;">${barsHtml}</div></div>`;
  }

  _renderFailureStageDistribution() {
    const entityId = this._getEntityForPrinter(this._selectedPrinter, 'failure_stage_distribution');
    if (this._selectedPrinter !== '全部' && !entityId) return '';

    let distribution = this._getAggregatedAttr('failure_stage_distribution');
    const cleaned = {};
    for (const key in distribution) {
      if (!['icon', 'friendly_name', 'device_class', 'unit_of_measurement'].includes(key)) {
        cleaned[key] = distribution[key];
      }
    }
    distribution = cleaned;

    if (Object.keys(distribution).length === 0) {
      try {
        const state = this._getState(entityId);
        const parsed = typeof state === 'string' ? JSON.parse(state) : state || {};
        for (const key in parsed) {
          if (!['icon', 'friendly_name', 'device_class', 'unit_of_measurement'].includes(key)) {
            distribution[key] = parsed[key];
          }
        }
      } catch { distribution = {}; }
    }

    const labels = Object.keys(distribution);
    const totalFailed = labels.reduce((sum, k) => sum + (distribution[k] || 0), 0);
    if (totalFailed === 0) {
      return `<div class="section-header"><div class="section-title"><span class="section-icon">📉</span><span>失败阶段分布</span></div></div><div class="chart-container"><div class="empty-state"><div style="font-size:28px;margin-bottom:8px;">🎉</div><div style="color:var(--success);font-weight:600;">暂无失败记录</div></div></div>`;
    }

    const stageColors = { '早期': '#f97316', '中期': '#eab308', '后期': '#ef4444' };
    const getStageColor = (label) => {
      for (const [key, color] of Object.entries(stageColors)) {
        if (label.includes(key)) return color;
      }
      return '#a855f7';
    };

    let barsHtml = '';
    for (const label of labels) {
      const value = distribution[label] || 0;
      const pct = totalFailed > 0 ? Math.round(value / totalFailed * 100) : 0;
      const color = getStageColor(label);
      barsHtml += `<div style="flex:1;display:flex;flex-direction:column;align-items:center;min-height:110px;">
        <div class="table-value" style="font-size:14px;margin-bottom:4px;">${value}</div>
        <div style="font-size:11px;color:var(--text-secondary);margin-bottom:8px;">${pct}%</div>
        <div style="width:100%;background:rgba(15,23,42,0.4);border-radius:8px;height:80px;padding:4px;position:relative;">
          <div style="width:100%;height:${Math.max(pct, 8)}%;background:${color};border-radius:6px;opacity:0.85;transition:height 0.5s ease;"></div>
        </div>
        <div style="font-size:12px;color:${color};margin-top:10px;text-align:center;font-weight:600;">${label}</div>
      </div>`;
    }

    return `<div class="section-header"><div class="section-title"><span class="section-icon">📉</span><span>失败阶段分布</span><span style="font-size:12px;color:var(--text-secondary);font-weight:400;margin-left:8px;">共 ${totalFailed} 次失败</span></div></div><div class="chart-container"><div style="display:flex;gap:16px;">${barsHtml}</div></div>`;
  }

  _renderFilamentSuccessStats() {
    const entityId = this._getEntityForPrinter(this._selectedPrinter, 'filament_success_stats');
    if (this._selectedPrinter !== '全部' && !entityId) return '';

    let stats = this._getAggregatedAttr('filament_success_stats');
    const cleaned = {};
    for (const key in stats) {
      if (!['icon', 'friendly_name', 'device_class', 'unit_of_measurement'].includes(key) && typeof stats[key] === 'object') {
        cleaned[key] = stats[key];
      }
    }
    stats = cleaned;

    if (Object.keys(stats).length === 0) {
      try {
        const state = this._getState(entityId);
        const parsed = typeof state === 'string' ? JSON.parse(state) : state || {};
        for (const key in parsed) {
          if (typeof parsed[key] === 'object' && parsed[key] !== null && 'total' in parsed[key]) {
            stats[key] = parsed[key];
          }
        }
      } catch { stats = {}; }
    }

    const types = Object.keys(stats);
    if (types.length === 0) {
      return `<div class="section-header"><div class="section-title"><span class="section-icon">🧵</span><span>耗材成功率统计</span></div></div><div class="chart-container"><div class="empty-state"><div class="empty-state-icon">📭</div><div class="empty-state-text">暂无数据</div></div></div>`;
    }

    const rateColor = (rate) => {
      if (rate >= 99) return '#22c55e';
      if (rate >= 95) return '#3b82f6';
      if (rate >= 90) return '#f59e0b';
      return '#ef4444';
    };

    let rowsHtml = '';
    for (const ft of types) {
      const d = stats[ft];
      const total = d.total || 0;
      const success = d.success || 0;
      const failed = d.failed || 0;
      const cancelled = d.cancelled || 0;
      const rate = d.success_rate || 0;
      const weight = d.weight_g || 0;
      const color = rateColor(rate);
      const barWidth = Math.max(rate, 3);
      rowsHtml += `<div style="display:flex;align-items:center;gap:12px;padding:8px 0;border-bottom:1px solid var(--border);">
        <div style="min-width:80px;font-weight:600;font-size:13px;">${this._escapeHtml(ft)}</div>
        <div style="flex:1;position:relative;">
          <div style="width:100%;height:20px;background:rgba(15,23,42,0.3);border-radius:10px;overflow:hidden;">
            <div style="width:${barWidth}%;height:100%;background:${color};border-radius:10px;transition:width 0.5s ease;opacity:0.8;"></div>
          </div>
          <div style="position:absolute;right:8px;top:50%;transform:translateY(-50%);font-size:12px;font-weight:700;color:${color};">${rate}%</div>
        </div>
        <div style="min-width:120px;font-size:12px;color:var(--text-secondary);text-align:right;">
          ✅${success} ❌${failed}${cancelled > 0 ? ` ⚠️${cancelled}` : ''} / ${total}次
        </div>
      </div>`;
    }

    return `<div class="section-header"><div class="section-title"><span class="section-icon">🧵</span><span>耗材成功率统计</span></div></div><div class="chart-container">${rowsHtml}</div>`;
  }

  /**
   * 渲染活动热力图
   */
  _renderActivityHeatmap() {
    const entityId = this._getEntityForPrinter(this._selectedPrinter, 'activity_heatmap');
    if (this._selectedPrinter !== '全部' && !entityId) return '';

    let heatmap = this._getAggregatedAttr('activity_heatmap');
    const cleaned = {};
    for (const key in heatmap) {
      if (/^\d{4}-\d{2}-\d{2}$/.test(key)) {
        cleaned[key] = heatmap[key];
      }
    }
    heatmap = cleaned;

    if (Object.keys(heatmap).length === 0) {
      try {
        const state = this._getState(entityId);
        const parsed = typeof state === 'string' ? JSON.parse(state) : state || {};
        for (const key in parsed) {
          if (/^\d{4}-\d{2}-\d{2}$/.test(key)) {
            heatmap[key] = parsed[key];
          }
        }
      } catch { heatmap = {}; }
    }

    const sortedDates = Object.keys(heatmap).filter(k => /^\d{4}-\d{2}-\d{2}$/.test(k)).sort();
    if (sortedDates.length === 0) {
      return `<div class="chart-container"><div class="empty-state"><div class="empty-state-icon">📭</div><div class="empty-state-text">暂无数据</div></div></div>`;
    }

    const maxCount = Math.max(...sortedDates.map(k => heatmap[k]), 1);
    const recentDates = sortedDates.slice(-35);

    const startDate = recentDates.length > 0 ? new Date(recentDates[0]) : new Date();

    const allDates = [];
    for (let i = 0; i < 35; i++) {
      const d = new Date(startDate);
      d.setDate(d.getDate() + i);
      allDates.push(d.toISOString().substring(0, 10));
    }

    let cellsHtml = '';
    for (const dateKey of allDates) {
      const count = heatmap[dateKey] || 0;
      const intensity = count > 0 ? Math.min(count / maxCount, 1) : 0;
      let bgColor = 'rgba(30, 41, 59, 0.6)';
      if (count > 0) {
        if (intensity < 0.33) bgColor = 'rgba(34, 197, 94, 0.3)';
        else if (intensity < 0.66) bgColor = 'rgba(34, 197, 94, 0.6)';
        else bgColor = 'rgba(34, 197, 94, 0.9)';
      }
      cellsHtml += `<div class="heatmap-cell" style="background:${bgColor};" 
        title="${dateKey}: ${count}次"
        data-date="${this._escapeHtml(dateKey)}" 
        data-count="${this._escapeHtml(String(count))}">
      </div>`;
    }

    return `<div class="chart-container" style="padding:8px 10px;"><div style="display:grid;grid-template-columns:repeat(7,1fr);gap:2px;">${cellsHtml}</div></div>`;
  }

  /**
   * 渲染热力图和时长分布（合在一起显示）
   */
  _renderHeatmapWithDuration() {
    const heatmapHtml = this._renderActivityHeatmap();
    const durationHtml = this._renderActivityDurationChart();
    
    if (!heatmapHtml && !durationHtml) return '';
    
    return `
      <div class="section-header">
        <div class="section-title">
          <span class="section-icon">📊</span>
          <span>打印活动概览（热力图 + 时长分布）</span>
        </div>
      </div>
      <div class="chart-container" style="display:flex;gap:16px;">
        <div style="flex:1;">${heatmapHtml || '<div class="empty-state"><div class="empty-state-icon">📭</div><div class="empty-state-text">暂无热力图数据</div></div>'}</div>
        <div style="flex:1;">${durationHtml || '<div class="empty-state"><div class="empty-state-icon">📭</div><div class="empty-state-text">暂无时长数据</div></div>'}</div>
      </div>
    `;
  }

  /**
   * 渲染活动时长图表（热力图旁边的柱状图）
   */
  _renderActivityDurationChart() {
    const entityId = this._getEntityForPrinter(this._selectedPrinter, 'activity_heatmap');
    if (this._selectedPrinter !== '全部' && !entityId) return '';

    let heatmap = this._getAggregatedAttr('activity_heatmap');
    const cleaned = {};
    for (const key in heatmap) {
      if (/^\d{4}-\d{2}-\d{2}$/.test(key)) {
        cleaned[key] = heatmap[key];
      }
    }
    heatmap = cleaned;

    if (Object.keys(heatmap).length === 0) {
      try {
        const state = this._getState(entityId);
        const parsed = typeof state === 'string' ? JSON.parse(state) : state || {};
        for (const key in parsed) {
          if (/^\d{4}-\d{2}-\d{2}$/.test(key)) {
            heatmap[key] = parsed[key];
          }
        }
      } catch { heatmap = {}; }
    }

    const sortedDates = Object.keys(heatmap).filter(k => /^\d{4}-\d{2}-\d{2}$/.test(k)).sort();
    if (sortedDates.length === 0) {
      return `<div style="height:100%;display:flex;flex-direction:column;justify-content:center;align-items:center;"><div class="empty-state-icon">📊</div><div class="empty-state-text">按日期统计</div></div>`;
    }

    const recentDates = sortedDates.slice(-7);
    const maxCount = Math.max(...recentDates.map(k => heatmap[k]), 1);
    
    const weekDays = ['日', '一', '二', '三', '四', '五', '六'];
    
    let barsHtml = '';
    for (const dateKey of recentDates) {
      const count = heatmap[dateKey] || 0;
      const heightPct = (count / maxCount) * 100;
      const date = new Date(dateKey);
      const dayLabel = weekDays[date.getDay()];
      
      barsHtml += `
        <div style="flex:1;display:flex;flex-direction:column;align-items:center;gap:4px;">
          <div style="height:120px;width:100%;background:rgba(15,23,42,0.4);border-radius:6px;display:flex;align-items:flex-end;padding:4px;">
            <div style="width:100%;height:${Math.max(heightPct, 5)}%;background:linear-gradient(to top, var(--primary), var(--secondary));border-radius:4px;transition:height 0.5s ease;"></div>
          </div>
          <div style="font-size:11px;color:var(--text-secondary);text-align:center;">${dayLabel}</div>
          <div style="font-size:12px;font-weight:600;color:var(--primary-light);">${count}</div>
        </div>
      `;
    }

    return `<div style="padding:8px;"><div style="display:flex;gap:8px;height:160px;">${barsHtml}</div></div>`;
  }

  /**
   * 渲染"之最"页签 - 各种极端记录
   */
  _renderExtremeStats() {
    const records = this._getHistoryForPrinter(this._selectedPrinter);
    if (!records || records.length === 0) return '';

    const allWithDuration = records.filter(r => r.duration_hours > 0);
    const allWithWeight = records.filter(r => (r.total_weight || 0) > 0);

    const longest = allWithDuration.length > 0
      ? allWithDuration.reduce((a, b) => a.duration_hours > b.duration_hours ? a : b) : null;
    const shortest = allWithDuration.length > 0
      ? allWithDuration.reduce((a, b) => a.duration_hours < b.duration_hours ? a : b) : null;
    const heaviest = allWithWeight.length > 0
      ? allWithWeight.reduce((a, b) => (a.total_weight || 0) > (b.total_weight || 0) ? a : b) : null;
    const lightest = allWithWeight.filter(r => (r.total_weight || 0) > 0).length > 0
      ? allWithWeight.filter(r => (r.total_weight || 0) > 0).reduce((a, b) => (a.total_weight || 0) < (b.total_weight || 0) ? a : b) : null;
    const mostColors = records.filter(r => (r.colors_used || []).length > 1).length > 0
      ? records.filter(r => (r.colors_used || []).length > 1).reduce((a, b) => (a.colors_used || []).length > (b.colors_used || []).length ? a : b) : null;

    const recordCard = (icon, title, record, valueFn, extraFn) => {
      if (!record) return '';
      const taskNameHtml = this._formatTaskName(record);
      const printerTag = this._selectedPrinter === '全部' && record._printer_name
        ? `<span class="printer-tag">${this._escapeHtml(record._printer_name)}</span>` : '';
      const fmtDate = (ts) => {
        if (!ts) return '';
        try {
          let d = ts.includes('T') ? new Date(ts) : new Date(ts.replace(' ', 'T'));
          if (isNaN(d.getTime())) return '';
          const p = (n) => String(n).padStart(2, '0');
          return `${d.getFullYear()}/${p(d.getMonth()+1)}/${p(d.getDate())}`;
        } catch(e) { return ''; }
      };
      const dateStr = fmtDate(record.end_time || record.start_time);
      const materialTag = record.filament_type
        ? `<span style="color:var(--primary);font-weight:500;">${this._escapeHtml(record.filament_type)}</span>` : '';
      const extraContent = extraFn ? extraFn(record) : '';
      return `<div class="stat-card" style="padding:14px;text-align:left;">
        <div style="font-size:13px;color:var(--text-muted);margin-bottom:6px;">${icon} ${title}</div>
        <div style="font-size:16px;font-weight:700;color:var(--primary-light);margin-bottom:4px;display:flex;align-items:center;gap:6px;">${valueFn(record)} ${extraContent}</div>
        <div style="font-size:12px;color:var(--text-secondary);">${taskNameHtml} ${printerTag}</div>
        <div style="font-size:11px;color:var(--text-muted);margin-top:3px;display:flex;gap:8px;flex-wrap:wrap;">
          ${dateStr ? `📅 ${dateStr}` : ''}${materialTag ? `<span style="background:rgba(99,102,241,0.12);padding:1px 6px;border-radius:8px;font-size:10px;">🧵 ${materialTag}</span>` : ''}
        </div>
      </div>`;
    };

    const renderColorDots = (r) => {
      const colorsUsed = r.colors_used || [];
      if (colorsUsed.length === 0) return '';
      let colorDots = colorsUsed.slice(0, 6).map(c =>
        `<span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:${this._sanitizeColor(c)};border:1px solid rgba(255,255,255,0.3);"></span>`
      ).join('');
      if (colorsUsed.length > 6) colorDots += `<span style="font-size:10px;color:var(--text-muted);">+${colorsUsed.length - 6}</span>`;
      return colorDots;
    };

    let html = '<div class="stats-grid" style="gap:10px;">';
    html += recordCard('⏱️', '最长打印', longest, r => this._formatDurationHours(r.duration_hours), renderColorDots);
    html += recordCard('⚡', '最短打印', shortest, r => this._formatDurationHours(r.duration_hours), renderColorDots);
    html += recordCard('⚖️', '最重打印', heaviest, r => `${(r.total_weight || 0).toFixed(1)}g`, renderColorDots);
    html += recordCard('🪶', '最轻打印', lightest, r => `${(r.total_weight || 0).toFixed(1)}g`, renderColorDots);
    html += recordCard('🎨', '最多颜色', mostColors, r => `${(r.colors_used || []).length} 色`, renderColorDots);
    html += '</div>';
    return html;
  }

  _renderRecordsTab() {
    const records = this._getHistoryForPrinter(this._selectedPrinter);
    if (!records || records.length === 0) {
      return `<div class="empty-state"><div class="empty-state-icon">📭</div><div class="empty-state-text">暂无数据</div></div>`;
    }

    const finished = records.filter(r => this._isSuccessStatus(r.status));
    const failed = records.filter(r => this._isFailedStatus(r.status));
    const allWithDuration = records.filter(r => r.duration_hours > 0);
    const allWithWeight = records.filter(r => (r.total_weight || 0) > 0);

    const avgDuration = allWithDuration.length > 0
      ? (allWithDuration.reduce((s, r) => s + r.duration_hours, 0) / allWithDuration.length) : 0;
    const avgWeight = allWithWeight.length > 0
      ? (allWithWeight.reduce((s, r) => s + (r.total_weight || 0), 0) / allWithWeight.length) : 0;
    const medianDuration = allWithDuration.length > 0
      ? [...allWithDuration].sort((a, b) => a.duration_hours - b.duration_hours)[Math.floor(allWithDuration.length / 2)].duration_hours : 0;

    return '';
  }

  _renderRecentPrints() {
    const history = this._getHistoryForPrinter(this._selectedPrinter);
    if (!Array.isArray(history) || history.length === 0) return '';
    const sorted = [...history].sort((a, b) => {
      const tA = a.end_time || a.start_time || '';
      const tB = b.end_time || b.start_time || '';
      return new Date(tB) - new Date(tA);
    });
    const recent = sorted.slice(0, 5);
    if (recent.length === 0) return '';
    let html = `<div class="section-header"><div class="section-title"><span class="section-icon">📋</span><span>最近打印</span></div></div>`;
    html += `<div style="display:flex;flex-direction:column;gap:8px;">`;
    for (const item of recent) {
      const status = item.status || 'unknown';
      const statusMap = {
        'finish': { icon: '✅', color: 'var(--success)' },
        '完成': { icon: '✅', color: 'var(--success)' },
        '成功': { icon: '✅', color: 'var(--success)' },
        'failed': { icon: '❌', color: 'var(--danger)' },
        'fail': { icon: '❌', color: 'var(--danger)' },
        '失败': { icon: '❌', color: 'var(--danger)' },
        'cancelled': { icon: '⚠️', color: 'var(--warning)' },
        '已取消': { icon: '⚠️', color: 'var(--warning)' },
        'printing': { icon: '🔵', color: 'var(--primary)' }
      };
      const si = statusMap[status] || { icon: '❓', color: 'var(--text-muted)' };
      const taskNameHtml = this._formatTaskName(item);
      const ft = this._escapeHtml(item.filament_type || '');
      const wt = item.total_weight ? `${item.total_weight.toFixed(1)}g` : '';
      let durMin = item.duration_minutes || (item.duration_hours ? item.duration_hours * 60 : null);
      if (!durMin && item.start_time && item.end_time) {
        try {
          const s = new Date(item.start_time.includes('T') ? item.start_time : item.start_time.replace(' ', 'T'));
          const e = new Date(item.end_time.includes('T') ? item.end_time : item.end_time.replace(' ', 'T'));
          if (!isNaN(s.getTime()) && !isNaN(e.getTime()) && e > s) durMin = (e - s) / 60000;
        } catch(ex) {}
      }
      const dur = durMin ? this._formatDuration(durMin) : '';
      const _fmtTs = (ts) => {
        if (!ts) return '';
        try {
          let d = ts.includes('T') ? new Date(ts) : new Date(ts.replace(' ', 'T'));
          if (isNaN(d.getTime())) return '';
          const p = (n) => String(n).padStart(2, '0');
          return `${p(d.getMonth()+1)}/${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
        } catch(ex) { return ''; }
      };
      const endTime = _fmtTs(item.end_time);
      const colorsUsed = item.colors_used || [];
      let colorDots = '';
      if (colorsUsed.length > 0) {
        colorDots = colorsUsed.slice(0, 4).map(c =>
          `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${this._sanitizeColor(c)};border:1px solid rgba(255,255,255,0.2);margin-right:2px;vertical-align:middle;"></span>`
        ).join('');
        if (colorsUsed.length > 4) colorDots += `<span style="font-size:10px;color:var(--text-muted);vertical-align:middle;">+${colorsUsed.length - 4}</span>`;
      }
      const isFailed = ['failed', 'fail', '失败'].includes(status);
      const taskNameColor = isFailed ? 'color:var(--danger);font-weight:600;' : '';
      html += `<div style="display:flex;align-items:center;gap:8px;padding:8px 12px;background:var(--surface-card);border-radius:8px;border:1px solid var(--border);flex-wrap:wrap;">
        <div style="flex:1;min-width:100px;font-size:12px;${taskNameColor}">${taskNameHtml}</div>
        ${dur ? `<span style="font-size:11px;color:var(--text-secondary);white-space:nowrap;">⏱${dur}</span>` : ''}
        ${endTime ? `<span style="font-size:11px;color:var(--text-muted);white-space:nowrap;">${endTime}</span>` : ''}
        ${ft ? `<span style="font-size:11px;color:var(--text-secondary);white-space:nowrap;">🧵${ft}</span>` : ''}
        ${wt ? `<span style="font-size:11px;color:var(--primary-light);font-weight:600;white-space:nowrap;">${wt}</span>` : ''}
        ${colorDots ? `<span style="white-space:nowrap;">${colorDots}</span>` : ''}
      </div>`;
    }
    html += `</div>`;
    return html;
  }

  /**
   * 渲染耗材使用情况
   */
  _renderFilamentBarCharts() {
    const history = this._getHistoryForPrinter(this._selectedPrinter);
    let typeUsage = {};
    let colorUsage = {};

    if (Array.isArray(history) && history.length > 0 &&
      history.some(item => this._isSuccessStatus(item.status) && (item.total_weight > 0 || item.filament_type))) {
      this._extractFilamentFromHistory(history, typeUsage, colorUsage);
    }

    if (Object.keys(typeUsage).length === 0 && Object.keys(colorUsage).length === 0) {
      this._extractFilamentFromStats(typeUsage, colorUsage);
    }

    if (Object.keys(typeUsage).length === 0 && Object.keys(colorUsage).length === 0) return '';

    let html = '';
    html += this._renderColorUsageBarChart(colorUsage);
    html += this._renderTypeUsageBarChart(typeUsage);
    return html;
  }

  _renderFilamentUsage() {
    const history = this._getHistoryForPrinter(this._selectedPrinter);
    let typeUsage = {};
    let colorUsage = {};
    let multiColorPrints = [];
    let hasData = false;

    if (Array.isArray(history) && history.length > 0 &&
      history.some(item => this._isSuccessStatus(item.status) && (item.total_weight > 0 || item.filament_type))) {

      const result = this._extractFilamentFromHistory(history, typeUsage, colorUsage);
      hasData = result.hasData;
      multiColorPrints = result.multiColorPrints || [];

    }

    if (!hasData && Object.keys(typeUsage).length === 0 && Object.keys(colorUsage).length === 0) {
      hasData = this._extractFilamentFromStats(typeUsage, colorUsage);
    }

    if (!hasData || (Object.keys(typeUsage).length === 0 && Object.keys(colorUsage).length === 0)) {
      return '';
    }

    const pieColors = ['#6366f1', '#22c55e', '#f59e0b', '#ef4444', '#a855f7', '#06b6d4', '#84cc16', '#78350f',
      '#db2777', '#14b8a6', '#f97316', '#64748b', '#4f46e5', '#65a30d', '#ea580c', '#0d9488'];

    let html = '';

    html += this._renderPieChart('耗材类型使用量', typeUsage, pieColors);
    html += this._renderPieChart('耗材颜色使用量', colorUsage, pieColors);
    html += this._renderColorUsageBarChart(colorUsage);
    html += this._renderTypeUsageBarChart(typeUsage);
    return html;
  }

  _formatColorName(colorCode) {
    if (!colorCode) return '未知';
    const cleanCode = colorCode.replace('#', '').substring(0, 6).toUpperCase();
    const standardColors = {
      'FFFFFF': '纯白', '000000': '纯黑', '808080': '灰色', '898989': '中性灰',
      'C0C0C0': '银灰', '161616': '炭黑', 'F72323': '正红', 'FF0000': '亮红',
      'DC143C': '猩红', 'CD5C5C': '印度红', 'B22222': '耐火砖红', '8B0000': '暗红',
      'FF6D00': '橙色', 'FFA500': '橘黄', 'FFF144': '柠檬黄', 'FFFF00': '纯黄',
      '23C160': '翠绿', '00FF00': '荧光绿', '228B22': '森林绿', '00CED1': '青色',
      '1AD2FF': '天蓝', '0000FF': '纯蓝', '9B59B6': '紫罗兰', 'FF69B4': '热粉红',
    };
    if (standardColors[cleanCode]) return standardColors[cleanCode];
    try {
      const r = parseInt(cleanCode.substring(0, 2), 16);
      const g = parseInt(cleanCode.substring(2, 4), 16);
      const b = parseInt(cleanCode.substring(4, 6), 16);
      const hsl = this._rgbToHsl(r, g, b);
      let hueName = '';
      if (hsl.s < 15) {
        if (hsl.l > 85) hueName = '米白';
        else if (hsl.l > 65) hueName = '浅灰';
        else if (hsl.l > 35) hueName = '灰色';
        else if (hsl.l > 15) hueName = '深灰';
        else hueName = '炭黑';
      } else {
        if (hsl.h < 15 || hsl.h >= 345) hueName = '红';
        else if (hsl.h < 45) hueName = '橙';
        else if (hsl.h < 75) hueName = '黄';
        else if (hsl.h < 150) hueName = '绿';
        else if (hsl.h < 195) hueName = '青';
        else if (hsl.h < 255) hueName = '蓝';
        else if (hsl.h < 285) hueName = '紫';
        else hueName = '品红';
        if (hsl.l < 25) hueName = '深' + hueName;
        else if (hsl.l < 45) hueName = '暗' + hueName;
        else if (hsl.l > 75) hueName = '浅' + hueName;
        if (hsl.s < 30) hueName += '(低饱和)';
      }
      return `${hueName} [${cleanCode}]`;
    } catch (e) {
      return `#${cleanCode}`;
    }
  }

  _rgbToHsl(r, g, b) {
    r /= 255; g /= 255; b /= 255;
    const max = Math.max(r, g, b);
    const min = Math.min(r, g, b);
    let h, s, l = (max + min) / 2;
    if (max === min) { h = s = 0; }
    else {
      const d = max - min;
      s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
      switch (max) {
        case r: h = ((g - b) / d + (g < b ? 6 : 0)) / 6; break;
        case g: h = ((b - r) / d + 2) / 6; break;
        case b: h = ((r - g) / d + 4) / 6; break;
      }
    }
    return { h: Math.round(h * 360), s: Math.round(s * 100), l: Math.round(l * 100) };
  }

  _getContrastColor(hexColor) {
    try {
      const hex = hexColor.replace('#', '').substring(0, 6);
      const r = parseInt(hex.substring(0, 2), 16);
      const g = parseInt(hex.substring(2, 4), 16);
      const b = parseInt(hex.substring(4, 6), 16);
      const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
      return luminance > 0.5 ? '#000' : '#fff';
    } catch { return '#000'; }
  }

  _renderPieChart(title, data, colors) {
    const entries = Object.entries(data).filter(([_, v]) => v > 0);
    const cleanTitle = title.replace(/[◆◇●■▲▼★☆♠♣♥♦⬛⬜◼◾◽▪▫]/g, '').replace(/\s+/g, ' ').trim();
    const titleIcon = this._getTitleIcon(cleanTitle);

    if (entries.length === 0) {
      return `<div class="section-header"><div class="section-title"><span class="section-icon">${titleIcon}</span><span>${cleanTitle}</span></div></div>
        <div class="chart-container"><div class="empty-state"><div class="empty-state-icon">📭</div><div class="empty-state-text">暂无数据</div></div></div>`;
    }

    const total = entries.reduce((sum, [_, v]) => sum + v, 0);
    let paths = '', legendHtml = '';

    for (let i = 0; i < entries.length; i++) {
      const [label, value] = entries[i];
      const pct = value / total;
      const endAngle = (i > 0 ? entries.slice(0, i).reduce((acc, [_, v]) => acc + v, 0) : 0) / total * 2 * Math.PI;
      const startAngle = endAngle - pct * 2 * Math.PI;
      const x1 = 80 + 70 * Math.cos(startAngle - Math.PI / 2);
      const y1 = 80 + 70 * Math.sin(startAngle - Math.PI / 2);
      const x2 = 80 + 70 * Math.cos(endAngle - Math.PI / 2);
      const y2 = 80 + 70 * Math.sin(endAngle - Math.PI / 2);
      const largeArc = pct > 0.5 ? 1 : 0;
      const d = `M80,80 L${x1},${y1} A70,70 0 ${largeArc},1 ${x2},${y2} Z`;
      const color = colors[i % colors.length];
      paths += `<path d="${d}" fill="${color}" stroke="rgba(15,23,42,0.8)" stroke-width="2"/>`;
      const displayName = label.length > 15 ? label.substring(0, 12) + '..' : label;
      legendHtml += `<div class="legend-item">
        <div class="legend-color" style="background:${color}"></div>
        <span class="legend-label">${displayName}</span>
        <span class="legend-value">${Math.round(value)}g</span>
      </div>`;
    }

    return `<div class="section-header"><div class="section-title"><span class="section-icon">${titleIcon}</span><span>${cleanTitle}</span></div></div>
      <div class="chart-container">
        <div class="pie-wrapper">
          <svg class="pie-chart" width="160" height="160" viewBox="0 0 160 160">${paths}</svg>
          <div class="pie-legend">${legendHtml}</div>
        </div>
      </div>`;
  }

  _renderColorUsageBarChart(colorUsage) {
    const entries = Object.entries(colorUsage).filter(([_, v]) => v > 0).sort((a, b) => b[1] - a[1]);
    if (entries.length === 0) return '';
    const maxWeight = Math.max(...entries.map(([_, v]) => v));
    let barsHtml = '';
    for (const [colorKey, weight] of entries) {
      const pct = maxWeight > 0 ? (weight / maxWeight) * 100 : 0;
      const displayName = this._formatColorName(colorKey);
      barsHtml += `<div style="display:flex;align-items:center;gap:10px;padding:6px 0;">
        <span style="width:12px;height:12px;border-radius:50%;background:${this._sanitizeColor(colorKey)};border:1px solid rgba(255,255,255,0.2);flex-shrink:0;"></span>
        <span style="min-width:90px;max-width:140px;font-size:12px;color:var(--text-secondary);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${this._escapeHtml(displayName)}</span>
        <div style="flex:1;height:20px;background:var(--surface-card);border-radius:4px;overflow:hidden;border:1px solid var(--border);">
          <div style="height:100%;width:${pct}%;background:${this._sanitizeColor(colorKey)};border-radius:4px;min-width:2px;opacity:0.85;"></div>
        </div>
        <span style="min-width:50px;text-align:right;font-size:12px;font-weight:700;color:var(--primary-light);">${Math.round(weight)}g</span>
      </div>`;
    }
    return `<div class="section-header"><div class="section-title"><span class="section-icon">🎨</span><span>颜色使用量对比图</span></div></div>
      <div class="chart-container">${barsHtml}</div>`;
  }

  _renderTypeUsageBarChart(typeUsage) {
    const entries = Object.entries(typeUsage).filter(([_, v]) => v > 0).sort((a, b) => b[1] - a[1]);
    if (entries.length === 0) return '';
    const maxWeight = Math.max(...entries.map(([_, v]) => v));
    const gradientColors = ['#6366f1','#22c55e','#f59e0b','#ef4444','#a855f7','#06b6d4','#84cc16','#db2777','#14b8a6','#f97316'];
    let barsHtml = '';
    for (let i = 0; i < entries.length; i++) {
      const [typeKey, weight] = entries[i];
      const pct = maxWeight > 0 ? (weight / maxWeight) * 100 : 0;
      const color = gradientColors[i % gradientColors.length];
      barsHtml += `<div style="display:flex;align-items:center;gap:10px;padding:6px 0;">
        <span style="min-width:90px;max-width:140px;font-size:12px;color:var(--text-secondary);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${this._escapeHtml(typeKey)}</span>
        <div style="flex:1;height:20px;background:var(--surface-card);border-radius:4px;overflow:hidden;border:1px solid var(--border);">
          <div style="height:100%;width:${pct}%;background:linear-gradient(90deg,${color},${color}88);border-radius:4px;min-width:2px;"></div>
        </div>
        <span style="min-width:50px;text-align:right;font-size:12px;font-weight:700;color:var(--primary-light);">${Math.round(weight)}g</span>
      </div>`;
    }
    return `<div class="section-header"><div class="section-title"><span class="section-icon">🏷️</span><span>耗材类型使用量对比图</span></div></div>
      <div class="chart-container">${barsHtml}</div>`;
  }

  _renderRealtimeMonitor() {
    const printers = this._getPrintersConfig();
    let html = `<div class="section-header"><div class="section-title"><span class="section-icon">📡</span><span>实时监控面板</span></div></div>`;

    // 只显示当前选择的打印机
    const selectedPrinterName = this._selectedPrinter;
    let printerToDisplay = null;
    
    if (selectedPrinterName !== '全部') {
      printerToDisplay = printers.find(p => p.printer_name === selectedPrinterName);
    } else if (printers.length > 0) {
      // 如果选择"全部"，只显示第一台打印机
      printerToDisplay = printers[0];
    }
    
    if (printerToDisplay) {
      const e = printerToDisplay.entities;
      // 优先从 current_print 获取真实任务名（模型名），否则回退到 current_task 实体
      const cp = this._getAttr(e.current_print) || {};
      const modelNameFromCP = cp.task_name_model || '';
      const configNameFromCP = cp.task_name_config || cp.config_name || '';
      let displayTaskName = modelNameFromCP || cp.task_name || '';
      if (!displayTaskName) {
        displayTaskName = this._getState(e.current_task) || '未配置';
        // 如果显示的是参数描述，尝试从 task_name 实体获取（可能是模型名）
        if (this._isParamDescription(displayTaskName)) {
          const rawTaskName = this._getState(e.task_name);
          if (rawTaskName && rawTaskName !== 'unknown' && rawTaskName !== displayTaskName && !this._isParamDescription(rawTaskName)) {
            displayTaskName = rawTaskName;
          }
        }
      }
      const printProgress = this._getState(e.print_progress) || '0';
      const currentWeight = this._getState(e.current_weight) || 'N/A';
      const chamberTemp = this._getState(e.chamber_temperature) || 'N/A';
      const speedProfile = this._getState(e.speed_profile) || 'N/A';
      const nozzleSize = this._getState(e.nozzle_size) || 'N/A';
      const activeTray = this._getState(e.active_tray);

      let statusClass = 'idle';
      let statusText = '空闲';
      if (printProgress && parseFloat(printProgress) > 0 && parseFloat(printProgress) < 100) {
        statusClass = 'printing';
        statusText = `打印中 ${printProgress}%`;
      } else if (displayTaskName && displayTaskName !== 'unknown' && displayTaskName !== 'unavailable' && displayTaskName !== '未配置') {
        statusClass = 'finish';
        statusText = '已完成';
      }

      // 计算预计完成时间 - 多源回退
      const remainingTime = this._getState(e.remaining_time);
      let endDisplay = '';
      // 方法1: end_time 实体
      const endTimeVal = this._getState(e.end_time);
      if (endTimeVal && endTimeVal !== 'unknown' && endTimeVal !== 'unavailable' && endTimeVal !== '') {
        try {
          const endDate = new Date(endTimeVal.includes('T') ? endTimeVal : endTimeVal.replace(' ', 'T'));
          if (!isNaN(endDate.getTime())) {
            endDisplay = `${endDate.getHours()}:${endDate.getMinutes().toString().padStart(2,'0')} 完成`;
          }
        } catch (e) {}
      }
      // 方法2: remaining_time 计算
      if (!endDisplay && remainingTime && remainingTime !== 'unknown' && remainingTime !== 'unavailable') {
        try {
          const mins = parseInt(remainingTime);
          if (!isNaN(mins) && mins > 0) {
            const ed = new Date(Date.now() + mins * 60000);
            endDisplay = `${ed.getHours()}:${ed.getMinutes().toString().padStart(2,'0')} 预计`;
          }
        } catch (e) {}
      }
      // 方法3: 用进度估算剩余时间
      if (!endDisplay && cp) {
        try {
          const prog = parseFloat(printProgress) || 0;
          const stStr = cp.start_time || '';
          if (prog > 5 && prog < 99 && stStr) {
            const st = new Date(stStr.includes('T') ? stStr : stStr.replace(' ', 'T'));
            if (!isNaN(st.getTime())) {
              const elapsed = Date.now() - st.getTime();
              const remainMs = elapsed / prog * (100 - prog);
              if (remainMs > 0 && remainMs < 86400000 * 7) {
                const estEnd = new Date(Date.now() + remainMs);
                endDisplay = `${estEnd.getHours()}:${estEnd.getMinutes().toString().padStart(2,'0')} 估算`;
              }
            }
          }
        } catch (e) {}
      }

      // AMS 耗材盘
      let amsHtml = '';
      const trayKeys = ['ams_1_tray_1', 'ams_1_tray_2', 'ams_1_tray_3', 'ams_1_tray_4'];
      const trays = trayKeys.map((k, i) => ({ num: i + 1, entity: e[k] })).filter(t => t.entity);
      if (trays.length > 0) {
        amsHtml = `<div style="margin-top:12px;">
          <div style="font-size:12px;font-weight:700;color:var(--text-primary);margin-bottom:8px;display:flex;align-items:center;gap:6px;">
            <span>🎨</span> AMS耗材盘
          </div>
          <div class="ams-grid">`;
        trays.forEach(tray => {
          const trayData = this._getAttr(tray.entity);
          const trayName = trayData.name || `托盘${tray.num}`;
          const trayColor = trayData.color || '#cccccc';
          const isActive = activeTray && activeTray.includes(`tray_${tray.num}`);
          amsHtml += `<div class="ams-tray ${isActive ? 'active' : ''}">
            <div class="ams-tray-number">托盘 ${tray.num}</div>
            <div class="ams-tray-color" style="background:${trayColor}"></div>
            <div class="ams-tray-name">${this._escapeHtml(trayName)}</div>
          </div>`;
        });
        amsHtml += '</div></div>';
      }

      html += `<div class="realtime-panel" style="margin-bottom:16px;">
        <div class="realtime-header">
          <div class="realtime-title">🖥️ ${this._escapeHtml(printerToDisplay.printer_name)}</div>
          <div style="display:flex;align-items:center;gap:8px;">
            ${printers.length > 1 ? printers.map(p => {
              const isActive = p.printer_name === printerToDisplay.printer_name;
              const pProgress = this._getState(p.entities.print_progress) || '0';
              const pPrinting = parseFloat(pProgress) > 0 && parseFloat(pProgress) < 100;
              return `<button class="monitor-switch-btn ${isActive ? 'active' : ''}" data-printer="${this._escapeHtml(p.printer_name)}" title="${this._escapeHtml(p.printer_name)}">
                <span class="monitor-switch-dot" style="background:${pPrinting ? 'var(--success)' : 'var(--text-muted)'}"></span>
                ${this._escapeHtml(p.printer_name)}
              </button>`;
            }).join('') : ''}
            <div class="status-badge ${statusClass}">${statusText}</div>
          </div>
        </div>
        <div class="realtime-grid">
          <div class="realtime-item">
            <div class="realtime-label">📋 当前任务</div>
            <div class="realtime-value">${this._escapeHtml(displayTaskName || '空闲')}</div>
          <div class="realtime-item">
            <div class="realtime-label">📊 打印进度</div>
            <div class="realtime-value" style="display:flex;justify-content:space-between;align-items:center;">
              <span>${printProgress}%</span>
              ${endDisplay ? `<span style="font-size:11px;color:var(--primary-light);font-weight:600;">⏰ ${endDisplay}</span>` : ''}
            </div>
            <div class="progress-track" style="margin-top:6px;">
              <div class="progress-fill" style="width:${printProgress}%"></div>
            </div>
          </div>
          ${currentWeight && currentWeight !== 'N/A' ? `<div class="realtime-item">
            <div class="realtime-label">⚖️ 当前耗材</div>
            <div class="realtime-value">${currentWeight}<small style="font-size:12px;color:var(--text-muted);font-weight:500;">g</small></div>
          </div>` : ''}
          ${chamberTemp && chamberTemp !== 'N/A' ? `<div class="realtime-item">
            <div class="realtime-label">💨 腔体</div>
            <div class="realtime-value">${chamberTemp}<small style="font-size:12px;color:var(--text-muted);font-weight:500;">°C</small></div>
          </div>` : ''}
          ${speedProfile && speedProfile !== 'N/A' ? `<div class="realtime-item">
            <div class="realtime-label">⚡ 速度</div>
            <div class="realtime-value">${this._escapeHtml(speedProfile)}</div>
          </div>` : ''}
          ${nozzleSize && nozzleSize !== 'N/A' ? `<div class="realtime-item">
            <div class="realtime-label">🔧 喷嘴</div>
            <div class="realtime-value">${nozzleSize}</div>
          </div>` : ''}
        </div>
        ${amsHtml}
      </div>`;
    }
    return html;
  }

  _renderLifetimeStats() {
    const lifetimeStats = this._getEntityForPrinter(this._selectedPrinter, 'material_stats_lifetime');
    if (this._selectedPrinter !== '全部' && !lifetimeStats) return '';
    const lifetimeData = this._getAggregatedAttr('material_stats_lifetime');
    if (!lifetimeData || !lifetimeData.total_weight_g) return '';
    const totalWeight = lifetimeData.total_weight_g || 0;
    const totalLength = lifetimeData.total_length_m || 0;
    const totalEnergy = lifetimeData.total_energy_kwh || 0;
    const totalPrints = lifetimeData.total_prints || 0;

    return `<div class="section-header"><div class="section-title"><span class="section-icon">🏆</span><span>终身统计（累计）</span></div></div>
      <div class="chart-container">
        <table class="stats-table">
          <thead><tr><th>指标</th><th style="text-align:right;">数值</th></tr></thead>
          <tbody>
            <tr><td>${ICON_3D_PRINTER(14, true)} 总打印次数</td><td style="text-align:right;" class="table-value">${totalPrints} 次</td></tr>
            <tr><td>🎨 总耗材重量</td><td style="text-align:right;" class="table-value">${totalWeight.toFixed(1)} 克</td></tr>
            <tr><td>📏 总耗材长度</td><td style="text-align:right;" class="table-value">${totalLength.toFixed(1)} 米</td></tr>
            <tr><td>⚡ 总能耗</td><td style="text-align:right;" class="table-value">${totalEnergy.toFixed(2)} kWh</td></tr>
          </tbody>
        </table>
      </div>`;
  }

  _extractFilamentFromHistory(history, typeUsage, colorUsage) {
    let hasData = false;
    const multiColorPrints = [];
    const processedTaskIds = new Set();

    for (const item of history) {
      const taskId = item.task_id || item.task_name || `${item.start_time}_${item.end_time}`;
      if (processedTaskIds.has(taskId)) continue;
      processedTaskIds.add(taskId);
      if (item.status !== 'finish') continue;

      let colorsUsed = item.colors_used || [];
      let totalColors = item.total_colors || 0;

      if (colorsUsed.length === 0 && item.filament_color) {
        const fc = String(item.filament_color).trim();
        if (fc.includes(',') || fc.includes(';') || fc.includes(' ')) {
          colorsUsed = fc.split(/[,;\s]+/).filter(c => c && c.startsWith('#'));
          if (colorsUsed.length > 0) totalColors = colorsUsed.length;
        } else if (fc.startsWith('#')) {
          colorsUsed = [fc];
          totalColors = 1;
        }
      }

      if (colorsUsed.length === 0 && item.color_usage && Array.isArray(item.color_usage)) {
        // 只统计有实际耗材消耗的颜色，避免将 weight=0 的托盘误判为多色
        colorsUsed = item.color_usage.filter(cu => cu && cu.color && cu.weight_g > 0).map(cu => cu.color);
        if (colorsUsed.length > 1) totalColors = colorsUsed.length;
      }

      let typesUsed = item.types_used || [];
      if (typesUsed.length === 0 && item.filament_type) {
        const ft = String(item.filament_type).trim();
        if (ft.includes(',') || ft.includes(';') || ft.includes('+') || ft.includes('/')) {
          typesUsed = ft.split(/[,;+\/]+/).map(t => t.trim()).filter(t => t && t.length > 1);
        }
      }

      // 去重：同一颜色因多个 tray 或大小写差异导致重复
      if (colorsUsed.length > 1) {
        const uniqueColors = [...new Set(colorsUsed.map(c => String(c).toLowerCase()))];
        if (uniqueColors.length < colorsUsed.length) {
          colorsUsed = uniqueColors;
          totalColors = Math.min(totalColors, uniqueColors.length);
        }
      }

      if (totalColors > 1 || typesUsed.length > 1) {
        multiColorPrints.push({
          ...item,
          colors_used: colorsUsed,
          types_used: typesUsed,
          total_colors: Math.max(totalColors, typesUsed.length)
        });

        if (item.color_usage && Array.isArray(item.color_usage)) {
          for (const cu of item.color_usage) {
            if (!cu.color || !cu.weight_g || cu.weight_g <= 0) continue;
            const colorKey = this._escapeHtml(cu.color);
            if (!colorUsage[colorKey]) colorUsage[colorKey] = 0;
            colorUsage[colorKey] += cu.weight_g;
            if (cu.type) {
              const typeKey = this._escapeHtml(cu.type);
              if (!typeUsage[typeKey]) typeUsage[typeKey] = 0;
              typeUsage[typeKey] += cu.weight_g;
            }
          }
        } else if (colorsUsed.length > 1 && item.total_weight) {
          const avgWeight = item.total_weight / colorsUsed.length;
          for (const color of colorsUsed) {
            const colorKey = this._escapeHtml(color);
            if (!colorUsage[colorKey]) colorUsage[colorKey] = 0;
            colorUsage[colorKey] += avgWeight;
          }
          if (typesUsed.length > 0) {
            const avgTypeWeight = item.total_weight / typesUsed.length;
            for (const type of typesUsed) {
              const typeKey = this._escapeHtml(type);
              if (!typeUsage[typeKey]) typeUsage[typeKey] = 0;
              typeUsage[typeKey] += avgTypeWeight;
            }
          }
          hasData = true;
        }
      } else {
        const ft = this._escapeHtml(item.filament_type || '未知');
        const fc = colorsUsed[0] ? this._escapeHtml(colorsUsed[0]) : this._escapeHtml(item.filament_color || '未知');
        const weight = item.total_weight || 0;
        if (weight > 0) {
          hasData = true;
          if (!typeUsage[ft]) typeUsage[ft] = 0;
          typeUsage[ft] += weight;
          if (!colorUsage[fc]) colorUsage[fc] = 0;
          colorUsage[fc] += weight;
        }
      }
    }

    return {
      hasData: hasData || Object.keys(typeUsage).length > 0 || multiColorPrints.length > 0,
      multiColorPrints
    };
  }

  _extractFilamentFromStats(typeUsage, colorUsage) {
    let hasData = false;
    const currentWeight = this._getState(this.config.current_weight);
    const totalUsage = this._getState(this.config.total_usage);
    const activeTrayName = this._getState(this.config.active_tray);

    let weight = 0;
    if (currentWeight && currentWeight !== 'unavailable' && currentWeight !== 'unknown' && currentWeight !== 'N/A') {
      weight = parseFloat(currentWeight);
    } else if (totalUsage && totalUsage !== 'unavailable' && totalUsage !== 'unknown' && totalUsage !== 'N/A') {
      weight = parseFloat(totalUsage);
    }

    if (Object.keys(typeUsage).length > 0 || Object.keys(colorUsage).length > 0) return false;

    if (weight > 0 && weight < 10000) {
      let filamentType = activeTrayName || '未知耗材';
      let filamentColor = '#FFFFFF';
      const trayConfigs = [this.config.ams_tray_1, this.config.ams_tray_2, this.config.ams_tray_3, this.config.ams_tray_4].filter(t => t);
      for (const trayConfig of trayConfigs) {
        const trayData = this._getAttr(trayConfig);
        if (trayData && trayData.name) {
          const trayName = trayData.name;
          const trayColor = trayData.color || '#FFFFFF';
          if (activeTrayName && (activeTrayName.includes(trayName) || trayName.includes(activeTrayName.replace(' HF', '')) || trayConfigs.indexOf(trayConfig) === 0)) {
            filamentType = trayName;
            filamentColor = trayColor;
            break;
          }
        }
      }
      const typeKey = this._escapeHtml(filamentType);
      const colorKey = this._escapeHtml(filamentColor);
      if (!typeUsage[typeKey] && !colorUsage[colorKey]) {
        typeUsage[typeKey] = weight;
        colorUsage[colorKey] = weight;
        hasData = true;
      }
    }
    return hasData;
  }

  _getTitleIcon(title) {
    const iconMap = {
      '耗材': '🧵', '类型': '🏷️', '颜色': '🎨', '使用': '📊',
      '成功': '✅', '趋势': '📈', '分布': '📊', '热力': '🔥', '活动': '📅',
      '实时': '📡', '监控': '🖥️', '终身': '🏆', '统计': '📋',
      'AMS': '🎨', '耗材盘': '💿', '多色': '🌈'
    };
    for (const [keyword, icon] of Object.entries(iconMap)) {
      if (title.includes(keyword)) return icon;
    }
    return '📊';
  }

  _renderHistoryStats(history) {
    if (!Array.isArray(history) || history.length === 0) {
      return `
        <div class="summary-item"><div class="summary-number">0</div><div class="summary-text">总记录</div></div>
        <div class="summary-item"><div class="summary-number">-</div><div class="summary-text">成功率</div></div>
        <div class="summary-item"><div class="summary-number">0g</div><div class="summary-text">总耗材</div></div>
        <div class="summary-item"><div class="summary-number">0h</div><div class="summary-text">总时长</div></div>
      `;
    }
    const total = history.length;
    const success = history.filter(h => this._isSuccessStatus(h.status)).length;
    const successRate = total > 0 ? ((success / total) * 100).toFixed(1) : 0;
    const totalWeight = history.reduce((sum, h) => sum + (h.total_weight || 0), 0).toFixed(1);
    const totalDuration = this._calculateTotalDuration(history);

    return `
      <div class="summary-item"><div class="summary-number">${total}</div><div class="summary-text">总记录</div></div>
      <div class="summary-item"><div class="summary-number" style="color:${successRate >= 80 ? 'var(--success)' : 'var(--warning)'};">${successRate}%</div><div class="summary-text">成功率</div></div>
      <div class="summary-item"><div class="summary-number">${this._formatWeight(totalWeight)}</div><div class="summary-text">总耗材</div></div>
      <div class="summary-item"><div class="summary-number">${totalDuration}</div><div class="summary-text">总时长</div></div>
    `;
  }

  _calculateTotalDuration(history) {
    let totalMinutes = 0;
    for (const item of history) {
      if (item.start_time && item.end_time) {
        try {
          const start = new Date(item.start_time);
          const end = new Date(item.end_time);
          totalMinutes += (end - start) / (1000 * 60);
        } catch (e) {}
      }
    }
    if (totalMinutes < 60) return `${totalMinutes.toFixed(0)}分钟`;
    const hours = Math.floor(totalMinutes / 60);
    const mins = Math.round(totalMinutes % 60);
    return mins > 0 ? `${hours}h${mins}m` : `${hours}h`;
  }

  _formatTaskName(item) {
    // 解析任务名为两行：模型名在上，配置名在下
    let modelName = '';
    let configName = '';
    
    // 优先使用单独的字段
    if (item.task_name_model) {
      modelName = this._escapeHtml(item.task_name_model);
    }
    if (item.task_name_config || item.config_name) {
      configName = this._escapeHtml(item.task_name_config || item.config_name);
    }
    
    // 如果没有单独字段，尝试从 task_name 中解析（格式："模型名 + 配置名"）
    if (!modelName && !configName && item.task_name) {
      const fullName = item.task_name;
      if (fullName.includes(' + ')) {
        const parts = fullName.split(' + ');
        modelName = this._escapeHtml(parts[0]);
        configName = this._escapeHtml(parts.slice(1).join(' + '));
      } else {
        modelName = this._escapeHtml(fullName);
      }
    }
    
    // 如果没有模型名但有配置名，用配置名作为模型名
    if (!modelName && configName) {
      modelName = configName;
      configName = '';
    }
    
    // 如果都没有，显示默认值
    if (!modelName) {
      modelName = this._escapeHtml(item.task_name || '未命名任务');
    }
    
    // 生成HTML
    if (configName) {
      return `<div style="display:flex;flex-direction:column;line-height:1.3;">
        <div style="font-weight:600;">${modelName}</div>
        <div style="font-size:0.85em;color:var(--text-secondary);">${configName}</div>
      </div>`;
    }
    return `<div>${modelName}</div>`;
  }

  _renderHistoryItem(item, index, options = {}) {
    const taskName = this._escapeHtml(item.task_name || '未命名任务');
    const taskNameHtml = this._formatTaskName(item);
    const status = (item.status || '').trim().toLowerCase();
    const statusConfig = {
      'finish': { text: '成功', class: 'success', icon: '✅' },
      '完成': { text: '成功', class: 'success', icon: '✅' },
      '成功': { text: '成功', class: 'success', icon: '✅' },
      'failed': { text: '失败', class: 'failed', icon: '❌' },
      'fail': { text: '失败', class: 'failed', icon: '❌' },
      '失败': { text: '失败', class: 'failed', icon: '❌' },
      'printing': { text: '进行中', class: 'printing', icon: '🔵' },
      'cancelled': { text: '已取消', class: 'failed', icon: '⚠️' },
      '已取消': { text: '已取消', class: 'failed', icon: '⚠️' }
    };
    let statusInfo = statusConfig[status] || statusConfig[item.status];
    if (!statusInfo) {
      const prog = parseInt(item.progress) || 0;
      if (prog >= 100) statusInfo = { text: '成功', class: 'success', icon: '✅' };
      else if (item.end_time && prog > 0 && prog < 100) statusInfo = { text: '失败', class: 'failed', icon: '❌' };
      else statusInfo = { text: '未知', class: '', icon: '❓' };
    }

    // 统一时区：UTC/本地时间都转为本地显示
    const _fmtLocal = (ts) => {
      if (!ts) return '';
      try {
        let d = ts.includes('T') ? new Date(ts) : new Date(ts.replace(' ', 'T'));
        if (isNaN(d.getTime())) return ts;
        const p = (n) => String(n).padStart(2, '0');
        return `${d.getFullYear()}/${p(d.getMonth()+1)}/${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
      } catch(e) { return ts; }
    };
    const startTime = _fmtLocal(item.start_time);
    const endTime = _fmtLocal(item.end_time);
    const timeRange = (startTime && endTime) ? `${startTime} ~ ${endTime}` : (endTime || startTime || '-');

    let durationMinutes = item.duration_minutes || (item.duration_hours ? item.duration_hours * 60 : null);
    if (!durationMinutes && startTime && endTime) {
      const start = new Date(startTime);
      const end = new Date(endTime);
      if (!isNaN(start.getTime()) && !isNaN(end.getTime()) && end > start) {
        durationMinutes = (end - start) / (1000 * 60);
      }
    }
    const duration = this._formatDuration(durationMinutes);
    const filamentType = this._escapeHtml(item.filament_type || '未知');
    const weight = item.total_weight ? `${item.total_weight.toFixed(1)}g` : '-';
    const energy = item.energy_kwh ? `${item.energy_kwh.toFixed(2)}kWh` : '';
    const colorsUsed = item.colors_used || [];
    const recordId = item.id || `record_${index}`;
    const showCheckbox = options.showCheckbox || false;
    const showPrinterTag = options.showPrinterTag || false;
    const printerName = item._printer_name || '';

    const coverImg = item.cover_image_local || item.cover_image_url;
    const colorBarHtml = colorsUsed.length > 0 ? `<div class="thumbnail-color-bar">${colorsUsed.map(color => `<div class="thumbnail-color-segment" style="background:${this._sanitizeColor(color)}"></div>`).join('')}</div>` : '';

    const coverHtml = coverImg
      ? `<img class="history-cover-img" src="${this._escapeHtml(coverImg)}" alt="${taskName}" onerror="this.style.display='none';this.nextElementSibling.style.display='flex';">
         <div class="history-thumbnail" style="display:none;background:linear-gradient(135deg, ${this._sanitizeColor(colorsUsed[0]) || 'rgba(99,102,241,0.2)'}, ${this._sanitizeColor(colorsUsed[1]) || this._sanitizeColor(colorsUsed[0]) || 'rgba(6,182,212,0.1)'});">${statusInfo.icon}${colorBarHtml}</div>`
      : `<div class="history-thumbnail" style="background:linear-gradient(135deg, ${this._sanitizeColor(colorsUsed[0]) || 'rgba(99,102,241,0.2)'}, ${this._sanitizeColor(colorsUsed[1]) || this._sanitizeColor(colorsUsed[0]) || 'rgba(6,182,212,0.1)'});">${statusInfo.icon}${colorBarHtml}</div>`;

    const taskNamePlain = item.task_name || '未命名任务';
    return `
      <div class="history-item" data-status="${status}" data-name="${taskNamePlain.toLowerCase()}" data-type="${filamentType.toLowerCase()}" data-record-id="${recordId}">
        ${showCheckbox ? `<input type="checkbox" class="record-checkbox" data-record-id="${recordId}" ${this._selectedRecords.has(recordId) ? 'checked' : ''}>` : ''}
        <div class="history-status ${statusInfo.class}">${statusInfo.icon} ${statusInfo.text}</div>
        ${coverHtml}
        <div class="history-details">
          <div class="history-task-name">${taskNameHtml} ${showPrinterTag && printerName ? `<span class="printer-tag">${printerName}</span>` : ''}</div>
          <div class="history-meta">
            <span>⏱️ ${duration}</span>
            <span>🧵 ${filamentType}</span>
            ${weight !== '-' ? `<span>⚖️ ${weight}</span>` : ''}
            ${energy ? `<span>⚡ ${energy}</span>` : ''}
            ${colorsUsed.length > 0 ? `<span class="color-dots-inline">${colorsUsed.slice(0, 4).map(c => `<span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:${this._sanitizeColor(c)};border:1px solid rgba(255,255,255,0.2);margin-right:2px;vertical-align:middle;"></span>`).join('')}${colorsUsed.length > 4 ? '+' + (colorsUsed.length - 4) : ''}</span>` : ''}
          </div>
          <div class="history-date">📅 ${timeRange}</div>
        </div>
      </div>
    `;
  }

  _formatDuration(minutes) {
    if (!minutes || minutes <= 0) return '-';
    minutes = parseFloat(minutes);
    if (minutes < 60) return `${Math.round(minutes)}min`;
    const hours = Math.floor(minutes / 60);
    const mins = Math.round(minutes % 60);
    return mins > 0 ? `${hours}.${(mins / 6).toFixed(1).substring(2)}h` : `${hours}h`;
  }

  _getAllMergedRecords() {
    const allRecords = [];
    const printers = this._getPrintersConfig();
    for (const p of printers) {
      if (!p.entities.print_history || !this._hass) continue;
      const entity = this._hass.states[p.entities.print_history];
      if (!entity?.attributes?.history) continue;
      const records = entity.attributes.history;
      records.forEach(r => {
        r._printer_name = p.printer_name;
        r._printer_entity = p.entities.print_history;
      });
      allRecords.push(...records);
    }
    allRecords.sort((a, b) => {
      const timeA = a.end_time || a.start_time || '';
      const timeB = b.end_time || b.start_time || '';
      return new Date(timeB) - new Date(timeA);
    });
    return allRecords;
  }

  _filterRecordsByDate(records) {
    return records.filter(r => {
      if (this._dateFrom || this._dateTo) {
        const time = r.end_time || r.start_time || '';
        if (!time) return false;
        const date = time.substring(0, 10);
        if (this._dateFrom && date < this._dateFrom) return false;
        if (this._dateTo && date > this._dateTo) return false;
      }
      if (this._filterStatus && !this._isStatusMatch(r.status, this._filterStatus)) return false;
      if (this._filterPrinter && (r._printer_name || '') !== this._filterPrinter) return false;
      if (this._filterColor) {
        const colors = r.colors_used || [];
        if (!colors.includes(this._filterColor) && r.filament_color !== this._filterColor) return false;
      }
      if (this._searchQuery) {
        const q = this._searchQuery.toLowerCase();
        const name = (r.task_name || '').toLowerCase();
        const type = (r.filament_type || '').toLowerCase();
        if (!name.includes(q) && !type.includes(q)) return false;
      }
      return true;
    });
  }

  _exportHistoryToCSV() {
    const allRecords = this._getAllMergedRecords();
    const filtered = this._filterRecordsByDate(allRecords);
    if (filtered.length === 0) {
      alert('没有可导出的记录');
      return;
    }

    const statusMap = { 'finish': '成功', '完成': '成功', '成功': '成功', 'failed': '失败', 'fail': '失败', '失败': '失败', 'cancelled': '已取消', '已取消': '已取消' };
    const headers = ['序号', '任务名称', '打印机', '状态', '开始时间', '结束时间', '时长(分钟)', '耗材类型', '耗材颜色', '耗材重量(g)', '耗材长度(m)', '能耗(kWh)', '喷嘴温度(°C)', '热床温度(°C)', '腔温(°C)', '速度配置', '喷嘴尺寸'];
    const rows = filtered.map((r, i) => {
      const chamberTemp = r.chamber_temp_last5min?.avg ?? r.chamber_temp_final ?? '';
      return [
        i + 1,
        r.task_name || '',
        r._printer_name || '',
        statusMap[r.status] || r.status || '',
        r.start_time || '',
        r.end_time || '',
        r.duration_minutes || r.print_duration || '',
        r.filament_type || '',
        r.filament_color || '',
        r.total_weight || r.weight || '',
        r.total_length || r.length || '',
        r.total_energy || '',
        r.nozzle_temp || '',
        r.bed_temp || '',
        chamberTemp,
        r.speed_profile || '',
        r.nozzle_size || ''
      ];
    });

    // BOM + CSV内容，确保Excel正确识别UTF-8
    const csvContent = '\uFEFF' + [headers, ...rows]
      .map(row => row.map(cell => {
        const s = String(cell).replace(/"/g, '""');
        return s.includes(',') || s.includes('"') || s.includes('\n') ? `"${s}"` : s;
      }).join(','))
      .join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').substring(0, 19);
    a.href = url;
    a.download = `打印历史_${timestamp}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  _renderMergedHistoryPage() {
    const allRecords = this._getAllMergedRecords();
    const filtered = this._filterRecordsByDate(allRecords);

    // 提取所有用过的颜色
    const colorSet = new Set();
    for (const r of allRecords) {
      const colors = r.colors_used || [];
      for (const c of colors) {
        if (c) colorSet.add(c);
      }
      if (r.filament_color && !colors.length) colorSet.add(r.filament_color);
    }
    const colorOptions = [...colorSet].map(c =>
      `<option value="${this._escapeHtml(c)}" ${this._filterColor === c ? 'selected' : ''}>${this._formatColorName(c)}</option>`
    ).join('');

    const printers = this._getPrintersConfig();
    const printerOptions = printers.length > 1 ? printers.map(p =>
      `<option value="${this._escapeHtml(p.printer_name)}" ${this._filterPrinter === p.printer_name ? 'selected' : ''}>${this._escapeHtml(p.printer_name)}</option>`
    ).join('') : '';

    // 分页
    const total = filtered.length;
    const totalPages = Math.max(1, Math.ceil(total / this._pageSize));
    if (this._currentPage > totalPages) this._currentPage = totalPages;
    const startIdx = (this._currentPage - 1) * this._pageSize;
    const pageItems = filtered.slice(startIdx, startIdx + this._pageSize);

    let paginationHtml = '';
    if (totalPages > 1) {
      let pageButtons = '';
      pageButtons += `<button class="page-btn" data-page="${this._currentPage - 1}" ${this._currentPage <= 1 ? 'disabled' : ''}>◀</button>`;
      const maxVisible = 7;
      let startPage = Math.max(1, this._currentPage - 3);
      let endPage = Math.min(totalPages, startPage + maxVisible - 1);
      if (endPage - startPage < maxVisible - 1) startPage = Math.max(1, endPage - maxVisible + 1);
      for (let p = startPage; p <= endPage; p++) {
        pageButtons += `<button class="page-btn ${p === this._currentPage ? 'active' : ''}" data-page="${p}">${p}</button>`;
      }
      pageButtons += `<button class="page-btn" data-page="${this._currentPage + 1}" ${this._currentPage >= totalPages ? 'disabled' : ''}>▶</button>`;
      paginationHtml = `
        <div class="pagination">
          ${pageButtons}
          <span class="page-info">${total} 条记录，第 ${this._currentPage}/${totalPages} 页</span>
        </div>`;
    }

    return `
      <div class="filter-bar">
        ${printerOptions ? `<select class="filter-select" id="filter-printer">
          <option value="" ${!this._filterPrinter ? 'selected' : ''}>全部打印机</option>
          ${printerOptions}
        </select>` : ''}
        <select class="filter-select" id="filter-status">
          <option value="" ${!this._filterStatus ? 'selected' : ''}>全部状态</option>
          <option value="finish" ${this._filterStatus === 'finish' ? 'selected' : ''}>✅ 成功</option>
          <option value="failed" ${this._filterStatus === 'failed' ? 'selected' : ''}>❌ 失败</option>
          <option value="cancelled" ${this._filterStatus === 'cancelled' ? 'selected' : ''}>⚠️ 已取消</option>
        </select>
        <select class="filter-select" id="filter-color">
          <option value="" ${!this._filterColor ? 'selected' : ''}>全部颜色</option>
          ${colorOptions}
        </select>
        <div class="date-filter">
          <input type="date" class="date-input" id="date-from" value="${this._dateFrom}">
          <span class="date-separator">至</span>
          <input type="date" class="date-input" id="date-to" value="${this._dateTo}">
        </div>
        <div class="search-box">
          <span class="search-icon">🔍</span>
          <input type="text" class="search-input" id="search-input" placeholder="搜索任务名称或耗材类型..." value="${this._escapeHtml(this._searchQuery)}">
        </div>
        <div class="filter-actions">
          <button class="btn-filter btn-filter-apply" id="btn-apply-filter">确定</button>
          <button class="btn-filter btn-filter-reset" id="btn-reset-filter">重置</button>
          <button class="btn-filter btn-filter-export" id="btn-export-csv" title="导出为CSV表格">📥 导出</button>
        </div>
      </div>
      <div class="summary-bar">
        ${this._renderHistoryStats(filtered)}
      </div>
      <div id="delete-bar" class="delete-bar" style="display:${this._selectedRecords.size > 0 ? 'flex' : 'none'};">
        <span class="delete-bar-text">已选择 <span id="selected-count">${this._selectedRecords.size}</span> 条记录</span>
        <button class="btn btn-danger" id="btn-delete-selected">🗑️ 删除选中</button>
      </div>
      <div class="history-wrapper">
        ${pageItems.length > 0
          ? pageItems.map((item, index) => this._renderHistoryItem(item, startIdx + index, { showCheckbox: true, showPrinterTag: true })).join('')
          : `<div class="history-empty-state"><div class="history-empty-icon">📭</div><div class="history-empty-text">暂无打印历史记录</div></div>`
        }
      </div>
      ${paginationHtml}
    `;
  }

  _getDetailChamberTemp(record) {
    const last5 = record.chamber_temp_last5min;
    if (last5 && last5.avg != null && last5.avg !== '') {
      const avg = last5.avg;
      const max = last5.max != null ? ` / ${last5.max}°C (高)` : '';
      const min = last5.min != null ? ` / ${last5.min}°C (低)` : '';
      return `${avg}°C (均)${max}${min}`;
    }
    if (record.chamber_temp_final != null && record.chamber_temp_final !== '') {
      return `${record.chamber_temp_final}°C (终值)`;
    }
    if (!this.config.chamber_temp || !this._hass) return '-';
    const temp = this._getState(this.config.chamber_temp);
    return temp && temp !== 'N/A' && temp !== 'unavailable' && temp !== 'unknown' ? `${temp}°C` : '-';
  }

  _renderDetailModal(record) {
    const taskNameHtml = this._formatTaskName(record);
    const status = record.status || '';
    const normalizedStatus = status.trim().toLowerCase();
    const statusConfig = {
      'finish': { text: '成功', icon: '✅', color: 'var(--success)' },
      '完成': { text: '成功', icon: '✅', color: 'var(--success)' },
      '成功': { text: '成功', icon: '✅', color: 'var(--success)' },
      'failed': { text: '失败', icon: '❌', color: 'var(--danger)' },
      'fail': { text: '失败', icon: '❌', color: 'var(--danger)' },
      '失败': { text: '失败', icon: '❌', color: 'var(--danger)' },
      'cancelled': { text: '已取消', icon: '⚠️', color: 'var(--warning)' },
      '已取消': { text: '已取消', icon: '⚠️', color: 'var(--warning)' },
      '取消': { text: '已取消', icon: '⚠️', color: 'var(--warning)' },
      'printing': { text: '进行中', icon: '🔵', color: 'var(--primary)' },
      '进行中': { text: '进行中', icon: '🔵', color: 'var(--primary)' },
    };
    let statusInfo = statusConfig[status] || statusConfig[normalizedStatus];
    if (!statusInfo) {
      const prog = parseInt(record.progress) || 0;
      if (prog >= 100) statusInfo = { text: '成功', icon: '✅', color: 'var(--success)' };
      else if (record.end_time && prog > 0 && prog < 100) statusInfo = { text: '失败', icon: '❌', color: 'var(--danger)' };
      else if (!status || status === '') statusInfo = { text: '未知', icon: '❓', color: 'var(--text-muted)' };
      else statusInfo = { text: status, icon: '❓', color: 'var(--text-muted)' };
    }

    const coverImg = record.cover_image_local || record.cover_image_url;
    const snapshotImg = record.snapshot_image_local;

    // 统一时区处理
    const _fmtDetail = (ts) => {
      if (!ts || ts === '-') return '-';
      try {
        let d = ts.includes('T') ? new Date(ts) : new Date(ts.replace(' ', 'T'));
        if (isNaN(d.getTime())) return ts.replace('T', ' ').substring(0, 19);
        const p = (n) => String(n).padStart(2, '0');
        return `${d.getFullYear()}-${p(d.getMonth()+1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
      } catch(e) { return ts; }
    };
    
    // 构建任务名称字段
    let modelName = '';
    let configName = '';
    if (record.task_name_model) {
      modelName = record.task_name_model;
    }
    if (record.task_name_config || record.config_name) {
      configName = record.task_name_config || record.config_name;
    }
    if (!modelName && !configName && record.task_name) {
      if (record.task_name.includes(' + ')) {
        const parts = record.task_name.split(' + ');
        modelName = parts[0];
        configName = parts.slice(1).join(' + ');
      } else {
        modelName = record.task_name;
      }
    }
    if (!modelName) {
      modelName = record.task_name || '-';
    }

    const fields = [
      { label: '模型名称', value: modelName },
      configName ? { label: '打印配置', value: configName } : null,
      { label: '打印机', value: record._printer_name || '-' },
      { label: '状态', value: `${statusInfo.icon} ${statusInfo.text}`, color: statusInfo.color },
      { label: '完成进度', value: `${record.progress || 0}%` },
      { label: '开始时间', value: _fmtDetail(record.start_time) },
      { label: '结束时间', value: _fmtDetail(record.end_time) },
      { label: '打印时长', value: record.duration_hours ? `${record.duration_hours.toFixed(2)} 小时` : '-' },
      { label: '耗材类型', value: record.filament_type || '-' },
      { label: '耗材重量', value: record.total_weight ? `${record.total_weight.toFixed(1)} g` : '-' },
      { label: '耗材长度', value: record.total_length ? `${record.total_length.toFixed(1)} m` : '-' },
      { label: '颜色数量', value: record.total_colors || (record.colors_used || []).length || '-' },
      { label: '颜色切换', value: record.color_changes_count || '-' },
      { label: '喷嘴类型', value: record.nozzle_type || '-' },
      { label: '喷嘴尺寸', value: record.nozzle_size || '-' },
      { label: '热床类型', value: record.print_bed_type || '-' },
      { label: '总层数', value: record.total_layer_count || '-' },
      { label: '能耗', value: record.energy_kwh ? `${record.energy_kwh.toFixed(3)} kWh` : '-' },
      { label: '💨 腔体温度', value: this._getDetailChamberTemp(record), color: 'var(--primary-light)' },
    ].filter(f => f !== null);

    let fieldsHtml = fields.map(f => `
      <div class="detail-field">
        <div class="detail-field-label">${f.label}</div>
        <div class="detail-field-value" ${f.color ? `style="color:${this._sanitizeColor(f.color)}"` : ''}>${this._escapeHtml(String(f.value))}</div>
      </div>
    `).join('');

    let colorsHtml = '';
    if (record.color_usage && record.color_usage.length > 0) {
      colorsHtml = `<div style="margin-top:16px;">
        <div style="font-size:14px;font-weight:700;color:var(--text-primary);margin-bottom:10px;">🎨 耗材颜色详情</div>`;
      for (const cu of record.color_usage) {
        colorsHtml += `<div style="display:flex;align-items:center;gap:10px;padding:8px 12px;background:var(--surface-card);border-radius:var(--radius);margin-bottom:6px;border:1px solid var(--border);">
          <span style="width:18px;height:18px;border-radius:50%;background:${this._sanitizeColor(cu.color)};border:2px solid rgba(255,255,255,0.2);flex-shrink:0;"></span>
          <span style="flex:1;font-size:13px;color:var(--text-secondary);">${this._escapeHtml(cu.type || '未知')} ${this._formatColorName(cu.color)}</span>
          <span style="font-size:13px;font-weight:700;color:var(--primary-light);">${cu.weight_g ? cu.weight_g.toFixed(1) + 'g' : '-'}</span>
          <span style="font-size:11px;color:var(--text-muted);">${cu.length_m ? cu.length_m.toFixed(1) + 'm' : ''}</span>
        </div>`;
      }
      colorsHtml += `</div>`;
    }

    let snapshotHtml = '';
    if (snapshotImg) {
      snapshotHtml = `<div style="margin-top:16px;">
        <div style="font-size:14px;font-weight:700;color:var(--text-primary);margin-bottom:10px;">📸 打印快照</div>
        <img class="detail-snapshot" src="${this._escapeHtml(snapshotImg)}" alt="打印快照" onerror="this.style.display='none';">
      </div>`;
    }

    return `
      <div class="modal-overlay">
        <div class="modal-content">
          <button class="modal-close" id="btn-close-modal">✕</button>
          ${coverImg ? `<img class="detail-cover" src="${this._escapeHtml(coverImg)}" alt="${this._escapeHtml(record.task_name)}" onerror="this.style.display='none';">` : ''}
          <div class="detail-title">${taskNameHtml}</div>
          <div class="detail-grid">${fieldsHtml}</div>
          ${colorsHtml}
          ${snapshotHtml}
        </div>
      </div>
    `;
  }

  _renderDeleteConfirm() {
    const count = this._selectedRecords.size;
    return `
      <div class="confirm-overlay">
        <div class="confirm-box">
          <div class="confirm-title">⚠️ 确认删除</div>
          <div class="confirm-text">您即将删除 <strong style="color:var(--danger);">${count}</strong> 条打印历史记录，此操作不可撤销。确定要继续吗？</div>
          <div class="confirm-actions">
            <button class="btn btn-cancel" id="btn-cancel-delete">取消</button>
            <button class="btn btn-danger" id="btn-confirm-delete">🗑️ 确认删除</button>
          </div>
        </div>
      </div>
    `;
  }

  getCardSize() { return 10; }

  static getStubConfig() {
    return {
      title: '打印机分析',
      print_history: '',
      total_prints: '',
      success_rate: '',
      average_duration: '',
      total_print_duration: '',
      total_energy: '',
      material_stats_7d: '',
      material_stats_30d: '',
      duration_distribution: '',
      activity_heatmap: '',
      print_status: ''
    };
  }
}

customElements.define('printer-analytics-card', PrinterAnalyticsCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: 'printer-analytics-card',
  name: '3D 打印机分析卡片',
  description: '现代化设计 · 16色多耗材追踪 · 智能颜色识别 · 完全中文界面'
});
