
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
    this._entityCache = {};
  }

  setConfig(config) {
    if (!config.entity) {
      throw new Error('Please define an entity (e.g., entity: sensor.xxx_print_history)');
    }
    this.config = config;
    this.render();
  }

  // 通过 print_history 实体找到同设备的所有 printer_analytics 实体
  _discoverEntities() {
    const historyEntity = this._hass?.states[this.config.entity];
    if (!historyEntity) return {};

    console.log('Printer Analytics Card: Discovering entities...');

    // 方案：通过实体 ID 前缀匹配
    const prefix = this._extractPrefix(this.config.entity);
    console.log('Printer Analytics Card: Using prefix:', prefix);
    
    const entities = {};
    for (const [entityId, state] of Object.entries(this._hass.states)) {
      if (entityId.startsWith(prefix) &amp;&amp; entityId.startsWith('sensor.')) {
        const name = state.attributes?.friendly_name || '';
        const key = this._nameToKey(name);
        if (key) {
          entities[key] = entityId;
          console.log('Printer Analytics Card: Mapped', key, '-&gt;', entityId);
        }
      }
    }
    
    // 确保 print_history 总是被设置
    if (!entities.print_history) {
      entities.print_history = this.config.entity;
    }
    
    console.log('Printer Analytics Card: Found entities:', entities);
    return entities;
  }

  // 从 print_history 实体 ID 提取前缀
  _extractPrefix(entityId) {
    // sensor.p2sda_yin_ji_p2sda_yin_ji_da_yin_li_shi
    // -&gt; sensor.p2sda_yin_ji_p2sda_yin_ji_
    const name = entityId.replace('sensor.', '');
    // 移除最后的 _da_yin_li_shi (打印历史) 或 _print_history
    const suffixes = ['_da_yin_li_shi', '_print_history', '_da_yin_zhuang_tai'];
    for (const s of suffixes) {
      if (name.endsWith(s)) {
        return 'sensor.' + name.substring(0, name.length - s.length) + '_';
      }
    }
    // 兜底：移除最后两段
    const parts = name.split('_');
    if (parts.length &gt; 2) {
      return 'sensor.' + parts.slice(0, -2).join('_') + '_';
    }
    return entityId.substring(0, entityId.lastIndexOf('_')) + '_';
  }

  // 将中文/英文实体名映射到 key
  _nameToKey(name) {
    const map = {
      '总打印次数': 'total_prints',
      '成功率': 'success_rate',
      '平均打印时长': 'average_duration',
      '总打印时长': 'total_online_duration',
      '打印总时长': 'total_print_duration',
      '总能耗': 'total_energy',
      '终身耗材统计': 'material_stats_lifetime',
      '7天耗材统计': 'material_stats_7d',
      '30天耗材统计': 'material_stats_30d',
      '打印时长分布': 'duration_distribution',
      '打印活动热力图': 'activity_heatmap',
      '打印历史': 'print_history',
      '打印状态': 'print_status',
      'Total Prints': 'total_prints',
      'Success Rate': 'success_rate',
      'Average Duration': 'average_duration',
      'Total Online Duration': 'total_online_duration',
      'Total Energy': 'total_energy',
      'Material Stats Lifetime': 'material_stats_lifetime',
      'Material Stats 7d': 'material_stats_7d',
      'Material Stats 30d': 'material_stats_30d',
      'Duration Distribution': 'duration_distribution',
      'Activity Heatmap': 'activity_heatmap',
      'Print History': 'print_history',
      'Print Status': 'print_status',
    };
    // 查找匹配的 key
    for (const [keyword, key] of Object.entries(map)) {
      if (name.includes(keyword)) return key;
    }
    return null;
  }

  // 获取传感器值
  _getValue(key) {
    if (!this._entityCache[key]) return '0';
    const state = this._hass?.states[this._entityCache[key]];
    return state?.state || '0';
  }

  // 获取传感器属性
  _getAttr(key, attr) {
    if (!this._entityCache[key]) return null;
    const state = this._hass?.states[this._entityCache[key]];
    return state?.attributes?.[attr];
  }

  // 获取完整的实体对象
  _getEntity(key) {
    if (!this._entityCache[key]) return null;
    return this._hass?.states[this._entityCache[key]];
  }

  render() {
    this.shadowRoot.innerHTML = `
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
          transition: transform 0.15s;
        }
        .stat-card:hover { transform: translateY(-2px); }
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
        .heatmap-cell[data-count]:hover::after {
          content: attr(data-date) ": " attr(data-count);
          position: absolute; bottom: 110%; left: 50%; transform: translateX(-50%);
          background: var(--card-background-color, #333); color: var(--primary-text-color, #fff);
          padding: 4px 8px; border-radius: 4px; font-size: 11px; white-space: nowrap; z-index: 10;
          box-shadow: 0 2px 6px rgba(0,0,0,0.2);
        }
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
        .debug-info { background: #fff3cd; border: 1px solid #ffc107; padding: 10px; border-radius: 6px; margin-bottom: 10px; font-size: 12px; }
      &lt;/style&gt;
      &lt;div class="card" id="card-content"&gt;
        &lt;div class="no-data"&gt;Loading...&lt;/div&gt;
      &lt;/div&gt;
    `;
  }

  set hass(hass) {
    this._hass = hass;
    if (hass &amp;&amp; this.config) {
      this._entityCache = this._discoverEntities();
      this.updateData();
    }
  }

  updateData() {
    const card = this.shadowRoot.getElementById('card-content');
    if (!card) return;
    
    const title = this.config.title || 'Printer Analytics (打印机分析)';
    
    let debugHtml = '';
    if (this.config.debug) {
      debugHtml = `&lt;div class="debug-info"&gt;
        &lt;div&gt;Config: ${JSON.stringify(this.config)}&lt;/div&gt;
        &lt;div&gt;Entity Cache: ${JSON.stringify(this._entityCache)}&lt;/div&gt;
        &lt;div&gt;History Entity: ${this._getEntity('print_history') ? 'OK' : 'Missing'}&lt;/div&gt;
      &lt;/div&gt;`;
    }
    
    let html = debugHtml;
    html += this._renderTimeDimensionStats(title);
    html += this._renderPeriodStats();
    html += this._renderSuccessRateTrend();
    html += this._renderDurationDistribution();
    html += this._renderActivityHeatmap();
    html += this._renderFilamentUsage();
    
    card.innerHTML = html || '&lt;div class="no-data"&gt;No data available&lt;/div&gt;';
  }

  _renderTimeDimensionStats(title) {
    const totalPrints = this._getValue('total_prints');
    const successRate = this._getValue('success_rate');
    const avgDuration = this._getValue('average_duration');
    const totalDuration = this._getValue('total_print_duration');
    const totalEnergy = this._getValue('total_energy');
    const printStatus = this._getValue('print_status');
    return `
      &lt;div class="section-title"&gt;📊 ${title}&lt;/div&gt;
      &lt;div class="stats-grid"&gt;
        &lt;div class="stat-card"&gt;&lt;div class="stat-icon"&gt;🖨️&lt;/div&gt;&lt;div class="stat-value"&gt;${totalPrints}&lt;/div&gt;&lt;div class="stat-label"&gt;Total Prints&lt;br/&gt;(总打印次数)&lt;/div&gt;&lt;/div&gt;
        &lt;div class="stat-card"&gt;&lt;div class="stat-icon"&gt;✅&lt;/div&gt;&lt;div class="stat-value"&gt;${successRate}%&lt;/div&gt;&lt;div class="stat-label"&gt;Success Rate&lt;br/&gt;(成功率)&lt;/div&gt;&lt;/div&gt;
        &lt;div class="stat-card"&gt;&lt;div class="stat-icon"&gt;⏱️&lt;/div&gt;&lt;div class="stat-value"&gt;${avgDuration}&lt;/div&gt;&lt;div class="stat-label"&gt;Avg Duration (min)&lt;br/&gt;(平均时长)&lt;/div&gt;&lt;/div&gt;
        &lt;div class="stat-card"&gt;&lt;div class="stat-icon"&gt;🕐&lt;/div&gt;&lt;div class="stat-value"&gt;${totalDuration}&lt;/div&gt;&lt;div class="stat-label"&gt;Total Duration (min)&lt;br/&gt;(总时长)&lt;/div&gt;&lt;/div&gt;
        &lt;div class="stat-card"&gt;&lt;div class="stat-icon"&gt;⚡&lt;/div&gt;&lt;div class="stat-value"&gt;${totalEnergy}&lt;/div&gt;&lt;div class="stat-label"&gt;Energy&lt;br/&gt;(总能耗)&lt;/div&gt;&lt;/div&gt;
        &lt;div class="stat-card"&gt;&lt;div class="stat-icon"&gt;${printStatus.includes('打印中') || printStatus.includes('printing') ? '🔵' : '⚪'}&lt;/div&gt;&lt;div class="stat-value" style="font-size:16px"&gt;${printStatus || 'Idle'}&lt;/div&gt;&lt;div class="stat-label"&gt;Status&lt;br/&gt;(打印状态)&lt;/div&gt;&lt;/div&gt;
      &lt;/div&gt;`;
  }

  _renderPeriodStats() {
    const periods = [
      { key: 'material_stats_7d', label: 'Last 7 Days (最近7天)', icon: '📅' },
      { key: 'material_stats_30d', label: 'Last 30 Days (最近30天)', icon: '📆' },
    ];
    let html = '';
    for (const period of periods) {
      const entity = this._getEntity(period.key);
      const attrs = entity?.attributes || {};
      const totalPrints = attrs.total_prints || 0;
      const successful = attrs.successful || 0;
      const failed = attrs.failed || 0;
      const successRate = attrs.success_rate || 0;
      const totalWeight = attrs.total_weight_g || 0;
      const totalLength = attrs.total_length_m || 0;
      const totalEnergy = attrs.total_energy_kwh || 0;
      const avgDuration = attrs.average_duration_minutes || 0;
      
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
        &lt;/div&gt;`;
    }
    return html;
  }

  _renderSuccessRateTrend() {
    const historyEntity = this._getEntity('print_history');
    const history = historyEntity?.attributes?.history || [];
    
    if (!Array.isArray(history) || history.length === 0) {
      return `&lt;div class="section-title"&gt;📈 Success Rate Trend (打印成功率趋势)&lt;/div&gt;&lt;div class="chart-container"&gt;&lt;div class="no-data"&gt;No history data&lt;/div&gt;&lt;/div&gt;`;
    }
    
    const sortedHistory = [...history].sort((a, b) =&gt; new Date(a.end_time) - new Date(b.end_time));
    let successCount = 0, totalCount = 0;
    const points = [];
    
    for (const item of sortedHistory) {
      totalCount++;
      if (item.status === 'finish') successCount++;
      
      const date = item.end_time.substring(0, 10);
      const rate = Math.round(successCount / totalCount * 100);
      points.push({ date, rate });
    }
    
    if (points.length === 0) {
      return `&lt;div class="section-title"&gt;📈 Success Rate Trend (打印成功率趋势)&lt;/div&gt;&lt;div class="chart-container"&gt;&lt;div class="no-data"&gt;No data&lt;/div&gt;&lt;/div&gt;`;
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
        &lt;div class="chart-title"&gt;Cumulative: ${successCount}/${totalCount} = ${Math.round(successCount/totalCount*100)}%&lt;/div&gt;
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
      &lt;/div&gt;`;
  }

  _renderDurationDistribution() {
    const entity = this._getEntity('duration_distribution');
    const attrs = entity?.attributes || {};
    
    // 获取数据，先尝试从属性获取，没有就尝试从 state 解析
    let distribution = attrs;
    if (Object.keys(distribution).length === 0) {
      try {
        distribution = typeof entity?.state === 'string' ? JSON.parse(entity.state) : entity?.state || {};
      } catch (e) {
        distribution = {};
      }
    }
    
    if (Object.keys(distribution).length === 0) {
      return `&lt;div class="section-title"&gt;📊 Duration Distribution (打印时长分布)&lt;/div&gt;&lt;div class="chart-container"&gt;&lt;div class="no-data"&gt;No data&lt;/div&gt;&lt;/div&gt;`;
    }
    
    const labels = Object.keys(distribution).filter(k =&gt; !['icon', 'friendly_name', 'device_class', 'unit_of_measurement'].includes(k));
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
    const entity = this._getEntity('activity_heatmap');
    let heatmap = entity?.attributes || {};
    
    // 过滤掉非日期属性
    const dateKeys = Object.keys(heatmap).filter(k =&gt; /^\d{4}-\d{2}-\d{2}$/.test(k));
    if (dateKeys.length === 0) {
      // 尝试从 state 解析
      try {
        const stateData = typeof entity?.state === 'string' ? JSON.parse(entity.state) : entity?.state || {};
        heatmap = stateData;
      } catch (e) {
        heatmap = {};
      }
    }
    
    // 构建热力图
    const sortedDates = Object.keys(heatmap).filter(k =&gt; /^\d{4}-\d{2}-\d{2}$/.test(k)).sort();
    if (sortedDates.length === 0) {
      return `&lt;div class="section-title"&gt;🗓️ Activity Heatmap (打印活动热力图)&lt;/div&gt;&lt;div class="chart-container"&gt;&lt;div class="no-data"&gt;No data&lt;/div&gt;&lt;/div&gt;`;
    }
    
    const maxCount = Math.max(...sortedDates.map(k =&gt; heatmap[k]), 1);
    const recentDates = sortedDates.slice(-35);
    const startDate = recentDates.length &gt; 0 ? new Date(recentDates[0]) : new Date();
    
    // 填充缺失的日期
    const allDates = [];
    for (let i = 0; i &lt; 35; i++) {
      const d = new Date(startDate);
      d.setDate(d.getDate() + i);
      const dateKey = d.toISOString().substring(0, 10);
      allDates.push(dateKey);
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
    const historyEntity = this._getEntity('print_history');
    const history = historyEntity?.attributes?.history || [];
    
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
    if (entries.length === 0) return `&lt;div class="section-title"&gt;${title}&lt;/div&gt;&lt;div class="chart-container"&gt;&lt;div class="no-data"&gt;No data&lt;/div&gt;&lt;/div&gt;`;
    
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
    return { entity: 'sensor.p2sda_yin_ji_p2sda_yin_ji_da_yin_li_shi', title: 'Printer Analytics' };
  }
}

customElements.define('printer-analytics-card', PrinterAnalyticsCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: 'printer-analytics-card',
  name: 'Printer Analytics Card',
  description: 'Card for Printer Analytics integration (打印机分析卡片)',
});

