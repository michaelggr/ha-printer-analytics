import shutil
import re

src = r"g:\dev\ha\ha\www\pa-v5.9.js"
dst1 = r"\\192.168.0.130\config\www\pa-v5.9.js"
dst2 = r"\\192.168.0.130\config\custom_components\printer_analytics\www\pa-v5.9.js"

with open(src, 'r', encoding='utf-8') as f:
    content = f.read()

# 完整替换函数
old_func = '''  _renderRealtimeMonitor() {
    const printers = this._getPrintersConfig();
    let html = `<div class="section-header"><div class="section-title"><span class="section-icon">📡</span><span>实时监控面板</span></div></div>`;

    for (const printer of printers) {
      const e = printer.entities;
      const currentTask = this._getState(e.current_task) || '未配置';
      const printProgress = this._getState(e.print_progress) || '0';
      const currentWeight = this._getState(e.current_weight) || 'N/A';
      const chamberTemp = this._getState(e.chamber_temperature) || 'N/A';
      const speedProfile = this._getState(e.speed_profile) || 'N/A';
      const nozzleSize = this._getState(e.nozzle_size) || 'N/A';
      const activeTray = this._getState(e.active_tray);
      const etaTime = this._getState(e.eta_time);

      let statusClass = 'idle';
      let statusText = '空闲';
      if (printProgress && parseFloat(printProgress) > 0 && parseFloat(printProgress) < 100) {
        statusClass = 'printing';
        statusText = `打印中 ${printProgress}%`;
      } else if (currentTask && currentTask !== 'unknown' && currentTask !== 'unavailable' && currentTask !== '未配置') {
        statusClass = 'finish';
        statusText = '已完成';
      }

      // 计算预计完成时间
      let endDisplay = '';
      if (etaTime && etaTime !== 'unknown' && etaTime !== 'unavailable') {
        try {
          const etaDate = new Date(etaTime);
          if (!isNaN(etaDate.getTime())) {
            const hours = etaDate.getHours();
            const mins = etaDate.getMinutes();
            endDisplay = `${hours}:${mins.toString().padStart(2, '0')} 完成`;
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
          <div class="realtime-title">🖥️ ${this._escapeHtml(printer.printer_name)}</div>
          <div class="status-badge ${statusClass}">${statusText}</div>
        </div>
        <div class="realtime-grid">
          <div class="realtime-item">
            <div class="realtime-label">📋 当前任务</div>
            <div class="realtime-value">${this._escapeHtml(currentTask || '空闲')}</div>
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
  }'''

new_func = '''  _renderRealtimeMonitor() {
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
      const currentTask = this._getState(e.current_task) || '未配置';
      const printProgress = this._getState(e.print_progress) || '0';
      const currentWeight = this._getState(e.current_weight) || 'N/A';
      const chamberTemp = this._getState(e.chamber_temperature) || 'N/A';
      const speedProfile = this._getState(e.speed_profile) || 'N/A';
      const nozzleSize = this._getState(e.nozzle_size) || 'N/A';
      const activeTray = this._getState(e.active_tray);
      const endTime = this._getState(e.end_time);

      let statusClass = 'idle';
      let statusText = '空闲';
      if (printProgress && parseFloat(printProgress) > 0 && parseFloat(printProgress) < 100) {
        statusClass = 'printing';
        statusText = `打印中 ${printProgress}%`;
      } else if (currentTask && currentTask !== 'unknown' && currentTask !== 'unavailable' && currentTask !== '未配置') {
        statusClass = 'finish';
        statusText = '已完成';
      }

      // 计算预计完成时间
      let endDisplay = '';
      if (endTime && endTime !== 'unknown' && endTime !== 'unavailable') {
        try {
          const endDate = new Date(endTime);
          if (!isNaN(endDate.getTime())) {
            const hours = endDate.getHours();
            const mins = endDate.getMinutes();
            endDisplay = `${hours}:${mins.toString().padStart(2, '0')} 完成`;
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
          <div class="status-badge ${statusClass}">${statusText}</div>
        </div>
        <div class="realtime-grid">
          <div class="realtime-item">
            <div class="realtime-label">📋 当前任务</div>
            <div class="realtime-value">${this._escapeHtml(currentTask || '空闲')}</div>
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
  }'''

content = content.replace(old_func, new_func)

# 递增版本号
match = re.search(r'v(\d+)\.(\d+)\.(\d+)', content)
if match:
    major, minor, patch = int(match.group(1)), int(match.group(2)), int(match.group(3))
    patch += 1
    new_version = f"v{major}.{minor}.{patch}"
    content = re.sub(r'v\d+\.\d+\.\d+', new_version, content, 1)
    print(f"Version: {match.group(0)} -> {new_version}")

with open(src, 'w', encoding='utf-8') as f:
    f.write(content)

print("Replaced realtime monitor function")

try:
    shutil.copy(src, dst1)
    print(f"Uploaded to {dst1}")
except Exception as e:
    print(f"Error: {e}")

try:
    shutil.copy(src, dst2)
    print(f"Uploaded to {dst2}")
except Exception as e:
    print(f"Error: {e}")

print(f"\n✅ Done! Version: {new_version}")
