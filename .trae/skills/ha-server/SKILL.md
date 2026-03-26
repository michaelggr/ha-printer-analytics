---
name: "ha-server"
description: "Performs server operations for Home Assistant using connection info from .ha_connection_info.json. Invoke when user needs to upload files, restart services, or interact with the Home Assistant server."
---

# HA Server Operations

This skill provides operations for interacting with the Home Assistant server using connection information stored in `.ha_connection_info.json`.

## Connection Information

Uses the following connection details from `.ha_connection_info.json`:

- **Home Assistant API**: http://192.168.0.130:8123/ with token
- **Samba Share**: \\192.168.0.130\config with username ha

## Available Operations

1. **Upload Files**: Upload configuration files to the Home Assistant server
2. **Restart Services**: Restart Home Assistant or related services
3. **API Calls**: Make API calls to the Home Assistant server
4. **Configuration Management**: Manage Home Assistant configuration files

## Usage Examples

- "Upload configuration.yaml to the server"
- "Restart Home Assistant service"
- "Check Home Assistant status"

