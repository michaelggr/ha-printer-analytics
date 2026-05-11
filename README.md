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
- **Chamber Temperature** — Record chamber temperature during the last 5 minutes of printing (avg/max/min). Supports any temperature sensor.
- **Multi-color Detection** — Auto-detect filament changes during printing

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
- **Auto-Generated** — Card YAML is auto-generated with all entity IDs filled in automatically
- **Modern Glass-morphism Design** — Gradient backgrounds, smooth animations, responsive layout
- **Three Display Modes**: `stats` / `history` / tab switching
- **Multi-Printer Support** — Merge history from multiple printers
- **Real-time Monitor** — Live nozzle/bed/chamber temperature, progress, AMS trays, power
- **Advanced Filtering** — Filter by status + date range + color + keyword search
- **Pagination** — 20 records per page for large datasets
- **Detail Modal** — Full print details including chamber temperature
- **CSV Export** — Excel-compatible CSV export
- **Batch Delete** — Multi-select with confirmation

### \ud83d\udcbe Data Safety
- **100-Year Storage** — Data stored by year in separate JSON files
- **Auto Backup Sync** — Data synced to `www/printer_analytics_data/` (included in HA snapshots)
- **Compressed Archives** — Monthly gzip backups, keeps last 12
- **Auto Restore** — Automatically restore from backup on reinstall
- **Legacy Migration** — Auto-migrate old single-file data to year-sharded format

## Installation

### HACS (Recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=michaelggr&repository=ha-printer-analytics&category=integration)

1. Go to **HACS** -> **Integrations**
2. Click three dots -> **Custom repositories**
3. Enter `https://github.com/michaelggr/ha-printer-analytics`, select **Integration**
4. Click **Add** -> Search "Printer Analytics" and install
5. Restart Home Assistant

### Manual

