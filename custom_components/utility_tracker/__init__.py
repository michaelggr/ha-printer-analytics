"""Utility Tracker 集成入口"""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ENABLE_LIGHT_STATS,
    CONF_MARIADB_DATABASE,
    CONF_MARIADB_HOST,
    CONF_MARIADB_PASSWORD,
    CONF_MARIADB_PORT,
    CONF_MARIADB_USER,
    DOMAIN,
    LIGHT_ACTION_OFF,
    LIGHT_ACTION_ON,
    SERVICE_BACKFILL_HISTORY,
    SERVICE_PURGE_DEVICE_DATA,
    SERVICE_SYNC_NOW,
    is_light_entity,
)
from .coordinator import UtilityTrackerCoordinator
from .db import UtilityDB

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """设置集成"""
    hass.data.setdefault(DOMAIN, {})

    db = UtilityDB(
        hass,
        host=entry.data[CONF_MARIADB_HOST],
        port=entry.data[CONF_MARIADB_PORT],
        user=entry.data[CONF_MARIADB_USER],
        password=entry.data[CONF_MARIADB_PASSWORD],
        database=entry.data[CONF_MARIADB_DATABASE],
    )

    # 建表
    try:
        await db.async_ensure_schema()
        # v2 迁移: utility_records 加 bill_no (同月多单据, 如退款)
        await db.async_migrate_bill_no()
    except Exception as e:
        _LOGGER.error("数据库 schema 初始化失败: %s", e)
        await db.async_close()
        return False

    coordinator = UtilityTrackerCoordinator(hass, entry, db)

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "db": db,
    }

    # 注册灯光 state listener,把开/关事件入 coordinator 队列
    if entry.data.get(CONF_ENABLE_LIGHT_STATS, True):
        def _collect_light_entity_ids() -> set[str]:
            """扫描当前所有灯光实体 (含灯光类 switch)"""
            return {
                s.entity_id
                for s in hass.states.async_all()
                if is_light_entity(s.entity_id, s.attributes.get("friendly_name"))
            }

        def _light_state_changed(event: Event[EventStateChangedData]) -> None:
            """灯光状态变化 -> 事件入队 (coordinator 定期批量写库)"""
            entity_id = event.data.get("entity_id", "")
            new_state = event.data.get("new_state")
            old_state = event.data.get("old_state")
            if new_state is None:
                return
            # 只关心 on/off 切换,忽略亮度/色温等属性变化
            new_on = new_state.state == "on"
            old_on = (old_state.state == "on") if old_state else False
            if new_on == old_on:
                return
            coordinator.queue_light_event({
                "entity_id": entity_id,
                "friendly_name": new_state.attributes.get("friendly_name"),
                "event_time": dt_util.now().strftime("%Y-%m-%d %H:%M:%S"),
                "action": LIGHT_ACTION_ON if new_on else LIGHT_ACTION_OFF,
                "brightness": new_state.attributes.get("brightness"),
                "color_temp": new_state.attributes.get("color_temp"),
            })
            _LOGGER.debug("灯光事件入队: %s -> %s", entity_id,
                          LIGHT_ACTION_ON if new_on else LIGHT_ACTION_OFF)

        def _rebuild_light_subscription() -> None:
            """重建灯光订阅: 先退订旧的,再按当前灯光实体列表订阅

            (async_track_state_change_event 需显式实体列表,MATCH_ALL 不可靠;
             coordinator 每轮发现新灯时调用本函数)
            """
            store = hass.data[DOMAIN][entry.entry_id]
            old_unsub = store.get("light_unsub")
            if old_unsub:
                try:
                    old_unsub()
                except Exception:
                    pass
            light_ids = _collect_light_entity_ids()
            store["light_entity_ids"] = light_ids
            if light_ids:
                store["light_unsub"] = async_track_state_change_event(
                    hass, list(light_ids), _light_state_changed
                )
            _LOGGER.info("灯光 listener 已订阅 %d 个实体", len(light_ids))

        # 首次订阅
        _rebuild_light_subscription()
        # 暴露给 coordinator,用于检测新增灯后重建订阅
        hass.data[DOMAIN][entry.entry_id]["rebuild_light_sub"] = (
            _rebuild_light_subscription
        )

    # 注册服务
    async def handle_sync_now(call: ServiceCall) -> None:
        _LOGGER.info("手动触发同步")
        await coordinator.async_request_refresh()

    async def handle_backfill(call: ServiceCall) -> None:
        _LOGGER.info("手动触发历史回填")
        await coordinator.async_request_refresh()

    async def handle_purge_device_data(call: ServiceCall) -> None:
        """清空设备功耗/灯光数据 (异常数据重置)"""
        result = await db.async_purge_device_data()
        _LOGGER.warning("设备/灯光数据已清空: %s", result)

    hass.services.async_register(DOMAIN, SERVICE_SYNC_NOW, handle_sync_now)
    hass.data[DOMAIN][entry.entry_id]["services"] = [
        SERVICE_SYNC_NOW, SERVICE_BACKFILL_HISTORY, SERVICE_PURGE_DEVICE_DATA,
    ]
    hass.services.async_register(DOMAIN, SERVICE_BACKFILL_HISTORY, handle_backfill)
    hass.services.async_register(DOMAIN, SERVICE_PURGE_DEVICE_DATA, handle_purge_device_data)

    # 首次刷新
    await coordinator.async_config_entry_first_refresh()

    # 转发到 sensor 平台
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.info("Utility Tracker 已启动 (entry_id=%s)", entry.entry_id)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """卸载集成"""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id, None)
        if data:
            # 移除灯光 listener
            unsub = data.get("light_unsub")
            if unsub:
                try:
                    unsub()
                except Exception:
                    pass
            db: UtilityDB = data.get("db")
            if db:
                await db.async_close()
            # 移除服务
            for service in data.get("services", []):
                if hass.services.has_service(DOMAIN, service):
                    hass.services.async_remove(DOMAIN, service)
    return unload_ok
