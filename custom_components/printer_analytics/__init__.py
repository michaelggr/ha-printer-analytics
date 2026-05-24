from __future__ import annotations

import json
import logging
import os
import shutil

import voluptuous as vol
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
    SERVICE_BACKFILL_TASK_NAMES_FROM_HISTORY,
    SERVICE_BACKFILL_RECORD_FIELDS,
    SERVICE_IMPORT_HISTORY,
    SERVICE_BACKUP_HISTORY,
    SERVICE_UPDATE_RECORD_FIELD,
)
from .coordinator import PrinterAnalyticsCoordinator

LOGGER = logging.getLogger(__name__)


def _sanitize_record(record: dict) -> dict:
    if not isinstance(record, dict):
        return {}
    return {k: v for k, v in record.items() if isinstance(k, str) and not k.startswith("_")}


def _match_status(status: str, status_filter: str) -> bool:
    status_value = (status or "").lower()
    filter_value = (status_filter or "").lower()
    if not filter_value:
        return True
    if filter_value == "finish":
        return status_value in ("finish", "completed", "success", "完成", "成功")
    if filter_value == "failed":
        return status_value in ("fail", "failed", "失败")
    if filter_value == "cancelled":
        return status_value in ("cancel", "cancelled", "已取消")
    return status_value == filter_value


def _calculate_history_stats(history: list[dict]) -> dict:
    from datetime import datetime

    records = history or []
    total = len(records)
    success = sum(1 for record in records if _match_status(record.get("status"), "finish"))
    total_weight = 0.0
    total_duration_hours = 0.0

    for record in records:
        total_weight += float(record.get("total_weight") or 0)
        duration = record.get("duration_hours")
        if duration is not None and duration != "":
            try:
                total_duration_hours += float(duration)
                continue
            except (TypeError, ValueError):
                pass
        start_time = record.get("start_time")
        end_time = record.get("end_time")
        if start_time and end_time:
            try:
                start_dt = datetime.fromisoformat(str(start_time).replace("Z", "+00:00"))
                end_dt = datetime.fromisoformat(str(end_time).replace("Z", "+00:00"))
                delta = (end_dt - start_dt).total_seconds() / 3600
                if delta > 0:
                    total_duration_hours += delta
            except ValueError:
                continue

    return {
        "total": total,
        "success_rate": round((success / total) * 100, 1) if total else 0,
        "total_weight": round(total_weight, 1),
        "total_duration_hours": round(total_duration_hours, 2),
    }


def _extract_available_colors(history: list[dict]) -> list[str]:
    colors: set[str] = set()
    for record in history or []:
        used_colors = record.get("colors_used") or []
        if used_colors:
            for color in used_colors:
                if color:
                    colors.add(color)
            continue
        filament_color = record.get("filament_color")
        if filament_color:
            colors.add(filament_color)
            continue
        for usage in record.get("color_usage") or []:
            if usage and usage.get("color") and usage.get("weight_g", 0) > 0:
                colors.add(usage["color"])
    return sorted(colors)


def _apply_filters(history: list[dict], status_filter: str, color_filter: str, printer_filter: str, date_from: str, date_to: str, search: str) -> list[dict]:
    records = history or []
    has_printer_tags = any(record.get("_printer_name") for record in records)
    search_value = (search or "").lower()
    result = []

    for record in records:
        if not _match_status(record.get("status"), status_filter):
            continue

        if color_filter:
            used_colors = record.get("colors_used") or []
            color_match = color_filter in used_colors or record.get("filament_color") == color_filter
            if not color_match:
                color_match = any(
                    usage and usage.get("color") == color_filter
                    for usage in record.get("color_usage") or []
                )
            if not color_match:
                continue

        if printer_filter and has_printer_tags and record.get("_printer_name") != printer_filter:
            continue

        if date_from or date_to:
            time_value = record.get("end_time") or record.get("start_time") or ""
            if not time_value:
                continue
            date_value = str(time_value)[:10]
            if date_from and date_value < date_from:
                continue
            if date_to and date_value > date_to:
                continue

        if search_value:
            task_name = (record.get("task_name") or "").lower()
            filament_type = (record.get("filament_type") or "").lower()
            if search_value not in task_name and search_value not in filament_type:
                continue

        result.append(record)

    return result


