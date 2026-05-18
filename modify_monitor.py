import shutil
import os
import re

src = r"g:\dev\ha\ha\www\pa-v5.9.js"
dst1 = r"\\192.168.0.130\config\www\pa-v5.9.js"
dst2 = r"\\192.168.0.130\config\custom_components\printer_analytics\www\pa-v5.9.js"

# 读取文件
with open(src, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. 添加预计完成时间实体
old_entity = '''const speedProfile = this._getState(e.speed_profile) || 'N/A';
      const nozzleSize = this._getState(e.nozzle_size) || 'N/A';
      const activeTray = this._getState(e.active_tray);'''

new_entity = '''const speedProfile = this._getState(e.speed_profile) || 'N/A';
      const nozzleSize = this._getState(e.nozzle_size) || 'N/A';
      const activeTray = this._getState(e.active_tray);
      const etaTime = this._getState(e.eta_time);'''

content = content.replace(old_entity, new_entity)

# 2. 计算预计完成时间
old_calc = '''// AMS 耗材盘
      let amsHtml = '';'''

new_calc = '''// 计算预计完成时间
      let etaDisplay = '';
      if (etaTime && etaTime !== 'unknown' && etaTime !== 'unavailable') {
        try {
          const etaDate = new Date(etaTime);
          if (!isNaN(etaDate.getTime())) {
            const hours = etaDate.getHours();
            const mins = etaDate.getMinutes();
            etaDisplay = `${hours}:${mins.toString().padStart(2, '0')} 完成`;
          }
        } catch (e) {}
      }

      // AMS 耗材盘
      let amsHtml = '';'''

content = content.replace(old_calc, new_calc)

# 3. 修改显示样式，添加预计完成时间
old_progress = '''<div class="realtime-item">
            <div class="realtime-label">📊 打印进度</div>
            <div class="realtime-value">${printProgress}%</div>
            <div class="progress-track" style="margin-top:8px;">
              <div class="progress-fill" style="width:${printProgress}%"></div>
            </div>
          </div>'''

new_progress = '''${etaDisplay ? `<div style="text-align:center;font-size:11px;color:var(--primary-light);font-weight:600;margin-bottom:4px;">⏰ ${etaDisplay}</div>` : ''}
          <div class="realtime-item">
            <div class="realtime-label">📊 打印进度</div>
            <div class="realtime-value">${printProgress}%</div>
            <div class="progress-track" style="margin-top:6px;">
              <div class="progress-fill" style="width:${printProgress}%"></div>
            </div>
          </div>'''

content = content.replace(old_progress, new_progress)

# 4. 缩小字体大小 - 找到CSS样式部分并修改
old_css = '''.realtime-label {
          font-size: 13px;
          font-weight: 600;
          color: var(--text-secondary);
          margin-bottom: 6px;
        }
        .realtime-value {
          font-size: 18px;
          font-weight: 700;
          color: var(--text-primary);
        }'''

new_css = '''.realtime-label {
          font-size: 11px;
          font-weight: 600;
          color: var(--text-secondary);
          margin-bottom: 4px;
        }
        .realtime-value {
          font-size: 14px;
          font-weight: 700;
          color: var(--text-primary);
        }'''

content = content.replace(old_css, new_css)

# 5. 缩小 ams 标题
old_ams_title = '''<div style="font-size:13px;font-weight:700;color:var(--text-primary);margin-bottom:10px;display:flex;align-items:center;gap:6px;">
            <span>🎨</span> AMS耗材盘
          </div>'''

new_ams_title = '''<div style="font-size:12px;font-weight:700;color:var(--text-primary);margin-bottom:8px;display:flex;align-items:center;gap:6px;">
            <span>🎨</span> AMS耗材盘
          </div>'''

content = content.replace(old_ams_title, new_ams_title)

# 6. 缩小 ams margin-top
old_ams_margin = '''amsHtml = `<div style="margin-top:16px;">'''
new_ams_margin = '''amsHtml = `<div style="margin-top:12px;">'''
content = content.replace(old_ams_margin, new_ams_margin)

# 7. 缩小 realtime-grid gap
old_grid_gap = '''.realtime-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
          gap: 16px;
        }'''
new_grid_gap = '''.realtime-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
          gap: 10px;
        }'''
content = content.replace(old_grid_gap, new_grid_gap)

# 写回文件
with open(src, 'w', encoding='utf-8') as f:
    f.write(content)

print("Modified realtime monitor")

# 上传到服务器
try:
    shutil.copy(src, dst1)
    print(f"Copied to {dst1}")
except Exception as e:
    print(f"Error copying to {dst1}: {e}")

try:
    shutil.copy(src, dst2)
    print(f"Copied to {dst2}")
except Exception as e:
    print(f"Error copying to {dst2}: {e}")

print("Done!")
