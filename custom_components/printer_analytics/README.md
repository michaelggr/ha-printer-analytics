# Printer Analytics

Track and analyze your 3D printer data in Home Assistant. Works seamlessly with Bambu Lab printers (P2S, A1 Mini, etc.) via the `bambu_lab` integration.

## Features

- **Print History Tracking** - Complete print records with task name, layers, nozzle type, bed type, filament, and more
- **Time-Dimension Statistics** - Total prints, success rate, average duration, energy consumption
- **Period Statistics** - 7-day and 30-day aggregated data
- **Built-in Lovelace Card** - Beautiful charts and visualizations, no external dependencies
- **Auto Cover Images** - Download and display print snapshots automatically
- **Auto-Discovery** - Automatically detects printer entities from `bambu_lab` integration
- **Bilingual UI** - Supports English and Chinese

## Supported Printers

- Bambu Lab P2S
- Bambu Lab A1 Mini
- Other printers via custom configuration

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Go to Integrations
3. Search for "Printer Analytics"
4. Click Install

### Manual Installation

1. Copy the `printer_analytics` folder to your `custom_components` directory
2. Restart Home Assistant

## Configuration

### Through UI

1. Go to Settings → Devices & Services → Add Integration
2. Search for "Printer Analytics"
3. Configure the printer name and print status entity

### Options

| Option | Description | Required |
|--------|-------------|----------|
| Printer Name | Display name for your printer | Yes |
| Print Status Entity | Sensor entity for print status (e.g., `sensor.p2s_xxx_print_status`) | Yes |
| Power Entity | Optional power sensor entity | No |
| Energy Entity | Optional energy consumption sensor | No |
| Chamber Temp Entity | Optional chamber temperature sensor | No |

## Lovelace Card

After installation, the integration automatically creates a dashboard. Access it from the sidebar under "打印机分析" (Printer Analytics).

### Manual Card Configuration

```yaml
type: custom:printer-analytics-card
title: "Printer Analytics"
print_history: sensor.p2s_p2s_da_yin_li_shi
print_status: sensor.p2s_p2s_da_yin_zhuang_tai
current_task: sensor.p2s_xxx_task_name
print_progress: sensor.p2s_xxx_print_progress
nozzle_temp: sensor.p2s_xxx_nozzle_temperature
bed_temp: sensor.p2s_xxx_bed_temperature
```

## Services

The integration provides the following services:

| Service | Description |
|---------|-------------|
| `printer_analytics.refresh_stats` | Refresh statistics |
| `printer_analytics.reset_history` | Reset print history |
| `printer_analytics.delete_history_records` | Delete specific history records |
| `printer_analytics.backfill_cover_images` | Download missing cover images |

## Troubleshooting

### No entities found

Make sure the `bambu_lab` integration is properly configured and your printer is online.

### Card not displaying

Ensure the `printer-analytics-card.js` resource is loaded in your Lovelace configuration.

## Support

- Report issues: [GitHub Issues](https://github.com/michaelggr/ha-printer-analytics/issues)
- Documentation: [Wiki](https://github.com/michaelggr/ha-printer-analytics/wiki)

## License

MIT License
