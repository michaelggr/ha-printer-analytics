# Printer Analytics

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/v/release/michaelggr/ha-printer-analytics)](https://github.com/michaelggr/ha-printer-analytics)

A Home Assistant custom integration for tracking and analyzing 3D printer data. Works with Bambu Lab and other printer integrations.

**[中文文档](#中文说明)**

## Features

- 🖨️ Track print history with detailed info (task name, layers, nozzle, bed type, filament, etc.)
- 📊 Time-dimension statistics (total prints, success rate, avg duration, energy, etc.)
- 📅 7-day and 30-day period statistics with 8 metrics each
- 📈 Built-in Lovelace card with charts (no external dependencies!)
  - Success rate trend (SVG line chart)
  - Print duration distribution (bar chart)
  - Activity heatmap
  - Filament type & color usage (pie charts)
- 📸 Auto-download cover images and print snapshots
- 📄 Generate complete print info documents (JSON)
- 🔌 Auto-discover printer entities from bambu_lab integration
- 🌐 Bilingual UI (English + Chinese)

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
   - **Printer Name**: A name for your printer (e.g., "Bambu X1C")
   - **Print Status Sensor**: Select the print status entity from your printer integration (e.g., `sensor.bambu_lab_print_status`)
   - **Power Sensor** (optional): Select a power sensor
   - **Energy Sensor** (optional): Select an energy sensor

## Lovelace Card

The integration automatically deploys a custom Lovelace card when you add the integration. No manual installation needed!

### Usage

Add a custom card in your Lovelace dashboard (requires full entity configuration):

```yaml
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
```

### Card Features

| Section | Description |
|---------|-------------|
| 📊 Time Dimension Stats | 6 key metrics at a glance |
| 📅 7-Day / 30-Day Stats | 8 metrics in table format |
| 📈 Success Rate Trend | Cumulative success rate over time |
| 📊 Duration Distribution | Print count by time bucket |
| 🗓️ Activity Heatmap | Daily print activity (last 5 weeks) |
| 🎨 Filament Type Usage | Pie chart by filament type |
| 🎨 Filament Color Usage | Pie chart by filament color |

## Sensors

| Sensor | Description |
|--------|-------------|
| `sensor.{name}_total_prints` | Total number of prints |
| `sensor.{name}_success_rate` | Print success rate (%) |
| `sensor.{name}_average_duration` | Average print duration (min) |
| `sensor.{name}_total_online_duration` | Total online duration (h) |
| `sensor.{name}_total_energy` | Total energy consumption (kWh) |
| `sensor.{name}_material_stats_lifetime` | Lifetime material statistics |
| `sensor.{name}_material_stats_7d` | 7-day material statistics |
| `sensor.{name}_material_stats_30d` | 30-day material statistics |
| `sensor.{name}_duration_distribution` | Print duration distribution |
| `sensor.{name}_activity_heatmap` | Print activity heatmap |
| `sensor.{name}_print_history` | Print history records |
| `sensor.{name}_print_status` | Current print status |

## Services

| Service | Description |
|---------|-------------|
| `printer_analytics.refresh_stats` | Force recalculate all statistics |
| `printer_analytics.reset_history` | Clear all print history |

## Data Storage

- Print history: `config/.printer_analytics/`
- Cover images & snapshots: `config/www/printer_analytics/`
- Print info documents: `config/www/printer_analytics/print_info/`

## Requirements

- Home Assistant 2023.8.0 or later
- A printer integration (e.g., [bambu_lab](https://github.com/greghesp/ha-bambulab)) for entity discovery

---

<a id="中文说明"></a>

## 中文说明

Home Assistant 自定义集成，用于跟踪和分析 3D 打印机数据。支持拓竹（Bambu Lab）及其他打印机集成。

### 功能

- 🖨️ 记录打印历史（任务名称、层数、喷嘴、打印床类型、耗材等）
- 📊 时间维度统计（总打印次数、成功率、平均时长、能耗等）
- 📅 7天/30天周期统计，各含 8 个指标
- 📈 内置 Lovelace 卡片，无需外部依赖
  - 成功率趋势（SVG 折线图）
  - 时长分布（柱状图）
  - 活动热力图
  - 耗材类型/颜色使用量（饼图）
- 📸 自动下载封面图和打印快照
- 📄 生成完整打印信息文档（JSON）
- 🔌 自动发现 bambu_lab 集成的打印机实体
- 🌐 中英文双语界面

### 安装

1. 在 HACS 中添加自定义仓库：`https://github.com/michaelggr/ha-printer-analytics`
2. 搜索 "Printer Analytics" 并安装
3. 重启 Home Assistant

### 配置

1. 进入 **设置** → **设备与服务** → **添加集成**
2. 搜索 **"Printer Analytics"**
3. 填写打印机名称、选择打印状态传感器等

### Lovelace 卡片

在仪表盘中添加自定义卡片（需要配置所有实体）：

```yaml
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
```

集成安装后自动部署卡片，在仪表板中添加：

```yaml
type: custom:printer-analytics-card
entity: sensor.你的打印机_print_history
title: 我的打印机分析
```

## License

MIT License
