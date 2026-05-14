﻿from __future__ import annotations

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
    CARD_FILENAME,
    CARD_URL,
    CONF_CHAMBER_TEMP_ENTITY,
    CONF_ENERGY_ENTITY,
    CONF_POWER_ENTITY,
    CONF_PRINTER_NAME,
    CONF_PRINT_STATUS_ENTITY,
    DASHBOARD_FILE,
    DOMAIN,
    PLATFORMS,
    SERVICE_REFRESH_STATS,
    SERVICE_RESET_HISTORY,
    SERVICE_DELETE_HISTORY_RECORDS,
    SERVICE_BACKFILL_COVER_IMAGES,
    SERVICE_BACKFILL_SNAPSHOTS,
    SERVICE_BACKFILL_TASK_NAMES,
)
from .coordinator import PrinterAnalyticsCoordinator

LOGGER = logging.getLogger(__name__)


async def _ensure_card_resource(hass: HomeAssistant) -> None:
    """确保卡片 JS 文件存在于 www 并注册为资源"""
    component_www = os.path.join(os.path.dirname(__file__), "www")
    src = os.path.join(component_www, CARD_FILENAME)
    dst = hass.config.path("www", CARD_FILENAME)

    def _copy_card():
        if os.path.exists(src):
            shutil.copy2(src, dst)
            LOGGER.info("Copied %s to www", CARD_FILENAME)
        elif not os.path.exists(dst):
            LOGGER.warning("%s not found", CARD_FILENAME)

    await hass.async_add_executor_job(_copy_card)

    try:
        if LOVELACE_DOMAIN in hass.data:
            lovelace_data = hass.data[LOVELACE_DOMAIN]
            resources = getattr(lovelace_data, 'resources', None)
            if resources is None and isinstance(lovelace_data, dict):
                resources = lovelace_data.get("resources")
            if resources and hasattr(resources, "async_create"):
                items = list(resources.async_items() if hasattr(resources, "async_items") else [])
                old_item = None
                for r in items:
                    url = r.get("url", "")
                    if url.startswith(f"/local/{CARD_FILENAME}"):
                        old_item = r
                        break
                if old_item is None:
                    await resources.async_create({"url": CARD_URL, "type": "module"})
                    LOGGER.info("Registered %s as Lovelace resource", CARD_FILENAME)
                elif old_item.get("url") != CARD_URL:
                    # 版本号变化，删除旧资源并注册新的
                    old_id = old_item.get("id")
                    if old_id and hasattr(resources, "async_delete"):
                        await resources.async_delete(old_id)
                    await resources.async_create({"url": CARD_URL, "type": "module"})
                    LOGGER.info("Updated Lovelace resource to %s", CARD_URL)
    except Exception as err:
        LOGGER.warning("Could not register resource: %s", err)


async def _generate_dashboard_yaml(hass: HomeAssistant) -> None:
    """自动生成仪表板 YAML - 监控置顶 + 统计分析/之最/全部历史 三页签"""
    entry_ids = list(hass.data.get(DOMAIN, {}).keys())
    if not entry_ids:
        LOGGER.warning("No printer analytics entries found, skipping dashboard YAML generation")
        return

    entity_reg = async_get_entity_registry(hass)
    printers = []

    # 每台打印机需要查找的传感器实体
    _SENSOR_KEYS = [
        "print_history", "total_prints", "success_rate", "average_duration",
        "total_print_duration", "total_energy", "material_stats_7d",
        "material_stats_30d", "material_stats_lifetime", "duration_distribution",
        "activity_heatmap", "failure_stage_distribution", "filament_success_stats",
        "print_status",
    ]
    # 每台打印机需要查找的 BambuLab 实时实体
    _REALTIME_KEYS = [
        "current_task", "print_progress", "current_weight", "current_length",
        "total_usage", "nozzle_temperature", "bed_temperature",
        "chamber_temperature", "active_tray", "ams_1_tray_1", "ams_1_tray_2",
        "ams_1_tray_3", "ams_1_tray_4", "wifi_signal", "speed_profile",
        "nozzle_size",
    ]

    # BambuLab 实时实体 key 到 HA 实体 ID 后缀的映射
    _REALTIME_KEY_MAP = {
        "current_task": "task_name",
        "print_progress": "print_progress",
        "current_weight": "print_weight",
        "current_length": "print_length",
        "total_usage": "total_usage",
        "nozzle_temperature": "nozzle_temperature",
        "bed_temperature": "bed_temperature",
        "chamber_temperature": "chamber_temperature",
        "active_tray": "active_tray",
        "ams_1_tray_1": "ams_1_tray_1",
        "ams_1_tray_2": "ams_1_tray_2",
        "ams_1_tray_3": "ams_1_tray_3",
        "ams_1_tray_4": "ams_1_tray_4",
        "wifi_signal": "wi_fi_signal",
        "speed_profile": "speed_profile",
        "nozzle_size": "nozzle_size",
    }

    for entry_id in entry_ids:
        coordinator = hass.data[DOMAIN].get(entry_id)
        if not coordinator or not hasattr(coordinator, "printer_name"):
            continue
        printer_name = coordinator.printer_name

        def _find_entity(sensor_key: str, _eid=entry_id) -> str:
            for entity in entity_reg.entities.values():
                if entity.config_entry_id == _eid and entity.unique_id == f"{_eid}_{sensor_key}":
                    return entity.entity_id
            return ""

        def _find_bambu_entity(entity_suffix: str, _pname=printer_name) -> str:
            # 按 entity_id 模式匹配: sensor.{prefix}_{serial}_{suffix}
            prefix = _pname.lower()
            for entity in entity_reg.entities.values():
                eid = entity.entity_id
                if eid.startswith(f"sensor.{prefix}_") and eid.endswith(f"_{entity_suffix}"):
                    return eid
            return ""

        sensor_entities = {k: _find_entity(k) for k in _SENSOR_KEYS}
        realtime_entities = {}
        for k, suffix in _REALTIME_KEY_MAP.items():
            eid = _find_bambu_entity(suffix)
            if eid:
                realtime_entities[k] = eid

        printers.append({
            "printer_name": printer_name,
            "sensor_entities": sensor_entities,
            "realtime_entities": realtime_entities,
        })

    if not printers:
        return

    lines = [
        '# ==================== 打印机分析 - 监控置顶 + 三页签 ====================',
        '# 自动生成 - 顶部监控 / 统计分析 / 之最 / 全部历史',
        'views:',
        '  - title: "🖨️ 打印机分析"',
        '    icon: mdi:printer-3d-eye',
        '    panel: true',
        '    cards:',
        '      - type: custom:printer-analytics-card',
        '        title: "🖨️ 打印机分析"',
    ]

    # 生成 printers 列表（每台打印机的传感器实体 + 实时实体）
    lines.append('        printers:')
    for p in printers:
        lines.append(f'          - printer_name: "{p["printer_name"]}"')
        # 传感器实体
        for k in _SENSOR_KEYS:
            v = p["sensor_entities"].get(k, "")
            if v:
                lines.append(f'            {k}: {v}')
        # 实时实体
        for k in _REALTIME_KEYS:
            v = p["realtime_entities"].get(k, "")
            if v:
                lines.append(f'            {k}: {v}')

    yaml_content = "\n".join(lines)

    def _write():
        filepath = hass.config.path(DASHBOARD_FILE)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(yaml_content)
        LOGGER.info("Generated dashboard YAML (monitor+3tabs): %s", filepath)

    await hass.async_add_executor_job(_write)


