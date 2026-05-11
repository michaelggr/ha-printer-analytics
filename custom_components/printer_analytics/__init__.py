from __future__ import annotations

import logging
from typing import Final, Optional

from homeassistant.components.lovelace import (
    DOMAIN as LOVELACE_DOMAIN,
    SERVICE_REFRESH,
    async_delete_config,
    async_get_config,
    async_save_config,
)
from homeassistant.components.websocket_api import (
    DOMAIN as WS_API_DOMAIN,
    async_register_commands,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PRINTER_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import async_get as async_get_device_registry
from homeassistant.helpers.storage import Store

from .const import (
    DOMAIN,
    _SUPERVISOR_DATA,
    ATTR_AWAIT_WORK,
    ATTR_TASK_GROUP,
    ATTR_WORK_TYPE,
    ATTR_TYPE_DASHBOARD_CONFIG,
    ATTR_TYPE_DASHBOARD_REFRESH,
    ATTR_TYPE_DELETE_CONFIG,
    ATTR_TYPE_REGISTER_LOVELACE_RESOURCE,
    ATTR_TYPE_SAVE_HISTORY,
    ATTR_TYPE_SET_ENTRY_TITLE,
    ATTR_TYPE_UPDATE_DEVICE_REGISTRY,
    ATTR_TYPE_WRITE_HISTORY,
    CONF_EXTRA_PRINT_HISTORY,
    CONF_PRINTERS,
    DASHBOARD_FILE,
    DATA_ENTITIES,
    DATA_ENTRY_IDS,
    DATA_WORKERS,
    EXTRA_PRINT_HISTORY,
    SERVICE_WRITE_HISTORY,
    SERVICE_SAVE_HISTORY,
    SERVICE_REGISTER_LOVELACE_RESOURCE,
    SERVICE_SET_ENTRY_TITLE,
    SERVICE_UPDATE_DEVICE_REGISTRY,
    SERVICE_YAML_UPDATE_DASHBOARD,
    WORK_TYPE_ASYNC,
    WORK_TYPE_AWAIT,
    WORK_TYPE_SYNC,
)
from .utils import _get_extra_print_history_config, _load_history_data

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    _LOGGER.info("Setting up Printer Analytics for %s", entry.data.get(CONF_PRINTER_NAME))

    if entry.entry_id in hass.data.get(DOMAIN, {}):
        _LOGGER.warning("Entry %s already loaded, ignoring", entry.entry_id)
        return False

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
        async_register_commands(hass)

    from .coordinator import PrinterAnalyticsCoordinator
    from .sensor import async_setup_entry as async_setup_sensors

    coordinator = PrinterAnalyticsCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry_ids = hass.data[DOMAIN].setdefault(DATA_ENTRY_IDS, [])
    if entry.entry_id not in entry_ids:
        entry_ids.append(entry.entry_id)

    hass.data[DOMAIN][entry.entry_id] = {
        DATA_ENTITIES: [],
        CONF_PRINTER_NAME: coordinator.printer_name,
        "coordinator": coordinator,
    }

    await async_setup_sensors(hass, entry, coordinator)

    from . import _async_register_services
    await _async_register_services(hass)

    await _async_write_history_entry(hass, coordinator)
    await _async_save_history_data(hass, entry.entry_id)
    await _register_lovelace_resource(hass)
    await _ensure_v52_resource(hass)

    await _generate_dashboard_yaml(hass)
    await _ensure_dashboard_registered(hass)

    # 设置设备图标（集成在HA集成页面显示的图标）
    try:
        dr_instance = async_get_device_registry(hass)
        device = dr_instance.async_get_device(identifiers={(DOMAIN, entry.entry_id)})
        if device:
            dr_instance.async_update_device(device.id, icon="mdi:chart-timeline-variant")
            _LOGGER.debug("设备图标已设置为 chart-timeline-variant")
    except Exception as err:
        _LOGGER.warning("设置设备图标失败: %s", err)

    _LOGGER.info("Printer Analytics setup for %s", entry.data.get(CONF_PRINTER_NAME))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    _LOGGER.info("Unloading Printer Analytics for %s", entry.data.get(CONF_PRINTER_NAME))

    from .sensor import async_unload_entry as unload_sensors
    success = await unload_sensors(hass, entry)

    workers = hass.data[DOMAIN].get(DATA_WORKERS, {})
    if entry.entry_id in workers:
        cancel = workers.pop(entry.entry_id, None)
        if cancel:
            cancel()

    entry_ids = hass.data[DOMAIN].get(DATA_ENTRY_IDS, [])
    if entry.entry_id in entry_ids:
        entry_ids.remove(entry.entry_id)

    if entry.entry_id in hass.data[DOMAIN]:
        del hass.data[DOMAIN][entry.entry_id]

    if not hass.data[DOMAIN].get(DATA_ENTRY_IDS):
        from . import _async_unregister_services
        await _async_unregister_services(hass)
        if DOMAIN in hass.data:
            del hass.data[DOMAIN]

    return success


async def _async_write_history_entry(hass: HomeAssistant, coordinator) -> None:
    history = coordinator.data.history if coordinator.data else []
    printers = hass.data.get(DOMAIN, {}).get(CONF_PRINTERS, {})
    printer_name = coordinator.printer_name

    entry_ids = hass.data.get(DOMAIN, {}).get(DATA_ENTRY_IDS, [])
    extra_history = []
    for eid in entry_ids:
        if eid == coordinator.entry.entry_id:
            continue
        cfg = printers.get(eid, {})
        extra = cfg.get(EXTRA_PRINT_HISTORY, {})
        if extra:
            extra_history.append({CONF_PRINTER_NAME: cfg.get(CONF_PRINTER_NAME, ""), EXTRA_PRINT_HISTORY: extra})

    await hass.services.async_call(
        SERVICE_WRITE_HISTORY,
        {"history": history, CONF_PRINTER_NAME: printer_name, EXTRA_PRINT_HISTORY: extra_history},
        blocking=True,
    )


async def _async_save_history_data(hass: HomeAssistant, entry_id: str) -> None:
    printers = hass.data.get(DOMAIN, {}).get(CONF_PRINTERS, {})
    cfg = printers.get(entry_id, {})
    extra = cfg.get(EXTRA_PRINT_HISTORY, {})

    await hass.services.async_call(
        SERVICE_SAVE_HISTORY,
        {CONF_PRINTER_NAME: cfg.get(CONF_PRINTER_NAME, ""), EXTRA_PRINT_HISTORY: extra},
        blocking=True,
    )


async def _register_lovelace_resource(hass: HomeAssistant) -> None:
    await hass.services.async_call(
        SERVICE_REGISTER_LOVELACE_RESOURCE,
        {CONF_PRINTER_NAME: "printer-analytics-card"},
        blocking=True,
    )


async def _ensure_v52_resource(hass: HomeAssistant) -> None:
    await hass.services.async_call(
        SERVICE_REGISTER_LOVELACE_RESOURCE,
        {CONF_PRINTER_NAME: "printer-analytics-card-v52"},
        blocking=True,
    )


async def _generate_dashboard_yaml(hass: HomeAssistant) -> None:
    printers = hass.data.get(DOMAIN, {}).get(CONF_PRINTERS, {})
    await hass.services.async_call(
        SERVICE_YAML_UPDATE_DASHBOARD,
        {CONF_PRINTERS: printers},
        blocking=True,
    )


async def _ensure_dashboard_registered(hass: HomeAssistant) -> None:
    dashboards = hass.data.get(DOMAIN, {}).get("dashboards", {})
    entry_ids = hass.data.get(DOMAIN, {}).get(DATA_ENTRY_IDS, [])
    printers = hass.data.get(DOMAIN, {}).get(CONF_PRINTERS, {})

    for entry_id in entry_ids:
        entry = hass.config_entries.async_get_entry(entry_id)
        if not entry:
            continue

        printer_name = printers.get(entry_id, {}).get(CONF_PRINTER_NAME, "")
        if not printer_name:
            printer_name = entry.data.get(CONF_PRINTER_NAME, "Printer")

        dashboard_key = f"printer_analytics_{entry_id}"

        config = {
            "mode": "yaml",
            "filename": DASHBOARD_FILE,
            "title": "打印机分析",
            "icon": "mdi:chart-timeline-variant",
            "show_in_sidebar": True,
        }

        dashboards[dashboard_key] = config
        hass.data[DOMAIN]["dashboards"] = dashboards

        _LOGGER.debug("Dashboard registered for %s: %s", printer_name, config)


async def async_update_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.services.async_call(
        SERVICE_SET_ENTRY_TITLE,
        {
            "entry_id": entry.entry_id,
            CONF_PRINTER_NAME: entry.data.get(CONF_PRINTER_NAME, ""),
        },
        blocking=True,
    )
    await _generate_dashboard_yaml(hass)
