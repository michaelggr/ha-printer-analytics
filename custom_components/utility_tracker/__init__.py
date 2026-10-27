"""Utility Tracker 集成入口"""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_MARIADB_DATABASE,
    CONF_MARIADB_HOST,
    CONF_MARIADB_PASSWORD,
    CONF_MARIADB_PORT,
    CONF_MARIADB_USER,
    DOMAIN,
    SERVICE_BACKFILL_HISTORY,
    SERVICE_SYNC_NOW,
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
    except Exception as e:
        _LOGGER.error("数据库 schema 初始化失败: %s", e)
        await db.async_close()
        return False

    coordinator = UtilityTrackerCoordinator(hass, entry, db)

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "db": db,
    }

    # 注册服务
    async def handle_sync_now(call: ServiceCall) -> None:
        _LOGGER.info("手动触发同步")
        await coordinator.async_request_refresh()

    async def handle_backfill(call: ServiceCall) -> None:
        _LOGGER.info("手动触发历史回填")
        await coordinator.async_request_refresh()

    hass.services.async_register(DOMAIN, SERVICE_SYNC_NOW, handle_sync_now)
    hass.data[DOMAIN][entry.entry_id]["services"] = [SERVICE_SYNC_NOW, SERVICE_BACKFILL_HISTORY]
    hass.services.async_register(DOMAIN, SERVICE_BACKFILL_HISTORY, handle_backfill)

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
            db: UtilityDB = data.get("db")
            if db:
                await db.async_close()
            # 移除服务
            for service in data.get("services", []):
                if hass.services.has_service(DOMAIN, service):
                    hass.services.async_remove(DOMAIN, service)
    return unload_ok
