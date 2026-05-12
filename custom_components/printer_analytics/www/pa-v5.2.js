/**
 * 打印机分析卡片 - v5.2.1
 * 版本: 5.2.1 (2026-05-11) - 统计数据合并单格+图标去底图+对齐优化
 *
 * 设计特点:
 * - 现代化渐变设计 + 玻璃拟态效果
 * - 合并历史记录页签（多打印机）
 * - 日期筛选 + 删除功能（二次确认）
 * - 任务封面图 + 详情弹窗（含快照图）
 * - 优化的数据可视化
 * - 响应式布局增强
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
    this._mode = ''; // 'stats'=仅统计, 'history'=仅全部历史, ''=默认含tab切换
    this._selectedRecords = new Set();
    this._deleteConfirmVisible = false;
    this._detailRecord = null;
    this._dateFrom = '';
    this._dateTo = '';
    this._filterStatus = '';
    this._filterColor = '';
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
    const hex = color.trim();
    if (/^#[0-9a-fA-F]{3,8}$/.test(hex)) return hex;
    const rgba = hex.match(/^rgba?\(\s*[\d.]+\s*,\s*[\d.]+\s*,\s*[\d.]+\s*(?:,\s*[\d.]+\s*)?\)$/);
    if (rgba) return hex;
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
          width: 48px;
          height: 48px;
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
          border-radius: 8px;
          min-height: 18px;
          cursor: default;
          border: 1px solid var(--border-light);
          transition: all 0.2s ease;
        }

        .heatmap-cell:hover {
          transform: scale(1.1);
          box-shadow: var(--shadow-sm);
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
          margin-top: 16px;
        }

        .progress-header {
          display: flex;
          justify-content: space-between;
          font-size: 12px;
          color: var(--text-secondary);
          margin-bottom: 8px;
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
          margin-bottom: 8px;
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
          font-size: 11px;
          color: var(--text-muted);
          text-transform: uppercase;
          letter-spacing: 0.6px;
          margin-bottom: 8px;
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
          grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
          gap: 14px;
          margin-top: 16px;
        }

        .ams-tray {
          background: var(--surface-card);
          border-radius: var(--radius);
          padding: 16px;
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
          margin-bottom: 8px;
        }

        .ams-tray-color {
          width: 48px;
          height: 48px;
          border-radius: 50%;
          margin: 0 auto 10px;
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
          padding: 8px 10px;
          background: var(--surface-card);
          border-radius: var(--radius);
          border: 1px solid var(--border);
          overflow: hidden;
        }

        .summary-item {
          flex: 1 1 0;
          text-align: center;
          min-width: 0;
        }

        .summary-number {
          font-size: 15px;
          font-weight: 700;
          color: var(--primary-light);
          line-height: 1.1;
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
          padding: 8px 14px;
          border: 1px solid var(--border);
          border-radius: var(--radius);
          background: var(--surface-card);
          font-size: 13px;
          font-weight: 500;
          color: var(--text-primary);
          cursor: pointer;
          min-width: 120px;
          transition: all 0.2s ease;
        }

        .filter-select:focus {
          outline: none;
          border-color: var(--primary);
          box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.2);
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
          margin-top: 16px;
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
          padding: 16px;
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
          margin-bottom: 8px;
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

      if (!this.config.print_history) {
        container.innerHTML = `<div class="error-state">⚠️ 错误: 缺少 print_history 配置项</div>`;
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
        <div class="header-badge">v5.2.1</div>
        </div>

        ${this._mode === '' ? `
        <div class="tab-container">
          <button class="tab-button ${this._activeTab === 'stats' ? 'active' : ''}" data-tab="stats">📊 统计分析</button>
          <button class="tab-button ${this._activeTab === 'merged' ? 'active' : ''}" data-tab="merged">🗂️ 全部历史</button>
        </div>
        ` : ''}

        ${this._mode !== 'history' ? `<div class="tab-content ${this._activeTab === 'stats' ? 'active' : ''}" id="tab-stats">` : ''}
      `;

      if (this._mode !== 'history') {
        try {
          html += this._renderTimeDimension();
          html += '<div style="height:1px;background:linear-gradient(90deg,transparent,var(--primary),transparent);margin:20px 0;opacity:0.3;"></div>';
          html += this._renderPeriodStats();
        } catch (e) {
          html += `<div class="error-state">统计渲染失败: ${this._escapeHtml(e.message)}</div>`;
        }

        try { html += this._renderSuccessRateTrend(); } catch (e) {
          html += `<div class="error-state">趋势图渲染失败: ${this._escapeHtml(e.message)}</div>`;
        }
        try { html += this._renderDurationDistribution(); } catch (e) {
          html += `<div class="error-state">分布图渲染失败: ${this._escapeHtml(e.message)}</div>`;
        }
        try { html += this._renderFailureStageDistribution(); } catch (e) {
          html += `<div class="error-state">失败阶段分布渲染失败: ${this._escapeHtml(e.message)}</div>`;
        }
        try { html += this._renderFilamentSuccessStats(); } catch (e) {
          html += `<div class="error-state">耗材成功率渲染失败: ${this._escapeHtml(e.message)}</div>`;
        }
        try { html += this._renderActivityHeatmap(); } catch (e) {
          html += `<div class="error-state">热力图渲染失败: ${this._escapeHtml(e.message)}</div>`;
        }
        try { html += this._renderFilamentUsage(); } catch (e) {
          html += `<div class="error-state">耗材使用渲染失败: ${this._escapeHtml(e.message)}</div>`;
        }
        try { html += this._renderRealtimeMonitor(); } catch (e) {
          html += `<div class="error-state">实时监控渲染失败: ${this._escapeHtml(e.message)}</div>`;
        }
        try { html += this._renderLifetimeStats(); } catch (e) {
          html += `<div class="error-state">终身统计渲染失败: ${this._escapeHtml(e.message)}</div>`;
        }

        html += `</div>`;
      }

      if (this._mode !== 'stats') {
        html += `
          <div class="tab-content ${this._activeTab === 'merged' ? 'active' : ''}" id="tab-merged">
        `;
        html += this._renderMergedHistoryPage();
        html += `</div>`;
      }

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
        this._dateFrom = '';
        this._dateTo = '';
        this._searchQuery = '';
        this._pendingFilterStatus = '';
        this._pendingFilterColor = '';
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
      return {
        totalPrints: this._getState(this.config.total_prints),
        successRate: this._getState(this.config.success_rate),
        avgDuration: this._getState(this.config.average_duration),
        totalDuration: this._getState(this.config.total_print_duration),
        totalEnergy: this._getState(this.config.total_energy),
        printStatus: this._getState(this.config.print_status),
        currentTask: this._getState(this.config.current_task),
        printProgress: this._getState(this.config.print_progress),
        currentWeight: this._getState(this.config.current_weight),
        historyLength: this._getHistory().length,
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

    const keys = ['totalPrints', 'successRate', 'avgDuration', 'totalDuration', 'totalEnergy',
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
    const totalPrints = this._escapeHtml(
      this.config.total_prints ? this._getState(this.config.total_prints) : '0'
    );
    const successRate = this._escapeHtml(
      this.config.success_rate ? this._getState(this.config.success_rate) : '0'
    );
    const avgDuration = this._escapeHtml(
      this.config.average_duration ? this._getState(this.config.average_duration) : '0'
    );
    const totalDuration = this._escapeHtml(
      this.config.total_print_duration ? this._getState(this.config.total_print_duration) : '0'
    );
    const totalEnergy = this._escapeHtml(
      this.config.total_energy ? this._getState(this.config.total_energy) : '0'
    );

    // 总耗材重量+长度（从终身统计实体attributes获取）
    let totalWeight = '0', totalLength = '0';
    if (this.config.material_stats_lifetime) {
      const ltAttrs = this._getAttr(this.config.material_stats_lifetime);
      totalWeight = String((ltAttrs.total_weight_g || 0).toFixed(1));
      totalLength = String((ltAttrs.total_length_m || 0).toFixed(1));
    }

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
              <div class="stat-value" style="font-size:20px;">${this._formatWeight(totalWeight)}</div>
              <div class="stat-label">总重量</div>
            </div>
            <div style="text-align:center;min-width:70px;">
              <div class="stat-icon">📏</div>
              <div class="stat-value" style="font-size:20px;">${totalLength}m</div>
              <div class="stat-label">总长度</div>
            </div>
            <div style="text-align:center;min-width:70px;">
              <div class="stat-icon">⏱️</div>
              <div class="stat-value" style="font-size:20px;">${avgDuration}</div>
              <div class="stat-label">平均时长</div>
            </div>
            <div style="text-align:center;min-width:70px;">
              <div class="stat-icon">🕐</div>
              <div class="stat-value" style="font-size:20px;">${this._formatDurationHours(totalDuration)}</div>
              <div class="stat-label">总时长</div>
            </div>
            <div style="text-align:center;min-width:70px;">
              <div class="stat-icon">⚡</div>
              <div class="stat-value" style="font-size:20px;">${totalEnergy}</div>
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
    const periods = [
      { key: 'material_stats_7d', label: '最近 7 天', icon: '📅' },
      { key: 'material_stats_30d', label: '最近 30 天', icon: '📆' },
    ];
    let html = '';
    for (const period of periods) {
      const entityId = this.config[period.key];
      const attrs = entityId ? this._getAttr(entityId) : {};
      const data = attrs || {};

      const totalPrints = this._escapeHtml(String(data.total_prints || 0));
      const successful = this._escapeHtml(String(data.successful || 0));
      const failed = this._escapeHtml(String(data.failed || 0));
      const successRate = this._escapeHtml(String(data.success_rate || 0));
      const totalWeight = this._escapeHtml(String(data.total_weight_g || 0));
      const totalLength = this._escapeHtml(String(data.total_length_m || 0));
      const totalEnergy = this._escapeHtml(String(data.total_energy_kwh || 0));
      const avgDuration = this._escapeHtml(String(data.average_duration_hours || 0));

      html += `
        <div class="section-header">
          <div class="section-title">
            <span class="section-icon">${period.icon}</span>
            <span>${this._escapeHtml(period.label)}</span>
          </div>
        </div>
        <div class="chart-container">
          <table class="stats-table">
            <thead><tr><th>指标</th><th style="text-align:right;">数值</th></tr></thead>
            <tbody>
              <tr><td>${ICON_3D_PRINTER(14, true)} 打印次数</td><td style="text-align:right;" class="table-value">${totalPrints}</td></tr>
              <tr><td>✅ 成功次数</td><td style="text-align:right;color:var(--success);font-weight:600;">${successful}</td></tr>
              <tr><td>❌ 失败次数</td><td style="text-align:right;color:var(--danger);font-weight:600;">${failed}</td></tr>
              <tr><td>📈 成功率</td><td style="text-align:right;" class="table-value">${successRate}%</td></tr>
              <tr><td>🎨 耗材重量</td><td style="text-align:right;" class="table-value">${totalWeight} g</td></tr>
              <tr><td>📏 耗材长度</td><td style="text-align:right;" class="table-value">${totalLength} m</td></tr>
              <tr><td>⚡ 能耗</td><td style="text-align:right;" class="table-value">${totalEnergy} kWh</td></tr>
              <tr><td>⏱️ 平均时长</td><td style="text-align:right;" class="table-value">${avgDuration} h</td></tr>
            </tbody>
          </table>
        </div>
      `;
    }
    return html;
  }

  /**
   * 渲染成功率趋势图
   */
  _renderSuccessRateTrend() {
    const history = this._getHistory();
    if (!Array.isArray(history) || history.length === 0) {
      return `<div class="section-header"><div class="section-title"><span class="section-icon">📈</span><span>成功率趋势</span></div></div><div class="chart-container"><div class="empty-state"><div class="empty-state-icon">📭</div><div class="empty-state-text">暂无历史数据</div></div></div>`;
    }

    const MAX_POINTS = 100;
    const sorted = [...history].sort((a, b) => new Date(a.end_time) - new Date(b.end_time));
    const sampledData = sorted.length > MAX_POINTS ? this._downsampleData(sorted, MAX_POINTS) : sorted;

    let successCount = 0, totalCount = 0;
    const points = [];
    for (const item of sampledData) {
      totalCount++;
      if (item.status === 'finish') successCount++;
      points.push({ rate: Math.round(successCount / totalCount * 100) });
    }

    const width = 520;
    const height = 140;
    const padding = 28;
    const chartW = width - padding * 2;
    const chartH = height - padding * 2;

    const pathPoints = points.map((p, i) => {
      const x = padding + (i / Math.max(points.length - 1, 1)) * chartW;
      const y = padding + chartH - (p.rate / 100) * chartH;
      return `${x},${y}`;
    });

    const areaPath = `M${padding},${height - padding} L${pathPoints.join(' L')} L${padding + chartW},${height - padding} Z`;
    const linePath = `M${pathPoints.join(' L')}`;

    const totalStr = this._escapeHtml(`${successCount}/${totalCount}`);
    const pctStr = this._escapeHtml(String(Math.round(successCount / totalCount * 100)));

    return `
      <div class="section-header">
        <div class="section-title">
          <span class="section-icon">📈</span>
          <span>打印成功率趋势</span>
        </div>
      </div>
      <div class="chart-container">
        <div class="chart-header">
          <div class="chart-title">累计: ${totalStr} 次 = ${pctStr}%</div>
          <div class="chart-subtitle">${sorted.length > MAX_POINTS ? `显示 ${sampledData.length}/${sorted.length} 条` : ''}</div>
        </div>
        <div style="position:relative;height:120px;">
          <svg width="100%" height="120" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none">
            <defs>
              <linearGradient id="trendArea" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stop-color="var(--primary)" stop-opacity="0.35"/>
                <stop offset="100%" stop-color="var(--primary)" stop-opacity="0.05"/>
              </linearGradient>
              <linearGradient id="trendLine" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%" stop-color="var(--primary)"/>
                <stop offset="100%" stop-color="var(--secondary)"/>
              </linearGradient>
            </defs>
            <path d="${areaPath}" fill="url(#trendArea)"/>
            <path d="${linePath}" fill="none" stroke="url(#trendLine)" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
            ${points.map((p, i) => {
              const x = padding + (i / Math.max(points.length - 1, 1)) * chartW;
              const y = padding + chartH - (p.rate / 100) * chartH;
              return `<circle cx="${x}" cy="${y}" r="4.5" fill="var(--primary)" opacity="${0.5 + (p.rate / 200)}"/>`;
            }).join('')}
          </svg>
        </div>
      </div>
    `;
  }

  /**
   * 渲染打印时长分布
   */
  _renderDurationDistribution() {
    const entityId = this.config.duration_distribution;
    if (!entityId) return '';

    let distribution = this._getAttr(entityId) || {};
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

    const labels = Object.keys(distribution).filter(k =>
      !['icon', 'friendly_name', 'device_class', 'unit_of_measurement'].includes(k)
    );
    if (labels.length === 0) {
      return `<div class="section-header"><div class="section-title"><span class="section-icon">📊</span><span>打印时长分布</span></div></div><div class="chart-container"><div class="empty-state"><div class="empty-state-icon">📭</div><div class="empty-state-text">暂无数据</div></div></div>`;
    }

    const maxVal = Math.max(...labels.map(k => distribution[k]), 1);
    const colors = ['#22c55e', '#84cc16', '#eab308', '#f97316', '#ef4444', '#a855f7'];

    let barsHtml = '';
    for (let i = 0; i < labels.length; i++) {
      const label = labels[i];
      const value = distribution[label] || 0;
      const heightPct = (value / maxVal) * 100;
      barsHtml += `<div style="flex:1;display:flex;flex-direction:column;align-items:center;min-height:110px;">
        <div class="table-value" style="font-size:14px;margin-bottom:8px;">${value}</div>
        <div style="width:100%;background:rgba(15,23,42,0.4);border-radius:8px;height:90px;padding:4px;position:relative;">
          <div style="width:100%;height:${Math.max(heightPct, 5)}%;background:linear-gradient(to top,${colors[i % colors.length]},${colors[(i + 1) % colors.length]});border-radius:6px;transition:height 0.5s ease;"></div>
        </div>
        <div style="font-size:12px;color:var(--text-secondary);margin-top:10px;text-align:center;font-weight:500;">${label}</div>
      </div>`;
    }

    return `<div class="section-header"><div class="section-title"><span class="section-icon">📊</span><span>打印时长分布</span></div></div><div class="chart-container"><div style="display:flex;gap:16px;">${barsHtml}</div></div>`;
  }

  _renderFailureStageDistribution() {
    const entityId = this.config.failure_stage_distribution;
    if (!entityId) return '';

    let distribution = this._getAttr(entityId) || {};
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
    const entityId = this.config.filament_success_stats;
    if (!entityId) return '';

    let stats = this._getAttr(entityId) || {};
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
    const entityId = this.config.activity_heatmap;
    if (!entityId) return '';

    let heatmap = this._getAttr(entityId) || {};
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
      return `<div class="section-header"><div class="section-title"><span class="section-icon">🗓️</span><span>打印活动热力图</span></div></div><div class="chart-container"><div class="empty-state"><div class="empty-state-icon">📭</div><div class="empty-state-text">暂无数据</div></div></div>`;
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

    return `<div class="section-header"><div class="section-title"><span class="section-icon">🗓️</span><span>打印活动热力图</span></div></div><div class="chart-container"><div style="display:grid;grid-template-columns:repeat(7,1fr);gap:8px;">${cellsHtml}</div></div>`;
  }

  /**
   * 渲染耗材使用情况
   */
  _renderFilamentUsage() {
    const history = this._getHistory();

    let typeUsage = {};
    let colorUsage = {};
    let multiColorPrints = [];
    let hasData = false;

    if (Array.isArray(history) && history.length > 0 &&
      history.some(item => item.status === 'finish' && (item.total_weight > 0 || item.filament_type))) {

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

    if (multiColorPrints.length > 0) {
      html += `<div class="section-header"><div class="section-title"><span class="section-icon">🌈</span><span>多色打印记录</span></div></div>`;
      html += `<div class="chart-container">`;
      html += `<div class="chart-header">
                <div class="chart-title">共 ${multiColorPrints.length} 次多色打印</div>
                <div class="chart-subtitle">支持最多 16 色可视化</div>
              </div>`;

      const recentMulti = multiColorPrints.slice(-5).reverse();
      for (const print of recentMulti) {
        const taskName = this._escapeHtml(print.task_name || '未知任务');

        // 统一时区：UTC/本地时间都转为本地显示
        const _fmt = (ts) => {
          if (!ts) return '';
          try {
            let d = ts.includes('T') ? new Date(ts) : new Date(ts.replace(' ', 'T'));
            if (isNaN(d.getTime())) return ts.substring(0, 16);
            const p = (n) => String(n).padStart(2, '0');
            return `${d.getFullYear()}/${p(d.getMonth()+1)}/${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
          } catch(e) { return ts; }
        };
        const endTime = _fmt(print.end_time);
        const colorsCount = print.total_colors || (print.colors_used || []).length;
        const changeCount = print.color_changes_count || 0;

        const multiSummary = print.multi_color_summary;
        const isPartial = multiSummary ? multiSummary.is_partial : false;
        const statusLabel = multiSummary ? multiSummary.status_label : '';
        const completionPct = multiSummary ? multiSummary.completion_progress : 100;
        const printStatus = multiSummary ? multiSummary.print_status : (print.status || '');

        let colorDetails = [];
        if (print.multi_color_summary && print.multi_color_summary.color_details) {
          colorDetails = print.multi_color_summary.color_details;
        } else if (print.color_usage && Array.isArray(print.color_usage)) {
          colorDetails = print.color_usage.map(cu => ({
            color: cu.color,
            weight_g: cu.weight_g || 0,
            type: cu.type || ''
          }));
        }

        const totalPrintWeight = print.total_weight || colorDetails.reduce((sum, d) => sum + (d.weight_g || 0), 0);

        let cardClass = 'multi-color-card';
        let statusIcon = '✅';

        if (isPartial) {
          cardClass = printStatus === 'cancelled' ? 'multi-color-card' : 'multi-color-card failed';
          statusIcon = printStatus === 'cancelled' ? '⚠️' : '❌';
        } else {
          cardClass = 'multi-color-card success';
        }

        html += `<div class="${cardClass}">
                  <div class="multi-color-header">
                    <div class="multi-color-title">${statusIcon} ${taskName}</div>
                  </div>
                  <div style="font-size:13px;color:var(--text-secondary);margin-top:4px;font-weight:500;">
                    ${endTime} | 🎨 ${colorsCount} 色 | 切换 ${changeCount} 次
                    ${isPartial ? ` | ${statusLabel} (${completionPct}%)` : ''}
                  </div>`;

        if (isPartial && completionPct > 0 && completionPct < 100) {
          html += `<div class="progress-container">
                    <div class="progress-header">
                      <span>打印进度</span>
                      <span style="color:var(--primary);font-weight:700;">${completionPct}%</span>
                    </div>
                    <div class="progress-track">
                      <div class="progress-fill" style="width:${completionPct}%"></div>
                    </div>
                  </div>`;
        }

        if (print.colors_used && print.colors_used.length > 0) {
          html += `<div class="color-tag-list">`;
          for (let i = 0; i < Math.min(print.colors_used.length, 8); i++) {
            const colorCode = print.colors_used[i];
            const displayName = this._formatColorName(colorCode);
            const colorDetail = colorDetails.find(d => d.color === colorCode);
            const colorWeight = colorDetail ? colorDetail.weight_g : 0;
            const colorPct = totalPrintWeight > 0 ? ((colorWeight / totalPrintWeight) * 100).toFixed(0) : '?';
            html += `<span class="color-tag" style="background:${this._sanitizeColor(colorCode)};color:${this._getContrastColor(colorCode)}">
              ● ${displayName}${colorWeight > 0 ? ` (${colorWeight}g, ${colorPct}%)` : ''}
            </span>`;
          }
          if (print.colors_used.length > 8) {
            html += `<span style="padding:6px 14px;border-radius:20px;font-size:12px;color:var(--text-secondary);background:var(--surface-card);border:1px solid var(--border);">+${print.colors_used.length - 8}</span>`;
          }
          html += `</div>`;
        }

        if (colorDetails.length > 0) {
          html += `<div style="margin-top:12px;padding-top:12px;border-top:1px dashed var(--border);font-size:12px;">`;
          for (const detail of colorDetails) {
            const pct = totalPrintWeight > 0 ? ((detail.weight_g / totalPrintWeight) * 100).toFixed(0) : '?';
            html += `<div style="display:flex;justify-content:space-between;align-items:center;padding:4px 0;border-radius:6px;">
              <span style="display:flex;align-items:center;gap:8px;">
                <span style="width:12px;height:12px;border-radius:50%;background:${this._sanitizeColor(detail.color)};border:2px solid rgba(255,255,255,0.2);"></span>
                <span style="color:var(--text-secondary);">${this._formatColorName(detail.color)}</span>
              </span>
              <span style="font-weight:700;color:var(--primary-light);">${detail.weight_g}g</span>
              <span style="color:var(--text-muted);font-size:11px;">(${pct}%)</span>
            </div>`;
          }
          html += `</div>`;
        }

        html += `</div>`;
      }

      html += `</div>`;
    }

    html += this._renderPieChart('耗材类型使用量', typeUsage, pieColors);
    html += this._renderPieChart('耗材颜色使用量', colorUsage, pieColors);
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

  _renderRealtimeMonitor() {
    const currentTask = this._getState(this.config.current_task) || '未配置';
    const printProgress = this._getState(this.config.print_progress) || '0';
    const currentWeight = this._getState(this.config.current_weight) || 'N/A';
    const currentLength = this._getState(this.config.current_length) || 'N/A';
    const totalUsage = this._getState(this.config.total_usage) || 'N/A';
    const nozzleTemp = this._getState(this.config.nozzle_temp) || 'N/A';
    const bedTemp = this._getState(this.config.bed_temp) || 'N/A';
    const chamberTemp = this._getState(this.config.chamber_temp) || 'N/A';
    const activeTray = this._getState(this.config.active_tray);
    const power = this._getState(this.config.power) || 'N/A';
    const speedProfile = this._getState(this.config.speed_profile) || 'N/A';
    const nozzleSize = this._getState(this.config.nozzle_size) || 'N/A';

    let statusClass = 'idle';
    let statusText = '空闲';
    if (printProgress && parseFloat(printProgress) > 0 && parseFloat(printProgress) < 100) {
      statusClass = 'printing';
      statusText = `打印中 ${printProgress}%`;
    } else if (currentTask && currentTask !== 'unknown' && currentTask !== 'unavailable' && currentTask !== '未配置') {
      statusClass = 'finish';
      statusText = '已完成';
    }

    let amsHtml = '';
    if (this.config.ams_tray_1 || this.config.ams_tray_2 || this.config.ams_tray_3 || this.config.ams_tray_4) {
      const trays = [
        { num: 1, entity: this.config.ams_tray_1 },
        { num: 2, entity: this.config.ams_tray_2 },
        { num: 3, entity: this.config.ams_tray_3 },
        { num: 4, entity: this.config.ams_tray_4 }
      ].filter(t => t.entity);

      if (trays.length > 0) {
        amsHtml = `<div style="margin-top:20px;">
          <div style="font-size:14px;font-weight:700;color:var(--text-primary);margin-bottom:14px;display:flex;align-items:center;gap:8px;">
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
    }

    return `<div class="section-header"><div class="section-title"><span class="section-icon">📡</span><span>实时监控面板</span></div></div>
      <div class="realtime-panel">
        <div class="realtime-header">
          <div class="realtime-title">🖥️ 打印机状态监控</div>
          <div class="status-badge ${statusClass}">${statusText}</div>
        </div>
        <div class="realtime-grid">
          <div class="realtime-item">
            <div class="realtime-label">📋 当前任务</div>
            <div class="realtime-value">${this._escapeHtml(currentTask || '空闲')}</div>
          </div>
          ${printProgress ? `<div class="realtime-item">
            <div class="realtime-label">📊 打印进度</div>
            <div class="realtime-value">${printProgress}%</div>
            <div class="progress-track" style="margin-top:8px;">
              <div class="progress-fill" style="width:${printProgress}%"></div>
            </div>
          </div>` : ''}
          ${currentWeight && currentWeight !== 'N/A' ? `<div class="realtime-item">
            <div class="realtime-label">⚖️ 当前耗材重量</div>
            <div class="realtime-value">${currentWeight}<small style="font-size:12px;color:var(--text-muted);font-weight:500;">g</small></div>
          </div>` : ''}
          ${totalUsage && totalUsage !== 'N/A' ? `<div class="realtime-item">
            <div class="realtime-label">📦 累计使用量</div>
            <div class="realtime-value">${totalUsage}<small style="font-size:12px;color:var(--text-muted);font-weight:500;">g</small></div>
          </div>` : ''}
          ${nozzleTemp && nozzleTemp !== 'N/A' ? `<div class="realtime-item">
            <div class="realtime-label">🌡️ 喷嘴温度</div>
            <div class="realtime-value">${nozzleTemp}<small style="font-size:12px;color:var(--text-muted);font-weight:500;">°C</small></div>
          </div>` : ''}
          ${bedTemp && bedTemp !== 'N/A' ? `<div class="realtime-item">
            <div class="realtime-label">🔥 热床温度</div>
            <div class="realtime-value">${bedTemp}<small style="font-size:12px;color:var(--text-muted);font-weight:500;">°C</small></div>
          </div>` : ''}
          ${chamberTemp && chamberTemp !== 'N/A' ? `<div class="realtime-item">
            <div class="realtime-label">💨 腔体温度</div>
            <div class="realtime-value">${chamberTemp}<small style="font-size:12px;color:var(--text-muted);font-weight:500;">°C</small></div>
          </div>` : ''}
          ${power && power !== 'N/A' ? `<div class="realtime-item">
            <div class="realtime-label">⚡ 当前功率</div>
            <div class="realtime-value">${power}<small style="font-size:12px;color:var(--text-muted);font-weight:500;">W</small></div>
          </div>` : ''}
          ${speedProfile && speedProfile !== 'N/A' ? `<div class="realtime-item">
            <div class="realtime-label">⚡ 打印速度</div>
            <div class="realtime-value">${this._escapeHtml(speedProfile)}</div>
          </div>` : ''}
          ${nozzleSize && nozzleSize !== 'N/A' ? `<div class="realtime-item">
            <div class="realtime-label">🔧 喷嘴尺寸</div>
            <div class="realtime-value">${nozzleSize}</div>
          </div>` : ''}
        </div>
        ${amsHtml}
      </div>`;
  }

  _renderLifetimeStats() {
    const lifetimeStats = this.config.material_stats_lifetime;
    if (!lifetimeStats) return '';
    const lifetimeData = this._getAttr(lifetimeStats);
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
        colorsUsed = item.color_usage.filter(cu => cu && cu.color).map(cu => cu.color);
        if (colorsUsed.length > 1) totalColors = colorsUsed.length;
      }

      let typesUsed = item.types_used || [];
      if (typesUsed.length === 0 && item.filament_type) {
        const ft = String(item.filament_type).trim();
        if (ft.includes(',') || ft.includes(';') || ft.includes('+') || ft.includes('/')) {
          typesUsed = ft.split(/[,;+\/]+/).map(t => t.trim()).filter(t => t && t.length > 1);
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
    const success = history.filter(h => h.status === 'finish').length;
    const successRate = total > 0 ? ((success / total) * 100).toFixed(1) : 0;
    const totalWeight = history.reduce((sum, h) => sum + (h.total_weight || 0), 0).toFixed(1);
    const totalDuration = this._calculateTotalDuration(history);

    return `
      <div class="summary-item"><div class="summary-number">${total}</div><div class="summary-text">总记录</div></div>
      <div class="summary-item"><div class="summary-number" style="color:${successRate >= 80 ? 'var(--success)' : 'var(--warning)'};">${successRate}%</div><div class="summary-text">成功率</div></div>
      <div class="summary-item"><div class="summary-number">${this._formatWeight(totalWeight)}</div><div class="summary-text">总耗材</div></div>
      <div class="summary-item"><div class="summary-number">${this._formatDurationMinutes(totalDuration)}</div><div class="summary-text">总时长</div></div>
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

  _renderHistoryItem(item, index, options = {}) {
    const taskName = this._escapeHtml(item.task_name || '未命名任务');
    const status = item.status || 'unknown';
    const statusConfig = {
      'finish': { text: '成功', class: 'success', icon: '✅' },
      'failed': { text: '失败', class: 'failed', icon: '❌' },
      'printing': { text: '进行中', class: 'printing', icon: '🔵' },
      'cancelled': { text: '已取消', class: 'failed', icon: '⚠️' }
    };
    const statusInfo = statusConfig[status] || { text: '未知', class: '', icon: '❓' };

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

    return `
      <div class="history-item" data-status="${status}" data-name="${taskName.toLowerCase()}" data-type="${filamentType.toLowerCase()}" data-record-id="${recordId}">
        ${showCheckbox ? `<input type="checkbox" class="record-checkbox" data-record-id="${recordId}" ${this._selectedRecords.has(recordId) ? 'checked' : ''}>` : ''}
        <div class="history-status ${statusInfo.class}">${statusInfo.icon} ${statusInfo.text}</div>
        ${coverHtml}
        <div class="history-details">
          <div class="history-task-name">${taskName} ${showPrinterTag && printerName ? `<span class="printer-tag">${printerName}</span>` : ''}</div>
          <div class="history-meta">
            <span>⏱️ ${duration}</span>
            <span>🧵 ${filamentType}</span>
            ${weight !== '-' ? `<span>⚖️ ${weight}</span>` : ''}
            ${energy ? `<span>⚡ ${energy}</span>` : ''}
            ${colorsUsed.length > 1 ? `<span>🎨 ${colorsUsed.length}色</span>` : ''}
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
    const extraHistories = this.config.extra_print_histories;
    if (!extraHistories || !this._hass) {
      const history = this._getHistory();
      history.forEach(r => {
        r._printer_name = this.config.printer_name || this.config.title?.replace(/[🖨️ ]/g, '') || '';
        r._printer_entity = this.config.print_history;
      });
      return history;
    }

    const mainHistory = this._getHistory();
    mainHistory.forEach(r => {
      r._printer_name = this.config.printer_name || this.config.title?.replace(/[🖨️ ]/g, '') || '本机';
      r._printer_entity = this.config.print_history;
    });
    allRecords.push(...mainHistory);

    for (const entry of extraHistories) {
      if (!entry.entity) continue;
      const entity = this._hass.states[entry.entity];
      if (!entity || !entity.attributes || !entity.attributes.history) continue;
      const printerName = entry.name || entity.attributes.friendly_name || entry.entity;
      const records = entity.attributes.history || [];
      records.forEach(r => {
        r._printer_name = printerName;
        r._printer_entity = entry.entity;
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
      if (this._filterStatus && r.status !== this._filterStatus) return false;
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

    const statusMap = { 'finish': '成功', 'failed': '失败', 'cancelled': '已取消' };
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
    // 优先用插件记录的最后5分钟平均温度
    const last5 = record.chamber_temp_last5min;
    if (last5 && last5.avg != null) {
      return `${last5.avg}°C (均) / ${last5.max}°C (高) / ${last5.min}°C (低)`;
    }
    // 其次用最终温度
    if (record.chamber_temp_final != null) {
      return `${record.chamber_temp_final}°C (终值)`;
    }
    // 兜底：读配置实体当前值
    if (!this.config.chamber_temp || !this._hass) return '-';
    const temp = this._getState(this.config.chamber_temp);
    return temp && temp !== 'N/A' ? `${temp}°C` : '-';
  }

  _renderDetailModal(record) {
    const taskName = this._escapeHtml(record.task_name || '未命名任务');
    const status = record.status || 'unknown';
    const statusConfig = {
      'finish': { text: '成功', icon: '✅', color: 'var(--success)' },
      'failed': { text: '失败', icon: '❌', color: 'var(--danger)' },
      'cancelled': { text: '已取消', icon: '⚠️', color: 'var(--warning)' },
      'printing': { text: '进行中', icon: '🔵', color: 'var(--primary)' }
    };
    const statusInfo = statusConfig[status] || { text: '未知', icon: '❓', color: 'var(--text-muted)' };

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
    const fields = [
      { label: '任务名称', value: record.task_name || '-' },
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
    ];

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
          ${coverImg ? `<img class="detail-cover" src="${this._escapeHtml(coverImg)}" alt="${taskName}" onerror="this.style.display='none';">` : ''}
          <div class="detail-title">${taskName}</div>
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