def _process_history_request(coordinator, sort: str, page: int, page_size: int, status_filter: str, color_filter: str, printer_filter: str, date_from: str, date_to: str, search: str) -> dict:
    history = coordinator.get_sorted_history(desc=(sort or "desc") != "asc") or []
    total_raw = len(history)
    available_colors = _extract_available_colors(history)
    filtered = _apply_filters(history, status_filter, color_filter, printer_filter, date_from, date_to, search)
    total = len(filtered)
    stats = _calculate_history_stats(filtered)
    page_size = max(1, int(page_size or 20))
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = max(1, min(int(page or 1), total_pages))
    start = (page - 1) * page_size
    end = start + page_size

    return {
        "records": [_sanitize_record(record) for record in filtered[start:end]],
        "total": total,
        "total_raw": total_raw,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "stats": stats,
        "available_colors": available_colors,
    }


try:
    HomeAssistant
except NameError:
    HomeAssistant = object
    ConfigEntry = object
    ServiceCall = object
    PrinterAnalyticsCoordinator = object


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
        "multi_color_ratio", "prepare_time_by_filament", "slice_mode_distribution",
        "over_500g_ratio", "nozzle_size_distribution", "failed_chamber_temp_distribution",
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

        # 集成配置中的腔体温度传感器优先于自动发现的 Bambu Lab 实体
        if hasattr(coordinator, "chamber_temp_entity") and coordinator.chamber_temp_entity:
            realtime_entities["chamber_temperature"] = coordinator.chamber_temp_entity

        printers.append({
            "printer_name": printer_name,
            "printer_serial": getattr(coordinator, "printer_serial", ""),
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
    try:
        coordinator = PrinterAnalyticsCoordinator(hass, entry)
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
        await coordinator.async_setup()
        await coordinator.async_config_entry_first_refresh()

        # 尽早注册服务，避免后续步骤异常导致服务未注册
        _register_services(hass)

        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        entry.async_on_unload(entry.add_update_listener(_async_update_listener))

        await _ensure_card_resource(hass)

        # 生成仪表板配置
        try:
            await _generate_dashboard_yaml(hass)
            await _ensure_dashboard_registered(hass)
        except Exception as err:
            LOGGER.warning("Dashboard generation skipped: %s", err)

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
    except Exception as err:
        LOGGER.error("Printer Analytics setup failed for %s: %s",
                     entry.data.get(CONF_PRINTER_NAME), err, exc_info=True)
        # 清理可能已经注册的数据
        if DOMAIN in hass.data and entry.entry_id in hass.data[DOMAIN]:
            hass.data[DOMAIN].pop(entry.entry_id)
        return False


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

    # 服务参数 Schema 定义
    ENTITY_ID_SCHEMA = vol.Schema({
        vol.Required(ATTR_ENTITY_ID): vol.Any(str, [str]),
    })

    DELETE_RECORDS_SCHEMA = vol.Schema({
        vol.Required(ATTR_ENTITY_ID): vol.Any(str, [str]),
        vol.Required("record_ids"): vol.Any(str, [str]),
    })

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

    async def _handle_backfill_task_names_from_history(call: ServiceCall) -> None:
        coordinator = _get_coordinator_from_call(hass, call)
        if coordinator:
            count = await coordinator.backfill_task_names_from_history()
            LOGGER.info("从HA历史反查补全了 %d 条任务名 for %s", count, coordinator.printer_name)

    async def _handle_backfill_record_fields(call: ServiceCall) -> None:
        coordinator = _get_coordinator_from_call(hass, call)
        if coordinator:
            count = await coordinator.backfill_record_fields()
            LOGGER.info("Backfilled %d record fields for %s", count, coordinator.printer_name)

    async def _handle_import_history(call: ServiceCall) -> None:
        """导入历史记录服务"""
        coordinator = _get_coordinator_from_call(hass, call)
        if coordinator:
            json_data = call.data.get("json_data", "")
            if json_data:
                try:
                    count = await coordinator.async_import_history(json_data)
                    LOGGER.info("Imported %d history records for %s", count, coordinator.printer_name)
                except Exception as e:
                    LOGGER.error("Failed to import history: %s", e)
                    raise
            else:
                LOGGER.warning("No json_data provided for import")

    async def _handle_backup_history(call: ServiceCall) -> None:
        """备份历史记录服务"""
        coordinator = _get_coordinator_from_call(hass, call)
        if coordinator:
            backup_path = await coordinator.async_backup_history()
            LOGGER.info("Backed up history to %s for %s", backup_path, coordinator.printer_name)

    async def _handle_update_record_field(call: ServiceCall) -> None:
        """更新记录字段服务"""
        coordinator = _get_coordinator_from_call(hass, call)
        if coordinator:
            record_id = call.data.get("record_id", "")
            field = call.data.get("field", "")
            value = call.data.get("value", "")
            if record_id and field:
                count = await coordinator.async_update_record_field(record_id, field, value)
                LOGGER.info("Updated %s field for record %s: %s", field, record_id, value)

    hass.services.async_register(DOMAIN, SERVICE_REFRESH_STATS, _handle_refresh_stats, schema=ENTITY_ID_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_RESET_HISTORY, _handle_reset_history, schema=ENTITY_ID_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_DELETE_HISTORY_RECORDS, _handle_delete_history_records, schema=DELETE_RECORDS_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_BACKFILL_COVER_IMAGES, _handle_backfill_cover_images, schema=ENTITY_ID_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_BACKFILL_SNAPSHOTS, _handle_backfill_snapshots, schema=ENTITY_ID_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_BACKFILL_TASK_NAMES, _handle_backfill_task_names, schema=ENTITY_ID_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_BACKFILL_TASK_NAMES_FROM_HISTORY, _handle_backfill_task_names_from_history, schema=ENTITY_ID_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_BACKFILL_RECORD_FIELDS, _handle_backfill_record_fields, schema=ENTITY_ID_SCHEMA)

    # 导入导出服务 Schema
    IMPORT_SCHEMA = vol.Schema({
        vol.Required(ATTR_ENTITY_ID): vol.Any(str, [str]),
        vol.Required("json_data"): str,
    })

    hass.services.async_register(DOMAIN, SERVICE_IMPORT_HISTORY, _handle_import_history, schema=IMPORT_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_BACKUP_HISTORY, _handle_backup_history, schema=ENTITY_ID_SCHEMA)

    # 更新记录字段 Schema
    UPDATE_FIELD_SCHEMA = vol.Schema({
        vol.Required(ATTR_ENTITY_ID): vol.Any(str, [str]),
        vol.Required("record_id"): str,
        vol.Required("field"): str,
        vol.Required("value"): str,
    })
    hass.services.async_register(DOMAIN, SERVICE_UPDATE_RECORD_FIELD, _handle_update_record_field, schema=UPDATE_FIELD_SCHEMA)

    # 注册 WebSocket 命令（服务端筛选+分页）
    try:
        _register_websocket_commands(hass)
    except Exception as err:
        LOGGER.warning("WebSocket command registration skipped: %s", err)


def _get_coordinator_from_call(
    hass: HomeAssistant, call: ServiceCall
) -> PrinterAnalyticsCoordinator | None:
    entity_id = call.data.get(ATTR_ENTITY_ID)
    if not entity_id:
        return None
    if isinstance(entity_id, list):
        entity_id = entity_id[0]

    # 方法1：通过 entity_registry 查找
    entity_reg = async_get_entity_registry(hass)
    for entry_id, coordinator in hass.data.get(DOMAIN, {}).items():
        if not isinstance(coordinator, PrinterAnalyticsCoordinator):
            continue
        for entity in entity_reg.entities.values():
            if entity.entity_id == entity_id and entity.config_entry_id == entry_id:
                return coordinator

    # 方法2：回退 - 直接匹配 coordinator 的实体列表
    for entry_id, coordinator in hass.data.get(DOMAIN, {}).items():
        if not isinstance(coordinator, PrinterAnalyticsCoordinator):
            continue
        if hasattr(coordinator, 'entity_id') and coordinator.entity_id == entity_id:
            return coordinator
        # 检查 coordinator 管理的传感器实体
        if hasattr(coordinator, 'sensor_entity_ids') and entity_id in coordinator.sensor_entity_ids:
            return coordinator

    # 方法3：最后回退 - 如果只有一个 coordinator，直接返回
    coordinators = [c for c in hass.data.get(DOMAIN, {}).values()
                    if isinstance(c, PrinterAnalyticsCoordinator)]
    if len(coordinators) == 1:
        LOGGER.warning("Fallback to single coordinator for entity_id=%s", entity_id)
        return coordinators[0]

    LOGGER.warning("No coordinator found for entity_id=%s", entity_id)
    return None


async def _ws_query_all_history(hass: HomeAssistant, connection, msg):
    """全局查询所有历史记录（包括已删除打印机的记录）"""
    from .storage import StorageManager

    # 获取历史目录路径
    history_dir = hass.config.path(".printer_analytics", "history_by_year")

    # 在 executor 中扫描所有文件
    all_records = await hass.async_add_executor_job(
        StorageManager.scan_all_history_files, history_dir
    )

    # 应用筛选
    filters = msg.get("filters", {})
    filtered = _apply_filters(
        all_records,
        status_filter=filters.get("status", ""),
        color_filter=filters.get("color", ""),
        printer_filter=filters.get("printer", ""),
        date_from=filters.get("date_from", ""),
        date_to=filters.get("date_to", ""),
        search=filters.get("search", "").lower(),
        slice_mode_filter=filters.get("slice_mode", ""),
        over_500g_filter=filters.get("over_500g", ""),
    )

    # 收集所有颜色选项（从全量数据）
    all_colors = _extract_available_colors(all_records)

    # 统计
    stats = _calculate_history_stats(filtered)

    # 分页
    page_size = max(1, int(msg.get("page_size", 20)))
    total = len(filtered)
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = max(1, min(int(msg.get("page", 1)), total_pages))
    start = (page - 1) * page_size
    end = start + page_size

    # 清理内部字段
    page_records = [_sanitize_record(r) for r in filtered[start:end]]

    # 获取所有已知序列号
    all_serials = await hass.async_add_executor_job(
        StorageManager.get_all_serials, history_dir
    )

    # 构建序列号到打印机名的映射
    serial_name_map = {}
    for coordinator in hass.data.get(DOMAIN, {}).values():
        if isinstance(coordinator, PrinterAnalyticsCoordinator) and coordinator.printer_serial:
            serial_name_map[coordinator.printer_serial.upper()] = coordinator.printer_name

    # 为记录添加打印机名
    for r in page_records:
        serial = (r.get("printer_serial") or "").upper()
        if serial and serial in serial_name_map:
            r["_printer_name"] = serial_name_map[serial]
        # 标记来源实体（用于删除操作）
        for coordinator in hass.data.get(DOMAIN, {}).values():
            if isinstance(coordinator, PrinterAnalyticsCoordinator):
                if coordinator.printer_serial and coordinator.printer_serial.upper() == serial:
                    # 找到对应的 coordinator，设置实体ID
                    r["_printer_entity"] = coordinator.print_status_entity or ""
                    break

    connection.send_result(msg["id"], {
        "records": page_records,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
        },
        "stats": stats,
        "filter_options": {
            "colors": sorted(all_colors),
            "all_serials": all_serials,
            "serial_name_map": serial_name_map,
            "total_records": len(all_records),
        },
    })


def _register_websocket_commands(hass: HomeAssistant) -> None:
    """注册 WebSocket 命令，支持服务端筛选+分页查询"""
    from homeassistant.components import websocket_api

    @websocket_api.websocket_command({
        vol.Required("type"): "printer_analytics/query_history",
        vol.Required("entry_id"): str,
        vol.Optional("filters", default={}): dict,
        vol.Optional("page", default=1): int,
        vol.Optional("page_size", default=20): int,
    })
    @websocket_api.async_response
    async def ws_query_history(hass: HomeAssistant, connection, msg):
        """服务端筛选+分页查询历史记录"""
        entry_id = msg["entry_id"]
        coordinator = hass.data.get(DOMAIN, {}).get(entry_id)
        if not coordinator or not isinstance(coordinator, PrinterAnalyticsCoordinator):
            connection.send_error(msg["id"], "not_found", f"Coordinator not found for {entry_id}")
            return

        result = coordinator.query_history(
            filters=msg.get("filters", {}),
            page=msg.get("page", 1),
            page_size=msg.get("page_size", 20),
        )
        connection.send_result(msg["id"], result)

    websocket_api.async_register_command(hass, ws_query_history)

    # 全局查询：扫描所有历史文件（包括已删除打印机的记录）
    hass.components.websocket_api.async_register_command(
        hass,
        "printer_analytics/query_all_history",
        _ws_query_all_history,
        websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
            vol.Required("type"): "printer_analytics/query_all_history",
            vol.Optional("filters", default={}): dict,
            vol.Optional("page", default=1): int,
            vol.Optional("page_size", default=20): int,
        }),
    )
