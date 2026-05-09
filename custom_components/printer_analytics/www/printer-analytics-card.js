
/**
 * Printer Analytics Card - 简化版
 * 用户直接配置所有实体 ID，不依赖自动发现
 */
class PrinterAnalyticsCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
  }

  setConfig(config) {
    this.config = config;
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

  _getAttr(entityId, attrKey) {
    const entity = this._hass?.states[entityId];
    return entity?.attributes?.[attrKey];
  }

  _getHistory() {
    const historyEntity = this._hass?.states[this.config.print_history];
    return historyEntity?.attributes?.history || [];
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
          box-shadow: var(--box-shadow, 0 2px 8px rgba(0,0,0,0.1));
          padding: 20px;
          color: var(--primary-text-color, #333);
          font-family: var(--paper-font-body1_-_font-family), sans-serif;
        }
        .section-title {
          font-size: 16px; font-weight: 600;
          margin: 20px 0 12px 0; padding-bottom: 8px;
          border-bottom: 2px solid var(--primary-color, #03a9f4);
          display: flex; align-items: center; gap: 8px;
        }
        .section-title:first-child { margin-top: 0; }
        .stats-grid {
          display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
          gap: 10px; margin-bottom: 8px;
        }
        .stat-card {
          background: var(--secondary-background-color, #f5f5f5);
          border-radius: 10px; padding: 14px 10px; text-align: center;
        }
        .stat-icon { font-size: 20px; margin-bottom: 4px; }
        .stat-value { font-size: 22px; font-weight: 700; line-height: 1.2; }
        .stat-label { font-size: 11px; color: var(--secondary-text-color, #888); margin-top: 4px; line-height: 1.3; }
        .chart-container {
          background: var(--secondary-background-color, #f5f5f5);
          border-radius: 10px; padding: 16px; margin-bottom: 12px;
        }
        .chart-title { font-size: 14px; font-weight: 600; margin-bottom: 12px; }
        .bar-chart { display: flex; align-items: flex-end; gap: 6px; height: 120px; padding-top: 20px; }
        .bar-col { flex: 1; display: flex; flex-direction: column; align-items: center; height: 100%; justify-content: flex-end; }
        .bar { width: 100%; max-width: 50px; border-radius: 4px 4px 0 0; transition: height 0.5s ease; min-height: 2px; }
        .bar-value { font-size: 11px; font-weight: 600; margin-bottom: 4px; }
        .bar-label { font-size: 10px; color: var(--secondary-text-color); margin-top: 6px; text-align: center; line-height: 1.2; }
        .heatmap-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 3px; }
        .heatmap-cell { aspect-ratio: 1; border-radius: 3px; min-height: 14px; cursor: default; position: relative; }
        .pie-container { display: flex; align-items: center; gap: 20px; flex-wrap: wrap; }
        .pie-svg { flex-shrink: 0; }
        .pie-legend { display: flex; flex-direction: column; gap: 6px; font-size: 13px; }
        .legend-item { display: flex; align-items: center; gap: 8px; }
        .legend-dot { width: 12px; height: 12px; border-radius: 50%; flex-shrink: 0; }
        .trend-container { position: relative; height: 100px; }
        .trend-svg { width: 100%; height: 100%; }
        .stats-table { width: 100%; border-collapse: collapse; font-size: 13px; }
        .stats-table th { text-align: left; padding: 8px 12px; background: var(--primary-color, #03a9f4); color: white; font-weight: 500; }
        .stats-table th:first-child { border-radius: 6px 0 0 0; }
        .stats-table th:last-child { border-radius: 0 6px 0 0; }
        .stats-table td { padding: 8px 12px; border-bottom: 1px solid var(--divider-color, #e0e0e0); }
        .stats-table tr:last-child td { border-bottom: none; }
        .stats-table tr:hover td { background: var(--secondary-background-color, #f5f5f5); }
        .no-data { text-align: center; color: var(--secondary-text-color, #888); padding: 20px; font-style: italic; }
        .error { background: #fce4ec; color: #c62828; padding: 15px; border-radius: 8px; border-left: 4px solid #c62828; }
        .debug { font-family: monospace; font-size: 11px; background: #fff3e0; padding: 10px; border-radius: 6px; white-space: pre-wrap; }
      </style>
      <div class="card" id="card-content">
        <div class="no-data">加载中...</div>
      </div>
    `;
  }

  updateData() {
    const container = this.shadowRoot.getElementById('card-content');
    if (!container) return;

    // 检查配置
    if (!this.config.print_history) {
      container.innerHTML = `
        <div class="error">
          <b>配置错误！</b><br><br>
          请在配置中设置 <code>print_history</code> 实体 ID。<br><br>
          示例配置：
          <pre style="background:#fff;padding:10px;border-radius:4px;margin-top:10px;">
type: custom:printer-analytics-card
title: P2S打印机
print_history: sensor.p2sda_yin_ji_p2sda_yin_ji_da_yin_li_shi
total_prints: sensor.p2sda_yin_ji_p2sda_yin_ji_zong_da_yin_ci_shu
success_rate: sensor.p2sda_yin_ji_p2sda_yin_ji_cheng_gong_lu
average_duration: sensor.p2sda_yin_ji_p2sda_yin_ji_ping_jun_da_yin_shi_chang
total_print_duration: sensor.p2sda_yin_ji_p2sda_yin_ji_da_yin_zong_shi_chang
total_energy: sensor.p2sda_yin_ji_p2sda_yin_ji_zong_neng_hao
material_stats_7d: sensor.p2sda_yin_ji_p2sda_yin_ji_7tian_hao_cai_tong_ji
material_stats_30d: sensor.p2sda_yin_ji_p2sda_yin_ji_30tian_hao_cai_tong_ji
duration_distribution: sensor.p2sda_yin_ji_p2sda_yin_ji_da_yin_shi_chang_fen_bu
activity_heatmap: sensor.p2sda_yin_ji_p2sda_yin_ji_da_yin_huo_dong_re_li_tu
print_status: sensor.p2sda_yin_ji_p2sda_yin_ji_da_yin_zhuang_tai
          </pre>
        </div>
      `;
      return;
    }

    const title = this.config.title || 'Printer Analytics';

    let html = '';
    html += this._renderTimeDimension(title);
    html += this._renderPeriodStats();
    html += this._renderSuccessRateTrend();
    html += this._renderDurationDistribution();
    html += this._renderActivityHeatmap();
    html += this._renderFilamentUsage();

    container.innerHTML = html || `<div class="no-data">暂无数据</div>`;
  }

  _renderTimeDimension(title) {
    const totalPrints = this.config.total_prints ? this._getState(this.config.total_prints) : '0';
    const successRate = this.config.success_rate ? this._getState(this.config.success_rate) : '0';
    const avgDuration = this.config.average_duration ? this._getState(this.config.average_duration) : '0';
    const totalDuration = this.config.total_print_duration ? this._getState(this.config.total_print_duration) : '0';
    const totalEnergy = this.config.total_energy ? this._getState(this.config.total_energy) : '0';
    const printStatus = this.config.print_status ? this._getState(this.config.print_status) : 'Idle';

    return `
      <div class="section-title">📊 ${title}</div>
      <div class="stats-grid">
        <div class="stat-card"><div class="stat-icon">🖨️</div><div class="stat-value">${totalPrints}</div><div class="stat-label">Total Prints<br>(总打印次数)</div></div>
        <div class="stat-card"><div class="stat-icon">✅</div><div class="stat-value">${successRate}%</div><div class="stat-label">Success Rate<br>(成功率)</div></div>
        <div class="stat-card"><div class="stat-icon">⏱️</div><div class="stat-value">${avgDuration}</div><div class="stat-label">Avg Duration (min)<br>(平均时长)</div></div>
        <div class="stat-card"><div class="stat-icon">🕐</div><div class="stat-value">${totalDuration}</div><div class="stat-label">Total Duration (min)<br>(总时长)</div></div>
        <div class="stat-card"><div class="stat-icon">⚡</div><div class="stat-value">${totalEnergy}</div><div class="stat-label">Energy<br>(总能耗)</div></div>
        <div class="stat-card"><div class="stat-icon">${printStatus.includes('打印中') || printStatus.includes('printing') ? '🔵' : '⚪'}</div><div class="stat-value" style="font-size:16px">${printStatus}</div><div class="stat-label">Status<br>(打印状态)</div></div>
      </div>
    `;
  }

  _renderPeriodStats() {
    const periods = [
      { key: 'material_stats_7d', label: 'Last 7 Days (最近7天)', icon: '📅' },
      { key: 'material_stats_30d', label: 'Last 30 Days (最近30天)', icon: '📆' },
    ];
    let html = '';
    for (const period of periods) {
      const entityId = this.config[period.key];
      const attrs = entityId ? this._getAttr(entityId, '') : {};
      const data = attrs || {};
      const totalPrints = data.total_prints || 0;
      const successful = data.successful || 0;
      const failed = data.failed || 0;
      const successRate = data.success_rate || 0;
      const totalWeight = data.total_weight_g || 0;
      const totalLength = data.total_length_m || 0;
      const totalEnergy = data.total_energy_kwh || 0;
      const avgDuration = data.average_duration_minutes || 0;

      html += `
        <div class="section-title">${period.icon} ${period.label}</div>
        <div class="chart-container">
          <table class="stats-table">
            <thead><tr><th>Metric (指标)</th><th>Value (值)</th></tr></thead>
            <tbody>
              <tr><td>Prints (打印次数)</td><td>${totalPrints}</td></tr>
              <tr><td>Successful (成功)</td><td>${successful}</td></tr>
              <tr><td>Failed (失败)</td><td>${failed}</td></tr>
              <tr><td>Success Rate (成功率)</td><td>${successRate}%</td></tr>
              <tr><td>Weight (耗材重量)</td><td>${totalWeight}g</td></tr>
              <tr><td>Length (耗材长度)</td><td>${totalLength}m</td></tr>
              <tr><td>Energy (能耗)</td><td>${totalEnergy} kWh</td></tr>
              <tr><td>Avg Duration (平均时长)</td><td>${avgDuration} min</td></tr>
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
      return `<div class="section-title">📈 Success Rate Trend (打印成功率趋势)</div><div class="chart-container"><div class="no-data">无历史数据</div></div>`;
    }

    const sorted = [...history].sort((a, b) => new Date(a.end_time) - new Date(b.end_time));
    let successCount = 0, totalCount = 0;
    const points = [];
    for (const item of sorted) {
      totalCount++;
      if (item.status === 'finish') successCount++;
      points.push({ rate: Math.round(successCount / totalCount * 100) });
    }

    const width = 500, height = 100, padding = 20;
    const chartW = width - padding * 2, chartH = height - padding * 2;

    const pathPoints = points.map((p, i) => {
      const x = padding + (i / Math.max(points.length - 1, 1)) * chartW;
      const y = padding + chartH - (p.rate / 100) * chartH;
      return `${x},${y}`;
    });

    const areaPath = `M${padding},${height - padding} L${pathPoints.join(' L')} L${padding + chartW},${height - padding} Z`;
    const linePath = `M${pathPoints.join(' L')}`;

    return `
      <div class="section-title">📈 Success Rate Trend (打印成功率趋势)</div>
      <div class="chart-container">
        <div class="chart-title">累计: ${successCount}/${totalCount} = ${Math.round(successCount/totalCount*100)}%</div>
        <div class="trend-container">
          <svg class="trend-svg" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none">
            <defs><linearGradient id="rateGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="var(--primary-color, #03a9f4)" stop-opacity="0.3"/>
              <stop offset="100%" stop-color="var(--primary-color, #03a9f4)" stop-opacity="0.05"/>
            </linearGradient></defs>
            <path d="${areaPath}" fill="url(#rateGrad)" />
            <path d="${linePath}" fill="none" stroke="var(--primary-color, #03a9f4)" stroke-width="2"/>
            ${points.map((p, i) => {
              const x = padding + (i / Math.max(points.length - 1, 1)) * chartW;
              const y = padding + chartH - (p.rate / 100) * chartH;
              return `<circle cx="${x}" cy="${y}" r="3" fill="var(--primary-color, #03a9f4)"/>`;
            }).join('')}
          </svg>
        </div>
      </div>
    `;
  }

  _renderDurationDistribution() {
    const entityId = this.config.duration_distribution;
    if (!entityId) return '';

    let distribution = this._getAttr(entityId, '') || {};
    if (Object.keys(distribution).length === 0) {
      try {
        const state = this._getState(entityId);
        distribution = typeof state === 'string' ? JSON.parse(state) : state || {};
      } catch {
        distribution = {};
      }
    }

    const labels = Object.keys(distribution).filter(k => !['icon', 'friendly_name', 'device_class', 'unit_of_measurement'].includes(k));
    if (labels.length === 0) {
      return `<div class="section-title">📊 Duration Distribution (打印时长分布)</div><div class="chart-container"><div class="no-data">无数据</div></div>`;
    }

    const maxVal = Math.max(...labels.map(k => distribution[k]), 1);
    const colors = ['#4CAF50', '#8BC34A', '#FFC107', '#FF9800', '#F44336', '#9C27B0'];

    let barsHtml = '';
    for (let i = 0; i < labels.length; i++) {
      const label = labels[i];
      const value = distribution[label] || 0;
      const heightPct = (value / maxVal) * 100;
      barsHtml += `<div class="bar-col"><div class="bar-value">${value}</div><div class="bar" style="height:${Math.max(heightPct, 2)}%;background:${colors[i % colors.length]}"></div><div class="bar-label">${label}</div></div>`;
    }

    return `<div class="section-title">📊 Duration Distribution (打印时长分布)</div><div class="chart-container"><div class="bar-chart">${barsHtml}</div></div>`;
  }

  _renderActivityHeatmap() {
    const entityId = this.config.activity_heatmap;
    if (!entityId) return '';

    let heatmap = this._getAttr(entityId, '') || {};
    const dateKeys = Object.keys(heatmap).filter(k => /^\d{4}-\d{2}-\d{2}$/.test(k));
    if (dateKeys.length === 0) {
      try {
        const state = this._getState(entityId);
        const parsed = typeof state === 'string' ? JSON.parse(state) : state || {};
        heatmap = parsed;
      } catch {
        heatmap = {};
      }
    }

    const sortedDates = Object.keys(heatmap).filter(k => /^\d{4}-\d{2}-\d{2}$/.test(k)).sort();
    if (sortedDates.length === 0) {
      return `<div class="section-title">🗓️ Activity Heatmap (打印活动热力图)</div><div class="chart-container"><div class="no-data">无数据</div></div>`;
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
      let color = 'var(--divider-color, #e0e0e0)';
      if (count > 0) {
        color = intensity < 0.33 ? '#c8e6c9' : intensity < 0.66 ? '#66bb6a' : '#2e7d32';
      }
      cellsHtml += `<div class="heatmap-cell" style="background:${color}" data-date="${dateKey}" data-count="${count}"></div>`;
    }

    return `<div class="section-title">🗓️ Activity Heatmap (打印活动热力图)</div><div class="chart-container"><div class="heatmap-grid">${cellsHtml}</div></div>`;
  }

  _renderFilamentUsage() {
    const history = this._getHistory();
    if (!Array.isArray(history) || history.length === 0) return '';

    const typeUsage = {};
    const colorUsage = {};
    const pieColors = ['#03a9f4', '#4caf50', '#ff9800', '#f44336', '#9c27b0', '#00bcd4', '#ffeb3b', '#795548'];

    for (const item of history) {
      if (item.status !== 'finish') continue;
      const ft = item.filament_type || 'Unknown';
      const fc = item.filament_color || 'Unknown';
      const weight = item.total_weight || 0;
      if (!typeUsage[ft]) typeUsage[ft] = 0;
      typeUsage[ft] += weight;
      if (!colorUsage[fc]) colorUsage[fc] = 0;
      colorUsage[fc] += weight;
    }

    let html = '';
    html += this._renderPieChart('🎨 Filament Type Usage (耗材类型使用量)', typeUsage, pieColors);
    html += this._renderPieChart('🎨 Filament Color Usage (耗材颜色使用量)', colorUsage, pieColors);
    return html;
  }

  _renderPieChart(title, data, colors) {
    const entries = Object.entries(data).filter(([_, v]) => v > 0);
    if (entries.length === 0) return `<div class="section-title">${title}</div><div class="chart-container"><div class="no-data">无数据</div></div>`;

    const total = entries.reduce((sum, [_, v]) => sum + v, 0);
    const size = 120, cx = size / 2, cy = size / 2, r = size / 2 - 5;
    let paths = '', startAngle = 0, legendHtml = '';

    for (let i = 0; i < entries.length; i++) {
      const [label, value] = entries[i];
      const pct = value / total;
      const endAngle = startAngle + pct * 2 * Math.PI;
      const x1 = cx + r * Math.cos(startAngle - Math.PI / 2);
      const y1 = cy + r * Math.sin(startAngle - Math.PI / 2);
      const x2 = cx + r * Math.cos(endAngle - Math.PI / 2);
      const y2 = cy + r * Math.sin(endAngle - Math.PI / 2);
      const largeArc = pct > 0.5 ? 1 : 0;
      const d = `M${cx},${cy} L${x1},${y1} A${r},${r} 0 ${largeArc},1 ${x2},${y2} Z`;
      const color = colors[i % colors.length];
      paths += `<path d="${d}" fill="${color}" stroke="var(--card-background-color, #fff)" stroke-width="2"/>`;
      legendHtml += `<div class="legend-item"><div class="legend-dot" style="background:${color}"></div><span>${label}: ${Math.round(value)}g (${Math.round(pct * 100)}%)</span></div>`;
      startAngle = endAngle;
    }

    return `<div class="section-title">${title}</div><div class="chart-container"><div class="pie-container"><svg class="pie-svg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">${paths}</svg><div class="pie-legend">${legendHtml}</div></div></div>`;
  }

  getCardSize() { return 6; }

  static getStubConfig() {
    return {
      title: 'Printer Analytics',
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
  name: 'Printer Analytics Card',
  description: 'Card for Printer Analytics integration - requires full entity configuration'
});

