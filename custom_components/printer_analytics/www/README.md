﻿﻿﻿# Printer Analytics Card

A custom Lovelace card for displaying printer analytics data in Home Assistant.

## Installation

### Method 1: Manual Installation

1. Copy the `printer-analytics-card.js` file to your Home Assistant's `www` directory.
2. In Home Assistant, go to Configuration → Lovelace Dashboards → Resources.
3. Click "Add Resource" and enter the URL: `/local/printer-analytics-card.js`.
4. Select "JavaScript Module" as the Resource Type.
5. Click "Create" to add the resource.

### Method 2: HACS Installation

1. Open HACS in Home Assistant.
2. Go to Frontend → Custom Repositories.
3. Add the repository URL: `https://github.com/user/printer_analytics`.
4. Select "Lovelace" as the Category.
5. Click "Add" to add the repository.
6. Search for "Printer Analytics Card" and install it.

## Configuration

### Basic Configuration

```yaml
type: custom:printer-analytics-card
entity: sensor.daheinu_print_history
```

### Advanced Configuration

```yaml
type: custom:printer-analytics-card
entity: sensor.daheinu_print_history
title: Printer Analytics
show_stats: true
show_history: true
```

### Configuration Options

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| entity | string | Yes | - | The printer analytics history sensor entity ID |
| title | string | No | "Printer Analytics" | The card title |
| show_stats | boolean | No | true | Whether to show the stats section |
| show_history | boolean | No | true | Whether to show the recent prints history |

## Usage

1. Open your Lovelace dashboard.
2. Click "Edit Dashboard" in the top right corner.
3. Click "Add Card" in the bottom right corner.
4. Search for "Printer Analytics Card" and select it.
5. Configure the card with your printer analytics sensor entity.
6. Click "Save" to add the card to your dashboard.
7. You can now drag and drop the card to any position on your dashboard.

## Screenshots

![Printer Analytics Card](https://example.com/printer-analytics-card.png)
