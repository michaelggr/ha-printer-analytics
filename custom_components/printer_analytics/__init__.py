from __future__ import annotations

import json
import logging
import os
import shutil

from homeassistant.components.lovelace import DOMAIN as LOVELACE_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.device_registry import async_get as async_get_device_registry
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry

from .const import (
    CONF_CHAMBER_TEMP_ENTITY,
    CONF_ENERGY_ENTITY,
    CONF_POWER_ENTITY,
    CONF_PRINTER_NAME,
    CONF_PRINT_STATUS_ENTITY,
    DOMAIN,
    SERVICE_REFRESH_STATS,
    SERVICE_RESET_HISTORY,
    SERVICE_DELETE_HISTORY_RECORDS,
)
from .coordinator import PrinterAnalyticsCoordinator

LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]

CARD_FILENAME = "printer-analytics-card.js"
HISTORY_CARD_FILENAME = "printer-history-list-card.js"
CARD_URL = f"/local/printer_analytics/{CARD_FILENAME}"
DASHBOARD_FILE = "ui-printer-analytics.yaml"

V52_CARD_URL = "/local/pa-v5.2.js?v=5.2"


async def _register_lovelace_resource(hass: HomeAssistant) -> None:
    component_dir = os.path.dirname(__file__)
    www_dir = hass.config.path("www", "printer_analytics")

    card_files = [CARD_FILENAME, HISTORY_CARD_FILENAME]

    def _copy_cards():
        os.makedirs(www_dir, exist_ok=True)
        for card_file in card_files:
            src = os.path.join(component_dir, "www", card_file)
            dst = os.path.join(www_dir, card_file)
            if os.path.exists(src):
                shutil.copy2(src, dst)
                LOGGER.info("Copied card to %s", dst)
            else:
                LOGGER.warning("Card source not found: %s", src)

    try:
        await hass.async_add_executor_job(_copy_cards)
    except Exception as err:
        LOGGER.error("Failed to copy cards: %s", err)
        return

    try:
        LOGGER.info("Cards copied to %s", www_dir)
    except Exception as err:
        LOGGER.warning("Failed to complete card setup: %s", err)


async def _ensure_v52_resource(hass: HomeAssistant) -> None:
    component_www = os.path.join(os.path.dirname(__file__), "www")
    src = os.path.join(component_www, "pa-v5.2.js")
    dst = hass.config.path("www", "pa-v5.2.js")

    def _copy_v52():
        if os.path.exists(src):
            shutil.copy2(src, dst)
            LOGGER.info("Copied pa-v5.2.js to www")
        elif not os.path.exists(dst):
            LOGGER.warning("pa-v5.2.js not found at %s or %s", src, dst)

    await hass.async_add_executor_job(_copy_v52)

    try:
        if LOVELACE_DOMAIN in hass.data:
            lovelace_data = hass.data[LOVELACE_DOMAIN]
            resources = getattr(lovelace_data, 'resources', None)
            if resources is None and isinstance(lovelace_data, dict):
                resources = lovelace_data.get("resources")
            if resources and hasattr(resources, "async_create"):
                exists = any(
                    r.get("url", "").startswith("/local/pa-v5.2.js")
                    for r in (resources.async_items() if hasattr(resources, "async_items") else [])
                )
                if not exists:
                    await resources.async_create({"url": V52_CARD_URL, "type": "module"})
                    LOGGER.info("Registered pa-v5.2.js as Lovelace resource")
    except Exception as err:
        LOGGER.warning("Could not register resource: %s", err)


