# Printer Analytics

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/v/release/michaelggr/ha-printer-analytics)](https://github.com/michaelggr/ha-printer-analytics)

A Home Assistant custom integration for tracking and analyzing 3D printer data. Works with Bambu Lab and other printer integrations.

**[中文说明](#中文说明)**

## Features

### \ud83d\udcca Data Tracking
- **Print History** — Automatically record every print job: task name, filament type/color/weight/length, duration, energy, nozzle/bed/chamber temperature, speed profile, AMS tray info, etc.
- **Cover Images & Snapshots** — Auto-download print cover images and print snapshots
- **Print Info Documents** — Generate complete print info JSON documents
- **Chamber Temperature** — Record chamber temperature during the last 5 minutes of printing (avg/max/min)

### \ud83d\udcc8 Statistics & Analytics
- **Lifetime Stats** — Total prints, success rate, average duration, total duration, total weight, total length, total energy, quality rating
- **7-Day / 30-Day Period Stats** — 8 metrics in table format per period
- **Success Rate Trend** — Cumulative success rate SVG line chart
- **Duration Distribution** — Print count by time bucket (bar chart)
- **Activity Heatmap** — Daily print activity over the last 5 weeks
- **Filament Usage** — Pie charts by filament type and color
- **Failure Stage Distribution** — Failed print stage analysis (early/mid/late)
- **Filament Success Stats** — Success rate per filament type

### \ud83d\udcda Lovelace Card (v5.2)
- **Modern Glass-morphism Design** — Gradient backgrounds, smooth animations, responsive layout
- **Three Display Modes**:
  - `stats` — Statistics analysis view only
  - `history` — All print history view only
  - Default — Tab switching between both views
- **Multi-Printer Support** — Merge history from multiple printers in one view
- **Real-time Monitor** — Live nozzle/bed/chamber temperature, print progress, AMS tray info, power consumption
- **Advanced Filtering** — Filter by status + date range + color + keyword search
- **Pagination** — Efficient browsing for large datasets (20 records per page)
- **Detail Modal** — Click any record to see full print details including chamber temperature
- **CSV Export** — Export filtered history to CSV file (Excel-compatible with BOM header)
- **Batch Delete** — Select multiple records and delete with confirmation
- **Dynamic Units** — Auto-format weight (g/kg/t) and duration (h/days/weeks/months)

### \ud83d\udcbe Data Safety
- **100-Year Storage** — Data stored by year in separate JSON files
- **Auto Backup Sync** — Data automatically synced to `www/printer_analytics_data/` (included in HA snapshots)
- **Compressed Archives** — Monthly full backup with gzip compression, keeps last 12 archives
- **Auto Restore** — Automatically restore data from backup directory when reinstalling
- **Legacy Migration** — Automatically migrate old single-file data to new year-sharded format

## Installation

### HACS (Recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=michaelggr&repository=ha-printer-analytics&category=integration)

1. Go to **HACS** → **Integrations**
2. Click the three dots (top right) → **Custom repositories**
3. Enter `https://github.com/michaelggr/ha-printer-analytics` as the repository URL, select **Integration** as category
4. Click **Add** → Search for "Printer Analytics" and install
5. Restart Home Assistant

### Manual Installation

1. Download the [latest release](https://github.com/michaelggr/ha-printer-analytics/releases)
2. Copy the entire `custom_components/printer_analytics/` folder to your HA's `custom_components/` directory
3. Restart Home Assistant

## Configuration

1. Go to **Settings** → **Devices & Services** → **Add Integration**
2. Search for **"Printer Analytics"** and click it
3. Fill in the configuration form:
   - **Printer Name**: A friendly name for your printer (e.g., "Bambu P2S" or "My Printer")
   - **Print Status Sensor**: Select the print status entity from your Bambu Lab or other printer integration
   - **Power Sensor** (optional): Select a power/energy sensor for power consumption tracking
   - **Energy Sensor** (optional): Select an cumulative energy sensor
   - **Chamber Temperature Sensor** (optional): Select a chamber temperature sensor (Bambu Lab P2S/X1 series support this)

### Finding Entity IDs

To find the correct entity IDs for configuration:

1. Go to **Settings** → **Devices & Services** → **Entities**
2. Search for your printer integration entities (e.g., "bambu_lab" or "p2s")
3. Look for entities like:
   - `sensor.p2s_print_status` — Print status
   - `sensor.p2s_task_name` — Current task name
   - `sensor.p2s_print_progress` — Print progress percentage
   - `sensor.p2s_nozzle_temperature` — Nozzle temperature
   - `sensor.p2s_bed_temperature` — Bed temperature
   - `sensor.p2s_chamber_temperature` — Chamber temperature (if supported)
   - `sensor.p2s_print_weight` — Current print weight

## Lovelace Card

The integration automatically registers a custom Lovelace card. Add it to your dashboard:

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

### Full Configuration (Multi-Printer Supported)

```yaml
type: custom:printer-analytics-card
title: \ud83d\udcfa P2S Printer Analytics
mode:                    # stats | history | (empty for tab switching)
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

| Option | Type | Description |
|--------|------|-------------|
| `mode` | string | Display mode: `stats` (stats only), `history` (history only), empty (tab switching) |
| `printer_name` | string | Printer name for multi-printer tag display |
| `print_history` | string | Entity ID of the print history sensor (required) |
| `total_prints` | string | Entity ID of total prints sensor (required) |
| `success_rate` | string | Entity ID of success rate sensor |
| `average_duration` | string | Entity ID of average duration sensor |
| `total_print_duration` | string | Entity ID of total print duration sensor |
| `total_energy` | string | Entity ID of total energy sensor |
| `material_stats_7d` | string | Entity ID of 7-day material stats |
| `material_stats_30d` | string | Entity ID of 30-day material stats |
| `material_stats_lifetime` | string | Entity ID of lifetime material stats (hides total filament from summary when set) |
| `duration_distribution` | string | Entity ID of duration distribution sensor |
| `failure_stage_distribution` | string | Entity ID of failure stage distribution sensor |
| `filament_success_stats` | string | Entity ID of filament success stats sensor |
| `activity_heatmap` | string | Entity ID of activity heatmap sensor |
| `print_status` | string | Entity ID of print status sensor (required) |
| `current_task` | string | Entity ID of current task name sensor (for real-time monitor) |
| `print_progress` | string | Entity ID of print progress sensor (for real-time monitor) |
| `current_weight` | string | Entity ID of current print weight sensor (for real-time monitor) |
| `nozzle_temp` | string | Entity ID of nozzle temperature sensor (for real-time monitor) |
| `bed_temp` | string | Entity ID of bed temperature sensor (for real-time monitor) |
| `chamber_temp` | string | Entity ID of chamber temperature sensor (for real-time monitor) |
| `active_tray` | string | Entity ID of active tray sensor (for AMS display) |
| `power_consumption` | string | Entity ID of power consumption sensor (for real-time monitor) |
| `speed_profile` | string | Entity ID of speed profile sensor |
| `nozzle_size` | string | Entity ID of nozzle size sensor |
| `ams_tray_1` ~ `ams_tray_4` | string | Entity IDs of AMS tray sensors |
| `extra_print_histories` | list | List of additional printer history entities to merge and display together |

## Sensors

| Sensor | Description | Unit |
|--------|-------------|------|
| `sensor.{name}_total_prints` | Total number of print jobs | prints |
| `sensor.{name}_success_rate` | Overall success rate | % |
| `sensor.{name}_average_duration` | Average print duration | hours |
| `sensor.{name}_total_print_duration` | Cumulative print duration | hours |
| `sensor.{name}_total_energy` | Cumulative energy consumption | kWh |
| `sensor.{name}_material_stats_lifetime` | Lifetime filament usage summary | - |
| `sensor.{name}_material_stats_7d` | Filament usage for last 7 days | - |
| `sensor.{name}_material_stats_30d` | Filament usage for last 30 days | - |
| `sensor.{name}_duration_distribution` | Print count by duration bucket | - |
| `sensor.{name}_activity_heatmap` | Daily print activity (5 weeks) | - |
| `sensor.{name}_failure_stage_distribution` | Failure stage analysis | - |
| `sensor.{name}_filament_success_stats` | Success rate by filament type | - |
| `sensor.{name}_print_history` | All print history records | - |
| `sensor.{name}_print_status` | Current status (printing/idle) | - |

## Services

| Service | Parameters | Description |
|---------|------------|-------------|
| `printer_analytics.refresh_stats` | `entity_id` (optional) | Force recalculate all statistics from history |
| `printer_analytics.reset_history` | `entity_id` (required) | Clear all print history (cannot be undone) |
| `printer_analytics.delete_history_records` | `entity_id`, `record_ids` | Delete specific records by ID (comma-separated or list) |

## Data Storage & Backup

| Path | Description | In HA Snapshot |
|------|-------------|----------------|
| `config/.printer_analytics/history_by_year/` | Main data (year-sharded JSON files) | No |
| `config/.printer_analytics/archives/` | Compressed monthly backups (.json.gz) | No |
| `config/www/printer_analytics_data/` | Auto-synced backup copy | Yes |
| `config/www/printer_analytics/` | Cover images & snapshots | Yes |

**Data Safety:**
- Data auto-syncs to `www/printer_analytics_data/` on every save (included in HA snapshots)
- Monthly gzip-compressed full backups kept for 12 months
- **Auto-restore on reinstall**: Data is automatically recovered from `www/printer_analytics_data/` when you re-add the integration
- Old single-file format auto-migrates to year-sharded format

## Requirements

- Home Assistant 2023.8.0 or later
- A printer integration (e.g., [bambu_lab](https://github.com/greghesp/ha-bambulab)) for entity auto-discovery

## License

MIT License

---

<a id="中文说明"></a>

## 中文说明

**Printer Analytics** 是一个 Home Assistant 自定义集成，用于自动追踪和分析 3D 打印机的各项数据。支持拓竹（Bambu Lab）全系列打印机及其他兼容打印机集成。

**[English Documentation](#printer-analytics)**

---

## \ud83d\udcda 一、功能特性

### \ud83d\udcc8 数据追踪

| 功能 | 说明 |
|------|------|
| **打印历史自动记录** | 每次打印完成后自动记录：任务名称、耗材类型/颜色/重量/长度、打印时长、能耗、喷嘴/热床/腔体温度、速度配置、AMS料盘信息等 |
| **封面图与快照** | 自动下载打印封面图和过程中拍摄的快照图 |
| **打印信息文档** | 为每次打印生成完整的 JSON 格式打印信息文档 |
| **腔体温度记录** | 记录打印结束前5分钟的腔体温度（平均值/最高/最低），支持拓竹P2S/X1等机型 |
| **多色打印检测** | 自动检测打印过程中的耗材切换，记录每种颜色和类型的使用 |

### \ud83d\udcc8 统计分析

| 功能 | 说明 |
|------|------|
| **终身统计** | 总打印次数、成功率、平均时长、总时长、总重量、总长度、总能耗、质量评级 |
| **7天/30天周期统计** | 每个周期以表格形式展示8项耗材指标 |
| **成功率趋势图** | 累计成功率 SVG 折线图，展示打印质量变化趋势 |
| **时长分布图** | 按时间段（<1h, 1-3h, 3-6h, 6-12h, >12h）统计打印数量 |
| **活动热力图** | 最近5周的每日打印活跃度，清晰展示打印习惯 |
| **耗材使用饼图** | 按耗材类型和颜色分类展示使用占比 |
| **失败阶段分析** | 按失败时进度阶段（早期0-30%/中期30-70%/后期70-100%）统计分析 |
| **耗材成功率** | 每种耗材类型的成功率和总使用量，识别问题耗材 |

### \ud83d\udcda Lovelace 卡片 (v5.2)

| 特性 | 说明 |
|------|------|
| **现代玻璃拟态设计** | 渐变背景、流畅动画、响应式布局，支持暗色主题 |
| **三种显示模式** | `stats`=仅统计 / `history`=仅历史 / 空值=Tab切换 |
| **多打印机合并** | 将多台打印机的历史记录合并在同一个卡片中展示 |
| **实时监控面板** | 显示喷嘴/热床/腔体温度、打印进度、AMS料盘信息、实时功耗 |
| **高级筛选** | 按状态（成功/失败/取消/进行中）+ 日期范围 + 颜色 + 关键词搜索 |
| **分页浏览** | 大数据集高效浏览，每页20条记录 |
| **详情弹窗** | 点击任意记录查看完整打印详情，含腔体温度、颜色切换记录等 |
| **CSV导出** | 将筛选后的历史导出为CSV文件（Excel兼容，含BOM头） |
| **批量删除** | 勾选多条记录后一键删除，带确认提示 |
| **动态单位** | 自动格式化重量（g/kg/t）和时长（h/天/周/月），适应数据增长 |

### \ud83d\udcbe 数据安全

| 特性 | 说明 |
|------|------|
| **100年存储** | 数据按年份分片存储在独立JSON文件中，永不过期 |
| **自动备份同步** | 每次保存时自动同步到 `www/printer_analytics_data/`（HA快照会包含） |
| **压缩归档** | 每月自动创建完整gzip压缩备份，保留最近12个月 |
| **重装自动恢复** | 重新添加集成时自动从备份目录恢复数据（entry_id变化也不影响） |
| **旧版迁移** | 自动将旧版单文件数据迁移到新的年份分片格式 |

---

## \ud83d\udcc8 二、安装指南

### 方式一：HACS 安装（推荐）

1. 进入 **HACS** → **集成**
2. 点击右上角 **三个点** → **自定义仓库**
3. 仓库URL填入：`https://github.com/michaelggr/ha-printer-analytics`，类别选择 **集成**
4. 点击 **添加** → 搜索 "Printer Analytics" → 点击安装
5. 安装完成后 **重启 Home Assistant**

### 方式二：手动安装

1. 从 [GitHub Releases](https://github.com/michaelggr/ha-printer-analytics/releases) 下载最新版本
2. 解压后将 `custom_components/printer_analytics/` 整个文件夹复制到 HA 的 `custom_components/` 目录
3. 重启 Home Assistant

---

## \ud83d\udcc8 三、配置指南

### 添加集成

1. 进入 **设置** → **设备与服务** → **添加集成**
2. 搜索 **"Printer Analytics"** 并点击
3. 填写配置表单（见下方说明）
4. 点击 **提交** 完成

### 配置表单说明

| 配置项 | 必填 | 说明 |
|--------|------|------|
| **打印机名称** | 是 | 给打印机起个名字，如 "Bambu P2S"、"A1mini"，将显示在传感器名称和卡片中 |
| **打印状态传感器** | 是 | 选择打印机集成提供的打印状态实体，如 `sensor.p2s_da_yin_zhuang_tai` |
| **功率传感器** | 否 | 选择功率传感器，用于记录打印实时功耗（如 `sensor.p2s_power`） |
| **能耗传感器** | 否 | 选择累计能耗传感器，用于统计总能耗（如 `sensor.p2s_zong_neng_hao`） |
| **腔体温度传感器** | 否 | 选择腔体温度传感器，用于记录打印结束前5分钟的腔体温度（仅P2S/X1等支持） |

### 如何查找实体ID

1. 进入 **设置** → **设备与服务** → **实体**
2. 搜索你的打印机集成名称（如 "bambu_lab"、"p2s"、"a1mini"）
3. 找到对应的实体，常用实体参考：

| 实体类型 | 实体ID示例 | 说明 |
|----------|-----------|------|
| 打印状态 | `sensor.p2s_da_yin_zhuang_tai` | 打印中/空闲/完成 |
| 任务名称 | `sensor.p2s_22e8bj5a2401765_task_name` | 当前打印任务名 |
| 打印进度 | `sensor.p2s_22e8bj5a2401765_print_progress` | 0-100% |
| 喷嘴温度 | `sensor.p2s_22e8bj5a2401765_nozzle_temperature` | 当前喷嘴温度 |
| 热床温度 | `sensor.p2s_22e8bj5a2401765_bed_temperature` | 当前热床温度 |
| 腔体温度 | `sensor.p2s_22e8bj5a2401765_chamber_temperature` | 当前腔体温度 |
| 当前重量 | `sensor.p2s_22e8bj5a2401765_print_weight` | 当前打印已使用耗材重量 |
| WiFi信号 | `sensor.p2s_22e8bj5a2401765_wi_fi_signal` | WiFi信号强度 |
| 速度配置 | `sensor.p2s_22e8bj5a2401765_speed_profile` | 当前速度配置名 |
| 喷嘴尺寸 | `sensor.p2s_22e8bj5a2401765_nozzle_size` | 当前喷嘴尺寸 |
| AMS料盘1-4 | `sensor.p2s_22e8bj5a2401765_ams_1_tray_X` | AMS各料盘信息 |

---

## \ud83d\udcda 四、Lovelace 卡片配置

集成安装后会自动注册自定义卡片。在仪表盘中添加卡片的方式：

1. 编辑仪表盘 → 点击右上角 **添加卡片** → 选择 **手动配置**
2. 选择 **自定义: printer-analytics-card**
3. 填入配置（参考下方示例）

### 基础配置示例

```yaml
type: custom:printer-analytics-card
title: 我的打印机
print_history: sensor.my_printer_print_history        # 必填：打印历史实体
total_prints: sensor.my_printer_total_prints          # 必填：总打印次数实体
success_rate: sensor.my_printer_success_rate           # 成功率
average_duration: sensor.my_printer_average_duration   # 平均时长
total_print_duration: sensor.my_printer_total_print_duration  # 总打印时长
total_energy: sensor.my_printer_total_energy           # 总能耗
material_stats_7d: sensor.my_printer_7day_stats       # 7天耗材统计
material_stats_30d: sensor.my_printer_30day_stats      # 30天耗材统计
duration_distribution: sensor.my_printer_duration_distribution  # 时长分布
activity_heatmap: sensor.my_printer_activity_heatmap    # 活动热力图
print_status: sensor.my_printer_print_status            # 必填：打印状态实体
```

### 完整配置示例（支持多打印机合并）

```yaml
type: custom:printer-analytics-card
title: \ud83d\udcfa P2S 打印机分析
mode:                      # stats | history | (留空=显示Tab切换视图)
printer_name: P2S          # 卡片中显示的打印机名称

# === 统计数据实体（必填部分）===
print_history: sensor.p2s_p2s_da_yin_li_shi              # 必填
total_prints: sensor.p2s_p2s_zong_da_yin_ci_shu           # 必填
success_rate: sensor.p2s_p2s_cheng_gong_lu
average_duration: sensor.p2s_p2s_ping_jun_da_yin_shi_chang
total_print_duration: sensor.p2s_p2s_da_yin_zong_shi_chang
total_energy: sensor.p2s_p2s_zong_neng_hao
material_stats_7d: sensor.p2s_p2s_7tian_hao_cai_tong_ji
material_stats_30d: sensor.p2s_p2s_30tian_hao_cai_tong_ji
material_stats_lifetime: sensor.p2s_p2s_zhong_shen_hao_cai_tong_ji
duration_distribution: sensor.p2s_p2s_da_yin_shi_chang_fen_bu
failure_stage_distribution: sensor.p2s_p2s_shi_bai_jie_duan_fen_bu
filament_success_stats: sensor.p2s_p2s_hao_cai_cheng_gong_lu_tong_ji
activity_heatmap: sensor.p2s_p2s_da_yin_huo_dong_re_li_tu
print_status: sensor.p2s_p2s_da_yin_zhuang_tai              # 必填

# === 实时监控实体（可选，用于显示实时数据）===
current_task: sensor.p2s_22e8bj5a2401765_task_name        # 当前任务名称
print_progress: sensor.p2s_22e8bj5a2401765_print_progress  # 打印进度
current_weight: sensor.p2s_22e8bj5a2401765_print_weight     # 当前已使用耗材
nozzle_temp: sensor.p2s_22e8bj5a2401765_nozzle_temperature  # 喷嘴温度
bed_temp: sensor.p2s_22e8bj5a2401765_bed_temperature        # 热床温度
chamber_temp: sensor.p2s_22e8bj5a2401765_chamber_temperature  # 腔体温度
active_tray: sensor.p2s_22e8bj5a2401765_active_tray        # 当前活跃料盘
power_consumption: sensor.p2s_22e8bj5a2401765_total_usage    # 实时功耗
speed_profile: sensor.p2s_22e8bj5a2401765_speed_profile      # 速度配置
nozzle_size: sensor.p2s_22e8bj5a2401765_nozzle_size        # 喷嘴尺寸
ams_tray_1: sensor.p2s_22e8bj5a2401765_ams_1_tray_1       # AMS料盘1
ams_tray_2: sensor.p2s_22e8bj5a2401765_ams_1_tray_2
ams_tray_3: sensor.p2s_22e8bj5a2401765_ams_1_tray_3
ams_tray_4: sensor.p2s_22e8bj5a2401765_ams_1_tray_4

# === 多打印机配置 ===
# 在一个卡片中同时显示多台打印机的历史记录
extra_print_histories:
  - entity: sensor.a1mini_a1mini_da_yin_li_shi    # 第二台打印机的历史实体
    name: A1mini                                 # 在卡片中显示的名称
```

### 卡片配置项说明

| 配置项 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| `type` | string | 是 | 必须填 `custom:printer-analytics-card` |
| `title` | string | 否 | 卡片标题 |
| `mode` | string | 否 | `stats`=仅统计视图 / `history`=仅历史视图 / 留空=Tab切换 |
| `printer_name` | string | 否 | 打印机名称，用于多打印机模式下的标签显示 |
| `print_history` | string | **是** | 打印历史传感器实体ID |
| `total_prints` | string | **是** | 总打印次数传感器实体ID |
| `success_rate` | string | 否 | 成功率传感器实体ID |
| `average_duration` | string | 否 | 平均打印时长传感器实体ID |
| `total_print_duration` | string | 否 | 打印总时长传感器实体ID |
| `total_energy` | string | 否 | 总能耗传感器实体ID |
| `material_stats_7d` | string | 否 | 7天耗材统计传感器实体ID |
| `material_stats_30d` | string | 否 | 30天耗材统计传感器实体ID |
| `material_stats_lifetime` | string | 否 | 终身耗材统计传感器实体ID |
| `duration_distribution` | string | 否 | 打印时长分布传感器实体ID |
| `failure_stage_distribution` | string | 否 | 失败阶段分布传感器实体ID |
| `filament_success_stats` | string | 否 | 耗材成功率统计传感器实体ID |
| `activity_heatmap` | string | 否 | 活动热力图传感器实体ID |
| `print_status` | string | **是** | 打印状态传感器实体ID |
| `current_task` | string | 否 | 当前任务名称传感器实体ID（实时监控用） |
| `print_progress` | string | 否 | 打印进度传感器实体ID（实时监控用） |
| `current_weight` | string | 否 | 当前打印重量传感器实体ID（实时监控用） |
| `nozzle_temp` | string | 否 | 喷嘴温度传感器实体ID（实时监控用） |
| `bed_temp` | string | 否 | 热床温度传感器实体ID（实时监控用） |
| `chamber_temp` | string | 否 | 腔体温度传感器实体ID（实时监控用） |
| `active_tray` | string | 否 | 活跃料盘传感器实体ID（AMS显示用） |
| `power_consumption` | string | 否 | 实时功耗传感器实体ID |
| `speed_profile` | string | 否 | 速度配置传感器实体ID |
| `nozzle_size` | string | 否 | 喷嘴尺寸传感器实体ID |
| `ams_tray_1` ~ `ams_tray_4` | string | 否 | AMS料盘1-4传感器实体ID |
| `extra_print_histories` | list | 否 | 额外打印机历史列表，用于多打印机合并展示 |

---

## \ud83d\udcc8 五、传感器说明

集成会自动创建以下传感器（以配置时填写的打印机名称为前缀）：

| 传感器 | 数据类型 | 说明 |
|--------|---------|------|
| **{打印机名}_总打印次数** | 数值（累计） | 记录的总打印次数 |
| **{打印机名}_成功率** | 百分比 | 成功次数/总次数 |
| **{打印机名}_平均打印时长** | 小时 | 所有成功打印的平均时长 |
| **{打印机名}_打印总时长** | 小时（累计） | 所有打印的总时长 |
| **{打印机名}_总能耗** | kWh（累计） | 所有打印的总能耗 |
| **{打印机名}_终身耗材统计** | 文本 | 格式："总重量 Xg, 总长度 Xm" |
| **{打印机名}_7天耗材统计** | 文本 | 最近7天的耗材使用量 |
| **{打印机名}_30天耗材统计** | 文本 | 最近30天的耗材使用量 |
| **{打印机名}_打印时长分布** | JSON | 各时长区间的打印次数 |
| **{打印机名}_打印活动热力图** | JSON | 最近5周每日打印次数 |
| **{打印机名}_失败阶段分布** | JSON | 早期/中期/后期失败次数 |
| **{打印机名}_耗材成功率统计** | JSON | 每种耗材的成功率 |
| **{打印机名}_打印历史** | JSON数组 | 所有历史记录详情 |
| **{打印机名}_打印状态** | 文本 | 当前状态：打印中/空闲 |

---

## \ud83d\udcc8 六、服务说明

在 **开发者工具** → **服务** 中可以使用以下服务：

| 服务名称 | 参数 | 说明 |
|----------|------|------|
| `printer_analytics.refresh_stats` | `entity_id`（可选） | **刷新统计** — 强制从历史记录重新计算所有统计数据，适用于历史记录被手动修改后 |
| `printer_analytics.reset_history` | `entity_id`（必填） | **重置历史** — 清空所有打印历史记录（**不可逆**，请谨慎使用） |
| `printer_analytics.delete_history_records` | `entity_id`（必填）, `record_ids`（必填） | **删除指定记录** — 按记录ID删除指定的历史记录，支持逗号分隔的字符串或列表格式 |

---

## \ud83d\udcc8 七、多打印机配置

配置第二台（或更多）打印机的步骤：

1. 进入 **设置** → **设备与服务** → **添加集成** → 添加 **Printer Analytics**
2. 填写第二台打印机的配置（如名称 "A1mini"）
3. 添加完成后，会生成第二组传感器
4. 编辑第一台打印机的卡片配置，添加 `extra_print_histories`：

```yaml
type: custom:printer-analytics-card
title: \ud83d\udcfa 多打印机总览
mode:
printer_name: P2S
print_history: sensor.p2s_p2s_da_yin_li_shi
total_prints: sensor.p2s_p2s_zong_da_yin_ci_shu
success_rate: sensor.p2s_p2s_cheng_gong_lu
average_duration: sensor.p2s_p2s_ping_jun_da_yin_shi_chang
total_print_duration: sensor.p2s_p2s_da_yin_zong_shi_chang
total_energy: sensor.p2s_p2s_zong_neng_hao
material_stats_7d: sensor.p2s_p2s_7tian_hao_cai_tong_ji
material_stats_30d: sensor.p2s_p2s_30tian_hao_cai_tong_ji
duration_distribution: sensor.p2s_p2s_da_yin_shi_chang_fen_bu
activity_heatmap: sensor.p2s_p2s_da_yin_huo_dong_re_li_tu
print_status: sensor.p2s_p2s_da_yin_zhuang_tai

# 合并第二台打印机的历史记录
extra_print_histories:
  - entity: sensor.a1mini_a1mini_da_yin_li_shi
    name: A1mini
```

---

## \ud83d\udcc8 八、数据存储说明

### 存储路径

| 路径 | 内容 | HA快照包含 |
|------|------|-----------|
| `config/.printer_analytics/history_by_year/` | 主数据，按年份分片的JSON文件 | ❌ 否 |
| `config/.printer_analytics/archives/` | 每月压缩备份（.json.gz） | ❌ 否 |
| `config/www/printer_analytics_data/` | 自动同步的备份副本 | ✅ 是 |
| `config/www/printer_analytics/` | 打印封面图和快照图 | ✅ 是 |

### 数据恢复

如果重装系统或迁移HA，只需：
1. 从HA快照中恢复 `www/printer_analytics_data/` 和 `www/printer_analytics/` 目录
2. 重新添加 Printer Analytics 集成
3. 系统会自动检测备份目录并恢复历史数据

---

## \ud83d\udcc8 九、常见问题

**Q: 集成安装后没有数据？**

> 确保打印机集成（如 bambulab）已正确配置并能获取到数据。Printer Analytics 依赖打印机集成提供实体数据。打印完成后数据会自动记录。

**Q: 如何查看具体的打印详情？**

> 在卡片的历史视图中，点击任意一条记录，会弹出详情窗口，显示完整的打印信息，包括腔体温度、颜色切换记录等。

**Q: 多打印机合并后历史记录如何排序？**

> 默认按打印结束时间倒序排列（最新的在前），不同打印机的记录会按时间穿插混合显示。

**Q: 数据丢失如何恢复？**

> 如果之前有 `www/printer_analytics_data/` 的备份，重新添加集成后会自动恢复。如果备份也没有，历史上记录的数据将无法找回。

**Q: 支持哪些打印机？**

> 理论上支持所有通过HA集成提供标准实体（如打印状态、任务名称、温度等）的打印机。已测试：拓竹Bambu Lab全系列（P2S、X1、P1S、A1mini等）。

---

## \ud83d\udcc8 十、系统要求

- **Home Assistant** 2023.8.0 或更新版本
- 一个打印机集成（推荐 [bambu_lab](https://github.com/greghesp/ha-bambulab)）用于实体自动发现

---

## \ud83d\udcc8 许可证

MIT License
