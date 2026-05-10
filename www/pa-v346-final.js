/**
 * 打印机分析卡片 - v3.4.8.1 极简无动画版（Material Design 3）
 * 版本: 3.4.8.1 (2026-05-10) - 修复所有时间显示的时区问题
 *
 * 更新日志:
 * - ✅ 完全中文化界面
 * - ✅ 支持16色多耗材可视化
 * - 🆕 实时监控面板（暗色主题）
 * - 🆕 AMS耗材盘可视化（P2S专属）
 * - 🔧 **v3.4.6 核心改进：**
 *   - ❌ 移除所有过渡动画（即时响应，零延迟）
 *   - 📑 内置Tab切换：统计页 ↔ 历史记录页
 *   - 🏠 历史记录完全集成到Home Assistant内
 *   - 📊 两台打印机分为独立视图
 *   - ⚡ 性能极致优化，零GPU开销
 */
class PrinterAnalyticsCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._lastRenderedData = null;
    this._renderDebounce = null;
    this._isRendering = false;
    this._activeTab = 'stats';  // v3.4.6: 当前激活的标签页
    console.log('[Printer Analytics] v3.4.6 初始化完成（极简无动画版）');
  }

  setConfig(config) {
    this.config = config;
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

  _escapeHtml(str) {
    if (str === null || str === undefined) return '';
    const div = document.createElement('div');
    div.textContent = String(str);
    return div.innerHTML;
  }

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

  render() {
    const container = this.shadowRoot;
    if (!container) return;

    container.innerHTML = `
      <style>
        :host {
          display: block;
          --md-sys-color-primary: #4fc3f7;
          --md-sys-color-on-primary: #fff;
          --md-sys-color-primary-container: #1a3a4a;
          --md-sys-color-secondary: #26c6da;
          --md-sys-color-surface: #1e1e2e;
          --md-sys-color-surface-variant: #2a2a3c;
          --md-sys-color-outline: rgba(255,255,255,0.08);
          --md-sys-elevation-1: 0 1px 3px rgba(0,0,0,0.3), 0 1px 2px rgba(0,0,0,0.2);
          --md-sys-elevation-2: 0 3px 6px rgba(0,0,0,0.4), 0 2px 4px rgba(0,0,0,0.2);
          --md-sys-shape-corner-extra-small: 6px;
          --md-sys-shape-corner-small: 10px;
          --md-sys-shape-corner-medium: 16px;
          --md-sys-shape-corner-large: 24px;
        }

        .card {
          background: var(--md-sys-color-surface);
          border-radius: var(--md-sys-shape-corner-large);
          box-shadow: var(--md-sys-elevation-1);
          padding: 28px;
          color: #e0e0e0;
          font-family: 'Roboto', 'Noto Sans SC', -apple-system, BlinkMacSystemFont, sans-serif;
        }
        
        .header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 20px;
          padding-bottom: 16px;
          border-bottom: 3px solid var(--md-sys-color-primary);
        }
        .header-title {
          font-size: 20px;
          font-weight: 700;
          color: var(--md-sys-color-primary);
          display: flex;
          align-items: center;
          gap: 12px;
        }
        .header-badge {
          background: linear-gradient(135deg, var(--md-sys-color-primary), var(--md-sys-color-secondary));
          color: var(--md-sys-color-on-primary);
          padding: 6px 16px;
          border-radius: var(--md-sys-shape-corner-extra-small);
          font-size: 11px;
          font-weight: 600;
        }
        
        /* ========== v3.4.6 Tab切换样式（无动画）========== */
        .tab-container {
          display: flex;
          gap: 4px;
          background: var(--md-sys-color-surface-variant, #f8f9fa);
          padding: 6px;
          border-radius: var(--md-sys-shape-corner-medium, 16px);
          margin-bottom: 20px;
        }
        .tab-button {
          flex: 1;
          padding: 10px 16px;
          border: none;
          background: transparent;
          color: var(--secondary-text-color, #666);
          font-size: 13px;
          font-weight: 600;
          border-radius: var(--md-sys-shape-corner-small, 10px);
          cursor: pointer;
        }
        .tab-button:hover {
          background: rgba(79,195,247,0.15);
          color: var(--md-sys-color-primary);
        }
        .tab-button.active {
          background: #2a2a3c;
          color: var(--md-sys-color-primary);
          box-shadow: var(--md-sys-elevation-1);
        }
        .tab-content {
          display: none;
        }
        .tab-content.active {
          display: block;
        }
        
        /* 统计卡片网格 */
        .stats-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
          gap: 16px;
          margin-bottom: 20px;
        }
        .stat-card {
          background: linear-gradient(145deg, var(--md-sys-color-surface), var(--md-sys-color-surface-variant));
          border-radius: var(--md-sys-shape-corner-medium);
          padding: 20px 14px;
          text-align: center;
          border: 1px solid var(--md-sys-color-outline);
          position: relative;
          overflow: hidden;
          cursor: default;
        }
        .stat-card:hover {
          box-shadow: var(--md-sys-elevation-2);
          border-color: var(--md-sys-color-primary);
        }
        .stat-card::before {
          content: '';
          position: absolute;
          top: 0;
          left: 0;
          right: 0;
          height: 4px;
          background: linear-gradient(90deg, var(--md-sys-color-primary), var(--md-sys-color-secondary));
          opacity: 0;
        }
        .stat-card:hover::before {
          opacity: 1;
        }
        .stat-icon {
          font-size: 28px;
          margin-bottom: 10px;
          display: inline-block;
          text-shadow: 0 1px 2px rgba(0,0,0,0.15);
        }
        .stat-value {
          font-size: 30px;
          font-weight: 800;
          line-height: 1.2;
          background: linear-gradient(135deg, #4fc3f7, #26c6da);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          background-clip: text;
          letter-spacing: -0.5px;
          margin-bottom: 8px;
        }
        .stat-label {
          font-size: 12px;
          color: #94a3b8;
          line-height: 1.5;
          font-weight: 500;
        }
        
        /* 区域标题 */
        .section-title {
          font-size: 16px;
          font-weight: 700;
          margin: 24px 0 14px 0;
          padding-bottom: 10px;
          border-bottom: 2px solid rgba(255,255,255,0.08);
          display: flex;
          align-items: center;
          gap: 12px;
          color: #e0e0e0;
        }
        .section-icon {
          width: 32px;
          height: 32px;
          border-radius: var(--md-sys-shape-corner-small);
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 18px;
          background: linear-gradient(135deg, #1a3a4a, #0d2137);
          box-shadow: var(--md-sys-elevation-1);
        }
        
        /* 图表容器 */
        .chart-container {
          background: linear-gradient(145deg, var(--md-sys-color-surface-variant), var(--md-sys-color-surface));
          border-radius: var(--md-sys-shape-corner-medium);
          padding: 22px;
          margin-bottom: 18px;
          border: 1px solid var(--md-sys-color-outline);
        }
        .chart-container:hover {
          box-shadow: var(--md-sys-elevation-2);
        }
        .chart-title {
          font-size: 14px;
          font-weight: 600;
          margin-bottom: 18px;
          color: #e0e0e0;
          display: flex;
          justify-content: space-between;
          align-items: center;
        }
        
        /* 表格样式 */
        .stats-table {
          width: 100%;
          border-collapse: separate;
          border-spacing: 0;
          font-size: 13px;
          border-radius: var(--md-sys-shape-corner-small);
          overflow: hidden;
          box-shadow: var(--md-sys-elevation-1);
        }
        .stats-table th {
          text-align: left;
          padding: 16px 18px;
          background: linear-gradient(135deg, var(--md-sys-color-primary), #0288d1);
          color: white;
          font-weight: 600;
          font-size: 12px;
          letter-spacing: 0.6px;
          text-transform: uppercase;
        }
        .stats-table td {
          padding: 14px 18px;
          border-bottom: 1px solid rgba(255,255,255,0.06);
          color: #c0c0c0;
        }
        .stats-table tr:last-child td { border-bottom: none; }
        .stats-table tr:hover td {
          background: rgba(79,195,247,0.1);
        }
        .table-value {
          font-weight: 700;
          color: var(--md-sys-color-primary);
          font-size: 14px;
        }
        
        /* 多色统计特殊样式 */
        .multi-color-card {
          background: linear-gradient(145deg, #2a2a3c, #1e1e2e);
          border-left-width: 6px !important;
          box-shadow: var(--md-sys-elevation-2);
        }
        .multi-color-card.success { 
          border-left-color: #4caf50 !important; 
          background: linear-gradient(145deg, #1a2e1a, #1e1e2e);
        }
        .multi-color-card.failed { 
          border-left-color: #f44336 !important; 
          background: linear-gradient(145deg, #2e1a1a, #1e1e2e);
        }
        
        .color-tag {
          display: inline-flex;
          align-items: center;
          gap: 7px;
          padding: 6px 14px;
          border-radius: 20px;
          font-size: 11px;
          font-weight: 600;
          border: 2px solid rgba(255,255,255,0.4);
          box-shadow: var(--md-sys-elevation-1);
        }
        
        /* 进度条 */
        .progress-bar-container {
          margin-top: 14px;
        }
        .progress-label {
          display: flex;
          justify-content: space-between;
          font-size: 11px;
          color: #94a3b8;
          margin-bottom: 6px;
          font-weight: 600;
        }
        .progress-track {
          background: linear-gradient(90deg, #2a2a3c, #333348);
          border-radius: 10px;
          height: 8px;
          overflow: hidden;
          position: relative;
          box-shadow: inset 0 2px 4px rgba(0,0,0,0.3);
        }
        .progress-fill {
          height: 100%;
          border-radius: 10px;
          transition: width 0.8s cubic-bezier(0.4, 0, 0.2, 1);
          position: relative;
          background: linear-gradient(90deg, var(--md-sys-color-primary), var(--md-sys-color-secondary));
          box-shadow: 0 2px 8px rgba(3,169,244,0.3);
        }
        
        /* 无数据/错误状态 */
        .no-data {
          text-align: center;
          color: #94a3b8;
          padding: 50px 24px;
          font-style: italic;
          font-size: 15px;
          background: linear-gradient(145deg, #2a2a3c, #1e1e2e);
          border-radius: var(--md-sys-shape-corner-medium);
          border: 2px dashed rgba(255,255,255,0.1);
        }
        .no-data::before {
          content: '📭';
          display: block;
          font-size: 48px;
          margin-bottom: 16px;
          opacity: 0.6;
        }
        .error {
          background: linear-gradient(145deg, #3e1a1a, #2e1515);
          color: #ef9a9a;
          padding: 20px 24px;
          border-radius: var(--md-sys-shape-corner-medium);
          border-left: 6px solid #f44336;
          font-weight: 600;
          word-break: break-all;
          box-shadow: var(--md-sys-elevation-2);
        }
        
        /* 饼图增强 */
        .pie-container {
          display: flex;
          align-items: center;
          gap: 28px;
          flex-wrap: wrap;
        }
        .pie-svg {
          box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        .pie-svg:hover {
          filter: drop-shadow(0 4px 12px rgba(0,0,0,0.2));
          transform: scale(1.05);
        }
        .legend-item {
          display: flex;
          align-items: center;
          gap: 12px;
          padding: 8px 0;
          cursor: default;
        }
        .legend-item:hover {
          background: rgba(79,195,247,0.08);
          padding-left: 8px;
          margin-left: -8px;
          border-radius: var(--md-sys-shape-corner-extra-small);
        }
        .legend-dot {
          width: 16px;
          height: 16px;
          border-radius: 50%;
          flex-shrink: 0;
          box-shadow: var(--md-sys-elevation-1), 0 2px 6px rgba(0,0,0,0.25);
        }
        .legend-item:hover .legend-dot {
          transform: scale(1.2);
          box-shadow: var(--md-sys-elevation-2), 0 4px 10px rgba(0,0,0,0.35);
        }
        
        /* 实时监控面板样式 - 暗色主题 */
        .realtime-panel {
          background: linear-gradient(145deg, #1a2332, #0d1117);
          border-radius: var(--md-sys-shape-corner-medium);
          padding: 22px;
          margin-bottom: 20px;
          border: 2px solid rgba(3,169,244,0.3);
          box-shadow: var(--md-sys-elevation-2), inset 0 0 30px rgba(0,0,0,0.5);
        }
        .realtime-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 18px;
          padding-bottom: 12px;
          border-bottom: 2px solid rgba(3,169,244,0.25);
        }
        .realtime-title {
          font-size: 16px;
          font-weight: 700;
          color: #64b5f6;
          display: flex;
          align-items: center;
          gap: 10px;
        }
        .realtime-status-badge {
          padding: 6px 16px;
          border-radius: 20px;
          font-size: 12px;
          font-weight: 600;
        }
        .realtime-status-badge.printing { background: linear-gradient(135deg, #03a9f4, #00bcd4); color: white; }
        .realtime-status-badge.finish { background: linear-gradient(135deg, #4caf50, #8bc34a); color: white; }
        .realtime-status-badge.idle { background: linear-gradient(135deg, #9e9e9e, #bdbdbd); color: white; }

        .realtime-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
          gap: 16px;
        }
        .realtime-item {
          background: linear-gradient(145deg, #1e2936, #0f172a);
          border-radius: var(--md-sys-shape-corner-small);
          padding: 16px;
          box-shadow: 0 2px 8px rgba(0,0,0,0.4);
          border-left: 4px solid rgba(100,181,246,0.4);
        }
        .realtime-item:hover {
          box-shadow: 0 4px 12px rgba(0,0,0,0.5), 0 0 12px rgba(3,169,244,0.15);
          border-left-color: #64b5f6;
        }
        .realtime-item-label {
          font-size: 11px;
          color: #94a3b8;
          text-transform: uppercase;
          letter-spacing: 0.5px;
          margin-bottom: 8px;
          font-weight: 600;
        }
        .realtime-item-value {
          font-size: 18px;
          font-weight: 800;
          color: #e2e8f0;
        }
        
        /* AMS耗材盘样式 */
        .ams-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
          gap: 12px;
          margin-top: 12px;
        }
        .ams-tray {
          background: linear-gradient(145deg, #1e2936, #0f172a);
          border-radius: var(--md-sys-shape-corner-extra-small);
          padding: 12px;
          text-align: center;
          box-shadow: 0 2px 8px rgba(0,0,0,0.4);
          position: relative;
          overflow: hidden;
        }
        .ams-tray.active {
          border: 3px solid #64b5f6;
          box-shadow: 0 4px 16px rgba(100,181,246,0.4), 0 0 15px rgba(100,181,246,0.3);
        }
        .ams-tray-number {
          font-size: 11px;
          color: #64748b;
          font-weight: 600;
          margin-bottom: 6px;
        }
        .ams-tray-color {
          width: 40px;
          height: 40px;
          border-radius: 50%;
          margin: 0 auto 8px;
          box-shadow: 0 2px 8px rgba(0,0,0,0.5), inset 0 2px 4px rgba(0,0,0,0.3);
          border: 2px solid rgba(255,255,255,0.1);
        }
        .ams-tray-name {
          font-size: 13px;
          font-weight: 700;
          color: #e2e8f0;
          line-height: 1.3;
        }

        /* ========== v3.4.6 历史记录列表样式（集成到HA）========== */
        .history-list {
          max-height: 600px;
          overflow-y: auto;
          padding-right: 8px;
        }
        .history-list::-webkit-scrollbar {
          width: 6px;
        }
        .history-list::-webkit-scrollbar-track {
          background: #2a2a3c;
          border-radius: 3px;
        }
        .history-list::-webkit-scrollbar-thumb {
          background: #4a4a5c;
          border-radius: 3px;
        }

        .history-item {
          display: flex;
          gap: 16px;
          padding: 16px;
          background: linear-gradient(145deg, #2a2a3c, #252538);
          border-radius: var(--md-sys-shape-corner-medium, 16px);
          margin-bottom: 12px;
          border: 1px solid transparent;
          cursor: default;
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
          background: linear-gradient(180deg, var(--md-sys-color-primary, #03a9f4), var(--md-sys-color-secondary, #00bcd4));
          opacity: 0;
        }
        .history-item:hover {
          box-shadow: var(--md-sys-elevation-2);
          border-color: rgba(79,195,247,0.2);
        }
        .history-item:hover::before {
          opacity: 1;
        }

        .history-thumbnail {
          width: 70px;
          height: 70px;
          border-radius: var(--md-sys-shape-corner-small, 10px);
          background: linear-gradient(135deg, #1a3a4a, #0d2137);
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 32px;
          flex-shrink: 0;
          position: relative;
          overflow: hidden;
          box-shadow: 0 2px 8px rgba(0,0,0,0.3);
        }
        .thumbnail-color-bar {
          position: absolute;
          bottom: 0;
          left: 0;
          right: 0;
          height: 6px;
          display: flex;
        }
        .thumbnail-color-segment {
          flex: 1;
        }

        .history-details {
          flex: 1;
          display: flex;
          flex-direction: column;
          gap: 4px;
        }
        .history-task-name {
          font-size: 14px;
          font-weight: 700;
          color: #e0e0e0;
          line-height: 1.3;
        }
        .history-params {
          font-size: 11px;
          color: #94a3b8;
          display: flex;
          gap: 10px;
          flex-wrap: wrap;
        }
        .param-tag {
          background: rgba(79,195,247,0.12);
          padding: 2px 8px;
          border-radius: 10px;
          font-weight: 500;
          color: #4fc3f7;
        }
        .history-meta {
          display: flex;
          align-items: center;
          gap: 14px;
          font-size: 11px;
          color: #94a3b8;
          margin-top: 4px;
        }
        .history-datetime {
          font-size: 10px;
          color: #64748b;
          margin-top: auto;
          padding-top: 4px;
          border-top: 1px dashed rgba(255,255,255,0.08);
        }

        .status-badge {
          position: absolute;
          top: 10px;
          right: 10px;
          padding: 4px 12px;
          border-radius: 16px;
          font-size: 10px;
          font-weight: 700;
        }
        .status-badge.success {
          background: linear-gradient(135deg, #1b5e20, #2e7d32);
          color: #a5d6a7;
        }
        .status-badge.failed {
          background: linear-gradient(135deg, #b71c1c, #c62828);
          color: #ef9a9a;
        }
        .status-badge.printing {
          background: linear-gradient(135deg, #0d47a1, #1565c0);
          color: #90caf9;
        }

        /* 统计信息条 */
        .stats-summary {
          display: flex;
          gap: 12px;
          margin-bottom: 16px;
          padding: 12px;
          background: linear-gradient(145deg, #2a2a3c, #252538);
          border-radius: var(--md-sys-shape-corner-small, 10px);
          border: 1px solid rgba(255,255,255,0.06);
        }
        .summary-item {
          flex: 1;
          text-align: center;
        }
        .summary-value {
          font-size: 18px;
          font-weight: 800;
          color: var(--md-sys-color-primary, #03a9f4);
        }
        .summary-label {
          font-size: 10px;
          color: #94a3b8;
          margin-top: 2px;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }

        /* 筛选栏 */
        .filter-bar {
          display: flex;
          gap: 10px;
          margin-bottom: 16px;
          flex-wrap: wrap;
        }
        .filter-select {
          padding: 8px 14px;
          border: 2px solid rgba(255,255,255,0.12);
          border-radius: var(--md-sys-shape-corner-extra-small, 6px);
          background: #2a2a3c;
          font-size: 12px;
          font-weight: 500;
          color: #e0e0e0;
          cursor: pointer;
          min-width: 120px;
        }
        .search-box {
          flex: 1;
          min-width: 180px;
          position: relative;
        }
        .search-input {
          width: 100%;
          padding: 8px 14px 8px 36px;
          border: 2px solid rgba(255,255,255,0.12);
          border-radius: var(--md-sys-shape-corner-extra-small, 6px);
          font-size: 12px;
          background: #2a2a3c;
          color: #e0e0e0;
        }
        .search-input:focus {
          outline: none;
          border-color: #4fc3f7;
          box-shadow: 0 0 0 3px rgba(79,195,247,0.2);
        }
        .search-icon {
          position: absolute;
          left: 12px;
          top: 50%;
          transform: translateY(-50%);
          color: #64748b;
          font-size: 14px;
        }

        .empty-state {
          text-align: center;
          padding: 60px 24px;
          color: #94a3b8;
        }
        .empty-icon {
          font-size: 64px;
          margin-bottom: 16px;
          opacity: 0.5;
        }
        .empty-text {
          font-size: 15px;
          font-weight: 500;
        }

        @media (max-width: 768px) {
          .card { padding: 20px; }
          .header { flex-direction: column; align-items: flex-start; gap: 12px; }
          .stats-grid { grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 12px; }
          .stats-grid { grid-template-columns: repeat(2, 1fr); gap: 10px; }
          .realtime-grid { grid-template-columns: 1fr; }
          .ams-grid { grid-template-columns: repeat(2, 1fr); }
          .pie-container { flex-direction: column; align-items: center; }
        }
      </style>
      <div class="card" id="card-content">
        <div class="no-data">加载中...</div>
      </div>
    `;
  }

  updateData() {
    if (this._isRendering) return;

    const container = this.shadowRoot.getElementById('card-content');
    if (!container) return;

    try {
      if (!this._hass) {
        container.innerHTML = `<div class="error"><b>⚠️ 错误：</b>未连接到 Home Assistant</div>`;
        return;
      }

      if (!this.config) {
        container.innerHTML = `<div class="error"><b>⚠️ 配置错误！</b>卡片配置为空</div>`;
        return;
      }

      if (!this.config.print_history) {
        container.innerHTML = `<div class="error"><b>⚠️ 配置错误！</b>缺少 print_history 配置项</div>`;
        return;
      }

      const currentDataSnapshot = this._generateDataSnapshot();

      if (this._lastRenderedData && this._isDataEqual(this._lastRenderedData, currentDataSnapshot)) {
        return;
      }

      this._isRendering = true;

      const title = this._escapeHtml(this.config.title || '🖨️ 打印机分析');

      let html = `
        <div class="header">
          <div class="header-title">📊 ${title}</div>
          <span class="header-badge">v3.4.6</span>
        </div>

        <div class="tab-container">
          <button class="tab-button ${this._activeTab === 'stats' ? 'active' : ''}" data-tab="stats">📈 统计分析</button>
          <button class="tab-button ${this._activeTab === 'history' ? 'active' : ''}" data-tab="history">📋 历史记录</button>
        </div>

        <div class="tab-content ${this._activeTab === 'stats' ? 'active' : ''}" id="tab-stats">
      `;

      try {
        html += this._renderTimeDimension();
        html += '<div style="height:1px;background:linear-gradient(90deg,transparent,var(--primary-color,#03a9f4),transparent);margin:16px 0;opacity:0.3"></div>';
        html += this._renderPeriodStats();
      } catch (e) {
        html += `<div class="error">统计渲染失败: ${this._escapeHtml(e.message)}</div>`;
      }

      try { html += this._renderSuccessRateTrend(); } catch (e) {
        html += `<div class="error">趋势图渲染失败: ${this._escapeHtml(e.message)}</div>`;
      }
      try { html += this._renderDurationDistribution(); } catch (e) {
        html += `<div class="error">分布图渲染失败: ${this._escapeHtml(e.message)}</div>`;
      }
      try { html += this._renderActivityHeatmap(); } catch (e) {
        html += `<div class="error">热力图渲染失败: ${this._escapeHtml(e.message)}</div>`;
      }
      try { html += this._renderFilamentUsage(); } catch (e) {
        html += `<div class="error">耗材使用渲染失败: ${this._escapeHtml(e.message)}</div>`;
      }
      try { html += this._renderRealtimeMonitor(); } catch (e) {
        html += `<div class="error">实时监控渲染失败: ${this._escapeHtml(e.message)}</div>`;
      }
      try { html += this._renderLifetimeStats(); } catch (e) {
        html += `<div class="error">终身统计渲染失败: ${this._escapeHtml(e.message)}</div>`;
      }

      html += `</div>`;

      html += `
        <div class="tab-content ${this._activeTab === 'history' ? 'active' : ''}" id="tab-history">
      `;
      html += this._renderHistoryPage();
      html += `</div>`;

      container.innerHTML = html || '<div class="no-data">暂无数据</div>';

      this._lastRenderedData = currentDataSnapshot;
      this._isRendering = false;

      // v3.4.6: 绑定Tab点击事件
      this._bindTabEvents();

    } catch (error) {
      console.error('打印机分析卡片错误:', error);
      container.innerHTML = `<div class="error"><b>❌ 渲染错误！</b>${this._escapeHtml(error.message)}</div>`;
      this._isRendering = false;
    }
  }

  _bindTabEvents() {
    const tabs = this.shadowRoot.querySelectorAll('.tab-button');
    tabs.forEach(tab => {
      tab.addEventListener('click', (e) => {
        const tabName = e.target.dataset.tab;
        this._activeTab = tabName;
        
        // 切换显示的tab内容
        this.shadowRoot.querySelectorAll('.tab-content').forEach(content => {
          content.classList.remove('active');
        });
        this.shadowRoot.getElementById(`tab-${tabName}`).classList.add('active');
        
        // 切换按钮状态
        tabs.forEach(t => t.classList.remove('active'));
        e.target.classList.add('active');
      });
    });
  }

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

  _isDataEqual(data1, data2) {
    if (!data1 || !data2) return false;
    
    const keys = ['totalPrints', 'successRate', 'avgDuration', 'totalDuration', 'totalEnergy',
                  'printStatus', 'currentTask', 'printProgress', 'currentWeight', 'historyLength'];
    
    for (const key of keys) {
      if (data1[key] !== data2[key]) return false;
    }
    
    return true;
  }

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
    const printStatus = this._escapeHtml(
      this.config.print_status ? this._getState(this.config.print_status) : '空闲'
    );

    let statusIcon = '⚪';
    let statusColor = '#9e9e9e';
    
    if (printStatus.includes('打印中') || printStatus.includes('printing') || printStatus.includes('running')) {
      statusIcon = '🔵';
      statusColor = '#03a9f4';
    } else if (printStatus.includes('完成') || printStatus.includes('finish')) {
      statusIcon = '✅';
      statusColor = '#4caf50';
    }

    return `
      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-icon">🖨️</div>
          <div class="stat-value">${totalPrints}</div>
          <div class="stat-label">总打印次数</div>
        </div>
        <div class="stat-card">
          <div class="stat-icon">✅</div>
          <div class="stat-value">${successRate}%</div>
          <div class="stat-label">成功率</div>
        </div>
        <div class="stat-card">
          <div class="stat-icon">⏱️</div>
          <div class="stat-value">${avgDuration}</div>
          <div class="stat-label">平均时长 (小时)</div>
        </div>
        <div class="stat-card">
          <div class="stat-icon">🕐</div>
          <div class="stat-value">${totalDuration}</div>
          <div class="stat-label">总时长 (小时)</div>
        </div>
        <div class="stat-card">
          <div class="stat-icon">⚡</div>
          <div class="stat-value">${totalEnergy}</div>
          <div class="stat-label">总能耗 (kWh)</div>
        </div>
        <div class="stat-card" style="border-color:${statusColor}">
          <div class="stat-icon">${statusIcon}</div>
          <div class="stat-value" style="font-size:16px;font-weight:600;color:${statusColor}">${printStatus}</div>
          <div class="stat-label">当前状态</div>
        </div>
      </div>
    `;
  }

  _renderPeriodStats() {
    const periods = [
      { key: 'material_stats_7d', label: '最近7天', icon: '📅' },
      { key: 'material_stats_30d', label: '最近30天', icon: '📆' },
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
        <div class="section-title">
          <span class="section-icon">${period.icon}</span>
          <span>${this._escapeHtml(period.label)}</span>
        </div>
        <div class="chart-container">
          <table class="stats-table">
            <thead><tr><th>指标</th><th class="table-value">数值</th></tr></thead>
            <tbody>
              <tr><td>🖨️ 打印次数</td><td class="table-value">${totalPrints}</td></tr>
              <tr><td>✅ 成功</td><td style="color:#4caf50;font-weight:600">${successful}</td></tr>
              <tr><td>❌ 失败</td><td style="color:#f44336;font-weight:600">${failed}</td></tr>
              <tr><td>📈 成功率</td><td class="table-value">${successRate}%</td></tr>
              <tr><td>🎨 耗材重量</td><td class="table-value">${totalWeight} 克</td></tr>
              <tr><td>📏 耗材长度</td><td class="table-value">${totalLength} 米</td></tr>
              <tr><td>⚡ 能耗</td><td class="table-value">${totalEnergy} kWh</td></tr>
              <tr><td>⏱️ 平均时长</td><td class="table-value">${avgDuration} 小时</td></tr>
            </tbody>
          </table>
        </div>
      `;
    }
    return html;
  }

  _renderSuccessRateTrend() {
    const history = this._getHistory();
    if (!Array.isArray(history) || history.length === 0) {
      return `<div class="section-title"><span class="section-icon">📈</span>打印成功率趋势</div><div class="chart-container"><div class="no-data">📭 暂无历史数据</div></div>`;
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

    const width = 500, height = 120, padding = 25;
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
    const pctStr = this._escapeHtml(String(Math.round(successCount/totalCount*100)));

    return `
      <div class="section-title"><span class="section-icon">📈</span>打印成功率趋势</div>
      <div class="chart-container">
        <div class="chart-title">
          <span>累计: ${totalStr} 次 = ${pctStr}%</span>
          <span class="chart-subtitle">${sorted.length > MAX_POINTS ? `显示 ${sampledData.length}/${sorted.length} 条` : ''}</span>
        </div>
        <div style="position:relative;height:100px">
          <svg class="trend-svg" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none">
            <defs><linearGradient id="rateGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="var(--primary-color, #03a9f4)" stop-opacity="0.3"/>
              <stop offset="100%" stop-color="var(--primary-color, #03a9f4)" stop-opacity="0.02"/>
            </linearGradient></defs>
            <path d="${areaPath}" fill="url(#rateGrad)" />
            <path d="${linePath}" fill="none" stroke="var(--primary-color, #03a9f4)" stroke-width="2.5"/>
            ${points.map((p, i) => {
              const x = padding + (i / Math.max(points.length - 1, 1)) * chartW;
              const y = padding + chartH - (p.rate / 100) * chartH;
              return `<circle cx="${x}" cy="${y}" r="3.5" fill="var(--primary-color, #03a9f4)" opacity="${0.6 + (p.rate/200)}"/>`;
            }).join('')}
          </svg>
        </div>
      </div>
    `;
  }

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
      return `<div class="section-title"><span class="section-icon">📊</span>打印时长分布</div><div class="chart-container"><div class="no-data">📭 暂无数据</div></div>`;
    }

    const maxVal = Math.max(...labels.map(k => distribution[k]), 1);
    const colors = ['#4CAF50', '#8BC34A', '#FFC107', '#FF9800', '#F44336', '#9C27B0'];

    let barsHtml = '';
    for (let i = 0; i < labels.length; i++) {
      const label = labels[i];
      const value = distribution[label] || 0;
      const heightPct = (value / maxVal) * 100;
      barsHtml += `<div style="flex:1;display:flex;flex-direction:column;align-items:center;min-height:110px">
        <div class="table-value" style="font-size:13px;margin-bottom:6px">${value}</div>
        <div style="width:100%;background:rgba(0,0,0,0.04);border-radius:6px;height:90px;padding:4px;position:relative">
          <div style="width:${Math.max(heightPct, 3)}%;height:100%;background:linear-gradient(to top,${colors[i % colors.length]},${colors[(i+1) % colors.length]});border-radius:4px"></div>
        </div>
        <div style="font-size:11px;color:var(--secondary-text-color);margin-top:6px;text-align:center;font-weight:500">${label}</div>
      </div>`;
    }

    return `<div class="section-title"><span class="section-icon">📊</span>打印时长分布</div><div class="chart-container"><div style="display:flex;gap:12px">${barsHtml}</div></div>`;
  }

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
      return `<div class="section-title"><span class="section-icon">🗓️</span>打印活动热力图</div><div class="chart-container"><div class="no-data">📭 暂无数据</div></div>`;
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
      let bgColor = 'var(--divider-color, #e0e0e0)';
      if (count > 0) {
        if (intensity < 0.33) bgColor = '#c8e6c9';
        else if (intensity < 0.66) bgColor = '#66bb6a';
        else bgColor = '#2e7d32';
      }
      cellsHtml += `<div style="
        aspect-ratio:1;border-radius:6px;min-height:16px;cursor:default;
        background:${bgColor};box-shadow:inset 0 0 0 1px rgba(255,255,255,0.2);
        title="${dateKey}: ${count}次"
      " data-date="${this._escapeHtml(dateKey)}" data-count="${this._escapeHtml(String(count))}"
      ></div>`;
    }

    return `<div class="section-title"><span class="section-icon">🗓️</span>打印活动热力图</div><div class="chart-container"><div style="display:grid;grid-template-columns:repeat(7,1fr);gap:4px">${cellsHtml}</div></div>`;
  }

  _renderFilamentUsage() {
    const history = this._getHistory();

    let typeUsage = {};
    let colorUsage = {};
    let multiColorPrints = [];
    let hasData = false;
    let dataSource = '';

    console.log(`[Printer Analytics] v3.4.6 _renderFilamentUsage开始 - history长度: ${history ? history.length : 'null/undefined'}`);

    if (Array.isArray(history) && history.length > 0 &&
                           history.some(item => item.status === 'finish' && (item.total_weight > 0 || item.filament_type))) {

      console.log('[Printer Analytics] ✅ 使用策略1: 从history提取数据');
      const result = this._extractFilamentFromHistory(history, typeUsage, colorUsage);
      hasData = result.hasData;
      multiColorPrints = result.multiColorPrints || [];
      dataSource = 'history';

      console.log(`[Printer Analytics] History提取结果 - hasData: ${hasData}, 类型数: ${Object.keys(typeUsage).length}, 颜色数: ${Object.keys(colorUsage).length}, 多色打印数: ${multiColorPrints.length}`);
    }

    if (!hasData && Object.keys(typeUsage).length === 0 && Object.keys(colorUsage).length === 0) {
      console.log('[Printer Analytics] ⚠️ 使用策略2: 触发Fallback');
      hasData = this._extractFilamentFromStats(typeUsage, colorUsage);
      dataSource = 'fallback';
    }

    console.log(`[Printer Analytics] 📊 最终数据源: ${dataSource}, 是否有数据: ${hasData}`);

    if (!hasData || (Object.keys(typeUsage).length === 0 && Object.keys(colorUsage).length === 0)) {
      console.warn('[Printer Analytics] 所有数据源均无耗材数据，跳过渲染');
      return '';
    }

    const pieColors = ['#03a9f4', '#4caf50', '#ff9800', '#f44336', '#9c27b0', '#00bcd4', '#ffeb3b', '#795548',
                     '#E91E63', '#8BC34A', '#FF5722', '#607D8B', '#3F51B5', '#CDDC39', '#FF6F00', '#009688'];

    let html = '';
    
    if (multiColorPrints.length > 0) {
      html += '<div class="section-title"><span class="section-icon">🌈</span>多色打印记录</div>';
      html += '<div class="chart-container">';
      html += `<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px">
                <span style="font-weight:600;font-size:14px">共 ${multiColorPrints.length} 次多色打印</span>
                <span style="font-size:12px;background:var(--primary-color,#03a9f4);color:white;padding:4px 12px;border-radius:12px;font-weight:600">最多16色</span>
              </div>`;
      
      const recentMulti = multiColorPrints.slice(-5).reverse();
      for (const print of recentMulti) {
        const taskName = this._escapeHtml(print.task_name || '未知任务');
        
        // 统一时区处理
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

        let borderColor = 'var(--primary-color, #03a9f4)';
        let statusIcon = '✅';
        let cardClass = 'multi-color-card success';

        if (isPartial) {
          borderColor = printStatus === 'cancelled' ? '#FF9800' : '#F44336';
          statusIcon = printStatus === 'cancelled' ? '⚠️' : '❌';
          cardClass = printStatus === 'cancelled' ? 'multi-color-card cancelled' : 'multi-color-card failed';
        }

        html += `<div class="${cardClass}" style="padding:14px;margin-bottom:12px;border-left:5px solid ${borderColor};border-radius:12px">`;
        html += `<div style="display:flex;align-items:center;gap:8px;font-weight:700;font-size:14px">${statusIcon} ${taskName}</div>`;

        let statusInfo = `🎨 ${colorsCount}种颜色 | 切换${changeCount}次`;
        if (isPartial) {
          statusInfo += ` | ${statusLabel}(${completionPct}%)`;
        }
        html += `<div style="font-size:12px;color:var(--secondary-text-color,#888);margin-top:6px;font-weight:500">${endTime} | ${statusInfo}</div>`;

        if (isPartial && completionPct > 0 && completionPct < 100) {
          html += `<div class="progress-bar-container">`;
          html += `<div class="progress-label"><span>打印进度</span><span style="color:${borderColor};font-weight:700">${completionPct}%</span></div>`;
          html += `<div class="progress-track"><div class="progress-fill" style="width:${completionPct}%"></div></div></div>`;
        }

        if (print.colors_used && print.colors_used.length > 0) {
          html += `<div style="margin-top:10px;display:flex;flex-wrap:wrap;gap:6px">`;
          for (let i = 0; i < Math.min(print.colors_used.length, 8); i++) {
            const colorCode = print.colors_used[i];
            const displayName = this._formatColorName(colorCode);
            const colorDetail = colorDetails.find(d => d.color === colorCode);
            const colorWeight = colorDetail ? colorDetail.weight_g : 0;
            const colorPct = totalPrintWeight > 0 ? ((colorWeight / totalPrintWeight) * 100).toFixed(0) : '?';

            html += `<span class="color-tag" style="background:${colorCode};color:${this._getContrastColor(colorCode)}">● ${displayName}${colorWeight > 0 ? ` (${colorWeight}g, ${colorPct}%)` : ''}</span>`;
          }
          if (print.colors_used.length > 8) {
            html += `<span style="padding:4px 10px;border-radius:12px;font-size:11px;color:var(--secondary-text-color);background:var(--secondary-background-color)">+${print.colors_used.length - 8}</span>`;
          }
          html += `</div>`;
        }

        if (colorDetails.length > 0) {
          html += `<div style="margin-top:10px;padding-top:10px;border-top:1px dashed rgba(0,0,0,0.1);font-size:12px">`;
          for (const detail of colorDetails) {
            const pct = totalPrintWeight > 0 ? ((detail.weight_g / totalPrintWeight) * 100).toFixed(0) : '?';
            html += `<div style="display:flex;justify-content:space-between;align-items:center;padding:3px 0;border-radius:6px">
                          <span style="display:flex;align-items:center;gap:6px">
                            <span style="width:10px;height:10px;border-radius:50%;background:${detail.color};border:2px solid rgba(255,255,255,0.3)"></span>
                            <span>${this._formatColorName(detail.color)}</span>
                          </span>
                          <span style="font-weight:600;color:var(--primary-color,#03a9f4)">${detail.weight_g}g</span>
                          <span style="color:var(--secondary-text-color,#888);font-size:11px">(${pct}%)</span>
                        </div>`;
          }
          html += `</div>`;
        }

        html += `</div>`;
      }
      
      html += '</div>';
    }

    html += this._renderPieChart('🧵 耗材类型使用量', typeUsage, pieColors);
    html += this._renderPieChart('🎨 耗材颜色使用量', colorUsage, pieColors);
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
      const hue = hsl.h;
      const sat = hsl.s;
      const light = hsl.l;
      
      let hueName = '';
      if (sat < 15) {
        if (light > 85) hueName = '米白';
        else if (light > 65) hueName = '浅灰';
        else if (light > 35) hueName = '灰色';
        else if (light > 15) hueName = '深灰';
        else hueName = '炭黑';
      } else {
        if (hue < 15 || hue >= 345) hueName = '红';
        else if (hue < 45) hueName = '橙';
        else if (hue < 75) hueName = '黄';
        else if (hue < 150) hueName = '绿';
        else if (hue < 195) hueName = '青';
        else if (hue < 255) hueName = '蓝';
        else if (hue < 285) hueName = '紫';
        else hueName = '品红';
        
        if (light < 25) hueName = '深' + hueName;
        else if (light < 45) hueName = '暗' + hueName;
        else if (light > 75) hueName = '浅' + hueName;
        
        if (sat < 30) hueName += '(低饱和)';
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
      return `<div class="section-title"><span class="section-icon">${titleIcon}</span>${cleanTitle}</div><div class="chart-container"><div class="no-data">暂无数据</div></div>`;
    }

    const total = entries.reduce((sum, [_, v]) => sum + v, 0);

    let paths = '', legendHtml = '';
    for (let i = 0; i < entries.length; i++) {
      const [label, value] = entries[i];
      const pct = value / total;
      const endAngle = (i > 0 ? entries.slice(0, i).reduce((acc, [_, v]) => acc + v, 0) : 0) / total * 2 * Math.PI;
      const startAngle = endAngle - pct * 2 * Math.PI;
      
      const x1 = 60 + 55 * Math.cos(startAngle - Math.PI / 2);
      const y1 = 60 + 55 * Math.sin(startAngle - Math.PI / 2);
      const x2 = 60 + 55 * Math.cos(endAngle - Math.PI / 2);
      const y2 = 60 + 55 * Math.sin(endAngle - Math.PI / 2);
      const largeArc = pct > 0.5 ? 1 : 0;
      
      const d = `M60,60 L${x1},${y1} A55,55 0 ${largeArc},1 ${x2},${y2} Z`;
      const color = colors[i % colors.length];
      paths += `<path d="${d}" fill="${color}" stroke="#fff" stroke-width="2"/>`;
      
      const displayName = label.length > 15 ? label.substring(0, 12) + '..' : label;
      legendHtml += `<div class="legend-item">
                      <div class="legend-dot" style="background:${color}"></div>
                      <span style="font-weight:500">${displayName}</span>
                      <span style="color:var(--primary-color,#03a9f4);font-weight:700;margin-left:auto">${Math.round(value)}g</span>
                    </div>`;
    }

    return `<div class="section-title"><span class="section-icon">${titleIcon}</span>${cleanTitle}</div>
            <div class="chart-container">
              <div class="pie-container">
                <svg class="pie-svg" width="120" height="120" viewBox="0 0 120 120">${paths}</svg>
                <div class="pie-legend">${legendHtml}</div>
              </div>
            </div>`;
  }

  _renderRealtimeMonitor() {
    console.log('[Printer Analytics] 开始渲染实时监控面板...');
    
    const currentTask = this._getState(this.config.current_task) || '未配置';
    const printProgress = this._getState(this.config.print_progress) || '0';
    const currentWeight = this._getState(this.config.current_weight) || 'N/A';
    const currentLength = this._getState(this.config.current_length) || 'N/A';
    const totalUsage = this._getState(this.config.total_usage) || 'N/A';
    const nozzleTemp = this._getState(this.config.nozzle_temp) || 'N/A';
    const bedTemp = this._getState(this.config.bed_temp) || 'N/A';
    const chamberTemp = this._getState(this.config.chamber_temp) || 'N/A';
    const activeTray = this._getState(this.config.active_tray);
    const powerConsumption = this._getState(this.config.power_consumption) || 'N/A';
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
      console.log('[Printer Analytics] 检测到AMS耗材盘配置');
      const trays = [
        { num: 1, entity: this.config.ams_tray_1 },
        { num: 2, entity: this.config.ams_tray_2 },
        { num: 3, entity: this.config.ams_tray_3 },
        { num: 4, entity: this.config.ams_tray_4 }
      ].filter(t => t.entity);
      
      if (trays.length > 0) {
        amsHtml = `<div class="section-title" style="margin-top:20px"><span class="section-icon">🎨</span>AMS耗材盘</div>
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
        
        amsHtml += '</div>';
      }
    }

    return `<div class="section-title"><span class="section-icon">📡</span>实时监控面板</div>
            <div class="realtime-panel">
              <div class="realtime-header">
                <div class="realtime-title">🖥️ 打印机状态监控</div>
                <div class="realtime-status-badge ${statusClass}">${statusText}</div>
              </div>
              
              <div class="realtime-grid">
                <div class="realtime-item">
                  <div class="realtime-item-label">📋 当前任务</div>
                  <div class="realtime-item-value">${this._escapeHtml(currentTask || '空闲')}</div>
                </div>
                
                ${printProgress ? `
                <div class="realtime-item">
                  <div class="realtime-item-label">📊 打印进度</div>
                  <div class="realtime-item-value">${printProgress}%</div>
                  <div style="margin-top:8px;background:#e0e0e0;border-radius:6px;height:8px;overflow:hidden">
                    <div style="width:${printProgress}%;height:100%;background:linear-gradient(90deg,#03a9f4,#00bcd4);border-radius:6px"></div>
                  </div>
                </div>` : ''}
                
                ${currentWeight ? `
                <div class="realtime-item">
                  <div class="realtime-item-label">⚖️ 当前耗材重量</div>
                  <div class="realtime-item-value">${currentWeight}<small style="font-size:12px;color:#666;font-weight:500">g</small></div>
                </div>` : ''}
                
                ${totalUsage ? `
                <div class="realtime-item">
                  <div class="realtime-item-label">📦 累计使用量</div>
                  <div class="realtime-item-value">${totalUsage}<small style="font-size:12px;color:#666;font-weight:500">g</small></div>
                </div>` : ''}
                
                ${nozzleTemp ? `
                <div class="realtime-item">
                  <div class="realtime-item-label">🌡️ 喷嘴温度</div>
                  <div class="realtime-item-value">${nozzleTemp}<small style="font-size:12px;color:#666;font-weight:500">°C</small></div>
                </div>` : ''}
                
                ${bedTemp ? `
                <div class="realtime-item">
                  <div class="realtime-item-label">🔥 热床温度</div>
                  <div class="realtime-item-value">${bedTemp}<small style="font-size:12px;color:#666;font-weight:500">°C</small></div>
                </div>` : ''}
                
                ${chamberTemp !== 'N/A' ? `
                <div class="realtime-item">
                  <div class="realtime-item-label">💨 腔体温度</div>
                  <div class="realtime-item-value">${chamberTemp}<small style="font-size:12px;color:#666;font-weight:500">°C</small></div>
                </div>` : ''}
                
                ${powerConsumption !== 'N/A' ? `
                <div class="realtime-item">
                  <div class="realtime-item-label">⚡ 功耗</div>
                  <div class="realtime-item-value">${powerConsumption}<small style="font-size:12px;color:#666;font-weight:500">W</small></div>
                </div>` : ''}
                
                ${speedProfile ? `
                <div class="realtime-item">
                  <div class="realtime-item-label">⚡ 打印速度</div>
                  <div class="realtime-item-value">${this._escapeHtml(speedProfile)}</div>
                </div>` : ''}
                
                ${nozzleSize ? `
                <div class="realtime-item">
                  <div class="realtime-item-label">🔧 喷嘴尺寸</div>
                  <div class="realtime-item-value">${nozzleSize}</div>
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

    return `<div class="section-title"><span class="section-icon">🏆</span>终身统计（累计）</div>
            <div class="chart-container">
              <table class="stats-table">
                <thead><tr><th>指标</th><th>数值</th></tr></thead>
                <tbody>
                  <tr><td>总打印次数</td><td class="table-value">${totalPrints} 次</td></tr>
                  <tr><td>总耗材重量</td><td class="table-value">${totalWeight.toFixed(1)} 克</td></tr>
                  <tr><td>总耗材长度</td><td class="table-value">${totalLength.toFixed(1)} 米</td></tr>
                  <tr><td>总能耗</td><td class="table-value">${totalEnergy.toFixed(2)} kWh</td></tr>
                </tbody>
              </table>
            </div>`;
  }

  // 从历史记录提取耗材数据
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
          if (colorsUsed.length > 0) {
            totalColors = colorsUsed.length;
          }
        } else if (fc.startsWith('#')) {
          colorsUsed = [fc];
          totalColors = 1;
        }
      }

      if (colorsUsed.length === 0 && item.color_usage && Array.isArray(item.color_usage)) {
        colorsUsed = item.color_usage
          .filter(cu => cu && cu.color)
          .map(cu => cu.color);
        if (colorsUsed.length > 1) {
          totalColors = colorsUsed.length;
        }
      }

      let typesUsed = item.types_used || [];
      if (typesUsed.length === 0 && item.filament_type) {
        const ft = String(item.filament_type).trim();
        if (ft.includes(',') || ft.includes(';') || ft.includes('+') || ft.includes('/')) {
          typesUsed = ft.split(/[,;+\/]+/).map(t => t.trim()).filter(t => t && t.length > 1);
        }
      }

      if (totalColors > 1) {
        multiColorPrints.push({
          ...item,
          colors_used: colorsUsed,
          types_used: typesUsed,
          total_colors: totalColors
        });

        if (item.color_usage && Array.isArray(item.color_usage)) {
          for (const cu of item.color_usage) {
            if (!cu.color || !cu.weight_g || cu.weight_g <= 0) continue;

            const colorKey = this._escapeHtml(cu.color);
            const weight = cu.weight_g;

            if (!colorUsage[colorKey]) colorUsage[colorKey] = 0;
            colorUsage[colorKey] += weight;

            if (cu.type) {
              const typeKey = this._escapeHtml(cu.type);
              if (!typeUsage[typeKey]) typeUsage[typeKey] = 0;
              typeUsage[typeKey] += weight;
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
      multiColorPrints: multiColorPrints
    };
  }

  // 从统计传感器提取耗材数据（Fallback机制）
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

    if (Object.keys(typeUsage).length > 0 || Object.keys(colorUsage).length > 0) {
      return false;
    }

    if (weight > 0 && weight < 10000) {
      let filamentType = activeTrayName || '未知耗材';
      let filamentColor = '#FFFFFF';

      const trayConfigs = [
        this.config.ams_tray_1,
        this.config.ams_tray_2,
        this.config.ams_tray_3,
        this.config.ams_tray_4
      ].filter(t => t);

      for (const trayConfig of trayConfigs) {
        const trayData = this._getAttr(trayConfig);
        if (trayData && trayData.name) {
          const trayName = trayData.name;
          const trayColor = trayData.color || '#FFFFFF';

          if (
            activeTrayName && (
              activeTrayName.includes(trayName) ||
              trayName.includes(activeTrayName.replace(' HF', '')) ||
              trayConfigs.indexOf(trayConfig) === 0
            )
          ) {
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

  // ========== v3.4.6 历史记录页面核心方法（集成到HA）==========

  _renderHistoryPage() {
    const history = this._getHistory();

    return `
      <div class="filter-bar">
        <select class="filter-select" id="filter-status">
          <option value="">全部状态</option>
          <option value="finish">✅ 成功</option>
          <option value="failed">❌ 失败</option>
          <option value="printing">🔵 进行中</option>
          <option value="cancelled">⚠️ 已取消</option>
        </select>

        <div class="search-box">
          <span class="search-icon">🔍</span>
          <input type="text" class="search-input" id="search-input"
                 placeholder="搜索任务名称或耗材类型...">
        </div>
      </div>

      <div class="stats-summary">
        ${this._renderHistoryStats(history)}
      </div>

      <div class="history-list">
        ${this._renderHistoryList(history)}
      </div>
    `;
  }

  _renderHistoryStats(history) {
    if (!Array.isArray(history) || history.length === 0) {
      return `
        <div class="summary-item"><div class="summary-value">0</div><div class="summary-label">总记录</div></div>
        <div class="summary-item"><div class="summary-value">-</div><div class="summary-label">成功率</div></div>
        <div class="summary-item"><div class="summary-value">0g</div><div class="summary-label">总耗材</div></div>
        <div class="summary-item"><div class="summary-value">0h</div><div class="summary-label">总时长</div></div>
      `;
    }

    const total = history.length;
    const success = history.filter(h => h.status === 'finish').length;
    const successRate = total > 0 ? ((success / total) * 100).toFixed(1) : 0;
    const totalWeight = history.reduce((sum, h) => sum + (h.total_weight || 0), 0).toFixed(1);
    const totalDuration = this._calculateTotalDuration(history);

    return `
      <div class="summary-item">
        <div class="summary-value">${total}</div>
        <div class="summary-label">总记录</div>
      </div>
      <div class="summary-item">
        <div class="summary-value" style="color: ${successRate >= 80 ? '#4caf50' : '#ff9800'}">${successRate}%</div>
        <div class="summary-label">成功率</div>
      </div>
      <div class="summary-item">
        <div class="summary-value">${totalWeight}g</div>
        <div class="summary-label">总耗材</div>
      </div>
      <div class="summary-item">
        <div class="summary-value">${totalDuration}</div>
        <div class="summary-label">总时长</div>
      </div>
    `;
  }

  _calculateTotalDuration(history) {
    let totalMinutes = 0;
    for (const item of history) {
      if (item.start_time && item.end_time) {
        try {
          const start = new Date(item.start_time);
          const end = new Date(item.end_time);
          const diffMs = end - start;
          totalMinutes += diffMs / (1000 * 60);
        } catch (e) { }
      }
    }

    if (totalMinutes < 60) return `${totalMinutes.toFixed(0)}分钟`;
    const hours = Math.floor(totalMinutes / 60);
    const mins = Math.round(totalMinutes % 60);
    return mins > 0 ? `${hours}h${mins}m` : `${hours}h`;
  }

  _renderHistoryList(history) {
    if (!Array.isArray(history) || history.length === 0) {
      return `
        <div class="empty-state">
          <div class="empty-icon">📭</div>
          <div class="empty-text">暂无打印历史记录</div>
        </div>
      `;
    }

    const sorted = [...history].sort((a, b) => {
      const timeA = a.end_time || a.start_time || '';
      const timeB = b.end_time || b.start_time || '';
      return new Date(timeB) - new Date(timeA);
    });

    return sorted.map((item, index) => this._renderHistoryItem(item, index)).join('');
  }

  _renderHistoryItem(item, index) {
    const taskName = this._escapeHtml(item.task_name || '未命名任务');
    const status = item.status || 'unknown';

    const statusConfig = {
      'finish': { text: '成功', class: 'success', icon: '✅' },
      'failed': { text: '失败', class: 'failed', icon: '❌' },
      'printing': { text: '进行中', class: 'printing', icon: '🔵' },
      'cancelled': { text: '已取消', class: 'cancelled', icon: '⚠️' }
    };
    const statusInfo = statusConfig[status] || { text: '未知', class: '', icon: '❓' };

    const layerHeight = item.layer_height ? `${item.layerHeight || item.layer_height}mm` : '-';
    const layers = item.layers || item.total_layers || '-';
    const infill = item.infill ? `${item.infill}%` : '-';

    // 统一处理时区：将UTC时间转换为本地时间显示
    const _formatLocalTime = (timeStr) => {
      if (!timeStr) return '';
      try {
        let d;
        if (timeStr.includes('T')) {
          d = new Date(timeStr);
        } else {
          d = new Date(timeStr.replace(' ', 'T'));
        }
        if (isNaN(d.getTime())) return timeStr.substring(0, 16).replace('T', ' ');
        const pad = (n) => String(n).padStart(2, '0');
        return `${d.getFullYear()}/${pad(d.getMonth()+1)}/${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
      } catch (e) { return timeStr; }
    };
    const startTime = _formatLocalTime(item.start_time);
    const endTime = _formatLocalTime(item.end_time);
    const timeDisplay = (startTime && endTime) ? `${startTime} ~ ${endTime}` : (endTime || startTime);
    const duration = this._formatDuration(item.duration_minutes || item.print_duration);

    const filamentType = this._escapeHtml(item.filament_type || '未知');
    const weight = item.total_weight ? `${item.total_weight.toFixed(1)}g` : '-';
    const colorsUsed = item.colors_used || [];

    const thumbnailIcon = status === 'finish' ? '✅' : (status === 'failed' ? '❌' : (status === 'printing' ? '🖨️' : '📄'));

    const colorBarHtml = colorsUsed.length > 0 ? `
      <div class="thumbnail-color-bar">
        ${colorsUsed.map(color => `<div class="thumbnail-color-segment" style="background:${color}"></div>`).join('')}
      </div>
    ` : '';

    return `
      <div class="history-item" data-status="${status}" data-name="${taskName.toLowerCase()}" data-type="${filamentType.toLowerCase()}">
        <div class="status-badge ${statusInfo.class}">${statusInfo.icon} ${statusInfo.text}</div>

        <div class="history-thumbnail" style="background: linear-gradient(135deg, ${colorsUsed[0] || '#e3f2fd'}, ${colorsUsed[1] || colorsUsed[0] || '#bbdefb'})">
          ${thumbnailIcon}
          ${colorBarHtml}
        </div>

        <div class="history-details">
          <div class="history-task-name">${taskName}</div>

          <div class="history-params">
            <span class="param-tag">层高 ${layerHeight}</span>
            <span class="param-tag">${layers} 层</span>
            <span class="param-tag">填充 ${infill}</span>
            ${weight !== '-' ? `<span class="param-tag">重量 ${weight}</span>` : ''}
          </div>

          <div class="history-meta">
            <span class="meta-item">⏱️ ${duration}</span>
            <span class="meta-item">🧵 ${filamentType}</span>
            ${colorsUsed.length > 1 ? `<span class="meta-item">🎨 ${colorsUsed.length}色</span>` : ''}
          </div>

          <div class="history-datetime">
            📅 ${timeDisplay}
          </div>
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
    return mins > 0 ? `${hours}.${(mins/6).toFixed(1).substring(2)}h` : `${hours}h`;
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
  name: '🖨️ 打印机分析卡片',
  description: '支持16色多耗材追踪 · 智能颜色识别 · 完全中文界面 · 内置历史记录'
});
