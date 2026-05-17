from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_CHAMBER_TEMP_ENTITY,
    CONF_ENERGY_ENTITY,
    CONF_POWER_ENTITY,
    CONF_PRINTER_NAME,
    CONF_PRINT_STATUS_ENTITY,
    DOMAIN,
)


class PrinterAnalyticsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            print_status_entity = user_input[CONF_PRINT_STATUS_ENTITY]
            existing = self._async_current_entries()
            for entry in existing:
                if entry.data.get(CONF_PRINT_STATUS_ENTITY) == print_status_entity:
                    errors["base"] = "already_configured"
                    break
            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_PRINTER_NAME],
                    data={
                        CONF_PRINTER_NAME: user_input[CONF_PRINTER_NAME],
                        CONF_PRINT_STATUS_ENTITY: print_status_entity,
                        CONF_POWER_ENTITY: user_input.get(CONF_POWER_ENTITY, ""),
                        CONF_ENERGY_ENTITY: user_input.get(CONF_ENERGY_ENTITY, ""),
                        CONF_CHAMBER_TEMP_ENTITY: user_input.get(CONF_CHAMBER_TEMP_ENTITY, ""),
                    },
                )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PRINTER_NAME): selector.TextSelector(),
                    vol.Required(CONF_PRINT_STATUS_ENTITY): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
                    ),
                    vol.Optional(CONF_POWER_ENTITY): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
                    ),
                    vol.Optional(CONF_ENERGY_ENTITY): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
                    ),
                    vol.Optional(CONF_CHAMBER_TEMP_ENTITY): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
                    ),
                }
            ),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> PrinterAnalyticsOptionsFlow:
        return PrinterAnalyticsOptionsFlow(config_entry)


class PrinterAnalyticsOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            options = {
                CONF_PRINTER_NAME: user_input.get(
                    CONF_PRINTER_NAME,
                    self.config_entry.data.get(CONF_PRINTER_NAME, ""),
                ),
                CONF_POWER_ENTITY: user_input.get(CONF_POWER_ENTITY, ""),
                CONF_ENERGY_ENTITY: user_input.get(CONF_ENERGY_ENTITY, ""),
                CONF_CHAMBER_TEMP_ENTITY: user_input.get(CONF_CHAMBER_TEMP_ENTITY, ""),
            }
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                title=options[CONF_PRINTER_NAME],
                data={
                    **self.config_entry.data,
                    CONF_PRINTER_NAME: options[CONF_PRINTER_NAME],
                    CONF_POWER_ENTITY: options[CONF_POWER_ENTITY],
                    CONF_ENERGY_ENTITY: options[CONF_ENERGY_ENTITY],
                    CONF_CHAMBER_TEMP_ENTITY: options[CONF_CHAMBER_TEMP_ENTITY],
                },
                options=options,
            )
            if user_input.get("reset_history"):
                coordinator = self.hass.data[DOMAIN].get(self.config_entry.entry_id)
                if coordinator:
                    await coordinator.async_reset_history()
            return self.async_create_entry(title="", data=options)

        _entity_defaults = {
            CONF_POWER_ENTITY: self.config_entry.data.get(CONF_POWER_ENTITY),
            CONF_ENERGY_ENTITY: self.config_entry.data.get(CONF_ENERGY_ENTITY),
            CONF_CHAMBER_TEMP_ENTITY: self.config_entry.data.get(CONF_CHAMBER_TEMP_ENTITY),
        }
        _entity_schema = {}
        for key, default_val in _entity_defaults.items():
            if default_val:
                _entity_schema[vol.Optional(key, default=default_val)] = selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                )
            else:
                _entity_schema[vol.Optional(key)] = selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_PRINTER_NAME,
                        default=self.config_entry.data.get(CONF_PRINTER_NAME, ""),
                    ): selector.TextSelector(),
                    **_entity_schema,
                    vol.Optional("reset_history", default=False): selector.BooleanSelector(),
                }
            ),
        )