1. Download [latest release](https://github.com/michaelggr/ha-printer-analytics/releases)
2. Copy `custom_components/printer_analytics/` to your HA's `custom_components/`
3. Restart Home Assistant

## Configuration

1. Go to **Settings** -> **Devices & Services** -> **Add Integration**
2. Search **"Printer Analytics"** and click it
3. Fill in:

| Field | Required | Description |
|-------|----------|-------------|
| **Printer Name** | Yes | A friendly name, e.g., "Bambu P2S" |
| **Print Status Sensor** | Yes | Select the print status entity from your printer integration |
| **Power Sensor** | No | Select a power sensor for consumption tracking |
| **Energy Sensor** | No | Select an cumulative energy sensor |
| **Chamber Temperature Sensor** | No | Select any temperature sensor to record chamber temp during prints |

After submitting, the integration will:
- Discover all related entities from the same printer device
- Create all 14 statistical sensors
- Generate the dashboard YAML file (`ui-printer-analysis.yaml`)

> You need to add the dashboard to HA's `configuration.yaml` under `lovelace: dashboards:` for it to appear in the sidebar. Example:
> ```yaml
> lovelace:
>   dashboards:
>     printer-analytics:
>       mode: yaml
>       filename: ui-printer-analysis.yaml
>       title: 打印机分析
>       icon: mdi:chart-timeline-variant
>       show_in_sidebar: true
> ```

### How Auto-Discovery Works

The integration uses the **Print Status Sensor** to identify your printer device, then automatically finds all other entities belonging to that same device (nozzle temp, bed temp, progress, AMS trays, etc.) and maps them to the corresponding statistical sensors.

### Multiple Printers

Repeat the configuration for each printer. Each printer gets its own set of sensors. The history view merges all printers' records automatically.

## Dashboard

The integration generates `ui-printer-analysis.yaml` which contains both a statistics view and an all-history view. Add it to `configuration.yaml` as shown above.

To manually add the card to any other dashboard:

```yaml
type: custom:printer-analytics-card
```

All entity IDs are auto-filled by the generated YAML.

## Sensors

| Sensor | Description |
|--------|-------------|
| `sensor.{name}_total_prints` | Total print count |
| `sensor.{name}_success_rate` | Success rate (%) |
| `sensor.{name}_average_duration` | Average print duration (hours) |
| `sensor.{name}_total_print_duration` | Cumulative print hours |
| `sensor.{name}_total_energy` | Cumulative energy (kWh) |
| `sensor.{name}_material_stats_lifetime` | Lifetime filament: weight + length |
| `sensor.{name}_material_stats_7d` | 7-day filament stats |
| `sensor.{name}_material_stats_30d` | 30-day filament stats |
| `sensor.{name}_duration_distribution` | Print count by duration bucket |
| `sensor.{name}_activity_heatmap` | Daily activity (5 weeks) |
| `sensor.{name}_failure_stage_distribution` | Failure stage analysis |
| `sensor.{name}_filament_success_stats` | Success rate by filament type |
| `sensor.{name}_print_history` | All history records (JSON array) |
| `sensor.{name}_print_status` | Current status: printing/idle |

## Services

| Service | Description |
|---------|-------------|
| `printer_analytics.refresh_stats` | Force recalculate all statistics |
| `printer_analytics.reset_history` | Clear all history (irreversible) |
| `printer_analytics.delete_history_records` | Delete specific records by ID |

## Data Storage

| Path | Description | In HA Snapshot |
|------|-------------|----------------|
| `config/.printer_analytics/history_by_year/` | Main data (year-sharded) | No |
| `config/.printer_analytics/archives/` | Monthly backups (.json.gz) | No |
| `config/www/printer_analytics_data/` | Auto-synced backup | Yes |
| `config/www/printer_analytics/` | Cover images & snapshots | Yes |

## Requirements

- Home Assistant 2023.8.0+
- A printer integration (e.g., [bambu_lab](https://github.com/greghesp/ha-bambulab))

## License

MIT License

---

<a id="中文说明"></a>

## 中文说明

**Printer Analytics** 是 Home Assistant 自定义集成，用于自动追踪和分析 3D 打印机数据。支持拓竹（Bambu Lab）全系列及其他打印机集成。

**[English Documentation](#printer-analytics)**

---

## \ud83d\udcda 一、功能特性

### \ud83d\udcc8 数据追踪

| 功能 | 说明 |
|------|------|
| **打印历史自动记录** | 每次打印完成后自动记录：任务名、耗材类型/颜色/重量/长度、时长、能耗、温度、速度配置、AMS料盘等 |
| **封面图与快照** | 自动下载打印封面图和过程中拍摄的快照图 |
| **打印信息文档** | 为每次打印生成完整的 JSON 打印信息文档 |
| **腔体温度记录** | 记录打印结束前5分钟的腔体温度（平均/最高/最低）。可选任意温度计传感器，不限打印机型号 |
| **多色打印检测** | 自动检测打印过程中的耗材切换 |

### \ud83d\udcc8 统计分析

| 功能 | 说明 |
|------|------|
| **终身统计** | 总次数、成功率、平均时长、总时长、总重量、总长度、总能耗、质量评级 |
| **7天/30天周期统计** | 每个周期8项耗材指标表格展示 |
| **成功率趋势图** | 累计成功率折线图 |
| **时长分布图** | 按时间段统计打印数量 |
| **活动热力图** | 最近5周每日打印活跃度 |
| **耗材使用饼图** | 按耗材类型和颜色分类展示 |
| **失败阶段分析** | 按失败时进度阶段统计分析 |
| **耗材成功率** | 每种耗材的成功率与使用量 |

### \ud83d\udcda Lovelace 卡片 (v5.2)

| 特性 | 说明 |
|------|------|
| **自动生成** | 卡片 YAML 全自动生成，所有 entity_id 自动填入 |
| **现代玻璃拟态设计** | 渐变背景、流畅动画、响应式布局 |
| **三种显示模式** | `stats`=统计 / `history`=历史 / Tab切换 |
| **多打印机合并** | 多台打印机历史记录合并展示 |
| **实时监控** | 温度、进度、AMS料盘、功耗实时显示 |
| **高级筛选** | 状态 + 日期范围 + 颜色 + 关键词搜索 |
| **CSV导出** | 筛选结果导出为Excel兼容CSV |
| **批量删除** | 勾选多条记录一键删除 |

---

## \ud83d\udcc8 二、安装

### HACS 安装（推荐）

1. 进入 **HACS** -> **集成**
2. 点击右上角 **三个点** -> **自定义仓库**
3. 填入 `https://github.com/michaelggr/ha-printer-analytics`，类别选 **集成**
4. 点击 **添加** -> 搜索 "Printer Analytics" 安装
5. 重启 Home Assistant

### 手动安装

1. 从 [GitHub Releases](https://github.com/michaelggr/ha-printer-analytics/releases) 下载最新版本
2. 将 `custom_components/printer_analytics/` 复制到 HA 的 `custom_components/` 目录
3. 重启 Home Assistant

---

## \ud83d\udcc8 三、配置

1. 进入 **设置** -> **设备与服务** -> **添加集成**
2. 搜索 **"Printer Analytics"** 点击
3. 填写表单：

| 配置项 | 必填 | 说明 |
|--------|------|------|
| **打印机名称** | 是 | 给打印机起个名字，如 "Bambu P2S" |
| **打印状态传感器** | 是 | 从下拉列表选择打印机集成提供的打印状态实体 |
| **功率传感器** | 否 | 用于记录打印实时功耗 |
| **能耗传感器** | 否 | 用于统计总能耗 |
| **腔体温度传感器** | 否 | 可选任意温度计传感器，不限打印机型号。如外接温湿度计、打印机自带腔体温度等 |

4. 点击 **提交**

### 集成自动完成的工作

- \u2705 根据打印状态传感器所在设备，自动发现同设备所有相关实体（喷嘴温度、热床温度、打印进度、AMS料盘等）
- \u2705 自动创建所有统计传感器（总打印次数、成功率、耗材统计、活动热力图等14个）
- \u2705 自动生成仪表板 YAML 文件 `ui-printer-analysis.yaml`

### 侧边栏配置

生成的 YAML 文件需要配置到 HA 中才能显示在侧边栏。在 `configuration.yaml` 中添加：

```yaml
lovelace:
  dashboards:
    printer-analytics:
      mode: yaml
      filename: ui-printer-analysis.yaml
      title: 打印机分析
      icon: mdi:chart-timeline-variant
      show_in_sidebar: true
```

配置完成后重启 HA，侧边栏就会出现"打印机分析"入口。

### 多打印机配置

再次进入 **添加集成** -> **Printer Analytics**，填写第二台打印机的名称和打印状态传感器。每台打印机独立统计，历史视图会自动合并所有打印机的记录。

---

## \ud83d\udcc8 四、仪表板

配置完成后，`ui-printer-analysis.yaml` 包含以下视图：

- **统计视图**：成功率趋势、时长分布、活动热力图、耗材饼图、失败阶段分析等
- **历史视图**：全部打印历史，支持筛选、搜索、分页、详情弹窗、CSV导出、批量删除

### 手动添加到其他仪表板

集成已自动注册 `printer-analytics-card` 组件，可以在任意仪表板手动添加：

```yaml
type: custom:printer-analytics-card
```

---

## \ud83d\udcc8 五、传感器

| 传感器 | 说明 |
|--------|------|
| **{打印机名}_总打印次数** | 累计打印次数 |
| **{打印机名}_成功率** | 成功次数/总次数 |
| **{打印机名}_平均打印时长** | 所有成功打印的平均时长 |
| **{打印机名}_打印总时长** | 累计打印时长 |
| **{打印机名}_总能耗** | 累计能耗 (kWh) |
| **{打印机名}_终身耗材统计** | 格式："总重量 Xg, 总长度 Xm" |
| **{打印机名}_7天耗材统计** | 最近7天耗材使用量 |
| **{打印机名}_30天耗材统计** | 最近30天耗材使用量 |
| **{打印机名}_打印时长分布** | 各时长区间的打印次数 |
| **{打印机名}_打印活动热力图** | 最近5周每日打印次数 |
| **{打印机名}_失败阶段分布** | 早期/中期/后期失败次数 |
| **{打印机名}_耗材成功率统计** | 每种耗材的成功率 |
| **{打印机名}_打印历史** | 所有历史记录（JSON数组） |
| **{打印机名}_打印状态** | 当前状态：打印中/空闲 |

---

## \ud83d\udcc8 六、服务

| 服务 | 说明 |
|------|------|
| `printer_analytics.refresh_stats` | 强制重新计算所有统计数据 |
| `printer_analytics.reset_history` | 清空所有历史记录（不可逆） |
| `printer_analytics.delete_history_records` | 按ID删除指定的历史记录 |

---

## \ud83d\udcc8 七、数据存储

| 路径 | 内容 | HA快照 |
|------|------|--------|
| `config/.printer_analytics/history_by_year/` | 主数据，按年份分片 | 否 |
| `config/.printer_analytics/archives/` | 每月压缩备份 | 否 |
| `config/www/printer_analytics_data/` | 自动同步备份副本 | 是 |
| `config/www/printer_analytics/` | 封面图和快照 | 是 |

### 数据恢复

重装系统后：
1. 从HA快照恢复 `www/printer_analytics_data/` 和 `www/printer_analytics/` 目录
2. 重新添加 Printer Analytics 集成
3. 系统自动检测备份并恢复历史数据

---

## \ud83d\udcc8 八、常见问题

**Q: 配置时找不到打印状态传感器？**

> 确保打印机集成（如 bambulab）已正确配置并正常上报数据。

**Q: 集成安装后没有数据？**

> 正常现象。数据会在**每次打印完成后**自动记录。正在打印的任务可在统计页的"当前打印"区域看到实时进度。

**Q: 腔体温度支持哪些打印机？**

> 所有打印机都支持。这是一个可选配置项，你可以选择任意温度传感器（如打印机自带腔体温度、外接温湿度计等），系统会在打印结束前5分钟自动记录温度数据。

**Q: 多台打印机如何配置？**

> 多次添加 Printer Analytics 集成即可。每台打印机独立统计，历史视图自动合并。

**Q: 侧边栏没有"打印机分析"入口？**

> 需要在 `configuration.yaml` 的 `lovelace: dashboards:` 下添加配置（见第三章）。配置后重启 HA 即可。

**Q: 支持哪些打印机？**

> 理论上支持所有提供标准HA实体的打印机。已测试：拓竹Bambu Lab全系列（P2S、X1、P1S、A1mini等）。

---

## \ud83d\udcc8 九、系统要求

- Home Assistant 2023.8.0 或更新版本
- 一个打印机集成（推荐 [bambu_lab](https://github.com/greghesp/ha-bambulab)）

---

## \ud83d\udcc8 十、许可证

MIT License
