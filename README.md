# Printer Analytics

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/v/release/michaelggr/ha-printer-analytics)](https://github.com/michaelggr/ha-printer-analytics)

A Home Assistant custom integration for tracking and analyzing 3D printer data. Works with Bambu Lab and other printer integrations.

**[中文说明](#中文说明)**

## Features

### 📊 Data Tracking
- **Print History** — Automatically record every print job with detailed info: task name, filament type/color/weight/length, duration, energy, nozzle/bed/chamber temperature, speed profile, etc.
- **Cover Images & Snapshots** — Auto-download print cover images and snapshot images
- **Print Info Documents** — Generate complete print info JSON documents
- **Chamber Temperature** — Record chamber temperature during the last 5 minutes of printing (avg/max/min)

### 📈 Statistics & Analytics
- **Lifetime Stats** — Total prints, success rate, average duration, total duration, total weight, total length, total energy, quality rating
- **7-Day / 30-Day Period Stats** — 8 metrics in table format per period
- **Success Rate Trend** — Cumulative success rate SVG line chart
- **Duration Distribution** — Print count by time bucket (bar chart)
- **Activity Heatmap** — Daily print activity over the last 5 weeks
- **Filament Usage** — Pie charts by filament type and color
- **Failure Stage Distribution** — Failed print stage analysis
- **Filament Success Stats** — Success rate per filament type

### 🖥️ Lovelace Card (v5.2)
- **Modern Glass-morphism Design** — Gradient backgrounds, smooth animations, responsive layout
- **Two Display Modes**:
  - `stats` — Statistics analysis view only
  - `history` — All print history view only
  - Default — Tab switching between both views
- **Multi-Printer Support** — Merge and display history from multiple printers in one view
- **Real-time Monitor** — Live nozzle/bed/chamber temperature, print progress, AMS tray info, power consumption
- **Advanced Filtering** — Filter by status + date range + color + keyword search
- **Pagination** — Efficient browsing for large datasets (20 records per page)
- **Detail Modal** — Click any record to see full print details including chamber temperature
- **CSV Export** — Export filtered history to CSV file (Excel-compatible with BOM header)
- **Batch Delete** — Select multiple records and delete with confirmation
- **Dynamic Units** — Auto-format weight (g/kg/t) and duration (h/days/weeks/months) for growing data

### 💾 Data Safety
- **100-Year Storage** — Data stored by year in separate JSON files
- **Auto Backup Sync** — Data automatically synced to `www/printer_analytics_data/` (included in HA snapshots)
- **Compressed Archives** — Monthly full backup with gzip compression, keeps last 12 archives
- **Auto Restore** — Automatically restore data from backup directory when reinstalling the integration
- **Legacy Migration** — Automatically migrate old single-file data to new year-sharded format

## Installation

### HACS (Recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=michaelggr&repository=ha-printer-analytics&category=integration)

1. Go to HACS → Integrations
2. Click the three dots → Custom repositories
3. Add `https://github.com/michaelggr/ha-printer-analytics` as an Integration
4. Search for "Printer Analytics" and install
5. Restart Home Assistant

### Manual

1. Download the latest release
2. Copy `custom_components/printer_analytics/` to your HA `custom_components/` directory
3. Restart Home Assistant

## Configuration

1. Go to **Settings** → **Devices & Services** → **Add Integration**
2. Search for **"Printer Analytics"**
3. Fill in the form:
   - **Printer Name**: A name for your printer (e.g., "Bambu P2S")
   - **Print Status Sensor**: Select the print status entity from your printer integration
   - **Power Sensor** (optional): Select a power sensor
   - **Energy Sensor** (optional): Select an energy sensor
   - **Chamber Temperature Sensor** (optional): Select a chamber temperature sensor

## Lovelace Card

The integration automatically deploys a custom Lovelace card. Add it to your dashboard:

### Basic Configuration

```yaml
type: custom:printer-analytics-card
title: My Printer
print_history: sensor.my_printer_print_history
total_prints: sensor.my_printer_total_prints
success_rate: sensor.my_printer_success_rate
average_duration: sensor.my_printer_average_duration
total_print_duration: sensor.my_printer_total_print_duration
total_energy: sensor.my_printer_total_energy
material_stats_7d: sensor.my_printer_7day_stats
material_stats_30d: sensor.my_printer_30day_stats
duration_distribution: sensor.my_printer_duration_distribution
activity_heatmap: sensor.my_printer_activity_heatmap
print_status: sensor.my_printer_print_status
```

### Full Configuration

```yaml
type: custom:printer-analytics-card
title: 🖨️ P2S Printer Analytics
mode: stats                    # stats | history | (empty for tabs)
printer_name: P2S
print_history: sensor.p2s_print_history
total_prints: sensor.p2s_total_prints
success_rate: sensor.p2s_success_rate
average_duration: sensor.p2s_average_duration
total_print_duration: sensor.p2s_total_print_duration
total_energy: sensor.p2s_total_energy
material_stats_7d: sensor.p2s_7day_stats
material_stats_30d: sensor.p2s_30day_stats
material_stats_lifetime: sensor.p2s_lifetime_stats
duration_distribution: sensor.p2s_duration_distribution
failure_stage_distribution: sensor.p2s_failure_stage_distribution
filament_success_stats: sensor.p2s_filament_success_stats
activity_heatmap: sensor.p2s_activity_heatmap
print_status: sensor.p2s_print_status
current_task: sensor.p2s_task_name
print_progress: sensor.p2s_print_progress
current_weight: sensor.p2s_print_weight
nozzle_temp: sensor.p2s_nozzle_temperature
bed_temp: sensor.p2s_bed_temperature
chamber_temp: sensor.p2s_chamber_temperature
active_tray: sensor.p2s_active_tray
power_consumption: sensor.p2s_power
speed_profile: sensor.p2s_speed_profile
nozzle_size: sensor.p2s_nozzle_size
ams_tray_1: sensor.p2s_ams_1_tray_1
ams_tray_2: sensor.p2s_ams_1_tray_2
ams_tray_3: sensor.p2s_ams_1_tray_3
ams_tray_4: sensor.p2s_ams_1_tray_4
extra_print_histories:
  - entity: sensor.a1mini_print_history
    name: a1mini
```

### Card Configuration Options

| Option | Description |
|--------|-------------|
| `mode` | Display mode: `stats` (statistics only), `history` (history only), or empty (tab switching) |
| `printer_name` | Printer name for multi-printer tag display |
| `extra_print_histories` | List of additional printer history entities to merge |
| `material_stats_lifetime` | Lifetime stats entity (hides total filament from summary when set) |

## Sensors

| Sensor | Description |
|--------|-------------|
| `sensor.{name}_total_prints` | Total number of prints |
| `sensor.{name}_success_rate` | Print success rate (%) |
| `sensor.{name}_average_duration` | Average print duration (hours) |
| `sensor.{name}_total_print_duration` | Total print duration (hours) |
| `sensor.{name}_total_energy` | Total energy consumption (kWh) |
| `sensor.{name}_material_stats_lifetime` | Lifetime material statistics |
| `sensor.{name}_material_stats_7d` | 7-day material statistics |
| `sensor.{name}_material_stats_30d` | 30-day material statistics |
| `sensor.{name}_duration_distribution` | Print duration distribution |
| `sensor.{name}_activity_heatmap` | Print activity heatmap |
| `sensor.{name}_failure_stage_distribution` | Failure stage distribution |
| `sensor.{name}_filament_success_stats` | Filament success rate statistics |
| `sensor.{name}_print_history` | Print history records |
| `sensor.{name}_print_status` | Current print status |

## Services

| Service | Description | Parameters |
|---------|-------------|------------|
| `printer_analytics.refresh_stats` | Force recalculate all statistics and reload history | `entity_id` (required) |
| `printer_analytics.reset_history` | Clear all print history | `entity_id` (required) |
| `printer_analytics.delete_history_records` | Delete specific records by ID | `entity_id` (required), `record_ids` (required, comma-separated) |
| `printer_analytics.backfill_cover_images` | Download missing cover images for existing history | `entity_id` (required) |
| `printer_analytics.backfill_snapshots` | Download missing snapshot images for existing history | `entity_id` (required) |
| `printer_analytics.backfill_task_names` | Fill missing task names from Bambu Cloud | `entity_id` (required) |

### Service Examples

```yaml
# Refresh statistics
service: printer_analytics.refresh_stats
target:
  entity_id: sensor.p2s_total_prints

# Delete specific records
service: printer_analytics.delete_history_records
target:
  entity_id: sensor.p2s_total_prints
data:
  record_ids: "abc123,def456"

# Backfill cover images
service: printer_analytics.backfill_cover_images
target:
  entity_id: sensor.p2s_total_prints
```

## Data Storage & Backup

| Path | Description | HA Backup |
|------|-------------|-----------|
| `config/.printer_analytics/history_by_year/` | Main data (by year) | ❌ |
| `config/.printer_analytics/archives/` | Compressed monthly backups | ❌ |
| `config/www/printer_analytics_data/` | Auto-synced backup copy | ✅ Included |
| `config/www/printer_analytics/` | Cover images & snapshots | ✅ Included |

**Data Safety Features:**
- Data is automatically synced to `www/printer_analytics_data/` on every save (included in HA snapshots)
- Monthly compressed full backups are created automatically (kept for 12 months)
- When reinstalling the integration, data is automatically restored from the backup directory
- Old single-file data format is automatically migrated to year-sharded format

## Architecture

```
custom_components/printer_analytics/
├── __init__.py           # Entry point, service registration, dashboard auto-deploy
├── config_flow.py        # UI configuration flow
├── const.py              # Constants and configuration
├── coordinator.py        # DataUpdateCoordinator, print lifecycle orchestration
├── data_models.py        # Data classes (PrinterStats, PrintRecord)
├── entity_discovery.py   # Auto-discover printer entities from bambu_lab
├── image_manager.py      # Cover image & snapshot download, Bambu Cloud auth
├── print_tracker.py      # Print start/end detection, material tracking
├── sensor.py             # HA sensor entities (14 sensors per printer)
├── statistics.py         # Statistics calculation with incremental cache
├── storage.py            # Year-sharded JSON storage, backup & restore
├── utils.py              # Security utilities (SecureFileHandler, URLValidator)
├── www/
│   └── pa-v5.2.js        # Lovelace custom card (3,366 lines)
└── tests/                # Test suite
```

### Data Flow

```
bambu_lab entities → entity_discovery → coordinator → print_tracker
                                                       ↓ (print end)
                                                  statistics (cached)
                                                       ↓
                                                  storage (year-sharded)
                                                       ↓
                                                  sensor (14 entities)
                                                       ↓
                                                  Lovelace card (JS)
```

## Changelog

### v5.8.3 (2026-05-15) — Performance Optimization

**Python Backend:**
- Statistics incremental cache (O(1) when data unchanged)
- Time parsing dictionary cache (max 512 entries)
- AMS entity ID cache (avoid full entity scan every 60s)
- Storage dirty flag (only write changed year files)
- Fix nested executor in `StorageManager._save_year_data`
- Year extraction: regex → string slice
- Move placeholder image detection to executor
- Sensor JSON truncation: binary search → estimation
- Snapshot download loop: add 24h safety limit
- Remove 8 delegate methods from Coordinator
- Add `vol.Schema` validation to all 6 services
- Unify `INVALID_ENTITY_STATES` to `const.py`
- Remove BOM from all files
- Fix `energy_kwh:` typo in conftest.py

**Frontend JS:**
- CSS extracted to constant, inject only once
- Merged records cache + shallow copy (no data mutation)
- Aggregated stats cache (3 traversals → 1)
- Unified status mapping to `STATUS_CONFIG`
- Unified time formatting to `_formatDateTime`
- `_escapeHtml`: DOM creation → string replace
- Delete 3 dead code methods
- JS reduced from 3,856 to 3,366 lines (-12.7%)

### v5.3.0 — Modular Architecture Refactor

- Split monolithic `coordinator.py` into 6 sub-modules
- Add year-sharded storage with backup & restore
- Add Bambu Cloud authentication for cover images
- Add multi-printer support in Lovelace card

## Requirements

- Home Assistant 2024.1.0 or later (tested up to 2026.4.4)
- A printer integration (e.g., [bambu_lab](https://github.com/greghesp/ha-bambulab)) for entity auto-discovery

> **Compatibility Note**: HA 2026.x changed the internal `LovelaceData` structure from dict to object. This integration has been updated to support both old and new HA versions.

## License

MIT License

---

<a id="中文说明"></a>

## 中文说明

Home Assistant 自定义集成，用于跟踪和分析 3D 打印机数据。支持拓竹（Bambu Lab）及其他打印机集成。

### 功能特性

#### 📊 数据追踪
- **打印历史** — 自动记录每次打印的详细信息：任务名称、耗材类型/颜色/重量/长度、时长、能耗、喷嘴/热床/腔体温度、速度配置等
- **封面图与快照** — 自动下载打印封面图和快照图
- **打印信息文档** — 生成完整的打印信息 JSON 文档
- **腔体温度** — 记录打印结束前5分钟的腔体温度（平均/最高/最低）

#### 📈 统计分析
- **终身统计** — 总打印次数、成功率、平均时长、总时长、总重量、总长度、总能耗、质量评级
- **7天/30天周期统计** — 每个周期8个指标的表格展示
- **成功率趋势** — 累计成功率 SVG 折线图
- **时长分布** — 按时间段统计打印数量（柱状图）
- **活动热力图** — 最近5周的每日打印活动
- **耗材使用** — 按耗材类型和颜色的饼图
- **失败阶段分布** — 按失败时的进度阶段分析（早期/中期/后期）
- **耗材成功率统计** — 每种耗材的成功率与使用量

#### 🖥️ Lovelace 卡片 (v5.2)
- **现代玻璃拟态设计** — 渐变背景、流畅动画、响应式布局
- **两种显示模式**：
  - `stats` — 仅显示统计分析
  - `history` — 仅显示全部历史
  - 默认 — Tab 切换两种视图
- **多打印机支持** — 合并显示多台打印机的历史记录
- **实时监控** — 喷嘴/热床/腔体温度、打印进度、AMS 料盘信息、功耗
- **高级筛选** — 按状态 + 日期范围 + 颜色 + 关键词搜索
- **分页显示** — 大数据集高效浏览（每页20条）
- **详情弹窗** — 点击记录查看完整打印详情，含腔体温度
- **CSV 导出** — 导出筛选后的历史为 CSV 文件（兼容 Excel，含 BOM 头）
- **批量删除** — 选择多条记录并确认删除
- **动态单位** — 自动格式化重量(g/kg/t)和时长(h/天/周/月)

#### 💾 数据安全
- **100年存储** — 数据按年份分片存储在独立 JSON 文件中
- **自动备份同步** — 每次保存时自动同步到 `www/printer_analytics_data/`（HA 快照会包含）
- **压缩归档** — 每月自动创建完整 gzip 压缩备份，保留最近12个
- **自动恢复** — 重装集成时自动从备份目录恢复数据
- **旧版迁移** — 自动将旧版单文件数据迁移到新的年份分片格式

### 安装

#### HACS 安装（推荐）

[![在 Home Assistant Community Store 中打开仓库](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=michaelggr&repository=ha-printer-analytics&category=integration)

1. 进入 HACS → 集成
2. 点击右上角三个点 → 自定义仓库
3. 添加 `https://github.com/michaelggr/ha-printer-analytics` 为集成
4. 搜索 "Printer Analytics" 并安装
5. 重启 Home Assistant

#### 手动安装

1. 下载最新发布包
2. 将 `custom_components/printer_analytics/` 复制到 HA 的 `custom_components/` 目录
3. 重启 Home Assistant

### 配置

1. 进入 **设置** → **设备与服务** → **添加集成**
2. 搜索 **"Printer Analytics"**
3. 填写表单：
   - **打印机名称**：为你的打印机起个名字（如 "Bambu P2S"）
   - **打印状态传感器**：选择打印机集成提供的打印状态实体
   - **功率传感器**（可选）：选择功率传感器
   - **能耗传感器**（可选）：选择能耗传感器
   - **腔体温度传感器**（可选）：选择腔体温度传感器

### Lovelace 卡片

集成安装后自动部署自定义卡片。在仪表盘中添加：

#### 基础配置

```yaml
type: custom:printer-analytics-card
title: 我的打印机
print_history: sensor.my_printer_print_history
total_prints: sensor.my_printer_total_prints
success_rate: sensor.my_printer_success_rate
average_duration: sensor.my_printer_average_duration
total_print_duration: sensor.my_printer_total_print_duration
total_energy: sensor.my_printer_total_energy
material_stats_7d: sensor.my_printer_7day_stats
material_stats_30d: sensor.my_printer_30day_stats
duration_distribution: sensor.my_printer_duration_distribution
activity_heatmap: sensor.my_printer_activity_heatmap
print_status: sensor.my_printer_print_status
```

#### 完整配置

```yaml
type: custom:printer-analytics-card
title: 🖨️ P2S 打印机分析
mode: stats                    # stats | history | (空=显示Tab切换)
printer_name: P2S
print_history: sensor.p2s_print_history
total_prints: sensor.p2s_total_prints
success_rate: sensor.p2s_success_rate
average_duration: sensor.p2s_average_duration
total_print_duration: sensor.p2s_total_print_duration
total_energy: sensor.p2s_total_energy
material_stats_7d: sensor.p2s_7day_stats
material_stats_30d: sensor.p2s_30day_stats
material_stats_lifetime: sensor.p2s_lifetime_stats
duration_distribution: sensor.p2s_duration_distribution
failure_stage_distribution: sensor.p2s_failure_stage_distribution
filament_success_stats: sensor.p2s_filament_success_stats
activity_heatmap: sensor.p2s_activity_heatmap
print_status: sensor.p2s_print_status
current_task: sensor.p2s_task_name
print_progress: sensor.p2s_print_progress
current_weight: sensor.p2s_print_weight
nozzle_temp: sensor.p2s_nozzle_temperature
bed_temp: sensor.p2s_bed_temperature
chamber_temp: sensor.p2s_chamber_temperature
active_tray: sensor.p2s_active_tray
power_consumption: sensor.p2s_power
speed_profile: sensor.p2s_speed_profile
nozzle_size: sensor.p2s_nozzle_size
ams_tray_1: sensor.p2s_ams_1_tray_1
ams_tray_2: sensor.p2s_ams_1_tray_2
ams_tray_3: sensor.p2s_ams_1_tray_3
ams_tray_4: sensor.p2s_ams_1_tray_4
extra_print_histories:
  - entity: sensor.a1mini_print_history
    name: a1mini
```

#### 卡片配置选项

| 选项 | 说明 |
|------|------|
| `mode` | 显示模式：`stats`（仅统计）、`history`（仅历史）、空=Tab切换 |
| `printer_name` | 打印机名称，用于多打印机标签显示 |
| `extra_print_histories` | 额外打印机的历史实体列表，用于多打印机合并 |
| `material_stats_lifetime` | 终身统计数据实体ID（设置后隐藏统计摘要中的总耗材项） |

### 传感器

| 传感器 | 说明 |
|--------|------|
| `sensor.{name}_total_prints` | 总打印次数 |
| `sensor.{name}_success_rate` | 成功率 (%) |
| `sensor.{name}_average_duration` | 平均打印时长 (小时) |
| `sensor.{name}_total_print_duration` | 打印总时长 (小时) |
| `sensor.{name}_total_energy` | 总能耗 (kWh) |
| `sensor.{name}_material_stats_lifetime` | 终身耗材统计 |
| `sensor.{name}_material_stats_7d` | 7天耗材统计 |
| `sensor.{name}_material_stats_30d` | 30天耗材统计 |
| `sensor.{name}_duration_distribution` | 打印时长分布 |
| `sensor.{name}_activity_heatmap` | 打印活动热力图 |
| `sensor.{name}_failure_stage_distribution` | 失败阶段分布 |
| `sensor.{name}_filament_success_stats` | 耗材成功率统计 |
| `sensor.{name}_print_history` | 打印历史记录 |
| `sensor.{name}_print_status` | 当前打印状态 |

### 服务

| 服务 | 说明 | 参数 |
|------|------|------|
| `printer_analytics.refresh_stats` | 强制重新计算所有统计数据并重新加载历史 | `entity_id`（必填） |
| `printer_analytics.reset_history` | 清除所有打印历史记录 | `entity_id`（必填） |
| `printer_analytics.delete_history_records` | 按ID删除指定记录 | `entity_id`（必填），`record_ids`（必填，逗号分隔） |
| `printer_analytics.backfill_cover_images` | 补全历史记录中缺失的封面图 | `entity_id`（必填） |
| `printer_analytics.backfill_snapshots` | 补全历史记录中缺失的快照图 | `entity_id`（必填） |
| `printer_analytics.backfill_task_names` | 从拓竹云补全缺失的任务名称 | `entity_id`（必填） |

#### 服务调用示例

```yaml
# 刷新统计
service: printer_analytics.refresh_stats
target:
  entity_id: sensor.p2s_total_prints

# 删除指定记录
service: printer_analytics.delete_history_records
target:
  entity_id: sensor.p2s_total_prints
data:
  record_ids: "abc123,def456"

# 补全封面图
service: printer_analytics.backfill_cover_images
target:
  entity_id: sensor.p2s_total_prints
```

### 数据存储与备份

| 路径 | 说明 | HA 备份 |
|------|------|---------|
| `config/.printer_analytics/history_by_year/` | 主数据（按年份分片） | ❌ |
| `config/.printer_analytics/archives/` | 压缩月度备份 | ❌ |
| `config/www/printer_analytics_data/` | 自动同步的备份副本 | ✅ 包含 |
| `config/www/printer_analytics/` | 封面图与快照 | ✅ 包含 |

**数据安全保障：**
- 每次保存数据时自动同步到 `www/printer_analytics_data/`（HA 快照会包含此目录）
- 每月自动创建完整 gzip 压缩备份，保留最近12个
- **重装集成时自动从备份目录恢复数据**（entry_id 变化也不影响）
- 旧版单文件数据格式自动迁移到新的年份分片格式

### 架构说明

```
custom_components/printer_analytics/
├── __init__.py           # 入口，服务注册，仪表盘自动部署
├── config_flow.py        # UI 配置流程
├── const.py              # 常量与配置
├── coordinator.py        # 数据更新协调器，打印生命周期管理
├── data_models.py        # 数据类（PrinterStats, PrintRecord）
├── entity_discovery.py   # 自动发现 bambu_lab 打印机实体
├── image_manager.py      # 封面图与快照下载，拓竹云认证
├── print_tracker.py      # 打印开始/结束检测，耗材追踪
├── sensor.py             # HA 传感器实体（每台打印机14个传感器）
├── statistics.py         # 统计计算（带增量缓存）
├── storage.py            # 年份分片 JSON 存储，备份与恢复
├── utils.py              # 安全工具（SecureFileHandler, URLValidator）
├── www/
│   └── pa-v5.2.js        # Lovelace 自定义卡片（3,366行）
└── tests/                # 测试套件
```

#### 数据流

```
bambu_lab 实体 → entity_discovery → coordinator → print_tracker
                                                    ↓ (打印结束)
                                               statistics (带缓存)
                                                    ↓
                                               storage (年份分片)
                                                    ↓
                                               sensor (14个实体)
                                                    ↓
                                               Lovelace 卡片 (JS)
```

### 更新日志

#### v5.8.3 (2026-05-15) — 性能优化

**Python 后端：**
- 统计计算增量缓存（数据未变化时 O(1) 返回）
- 时间解析字典缓存（最大 512 条）
- AMS 实体 ID 缓存（避免每 60 秒遍历全部 HA 实体）
- 存储脏标记（只写入变化的年份文件）
- 修复 `StorageManager._save_year_data` 嵌套 executor 问题
- 年份提取：正则 → 字符串切片
- 占位图检测移到 executor（消除启动阻塞）
- 传感器 JSON 截断优化：二分查找 → 估算+单次验证
- 快照下载循环添加 24 小时安全上限
- 删除 Coordinator 8 个纯委托方法
- 6 个服务添加 `vol.Schema` 参数验证
- 统一 `INVALID_ENTITY_STATES` 到 `const.py`
- 移除所有文件 BOM
- 修复 `energy_kwh:` 拼写错误

**前端 JS：**
- CSS 提取为常量，只注入一次
- 合并记录缓存 + 浅拷贝（不再修改 HA 原始数据）
- 统计计算合并缓存（3 次遍历 → 1 次）
- 状态判断统一为 `STATUS_CONFIG` 静态常量
- 时间格式化统一为 `_formatDateTime` 方法
- `_escapeHtml`：DOM 创建 → 字符串替换
- 删除 3 个死代码方法
- JS 从 3,856 行瘦身到 3,366 行（-12.7%）

#### v5.3.0 — 模块化架构重构

- 将单体 `coordinator.py` 拆分为 6 个子模块
- 添加年份分片存储与备份恢复
- 添加拓竹云认证用于封面图下载
- 添加 Lovelace 卡片多打印机支持

### 系统要求

- Home Assistant 2024.1.0 或更新版本（已测试至 2026.4.4）
- 一个打印机集成（如 [bambu_lab](https://github.com/greghesp/ha-bambulab)）用于实体自动发现

> **兼容性说明**：HA 2026.x 将内部 `LovelaceData` 结构从 dict 改为对象，本集成已更新以同时支持新旧版本。

## 许可证

MIT License
