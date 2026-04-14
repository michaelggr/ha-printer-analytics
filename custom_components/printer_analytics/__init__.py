from __future__ import annotations

import logging
import os
import shutil

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall

from .const import (
    CONF_ENERGY_ENTITY,
    CONF_POWER_ENTITY,
    CONF_PRINTER_NAME,
    CONF_PRINT_STATUS_ENTITY,
    DOMAIN,
    SERVICE_REFRESH_STATS,
    SERVICE_RESET_HISTORY,
)
from .coordinator import PrinterAnalyticsCoordinator

LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]

CARD_FILENAME = "printer-analytics-card.js"
CARD_URL = f"/local/printer_analytics/{CARD_FILENAME}"


async def _register_lovelace_resource(hass: HomeAssistant) -> None:
    """将自定义卡片 JS 复制到 www 并注册为 Lovelace 资源"""
    component_dir = os.path.dirname(__file__)
    src = os.path.join(component_dir, "www", CARD_FILENAME)
    www_dir = hass.config.path("www", "printer_analytics")
    dst = os.path.join(www_dir, CARD_FILENAME)

    def _copy_card():
        os.makedirs(www_dir, exist_ok=True)
        if os.path.exists(src):
            shutil.copy2(src, dst)
            LOGGER.info("Copied card to %s", dst)
        else:
            LOGGER.warning("Card source not found: %s", src)

    try:
        await hass.async_add_executor_job(_copy_card)
    except Exception as err:
        LOGGER.error("Failed to copy card: %s", err)
        return

    # 注册 Lovelace 资源
    try:
        from homeassistant.components.lovelace import DOMAIN as LOVELACE_DOMAIN
        resources = hass.data.get(LOVELACE_DOMAIN, {}).get("resources")
        if resources is None:
            return

        existing = [
            r for r in resources.async_items()
            if r.get("url") == CARD_URL
        ]
        if not existing:
            resources.async_create_item({
                "res_type": "module",
                "url": CARD_URL,
            })
            LOGGER.info("Registered Lovelace resource: %s", CARD_URL)
        else:
            LOGGER.info("Lovelace resource already registered: %s", CARD_URL)
    except Exception as err:
        LOGGER.warning("Failed to register Lovelace resource (card still works if manually added): %s", err)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = PrinterAnalyticsCoordinator(hass, entry)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await coordinator.async_setup()
    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    _register_services(hass)
    # 自动注册 Lovelace 卡片
    await _register_lovelace_resource(hass)
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

    async def _handle_reset_history(call: ServiceCall) -> None:
        coordinator = _get_coordinator_from_call(hass, call)
        if coordinator:
            await coordinator.async_reset_history()
            LOGGER.info("History reset for %s", coordinator.printer_name)

    hass.services.async_register(DOMAIN, SERVICE_REFRESH_STATS, _handle_refresh_stats)
    hass.services.async_register(DOMAIN, SERVICE_RESET_HISTORY, _handle_reset_history)


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
