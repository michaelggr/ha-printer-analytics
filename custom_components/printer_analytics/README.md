# Printer Analytics

Track and analyze 3D printer data in Home Assistant.

## Features

- Track print history with detailed info (task name, layers, nozzle, bed type, filament, etc.)
- Time-dimension statistics (total prints, success rate, avg duration, energy, etc.)
- 7-day and 30-day period statistics
- Built-in Lovelace card with charts (no external dependencies!)
- Auto-download cover images and print snapshots
- Generate complete print info documents (JSON)
- Auto-discover printer entities from bambu_lab integration
- Bilingual UI (English + Chinese)

## Lovelace Card

The integration automatically deploys a custom card. Add it to your dashboard:

```yaml
type: custom:printer-analytics-card
entity: sensor.YOUR_PRINTER_print_history
title: My Printer Analytics
```

For full documentation, see the repository README.
