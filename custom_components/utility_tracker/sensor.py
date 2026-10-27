"""Utility Tracker 统计传感器"""
from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_LAST_ERROR, ATTR_TOTAL_RECORDS, DOMAIN
from .coordinator import UtilityTrackerCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """注册 sensor 实体"""
    coordinator: UtilityTrackerCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([
        UtilityTrackerLastSyncSensor(coordinator, entry),
        UtilityTrackerTotalRecordsSensor(coordinator, entry),
        UtilityTrackerDBStatusSensor(coordinator, entry),
        UtilityTrackerElectricityMonthSensor(coordinator, entry),
        UtilityTrackerGasMonthSensor(coordinator, entry),
    ])


class _BaseSensor(CoordinatorEntity[UtilityTrackerCoordinator], SensorEntity):
    """基类"""

    _attr_has_entity_name = True

    def __init__(self, coordinator: UtilityTrackerCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Utility Tracker",
            "manufacturer": "Custom",
            "model": "Utility Tracker",
        }


class UtilityTrackerLastSyncSensor(_BaseSensor):
    """最近同步时间"""

    _attr_name = "Last Sync"
    _attr_icon = "mdi:sync"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_last_sync"

    @property
    def native_value(self):
        return self.coordinator.last_sync

    @property
    def extra_state_attributes(self):
        return {
            ATTR_LAST_ERROR: self.coordinator.last_error,
        }


class UtilityTrackerTotalRecordsSensor(_BaseSensor):
    """总记录数"""

    _attr_name = "Total Records"
    _attr_icon = "mdi:database"
    _attr_state_class = SensorStateClass.TOTAL

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_total_records"

    @property
    def native_value(self):
        return self.coordinator.total_records


class UtilityTrackerDBStatusSensor(_BaseSensor):
    """数据库连接状态"""

    _attr_name = "DB Status"
    _attr_icon = "mdi:database-check"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_db_status"

    @property
    def native_value(self):
        return "ok" if self.coordinator.last_error is None else "error"

    @property
    def extra_state_attributes(self):
        return {
            ATTR_LAST_ERROR: self.coordinator.last_error,
            ATTR_TOTAL_RECORDS: self.coordinator.total_records,
        }


class UtilityTrackerElectricityMonthSensor(_BaseSensor):
    """本月电费合计(所有户号)

    数据由 coordinator._async_update_data 在每次同步后查询并放入 coordinator.data,
    本 sensor 仅从 coordinator.data 读取 (CoordinatorEntity 默认 should_poll=False,
    不能依赖 async_update 被调用)。
    """

    _attr_name = "Electricity This Month"
    _attr_icon = "mdi:flash"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = "CNY"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_elec_month"

    @property
    def native_value(self):
        return (self.coordinator.data or {}).get("electricity_this_month")


class UtilityTrackerGasMonthSensor(_BaseSensor):
    """本月燃气费 (同 ElectricityMonthSensor, 从 coordinator.data 读取)"""

    _attr_name = "Gas This Month"
    _attr_icon = "mdi:fire"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = "CNY"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_gas_month"

    @property
    def native_value(self):
        return (self.coordinator.data or {}).get("gas_this_month")