async def _ensure_dashboard_registered(hass: HomeAssistant) -> None:
    """确保打印机分析仪表板在 Lovelace 中已注册"""
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

    await _ensure_card_resource(hass)

    # 生成仪表板配置
    await _generate_dashboard_yaml(hass)
    await _ensure_dashboard_registered(hass)

    # 设置集成页面图标（Config Entry Icon）
    try:
        hass.config_entries.async_update_entry(entry, icon="mdi:chart-timeline-variant")
        LOGGER.debug("集成页面图标已设置为 chart-timeline-variant")
    except Exception as err:
        LOGGER.debug("设置集成图标跳过: %s", err)

    # 设置设备图标（设备页面显示的图标）
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
            await coordinator._load_history()
            await coordinator.async_request_refresh()
            LOGGER.info("Stats and history refreshed for %s", coordinator.printer_name)

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

    async def _handle_backfill_cover_images(call: ServiceCall) -> None:
        coordinator = _get_coordinator_from_call(hass, call)
        if coordinator:
            count = await coordinator.backfill_cover_images()
            LOGGER.info("Backfilled %d cover images for %s", count, coordinator.printer_name)

    async def _handle_backfill_snapshots(call: ServiceCall) -> None:
        coordinator = _get_coordinator_from_call(hass, call)
        if coordinator:
            count = await coordinator.backfill_snapshots()
            LOGGER.info("Backfilled %d snapshots for %s", count, coordinator.printer_name)

    async def _handle_backfill_task_names(call: ServiceCall) -> None:
        coordinator = _get_coordinator_from_call(hass, call)
        if coordinator:
            count = await coordinator.backfill_task_names()
            LOGGER.info("Backfilled %d task names for %s", count, coordinator.printer_name)

    hass.services.async_register(DOMAIN, SERVICE_REFRESH_STATS, _handle_refresh_stats)
    hass.services.async_register(DOMAIN, SERVICE_RESET_HISTORY, _handle_reset_history)
    hass.services.async_register(DOMAIN, SERVICE_DELETE_HISTORY_RECORDS, _handle_delete_history_records)
    hass.services.async_register(DOMAIN, SERVICE_BACKFILL_COVER_IMAGES, _handle_backfill_cover_images)
    hass.services.async_register(DOMAIN, SERVICE_BACKFILL_SNAPSHOTS, _handle_backfill_snapshots)
    hass.services.async_register(DOMAIN, SERVICE_BACKFILL_TASK_NAMES, _handle_backfill_task_names)


def _get_coordinator_from_call(
    hass: HomeAssistant, call: ServiceCall
) -> PrinterAnalyticsCoordinator | None:
    entity_id = call.data.get(ATTR_ENTITY_ID)
    if not entity_id:
        return None
    if isinstance(entity_id, list):
        entity_id = entity_id[0]
    for entry_id, coordinator in hass.data.get(DOMAIN, {}).items():
        if not isinstance(coordinator, PrinterAnalyticsCoordinator):
            continue
        entity_reg = async_get_entity_registry(hass)
        for entity in entity_reg.entities.values():
            if entity.entity_id == entity_id and entity.config_entry_id == entry_id:
                return coordinator
    return None
