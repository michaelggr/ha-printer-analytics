/**
 * Printer Analytics Card
 * 自包含的 Lovelace 卡片，无需外部依赖
 * 包含：时间维度统计、7天/30天统计、成功率趋势、时长分布、活动热力图、耗材统计
 */
class PrinterAnalyticsCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._initialized = false;
  }

  setConfig(config) {
    if (!config.entity) {
      throw new Error('Please define an entity (e.g., entity: sensor.daheinu_print_history)');
    }
    this.config = config;
    this.render();
  }

  // 从实体 ID 中提取打印机 slug
  _getSlug() {
    const entityId = this.config.entity;
    // sensor.daheinu_print_history -> daheinu
    const parts = entityId.replace('sensor.', '').split('_');
    // 移除最后的 _print_history
    parts.pop();
    parts.pop();
    return parts.join('_');
  }

  // 获取传感器状态
  _getState(suffix) {
    const slug = this._getSlug();
    const entityId = `sensor.${slug}_${suffix}`;
    const state = this._hass?.states[entityId];
    return state;
  }

  // 获取传感器值
  _getValue(suffix) {
    const state = this._getState(suffix);
    return state?.state || '0';
  }

  // 获取传感器属性
  _getAttr(suffix, attr) {
    const state = this._getState(suffix);
    return state?.attributes?.[attr];
  }

  render() {
    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
        }
        .card {
          background: var(--card-background-color, #fff);
          border-radius: var(--border-radius, 12px);
          box-shadow: var(--box-shadow, 0 2px 8px rgba(0,0,0,0.1));
          padding: 20px;
          color: var(--primary-text-color, #333);
          font-family: var(--paper-font-body1_-_font-family), sans-serif;
        }
        .section-title {
          font-size: 16px;
          font-weight: 600;
          margin: 20px 0 12px 0;
          padding-bottom: 8px;
          border-bottom: 2px solid var(--primary-color, #03a9f4);
          display: flex;
          align-items: center;
          gap: 8px;
        }
        .section-title:first-child {
          margin-top: 0;
        }
        .stats-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
          gap: 10px;
          margin-bottom: 8px;
        }
        .stat-card {
          background: var(--secondary-background-color, #f5f5f5);
          border-radius: 10px;
          padding: 14px 10px;
          text-align: center;
          transition: transform 0.15s;
        }
        .stat-card:hover {
          transform: translateY(-2px);
        }
        .stat-icon {
          font-size: 20px;
          margin-bottom: 4px;
        }
        .stat-value {
          font-size: 22px;
          font-weight: 700;
          color: var(--primary-text-color, #333);
          line-height: 1.2;
        }
        .stat-label {
          font-size: 11px;
          color: var(--secondary-text-color, #888);
          margin-top: 4px;
          line-height: 1.3;
        }
        .chart-container {
          background: var(--secondary-background-color, #f5f5f5);
          border-radius: 10px;
          padding: 16px;
          margin-bottom: 12px;
        }
        .chart-title {
          font-size: 14px;
          font-weight: 600;
          margin-bottom: 12px;
        }
        /* 柱状图 */
        .bar-chart {
          display: flex;
          align-items: flex-end;
          gap: 6px;
          height: 120px;
          padding-top: 20px;
        }
        .bar-col {
          flex: 1;
          display: flex;
          flex-direction: column;
          align-items: center;
          height: 100%;
          justify-content: flex-end;
        }
        .bar {
          width: 100%;
          max-width: 50px;
          border-radius: 4px 4px 0 0;
          background: var(--primary-color, #03a9f4);
          transition: height 0.5s ease;
          min-height: 2px;
          position: relative;
        }
        .bar-value {
          font-size: 11px;
          font-weight: 600;
          margin-bottom: 4px;
          color: var(--primary-text-color);
        }
        .bar-label {
          font-size: 10px;
          color: var(--secondary-text-color);
          margin-top: 6px;
          text-align: center;
          line-height: 1.2;
        }
        /* 热力图 */
        .heatmap-grid {
          display: grid;
          grid-template-columns: repeat(7, 1fr);
          gap: 3px;
        }
        .heatmap-cell {
          aspect-ratio: 1;
          border-radius: 3px;
          background: var(--divider-color, #e0e0e0);
          position: relative;
          cursor: default;
          min-height: 14px;
        }
        .heatmap-cell[data-count]:hover::after {
          content: attr(data-date) ": " attr(data-count);
          position: absolute;
          bottom: 110%;
          left: 50%;
          transform: translateX(-50%);
          background: var(--card-background-color, #333);
          color: var(--primary-text-color, #fff);
          padding: 4px 8px;
          border-radius: 4px;
          font-size: 11px;
          white-space: nowrap;
          z-index: 10;
          box-shadow: 0 2px 6px rgba(0,0,0,0.2);
        }
        /* 饼图 */
        .pie-container {
          display: flex;
          align-items: center;
          gap: 20px;
          flex-wrap: wrap;
        }
        .pie-svg {
          flex-shrink: 0;
        }
        .pie-legend {
          display: flex;
          flex-direction: column;
          gap: 6px;
          font-size: 13px;
        }
        .legend-item {
          display: flex;
          align-items: center;
          gap: 8px;
        }
        .legend-dot {
          width: 12px;
          height: 12px;
          border-radius: 50%;
          flex-shrink: 0;
        }
        /* 趋势线 */
        .trend-container {
          position: relative;
          height: 100px;
        }
        .trend-svg {
          width: 100%;
          height: 100%;
        }
        /* 表格 */
        .stats-table {
          width: 100%;
          border-collapse: collapse;
          font-size: 13px;
        }
        .stats-table th {
          text-align: left;
          padding: 8px 12px;
          background: var(--primary-color, #03a9f4);
          color: white;
          font-weight: 500;
        }
        .stats-table th:first-child {
          border-radius: 6px 0 0 0;
        }
        .stats-table th:last-child {
          border-radius: 0 6px 0 0;
        }
        .stats-table td {
          padding: 8px 12px;
          border-bottom: 1px solid var(--divider-color, #e0e0e0);
        }
        .stats-table tr:last-child td {
          border-bottom: none;
        }
        .stats-table tr:hover td {
          background: var(--secondary-background-color, #f5f5f5);
        }
        .no-data {
          text-align: center;
          color: var(--secondary-text-color, #888);
          padding: 20px;
          font-style: italic;
        }
      </style>
      <div class="card" id="card-content">
        <div class="no-data">Loading...</div>
      </div>
    `;
  }

  set hass(hass) {
    this._hass = hass;
    if (hass && this.config) {
      this.updateData();
    }
  }

  updateData() {
    const card = this.shadowRoot.getElementById('card-content');
    if (!card) return;

    const title = this.config.title || 'Printer Analytics (打印机分析)';
    let html = '';

    // === 1. 时间维度统计 ===
    html += this._renderTimeDimensionStats(title);

    // === 2. 7天/30天统计表格 ===
    html += this._renderPeriodStats();

    // === 3. 图表 ===
    html += this._renderSuccessRateTrend();
    html += this._renderDurationDistribution();
    html += this._renderActivityHeatmap();
    html += this._renderFilamentUsage();

    card.innerHTML = html || '<div class="no-data">No data available</div>';
  }

  _renderTimeDimensionStats(title) {
    const totalPrints = this._getValue('total_prints');
    const successRate = this._getValue('success_rate');
    const avgDuration = this._getValue('average_duration');
    const totalDuration = this._getValue('total_online_duration');
    const totalEnergy = this._getValue('total_energy');
    const printStatus = this._getValue('print_status');

    return `
      <div class="section-title">📊 ${title}</div>
      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-icon">🖨️</div>
          <div class="stat-value">${totalPrints}</div>
          <div class="stat-label">Total Prints<br/>(总打印次数)</div>
        </div>
        <div class="stat-card">
          <div class="stat-icon">✅</div>
          <div class="stat-value">${successRate}%</div>
          <div class="stat-label">Success Rate<br/>(成功率)</div>
        </div>
        <div class="stat-card">
          <div class="stat-icon">⏱️</div>
          <div class="stat-value">${avgDuration}</div>
          <div class="stat-label">Avg Duration (min)<br/>(平均时长)</div>
        </div>
        <div class="stat-card">
          <div class="stat-icon">🕐</div>
          <div class="stat-value">${totalDuration}</div>
          <div class="stat-label">Total Duration (h)<br/>(总时长)</div>
        </div>
        <div class="stat-card">
          <div class="stat-icon">⚡</div>
          <div class="stat-value">${totalEnergy}</div>
          <div class="stat-label">Energy (kWh)<br/>(总能耗)</div>
        </div>
        <div class="stat-card">
          <div class="stat-icon">${printStatus === '打印中' ? '🔵' : '⚪'}</div>
          <div class="stat-value" style="font-size:16px">${printStatus || 'Idle'}</div>
          <div class="stat-label">Status<br/>(打印状态)</div>
        </div>
      </div>
    `;
  }

  _renderPeriodStats() {
    const periods = [
      { key: '7d', label: 'Last 7 Days (最近7天)', icon: '📅' },
      { key: '30d', label: 'Last 30 Days (最近30天)', icon: '📆' },
    ];

    let html = '';
    for (const period of periods) {
      const stats = this._getAttr(`material_stats_${period.key}`, '') || {};
      if (typeof stats === 'string') continue;

      html += `
        <div class="section-title">${period.icon} ${period.label}</div>
        <div class="chart-container">
          <table class="stats-table">
            <thead>
              <tr>
                <th>Metric (指标)</th>
                <th>Value (值)</th>
              </tr>
            </thead>
            <tbody>
              <tr><td>Prints (打印次数)</td><td>${stats.total_prints || 0}</td></tr>
              <tr><td>Successful (成功)</td><td>${stats.successful || 0}</td></tr>
              <tr><td>Failed (失败)</td><td>${stats.failed || 0}</td></tr>
              <tr><td>Success Rate (成功率)</td><td>${stats.success_rate || 0}%</td></tr>
              <tr><td>Weight (耗材重量)</td><td>${stats.total_weight_g || 0}g</td></tr>
              <tr><td>Length (耗材长度)</td><td>${stats.total_length_m || 0}m</td></tr>
              <tr><td>Energy (能耗)</td><td>${stats.total_energy_kwh || 0} kWh</td></tr>
              <tr><td>Avg Duration (平均时长)</td><td>${stats.average_duration_minutes || 0} min</td></tr>
            </tbody>
          </table>
        </div>
      `;
    }
    return html;
  }

  _renderSuccessRateTrend() {
    const history = this._getAttr('print_history', 'history') || [];
    if (!Array.isArray(history) || history.length === 0) {
      return `
        <div class="section-title">📈 Success Rate Trend (打印成功率趋势)</div>
        <div class="chart-container"><div class="no-data">No history data</div></div>
      `;
    }

    // 按日期聚合成功率
    const dailyData = {};
    let successCount = 0;
    let totalCount = 0;
    const sorted = [...history].sort((a, b) => new Date(a.end_time) - new Date(b.end_time));

    for (const item of sorted) {
      if (!item.end_time) continue;
      totalCount++;
      if (item.status === 'finish') successCount++;
      const date = item.end_time.substring(0, 10);
      if (!dailyData[date]) {
        dailyData[date] = { success: 0, total: 0 };
      }
      dailyData[date].total++;
      if (item.status === 'finish') dailyData[date].success++;
    }

    const dates = Object.keys(dailyData).sort();
    if (dates.length === 0) {
      return `
        <div class="section-title">📈 Success Rate Trend (打印成功率趋势)</div>
        <div class="chart-container"><div class="no-data">No data</div></div>
      `;
    }

    // 生成 SVG 折线图
    const points = [];
    let cumSuccess = 0, cumTotal = 0;
    for (const date of dates) {
      cumSuccess += dailyData[date].success;
      cumTotal += dailyData[date].total;
      const rate = Math.round(cumSuccess / cumTotal * 100);
      points.push({ date, rate });
    }

    const width = 500;
    const height = 80;
    const padding = 10;
    const chartW = width - padding * 2;
    const chartH = height - padding * 2;

    const pathPoints = points.map((p, i) => {
      const x = padding + (i / Math.max(points.length - 1, 1)) * chartW;
      const y = padding + chartH - (p.rate / 100) * chartH;
      return `${x},${y}`;
    });

    const areaPath = `M${padding},${height - padding} ` +
      pathPoints.map((p, i) => `L${p}`).join(' ') +
      ` L${padding + chartW},${height - padding} Z`;
    const linePath = `M${pathPoints.join(' L')}`;

    return `
      <div class="section-title">📈 Success Rate Trend (打印成功率趋势)</div>
      <div class="chart-container">
        <div class="chart-title">Cumulative: ${successCount}/${totalCount} = ${Math.round(successCount/totalCount*100)}%</div>
        <div class="trend-container">
          <svg class="trend-svg" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none">
            <defs>
              <linearGradient id="rateGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stop-color="var(--primary-color, #03a9f4)" stop-opacity="0.3"/>
                <stop offset="100%" stop-color="var(--primary-color, #03a9f4)" stop-opacity="0.05"/>
              </linearGradient>
            </defs>
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
    const dist = this._getAttr('duration_distribution', '') || {};
    if (typeof dist === 'string' || Object.keys(dist).length === 0) {
      return `
        <div class="section-title">📊 Duration Distribution (打印时长分布)</div>
        <div class="chart-container"><div class="no-data">No data</div></div>
      `;
    }

    const labels = Object.keys(dist);
    const values = Object.values(dist);
    const maxVal = Math.max(...values, 1);

    const colors = ['#4CAF50', '#8BC34A', '#FFC107', '#FF9800', '#F44336', '#9C27B0'];

    let barsHtml = '';
    for (let i = 0; i < labels.length; i++) {
      const heightPct = (values[i] / maxVal) * 100;
      barsHtml += `
        <div class="bar-col">
          <div class="bar-value">${values[i]}</div>
          <div class="bar" style="height:${Math.max(heightPct, 2)}%;background:${colors[i % colors.length]}"></div>
          <div class="bar-label">${labels[i]}</div>
        </div>
      `;
    }

    return `
      <div class="section-title">📊 Duration Distribution (打印时长分布)</div>
      <div class="chart-container">
        <div class="bar-chart">${barsHtml}</div>
      </div>
    `;
  }

  _renderActivityHeatmap() {
    const heatmap = this._getAttr('activity_heatmap', '') || {};
    if (typeof heatmap === 'string' || Object.keys(heatmap).length === 0) {
      return `
        <div class="section-title">🗓️ Activity Heatmap (打印活动热力图)</div>
        <div class="chart-container"><div class="no-data">No data</div></div>
      `;
    }

    const dates = Object.keys(heatmap).sort();
    const maxCount = Math.max(...Object.values(heatmap), 1);

    // 取最近 35 天（5 周）
    const recentDates = dates.slice(-35);
    const startDate = recentDates.length > 0 ? new Date(recentDates[0]) : new Date();

    let cellsHtml = '';
    for (let i = 0; i < 35; i++) {
      const d = new Date(startDate);
      d.setDate(d.getDate() + i);
      const dateKey = d.toISOString().substring(0, 10);
      const count = heatmap[dateKey] || 0;
      const intensity = count > 0 ? Math.min(count / maxCount, 1) : 0;

      // 颜色从浅到深
      let color;
      if (count === 0) {
        color = 'var(--divider-color, #e0e0e0)';
      } else if (intensity < 0.33) {
        color = '#c8e6c9';
      } else if (intensity < 0.66) {
        color = '#66bb6a';
      } else {
        color = '#2e7d32';
      }

      cellsHtml += `<div class="heatmap-cell" style="background:${color}" data-date="${dateKey}" data-count="${count}"></div>`;
    }

    return `
      <div class="section-title">🗓️ Activity Heatmap (打印活动热力图)</div>
      <div class="chart-container">
        <div class="heatmap-grid">${cellsHtml}</div>
      </div>
    `;
  }

  _renderFilamentUsage() {
    const history = this._getAttr('print_history', 'history') || [];
    if (!Array.isArray(history) || history.length === 0) return '';

    // 按耗材类型聚合
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

    // 耗材类型饼图
    html += this._renderPieChart(
      '🎨 Filament Type Usage (耗材类型使用量)',
      typeUsage,
      pieColors
    );

    // 耗材颜色饼图
    html += this._renderPieChart(
      '🎨 Filament Color Usage (耗材颜色使用量)',
      colorUsage,
      pieColors
    );

    return html;
  }

  _renderPieChart(title, data, colors) {
    const entries = Object.entries(data).filter(([_, v]) => v > 0);
    if (entries.length === 0) {
      return `
        <div class="section-title">${title}</div>
        <div class="chart-container"><div class="no-data">No data</div></div>
      `;
    }

    const total = entries.reduce((sum, [_, v]) => sum + v, 0);
    const size = 120;
    const cx = size / 2;
    const cy = size / 2;
    const r = size / 2 - 5;

    let paths = '';
    let startAngle = 0;
    let legendHtml = '';

    for (let i = 0; i < entries.length; i++) {
      const [label, value] = entries[i];
      const pct = value / total;
      const endAngle = startAngle + pct * 2 * Math.PI;

      // SVG arc
      const x1 = cx + r * Math.cos(startAngle - Math.PI / 2);
      const y1 = cy + r * Math.sin(startAngle - Math.PI / 2);
      const x2 = cx + r * Math.cos(endAngle - Math.PI / 2);
      const y2 = cy + r * Math.sin(endAngle - Math.PI / 2);
      const largeArc = pct > 0.5 ? 1 : 0;

      const d = `M${cx},${cy} L${x1},${y1} A${r},${r} 0 ${largeArc},1 ${x2},${y2} Z`;
      const color = colors[i % colors.length];
      paths += `<path d="${d}" fill="${color}" stroke="var(--card-background-color, #fff)" stroke-width="2"/>`;

      legendHtml += `
        <div class="legend-item">
          <div class="legend-dot" style="background:${color}"></div>
          <span>${label}: ${Math.round(value)}g (${Math.round(pct * 100)}%)</span>
        </div>
      `;

      startAngle = endAngle;
    }

    return `
      <div class="section-title">${title}</div>
      <div class="chart-container">
        <div class="pie-container">
          <svg class="pie-svg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
            ${paths}
          </svg>
          <div class="pie-legend">${legendHtml}</div>
        </div>
      </div>
    `;
  }

  getCardSize() {
    return 6;
  }

  static getStubConfig() {
    return {
      entity: 'sensor.daheinu_print_history',
      title: 'Printer Analytics',
    };
  }
}

// 注册卡片
customElements.define('printer-analytics-card', PrinterAnalyticsCard);

// 注册到 Lovelace 卡片选择器
window.customCards = window.customCards || [];
window.customCards.push({
  type: 'printer-analytics-card',
  name: 'Printer Analytics Card',
  description: 'Card for Printer Analytics integration (打印机分析卡片)',
  documentationURL: 'https://github.com/user/printer_analytics',
});