async def _generate_dashboard_yaml(hass: HomeAssistant) -> None:
    entry_ids = list(hass.data.get(DOMAIN, {}).keys())
    if not entry_ids:
        LOGGER.warning("No printer analytics entries found, skipping dashboard YAML generation")
        return

    entity_reg = async_get_entity_registry(hass)
    printers = []

    for entry_id in entry_ids:
        coordinator = hass.data[DOMAIN].get(entry_id)
        if not coordinator or not hasattr(coordinator, "printer_name"):
            continue
        printer_name = coordinator.printer_name
        slug = printer_name.lower().replace(" ", "_")

        def _find_entity(sensor_key: str) -> str:
            for entity in entity_reg.entities.values():
                if entity.config_entry_id == entry_id and entity.unique_id == f"{entry_id}_{sensor_key}":
                    return entity.entity_id
            return ""

        entity_ids = {
            "print_history": _find_entity("print_history"),
            "total_prints": _find_entity("total_prints"),
            "success_rate": _find_entity("success_rate"),
            "average_duration": _find_entity("average_duration"),
            "total_print_duration": _find_entity("total_print_duration"),
            "total_energy": _find_entity("total_energy"),
            "material_stats_7d": _find_entity("material_stats_7d"),
            "material_stats_30d": _find_entity("material_stats_30d"),
            "material_stats_lifetime": _find_entity("material_stats_lifetime"),
            "duration_distribution": _find_entity("duration_distribution"),
            "activity_heatmap": _find_entity("activity_heatmap"),
            "failure_stage_distribution": _find_entity("failure_stage_distribution"),
            "filament_success_stats": _find_entity("filament_success_stats"),
            "print_status": _find_entity("print_status"),
        }
        printers.append({
            "printer_name": printer_name,
            "slug": slug,
            "entity_ids": entity_ids,
        })

    lines = ["title: 打印机分析", "views:"]

    for p in printers:
        e = p["entity_ids"]
        lines.append(f"""
  - title: "{p['printer_name']}打印机"
    icon: mdi:printer-3d
    path: {p['slug']}
    cards:
      - type: custom:printer-analytics-card
        title: "🖨️ {p['printer_name']}打印机分析"
        mode: stats
        printer_name: {p['printer_name']}
        print_history: {e['print_history']}
        total_prints: {e['total_prints']}
        success_rate: {e['success_rate']}
        average_duration: {e['average_duration']}
        total_print_duration: {e['total_print_duration']}
        total_energy: {e['total_energy']}
        material_stats_7d: {e['material_stats_7d']}
        material_stats_30d: {e['material_stats_30d']}
        material_stats_lifetime: {e['material_stats_lifetime']}
        duration_distribution: {e['duration_distribution']}
        activity_heatmap: {e['activity_heatmap']}
        failure_stage_distribution: {e['failure_stage_distribution']}
        filament_success_stats: {e['filament_success_stats']}
        print_status: {e['print_status']}")

    all_history_entities = [p for p in printers if p["entity_ids"]["print_history"]]
    if all_history_entities:
        first_p = all_history_entities[0]
        lines.append(f"""
  - title: 全部历史
    icon: mdi:history
    path: all-history
    cards:
      - type: custom:printer-analytics-card
        title: "🗂️ 全部打印历史"
        mode: history
        printer_name: 全部打印机
        print_history: {first_p['entity_ids']['print_history']}")

        if len(all_history_entities) > 1:
            lines[-1] += "\n        extra_print_histories:"
            for p in all_history_entities[1:]:
                lines[-1] += f"""
          - entity: {p['entity_ids']['print_history']}
            name: {p['printer_name']}"""

    yaml_content = "\n".join(lines)

    def _write():
        filepath = hass.config.path(DASHBOARD_FILE)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(yaml_content)
        LOGGER.info("Generated dashboard YAML: %s", filepath)

    await hass.async_add_executor_job(_write)


async def _ensure_dashboard_registered(hass: HomeAssistant) -> None:
    try:
        if LOVELACE_DOMAIN not in hass.data:
            LOGGER.warning("Lovelace component not available, skipping dashboard registration")
            return

        lovelace_data = hass.data[LOVELACE_DOMAIN]
        dashboards = getattr(lovelace_data, 'dashboards', None)
        if dashboards is None and isinstance(lovelace_data, dict):
            dashboards = lovelace_data.get("dashboards")
        if not dashboards:
            LOGGER.warning("Lovelace dashboards not available")
            return

        dashboard_id = "printer-analytics"

        async def _create_or_update():
            exists = dashboard_id in dashboards
            config = {
                "mode": "yaml",
                "filename": DASHBOARD_FILE,
                "title": "打印机分析",
                "icon": "mdi:chart-timeline-variant",
                "show_in_sidebar": True,
            }

            if hasattr(dashboards, "async_create_or_update"):
                await dashboards.async_create_or_update(dashboard_id, config)
            elif hasattr(dashboards, "async_create") and not exists:
                await dashboards.async_create(dashboard_id, config)

            if not exists:
                LOGGER.info("已自动创建打印机分析仪表板")
            else:
                LOGGER.debug("打印机分析仪表板已存在")

        await _create_or_update()
    except Exception as err:
        LOGGER.warning("Could not register dashboard: %s", err)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = PrinterAnalyticsCoordinator(hass, entry)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await coordinator.async_setup()
    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    _register_services(hass)

    await _register_lovelace_resource(hass)
    await _ensure_v52_resource(hass)

    await _generate_dashboard_yaml(hass)
    await _ensure_dashboard_registered(hass)

    try:
        dr = async_get_device_registry(hass)
        device = dr.async_get_device(identifiers={(DOMAIN, entry.entry_id)})
        if device:
            supported_kwargs = {}
            if "icon" in dr.async_update_device.__code__.co_varnames:
                supported_kwargs["icon"] = "mdi:chart-timeline-variant"
            if supported_kwargs:
                dr.async_update_device(device.id, **supported_kwargs)
                LOGGER.debug("设备图标已设置")
    except Exception as err:
        LOGGER.debug("设置设备图标跳过: %s", err)

    LOGGER.info("Printer Analytics setup for %s", entry.data.get(CONF_PRINTER_NAME))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator: PrinterAnalyticsCoordinator | None = hass.data[DOMAIN].get(
        entry.entry_id
    )
    if coordinator:
        await coordinator.async_shutdown()
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok and entry.entry_id in hass.data.get(DOMAIN, {}):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


def _register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_REFRESH_STATS):
        return

    async def _handle_refresh_stats(call: ServiceCall) -> None:
        coordinator = _get_coordinator_from_call(hass, call)
        if coordinator:
            await coordinator.async_request_refresh()
            LOGGER.info("Stats refreshed for %s", coordinator.printer_name)
            LOGGER.info("Entity map for %s: %s", coordinator.printer_name, coordinator._entity_map)

    async def _handle_reset_history(call: ServiceCall) -> None:
        coordinator = _get_coordinator_from_call(hass, call)
        if coordinator:
            await coordinator.async_reset_history()
            LOGGER.info("History reset for %s", coordinator.printer_name)

    async def _handle_delete_history_records(call: ServiceCall) -> None:
        coordinator = _get_coordinator_from_call(hass, call)
        if coordinator:
            record_ids_raw = call.data.get("record_ids", "")
            if isinstance(record_ids_raw, str):
                record_ids = [rid.strip() for rid in record_ids_raw.split(",") if rid.strip()]
            elif isinstance(record_ids_raw, list):
                record_ids = record_ids_raw
            else:
                record_ids = []
            deleted = await coordinator.async_delete_history_records(record_ids)
            LOGGER.info("Deleted %d history records for %s", deleted, coordinator.printer_name)

    hass.services.async_register(DOMAIN, SERVICE_REFRESH_STATS, _handle_refresh_stats)
    hass.services.async_register(DOMAIN, SERVICE_RESET_HISTORY, _handle_reset_history)
    hass.services.async_register(DOMAIN, SERVICE_DELETE_HISTORY_RECORDS, _handle_delete_history_records)


def _get_coordinator_from_call(
    hass: HomeAssistant, call: ServiceCall
) -> PrinterAnalyticsCoordinator | None:
    entity_id = call.data.get(ATTR_ENTITY_ID)
    if not entity_id:
        return None
    if isinstance(entity_id, list):
        entity_id = entity_id[0]
    for entry_id, coordinator in hass.data.get(DOMAIN, {}).items():
        if isinstance(coordinator, PrinterAnalyticsCoordinator):
            return coordinator
    return None
