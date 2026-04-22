
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
    if (hass &amp;&amp; this.config) {
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
      &lt;style&gt;
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
      &lt;/style&gt;
      &lt;div class="card" id="card-content"&gt;
        &lt;div class="no-data"&gt;加载中...&lt;/div&gt;
      &lt;/div&gt;
    `;
  }

  updateData() {
    const container = this.shadowRoot.getElementById('card-content');
    if (!container) return;

    // 检查配置
    if (!this.config.print_history) {
      container.innerHTML = `
        &lt;div class="error"&gt;
          &lt;b&gt;配置错误！&lt;/b&gt;&lt;br&gt;&lt;br&gt;
          请在配置中设置 &lt;code&gt;print_history&lt;/code&gt; 实体 ID。&lt;br&gt;&lt;br&gt;
          示例配置：
          &lt;pre style="background:#fff;padding:10px;border-radius:4px;margin-top:10px;"&gt;
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
          &lt;/pre&gt;
        &lt;/div&gt;
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

    container.innerHTML = html || `&lt;div class="no-data"&gt;暂无数据&lt;/div&gt;`;
  }

  _renderTimeDimension(title) {
    const totalPrints = this.config.total_prints ? this._getState(this.config.total_prints) : '0';
    const successRate = this.config.success_rate ? this._getState(this.config.success_rate) : '0';
    const avgDuration = this.config.average_duration ? this._getState(this.config.average_duration) : '0';
    const totalDuration = this.config.total_print_duration ? this._getState(this.config.total_print_duration) : '0';
    const totalEnergy = this.config.total_energy ? this._getState(this.config.total_energy) : '0';
    const printStatus = this.config.print_status ? this._getState(this.config.print_status) : 'Idle';

    return `
      &lt;div class="section-title"&gt;📊 ${title}&lt;/div&gt;
      &lt;div class="stats-grid"&gt;
        &lt;div class="stat-card"&gt;&lt;div class="stat-icon"&gt;🖨️&lt;/div&gt;&lt;div class="stat-value"&gt;${totalPrints}&lt;/div&gt;&lt;div class="stat-label"&gt;Total Prints&lt;br&gt;(总打印次数)&lt;/div&gt;&lt;/div&gt;
        &lt;div class="stat-card"&gt;&lt;div class="stat-icon"&gt;✅&lt;/div&gt;&lt;div class="stat-value"&gt;${successRate}%&lt;/div&gt;&lt;div class="stat-label"&gt;Success Rate&lt;br&gt;(成功率)&lt;/div&gt;&lt;/div&gt;
        &lt;div class="stat-card"&gt;&lt;div class="stat-icon"&gt;⏱️&lt;/div&gt;&lt;div class="stat-value"&gt;${avgDuration}&lt;/div&gt;&lt;div class="stat-label"&gt;Avg Duration (min)&lt;br&gt;(平均时长)&lt;/div&gt;&lt;/div&gt;
        &lt;div class="stat-card"&gt;&lt;div class="stat-icon"&gt;🕐&lt;/div&gt;&lt;div class="stat-value"&gt;${totalDuration}&lt;/div&gt;&lt;div class="stat-label"&gt;Total Duration (min)&lt;br&gt;(总时长)&lt;/div&gt;&lt;/div&gt;
        &lt;div class="stat-card"&gt;&lt;div class="stat-icon"&gt;⚡&lt;/div&gt;&lt;div class="stat-value"&gt;${totalEnergy}&lt;/div&gt;&lt;div class="stat-label"&gt;Energy&lt;br&gt;(总能耗)&lt;/div&gt;&lt;/div&gt;
        &lt;div class="stat-card"&gt;&lt;div class="stat-icon"&gt;${printStatus.includes('打印中') || printStatus.includes('printing') ? '🔵' : '⚪'}&lt;/div&gt;&lt;div class="stat-value" style="font-size:16px"&gt;${printStatus}&lt;/div&gt;&lt;div class="stat-label"&gt;Status&lt;br&gt;(打印状态)&lt;/div&gt;&lt;/div&gt;
      &lt;/div&gt;
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
        &lt;div class="section-title"&gt;${period.icon} ${period.label}&lt;/div&gt;
        &lt;div class="chart-container"&gt;
          &lt;table class="stats-table"&gt;
            &lt;thead&gt;&lt;tr&gt;&lt;th&gt;Metric (指标)&lt;/th&gt;&lt;th&gt;Value (值)&lt;/th&gt;&lt;/tr&gt;&lt;/thead&gt;
            &lt;tbody&gt;
              &lt;tr&gt;&lt;td&gt;Prints (打印次数)&lt;/td&gt;&lt;td&gt;${totalPrints}&lt;/td&gt;&lt;/tr&gt;
              &lt;tr&gt;&lt;td&gt;Successful (成功)&lt;/td&gt;&lt;td&gt;${successful}&lt;/td&gt;&lt;/tr&gt;
              &lt;tr&gt;&lt;td&gt;Failed (失败)&lt;/td&gt;&lt;td&gt;${failed}&lt;/td&gt;&lt;/tr&gt;
              &lt;tr&gt;&lt;td&gt;Success Rate (成功率)&lt;/td&gt;&lt;td&gt;${successRate}%&lt;/td&gt;&lt;/tr&gt;
              &lt;tr&gt;&lt;td&gt;Weight (耗材重量)&lt;/td&gt;&lt;td&gt;${totalWeight}g&lt;/td&gt;&lt;/tr&gt;
              &lt;tr&gt;&lt;td&gt;Length (耗材长度)&lt;/td&gt;&lt;td&gt;${totalLength}m&lt;/td&gt;&lt;/tr&gt;
              &lt;tr&gt;&lt;td&gt;Energy (能耗)&lt;/td&gt;&lt;td&gt;${totalEnergy} kWh&lt;/td&gt;&lt;/tr&gt;
              &lt;tr&gt;&lt;td&gt;Avg Duration (平均时长)&lt;/td&gt;&lt;td&gt;${avgDuration} min&lt;/td&gt;&lt;/tr&gt;
            &lt;/tbody&gt;
          &lt;/table&gt;
        &lt;/div&gt;
      `;
    }
    return html;
  }

  _renderSuccessRateTrend() {
    const history = this._getHistory();
    if (!Array.isArray(history) || history.length === 0) {
      return `&lt;div class="section-title"&gt;📈 Success Rate Trend (打印成功率趋势)&lt;/div&gt;&lt;div class="chart-container"&gt;&lt;div class="no-data"&gt;无历史数据&lt;/div&gt;&lt;/div&gt;`;
    }

    const sorted = [...history].sort((a, b) =&gt; new Date(a.end_time) - new Date(b.end_time));
    let successCount = 0, totalCount = 0;
    const points = [];
    for (const item of sorted) {
      totalCount++;
      if (item.status === 'finish') successCount++;
      points.push({ rate: Math.round(successCount / totalCount * 100) });
    }

    const width = 500, height = 100, padding = 20;
    const chartW = width - padding * 2, chartH = height - padding * 2;

    const pathPoints = points.map((p, i) =&gt; {
      const x = padding + (i / Math.max(points.length - 1, 1)) * chartW;
      const y = padding + chartH - (p.rate / 100) * chartH;
      return `${x},${y}`;
    });

    const areaPath = `M${padding},${height - padding} L${pathPoints.join(' L')} L${padding + chartW},${height - padding} Z`;
    const linePath = `M${pathPoints.join(' L')}`;

    return `
      &lt;div class="section-title"&gt;📈 Success Rate Trend (打印成功率趋势)&lt;/div&gt;
      &lt;div class="chart-container"&gt;
        &lt;div class="chart-title"&gt;累计: ${successCount}/${totalCount} = ${Math.round(successCount/totalCount*100)}%&lt;/div&gt;
        &lt;div class="trend-container"&gt;
          &lt;svg class="trend-svg" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none"&gt;
            &lt;defs&gt;&lt;linearGradient id="rateGrad" x1="0" y1="0" x2="0" y2="1"&gt;
              &lt;stop offset="0%" stop-color="var(--primary-color, #03a9f4)" stop-opacity="0.3"/&gt;
              &lt;stop offset="100%" stop-color="var(--primary-color, #03a9f4)" stop-opacity="0.05"/&gt;
            &lt;/linearGradient&gt;&lt;/defs&gt;
            &lt;path d="${areaPath}" fill="url(#rateGrad)" /&gt;
            &lt;path d="${linePath}" fill="none" stroke="var(--primary-color, #03a9f4)" stroke-width="2"/&gt;
            ${points.map((p, i) =&gt; {
              const x = padding + (i / Math.max(points.length - 1, 1)) * chartW;
              const y = padding + chartH - (p.rate / 100) * chartH;
              return `&lt;circle cx="${x}" cy="${y}" r="3" fill="var(--primary-color, #03a9f4)"/&gt;`;
            }).join('')}
          &lt;/svg&gt;
        &lt;/div&gt;
      &lt;/div&gt;
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

    const labels = Object.keys(distribution).filter(k =&gt; !['icon', 'friendly_name', 'device_class', 'unit_of_measurement'].includes(k));
    if (labels.length === 0) {
      return `&lt;div class="section-title"&gt;📊 Duration Distribution (打印时长分布)&lt;/div&gt;&lt;div class="chart-container"&gt;&lt;div class="no-data"&gt;无数据&lt;/div&gt;&lt;/div&gt;`;
    }

    const maxVal = Math.max(...labels.map(k =&gt; distribution[k]), 1);
    const colors = ['#4CAF50', '#8BC34A', '#FFC107', '#FF9800', '#F44336', '#9C27B0'];

    let barsHtml = '';
    for (let i = 0; i &lt; labels.length; i++) {
      const label = labels[i];
      const value = distribution[label] || 0;
      const heightPct = (value / maxVal) * 100;
      barsHtml += `&lt;div class="bar-col"&gt;&lt;div class="bar-value"&gt;${value}&lt;/div&gt;&lt;div class="bar" style="height:${Math.max(heightPct, 2)}%;background:${colors[i % colors.length]}"&gt;&lt;/div&gt;&lt;div class="bar-label"&gt;${label}&lt;/div&gt;&lt;/div&gt;`;
    }

    return `&lt;div class="section-title"&gt;📊 Duration Distribution (打印时长分布)&lt;/div&gt;&lt;div class="chart-container"&gt;&lt;div class="bar-chart"&gt;${barsHtml}&lt;/div&gt;&lt;/div&gt;`;
  }

  _renderActivityHeatmap() {
    const entityId = this.config.activity_heatmap;
    if (!entityId) return '';

    let heatmap = this._getAttr(entityId, '') || {};
    const dateKeys = Object.keys(heatmap).filter(k =&gt; /^\d{4}-\d{2}-\d{2}$/.test(k));
    if (dateKeys.length === 0) {
      try {
        const state = this._getState(entityId);
        const parsed = typeof state === 'string' ? JSON.parse(state) : state || {};
        heatmap = parsed;
      } catch {
        heatmap = {};
      }
    }

    const sortedDates = Object.keys(heatmap).filter(k =&gt; /^\d{4}-\d{2}-\d{2}$/.test(k)).sort();
    if (sortedDates.length === 0) {
      return `&lt;div class="section-title"&gt;🗓️ Activity Heatmap (打印活动热力图)&lt;/div&gt;&lt;div class="chart-container"&gt;&lt;div class="no-data"&gt;无数据&lt;/div&gt;&lt;/div&gt;`;
    }

    const maxCount = Math.max(...sortedDates.map(k =&gt; heatmap[k]), 1);
    const recentDates = sortedDates.slice(-35);
    const startDate = recentDates.length &gt; 0 ? new Date(recentDates[0]) : new Date();

    const allDates = [];
    for (let i = 0; i &lt; 35; i++) {
      const d = new Date(startDate);
      d.setDate(d.getDate() + i);
      allDates.push(d.toISOString().substring(0, 10));
    }

    let cellsHtml = '';
    for (const dateKey of allDates) {
      const count = heatmap[dateKey] || 0;
      const intensity = count &gt; 0 ? Math.min(count / maxCount, 1) : 0;
      let color = 'var(--divider-color, #e0e0e0)';
      if (count &gt; 0) {
        color = intensity &lt; 0.33 ? '#c8e6c9' : intensity &lt; 0.66 ? '#66bb6a' : '#2e7d32';
      }
      cellsHtml += `&lt;div class="heatmap-cell" style="background:${color}" data-date="${dateKey}" data-count="${count}"&gt;&lt;/div&gt;`;
    }

    return `&lt;div class="section-title"&gt;🗓️ Activity Heatmap (打印活动热力图)&lt;/div&gt;&lt;div class="chart-container"&gt;&lt;div class="heatmap-grid"&gt;${cellsHtml}&lt;/div&gt;&lt;/div&gt;`;
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
    const entries = Object.entries(data).filter(([_, v]) =&gt; v &gt; 0);
    if (entries.length === 0) return `&lt;div class="section-title"&gt;${title}&lt;/div&gt;&lt;div class="chart-container"&gt;&lt;div class="no-data"&gt;无数据&lt;/div&gt;&lt;/div&gt;`;

    const total = entries.reduce((sum, [_, v]) =&gt; sum + v, 0);
    const size = 120, cx = size / 2, cy = size / 2, r = size / 2 - 5;
    let paths = '', startAngle = 0, legendHtml = '';

    for (let i = 0; i &lt; entries.length; i++) {
      const [label, value] = entries[i];
      const pct = value / total;
      const endAngle = startAngle + pct * 2 * Math.PI;
      const x1 = cx + r * Math.cos(startAngle - Math.PI / 2);
      const y1 = cy + r * Math.sin(startAngle - Math.PI / 2);
      const x2 = cx + r * Math.cos(endAngle - Math.PI / 2);
      const y2 = cy + r * Math.sin(endAngle - Math.PI / 2);
      const largeArc = pct &gt; 0.5 ? 1 : 0;
      const d = `M${cx},${cy} L${x1},${y1} A${r},${r} 0 ${largeArc},1 ${x2},${y2} Z`;
      const color = colors[i % colors.length];
      paths += `&lt;path d="${d}" fill="${color}" stroke="var(--card-background-color, #fff)" stroke-width="2"/&gt;`;
      legendHtml += `&lt;div class="legend-item"&gt;&lt;div class="legend-dot" style="background:${color}"&gt;&lt;/div&gt;&lt;span&gt;${label}: ${Math.round(value)}g (${Math.round(pct * 100)}%)&lt;/span&gt;&lt;/div&gt;`;
      startAngle = endAngle;
    }

    return `&lt;div class="section-title"&gt;${title}&lt;/div&gt;&lt;div class="chart-container"&gt;&lt;div class="pie-container"&gt;&lt;svg class="pie-svg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}"&gt;${paths}&lt;/svg&gt;&lt;div class="pie-legend"&gt;${legendHtml}&lt;/div&gt;&lt;/div&gt;&lt;/div&gt;`;
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

