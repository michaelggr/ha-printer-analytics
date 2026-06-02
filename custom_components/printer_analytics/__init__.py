from __future__ import annotations

import json
import logging
import os
import shutil
import time

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
from .utils import match_record_filter

LOGGER = logging.getLogger(__name__)


def _sanitize_record(record: dict) -> dict:
    if not isinstance(record, dict):
        return {}
    return {k: v for k, v in record.items() if isinstance(k, str) and not k.startswith("_")}


def _match_status(status: str, status_filter: str) -> bool:
    from .const import SUCCESS_STATUSES, FAILURE_STATUSES, CANCELLED_STATUSES

    status_value = status or ""
    filter_value = (status_filter or "").lower()
    if not filter_value:
        return True
    if filter_value == "finish":
        return status_value in SUCCESS_STATUSES
    if filter_value == "failed":
        return status_value in FAILURE_STATUSES
    if filter_value == "cancelled":
        return status_value in CANCELLED_STATUSES
    return status_value == filter_value or status_value.lower() == filter_value


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


def _apply_filters(history: list[dict], status_filter: str, color_filter: str, printer_filter: str, date_from: str, date_to: str, search: str, slice_mode_filter: str = "", over_500g_filter: str = "") -> list[dict]:
    """筛选历史记录（委托给 utils.match_record_filter 统一实现）"""
    return [record for record in (history or [])
            if match_record_filter(record, status_filter, color_filter, printer_filter,
                                   date_from, date_to, search, slice_mode_filter, over_500g_filter)]


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

        # 注册 Bambu Cloud 定时同步
        try:
            from homeassistant.helpers.event import async_track_time_interval
            from datetime import timedelta
            from .const import BAMBU_SYNC_INTERVAL_HOURS

            async def _bambu_scheduled_sync(_now):
                from .bambu_cloud import load_bambu_token, check_token, save_bambu_token
                now_str = _now.strftime("%Y-%m-%d %H:%M:%S") if _now else "unknown"
                LOGGER.info("[Bambu定时] 定时同步触发, 当前时间=%s", now_str)
                auth = await load_bambu_token(hass)
                if not auth or not auth.get("token"):
                    LOGGER.info("[Bambu定时] 未登录，跳过同步")
                    return
                valid = await check_token(auth["token"])
                if not valid:
                    auth["token"] = ""
                    await save_bambu_token(hass, auth)
                    LOGGER.warning("[Bambu定时] Token 已过期，已标记")
                    return
                for eid, coord in hass.data.get(DOMAIN, {}).items():
                    if isinstance(coord, PrinterAnalyticsCoordinator):
                        try:
                            result = await coord.async_bambu_sync()
                            LOGGER.info("[Bambu定时] 定时同步完成: %s", result)
                        except Exception as err:
                            LOGGER.warning("[Bambu定时] 定时同步失败: %s", err, exc_info=True)

            unsub = async_track_time_interval(
                hass, _bambu_scheduled_sync, timedelta(hours=BAMBU_SYNC_INTERVAL_HOURS)
            )
            entry.async_on_unload(unsub)
            from datetime import datetime as _dt, timezone as _tz, timedelta as _td
            _next_run = _dt.now(_tz(_td(hours=8))) + _td(hours=BAMBU_SYNC_INTERVAL_HOURS)
            LOGGER.info(
                "[Bambu定时] 定时同步已注册（每 %d 小时），预计下次执行: %s",
                BAMBU_SYNC_INTERVAL_HOURS, _next_run.strftime("%Y-%m-%d %H:%M:%S"),
            )
        except Exception as err:
            LOGGER.warning("Bambu Cloud 定时同步注册跳过: %s", err)

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
                    result = await coordinator.async_import_history(json_data)
                    LOGGER.info("Imported history for %s: %s", coordinator.printer_name, result)
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

    # 方法2：回退 - 直接匹配 coordinator 的实体列表和属性
    for entry_id, coordinator in hass.data.get(DOMAIN, {}).items():
        if not isinstance(coordinator, PrinterAnalyticsCoordinator):
            continue
        if hasattr(coordinator, 'entity_id') and coordinator.entity_id == entity_id:
            return coordinator
        # 检查 coordinator 管理的传感器实体
        if hasattr(coordinator, 'sensor_entity_ids') and entity_id in coordinator.sensor_entity_ids:
            return coordinator
        # 匹配 print_status_entity（前端删除操作传入的 entity_id）
        if hasattr(coordinator, 'print_status_entity') and coordinator.print_status_entity == entity_id:
            return coordinator
        # 匹配 printer_serial（entity_id 可能包含序列号）
        if hasattr(coordinator, 'printer_serial') and coordinator.printer_serial and coordinator.printer_serial.upper() in entity_id.upper():
            return coordinator

    # 方法3：最后回退 - 如果只有一个 coordinator，直接返回
    coordinators = [c for c in hass.data.get(DOMAIN, {}).values()
                    if isinstance(c, PrinterAnalyticsCoordinator)]
    if len(coordinators) == 1:
        LOGGER.warning("Fallback to single coordinator for entity_id=%s", entity_id)
        return coordinators[0]

    LOGGER.warning("No coordinator found for entity_id=%s", entity_id)
    return None


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
    @websocket_api.websocket_command({
        vol.Required("type"): "printer_analytics/query_all_history",
        vol.Optional("filters", default={}): dict,
        vol.Optional("page", default=1): int,
        vol.Optional("page_size", default=20): int,
    })
    @websocket_api.async_response
    async def ws_query_all_history(hass: HomeAssistant, connection, msg):
        """全局查询所有历史记录（包括已删除打印机的记录）"""
        try:
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

            # 清理内部字段，但先保存 _source_serial（从文件名提取的正确序列号）
            page_data = []
            for r in filtered[start:end]:
                source_serial = (r.get("_source_serial") or "").upper()
                clean = _sanitize_record(r)
                clean["_source_serial"] = source_serial  # 保留来源序列号
                page_data.append(clean)

            # 获取所有已知序列号
            all_serials = await hass.async_add_executor_job(
                StorageManager.get_all_serials, history_dir
            )

            # 构建序列号到打印机名的映射
            serial_name_map = {}
            for coordinator in hass.data.get(DOMAIN, {}).values():
                if isinstance(coordinator, PrinterAnalyticsCoordinator) and coordinator.printer_serial:
                    serial_name_map[coordinator.printer_serial.upper()] = coordinator.printer_name

            # 为记录添加打印机名和实体ID（优先使用 _source_serial）
            for r in page_data:
                # 优先用 _source_serial（文件名提取），回退到 printer_serial（记录字段）
                serial = r.get("_source_serial") or (r.get("printer_serial") or "").upper()
                if serial and serial in serial_name_map:
                    r["_printer_name"] = serial_name_map[serial]
                # 标记来源实体（用于删除操作）
                for coordinator in hass.data.get(DOMAIN, {}).values():
                    if isinstance(coordinator, PrinterAnalyticsCoordinator):
                        if coordinator.printer_serial and coordinator.printer_serial.upper() == serial:
                            r["_printer_entity"] = coordinator.print_status_entity or ""
                            break

            connection.send_result(msg["id"], {
                "records": page_data,
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
        except Exception as err:
            LOGGER.error("query_all_history 执行失败: %s", err, exc_info=True)
            connection.send_error(msg["id"], "unknown_error", str(err))

    websocket_api.async_register_command(hass, ws_query_all_history)

    # 全局删除：直接从文件中删除记录（不依赖 coordinator，支持已删除打印机）
    @websocket_api.websocket_command({
        vol.Required("type"): "printer_analytics/delete_global_records",
        vol.Required("record_ids"): str,
    })
    @websocket_api.async_response
    async def ws_delete_global_records(hass: HomeAssistant, connection, msg):
        """全局删除记录（直接操作文件，支持已删除打印机）"""
        try:
            from .storage import StorageManager

            record_ids_raw = msg.get("record_ids", "")
            if isinstance(record_ids_raw, str):
                ids_set = set(rid.strip() for rid in record_ids_raw.split(",") if rid.strip())
            elif isinstance(record_ids_raw, list):
                ids_set = set(record_ids_raw)
            else:
                ids_set = set()

            if not ids_set:
                connection.send_result(msg["id"], {"deleted": 0})
                return

            history_dir = hass.config.path(".printer_analytics", "history_by_year")

            def _delete_from_files():
                import os, json
                if not os.path.isdir(history_dir):
                    return 0
                total_deleted = 0
                for f in sorted(os.listdir(history_dir)):
                    if not f.endswith(".json") or f.endswith("_stats.json"):
                        continue
                    file_path = os.path.join(history_dir, f)
                    try:
                        with open(file_path, "r", encoding="utf-8") as fh:
                            data = json.load(fh)
                        records = data.get("history", []) if isinstance(data, dict) else data
                        original = len(records)
                        filtered = [r for r in records if r.get("id") not in ids_set]
                        deleted = original - len(filtered)
                        if deleted > 0:
                            if isinstance(data, dict):
                                data["history"] = filtered
                            else:
                                data = filtered
                            with open(file_path, "w", encoding="utf-8") as fh:
                                json.dump(data, fh, ensure_ascii=False, indent=2)
                            total_deleted += deleted
                            LOGGER.info("全局删除：从文件 %s 删除了 %d 条记录", f, deleted)
                    except Exception as err:
                        LOGGER.warning("全局删除处理文件 %s 失败: %s", f, err)
                return total_deleted

            deleted = await hass.async_add_executor_job(_delete_from_files)

            # 同时从在线 coordinator 的内存缓存中删除
            for coordinator in hass.data.get(DOMAIN, {}).values():
                if isinstance(coordinator, PrinterAnalyticsCoordinator):
                    original = len(coordinator.history)
                    coordinator.history = [r for r in coordinator.history if r.get("id") not in ids_set]
                    if len(coordinator.history) < original:
                        if coordinator.statistics:
                            coordinator.statistics.invalidate_cache()
                        await coordinator._save_history()
                        coordinator.async_set_updated_data(coordinator._calculate_statistics())

            connection.send_result(msg["id"], {"deleted": deleted})
        except Exception as err:
            LOGGER.error("全局删除执行失败: %s", err, exc_info=True)
            connection.send_error(msg["id"], "delete_failed", str(err))

    websocket_api.async_register_command(hass, ws_delete_global_records)

    @websocket_api.websocket_command({
        vol.Required("type"): "printer_analytics/import_history",
        vol.Required("entry_id"): str,
        vol.Required("json_data"): str,
    })
    @websocket_api.async_response
    async def ws_import_history(hass: HomeAssistant, connection, msg):
        """通过 WebSocket 导入历史记录，返回结构化统计"""
        entry_id = msg["entry_id"]
        coordinator = hass.data.get(DOMAIN, {}).get(entry_id)
        if not coordinator or not isinstance(coordinator, PrinterAnalyticsCoordinator):
            connection.send_error(msg["id"], "not_found", f"Coordinator not found for {entry_id}")
            return

        try:
            result = await coordinator.async_import_history(msg["json_data"])
            connection.send_result(msg["id"], result)
        except ValueError as err:
            connection.send_error(msg["id"], "invalid_data", str(err))
        except Exception as err:
            LOGGER.error("WebSocket 导入失败: %s", err, exc_info=True)
            connection.send_error(msg["id"], "import_failed", str(err))

    websocket_api.async_register_command(hass, ws_import_history)

    # ---- Bambu Cloud 同步 ----

    @websocket_api.websocket_command({
        vol.Required("type"): "printer_analytics/bambu_send_code",
        vol.Required("phone"): str,
    })
    @websocket_api.async_response
    async def ws_bambu_send_code(hass: HomeAssistant, connection, msg):
        from .bambu_cloud import send_code
        phone = msg["phone"]
        LOGGER.info("[Bambu WS] 收到发送验证码请求: phone=%s", phone[:3] + "***")
        result = await send_code(phone)
        LOGGER.info("[Bambu WS] 发送验证码结果: success=%s", result.get("success"))
        connection.send_result(msg["id"], result)

    websocket_api.async_register_command(hass, ws_bambu_send_code)

    @websocket_api.websocket_command({
        vol.Required("type"): "printer_analytics/bambu_login",
        vol.Required("phone"): str,
        vol.Required("code"): str,
    })
    @websocket_api.async_response
    async def ws_bambu_login(hass: HomeAssistant, connection, msg):
        from .bambu_cloud import login_with_code, save_bambu_token
        phone = msg["phone"]
        LOGGER.info("[Bambu WS] 收到登录请求: phone=%s", phone[:3] + "***")
        result = await login_with_code(phone, msg["code"])
        if result.get("success") and result.get("token"):
            auth_data = {
                "phone": phone,
                "token": result["token"],
                "saved_at": time.time(),
                "last_sync": None,
                "last_sync_count": 0,
            }
            await save_bambu_token(hass, auth_data)
            LOGGER.info("[Bambu WS] 登录成功，Token 已保存")
        else:
            LOGGER.warning("[Bambu WS] 登录失败: %s", result.get("error"))
        connection.send_result(msg["id"], result)

    websocket_api.async_register_command(hass, ws_bambu_login)

    @websocket_api.websocket_command({
        vol.Required("type"): "printer_analytics/bambu_sync",
        vol.Required("entry_id"): str,
    })
    @websocket_api.async_response
    async def ws_bambu_sync(hass: HomeAssistant, connection, msg):
        entry_id = msg["entry_id"]
        LOGGER.info("[Bambu WS] 收到同步请求: entry_id=%s", entry_id)
        coordinator = hass.data.get(DOMAIN, {}).get(entry_id)
        if not coordinator or not isinstance(coordinator, PrinterAnalyticsCoordinator):
            LOGGER.warning("[Bambu WS] Coordinator 未找到: entry_id=%s", entry_id)
            connection.send_error(msg["id"], "not_found", f"Coordinator not found for {entry_id}")
            return
        try:
            result = await coordinator.async_bambu_sync()
            LOGGER.info("[Bambu WS] 同步请求完成: success=%s", result.get("success"))
            connection.send_result(msg["id"], result)
        except Exception as err:
            LOGGER.error("[Bambu WS] 同步失败: %s", err, exc_info=True)
            connection.send_error(msg["id"], "sync_failed", str(err))

    websocket_api.async_register_command(hass, ws_bambu_sync)

    @websocket_api.websocket_command({
        vol.Required("type"): "printer_analytics/bambu_status",
    })
    @websocket_api.async_response
    async def ws_bambu_status(hass: HomeAssistant, connection, msg):
        from .bambu_cloud import load_bambu_token, check_token
        auth = await load_bambu_token(hass)
        if not auth or not auth.get("token"):
            connection.send_result(msg["id"], {"logged_in": False, "phone": "", "last_sync": None, "last_sync_count": 0})
            return
        valid = await check_token(auth["token"])
        LOGGER.info("[Bambu WS] 状态查询: logged_in=%s, phone=%s", valid, auth.get("phone", ""))
        connection.send_result(msg["id"], {
            "logged_in": valid,
            "phone": auth.get("phone", ""),
            "last_sync": auth.get("last_sync"),
            "last_sync_count": auth.get("last_sync_count", 0),
        })

    websocket_api.async_register_command(hass, ws_bambu_status)

    @websocket_api.websocket_command({
        vol.Required("type"): "printer_analytics/bambu_logout",
    })
    @websocket_api.async_response
    async def ws_bambu_logout(hass: HomeAssistant, connection, msg):
        from .bambu_cloud import delete_bambu_token
        LOGGER.info("[Bambu WS] 收到登出请求")
        await delete_bambu_token(hass)
        connection.send_result(msg["id"], {"success": True})

    websocket_api.async_register_command(hass, ws_bambu_logout)
