"""Utility Tracker 配置流"""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import (
    CONF_ENABLE_ELECTRICITY,
    CONF_ENABLE_GAS,
    CONF_MARIADB_DATABASE,
    CONF_MARIADB_HOST,
    CONF_MARIADB_PASSWORD,
    CONF_MARIADB_PORT,
    CONF_MARIADB_USER,
    CONF_SYNC_INTERVAL_HOURS,
    DEFAULT_MARIADB_DATABASE,
    DEFAULT_MARIADB_HOST,
    DEFAULT_MARIADB_PORT,
    DEFAULT_MARIADB_USER,
    DEFAULT_SYNC_INTERVAL_HOURS,
    DOMAIN,
)
from .db import UtilityDB

_LOGGER = logging.getLogger(__name__)


async def _validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, str]:
    """验证 MariaDB 连接,失败抛 HomeAssistantError"""
    db = UtilityDB(
        hass,
        host=data[CONF_MARIADB_HOST],
        port=data[CONF_MARIADB_PORT],
        user=data[CONF_MARIADB_USER],
        password=data[CONF_MARIADB_PASSWORD],
        database=data[CONF_MARIADB_DATABASE],
    )
    ok, msg = await db.async_test_connection()
    await db.async_close()
    if not ok:
        _LOGGER.error("MariaDB 连接失败: %s", msg)
        raise CannotConnect(msg)
    return {"title": f"Utility Tracker ({data[CONF_MARIADB_DATABASE]})"}


class UtilityTrackerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Utility Tracker 配置流"""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await _validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("配置验证未知错误")
                errors["base"] = "unknown"
            else:
                # 同一数据库只允许一个 entry
                unique = f"{user_input[CONF_MARIADB_HOST]}:{user_input[CONF_MARIADB_PORT]}/{user_input[CONF_MARIADB_DATABASE]}"
                await self.async_set_unique_id(unique)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=user_input)

        schema = vol.Schema({
            vol.Required(CONF_MARIADB_HOST, default=DEFAULT_MARIADB_HOST): str,
            vol.Required(CONF_MARIADB_PORT, default=DEFAULT_MARIADB_PORT): int,
            vol.Required(CONF_MARIADB_USER, default=DEFAULT_MARIADB_USER): str,
            vol.Required(CONF_MARIADB_PASSWORD): str,
            vol.Required(CONF_MARIADB_DATABASE, default=DEFAULT_MARIADB_DATABASE): str,
            vol.Required(CONF_ENABLE_ELECTRICITY, default=True): bool,
            vol.Required(CONF_ENABLE_GAS, default=True): bool,
            vol.Required(CONF_SYNC_INTERVAL_HOURS, default=DEFAULT_SYNC_INTERVAL_HOURS): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=24)
            ),
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)


class CannotConnect(HomeAssistantError):
    """无法连接 MariaDB"""
