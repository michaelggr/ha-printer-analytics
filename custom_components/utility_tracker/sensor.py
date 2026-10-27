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
        # 分户: 自住 (东方新天地) vs 出租 (东方佳园)
        UtilityTrackerElecMonthMainSensor(coordinator, entry),
        UtilityTrackerElecMonthRentalSensor(coordinator, entry),
        UtilityTrackerGasMonthMainSensor(coordinator, entry),
        UtilityTrackerGasMonthRentalSensor(coordinator, entry),
        UtilityTrackerCurrentPowerSensor(coordinator, entry),
        UtilityTrackerPowerTodaySensor(coordinator, entry),
        UtilityTrackerLightCountTodaySensor(coordinator, entry),
        UtilityTrackerLightDurationTodaySensor(coordinator, entry),
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
        ts = self.coordinator.last_sync
        if ts is None:
            return None
        # HA TIMESTAMP device class 要求 timezone-aware datetime
        if ts.tzinfo is None:
            from homeassistant.util.dt import get_default_time_zone
            return ts.replace(tzinfo=get_default_time_zone())
        return ts

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
            "gas_discovery": self.coordinator.last_gas_discovery,
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


# =====================================================================
# 分户月度传感器 (自住 vs 出租)
# 电: 0065=自住(东方新天地), 7061=出租(东方佳园)
# 气: 1040395237=自住(东方新天地), 1021540961=出租(东方佳园)
# =====================================================================


class _MonthCostBaseSensor(_BaseSensor):
    """分户月度费用 sensor 基类"""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = "CNY"
    _data_key: str = ""
    _uid_suffix: str = ""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_{self._uid_suffix}"

    @property
    def native_value(self):
        return (self.coordinator.data or {}).get(self._data_key)


class UtilityTrackerElecMonthMainSensor(_MonthCostBaseSensor):
    """本月电费-自住 (东方新天地 0065)"""

    _attr_name = "Electricity This Month Main"
    _attr_icon = "mdi:flash"
    _data_key = "electricity_this_month_main"
    _uid_suffix = "elec_month_main"


class UtilityTrackerElecMonthRentalSensor(_MonthCostBaseSensor):
    """本月电费-出租 (东方佳园 7061)"""

    _attr_name = "Electricity This Month Rental"
    _attr_icon = "mdi:flash-outline"
    _data_key = "electricity_this_month_rental"
    _uid_suffix = "elec_month_rental"


class UtilityTrackerGasMonthMainSensor(_MonthCostBaseSensor):
    """本月燃气费-自住 (东方新天地 1040395237)"""

    _attr_name = "Gas This Month Main"
    _attr_icon = "mdi:fire"
    _data_key = "gas_this_month_main"
    _uid_suffix = "gas_month_main"


class UtilityTrackerGasMonthRentalSensor(_MonthCostBaseSensor):
    """本月燃气费-出租 (东方佳园 1021540961)"""

    _attr_name = "Gas This Month Rental"
    _attr_icon = "mdi:fire-circle"
    _data_key = "gas_this_month_rental"
    _uid_suffix = "gas_month_rental"


# =====================================================================
# 设备功耗 sensor
# =====================================================================


class UtilityTrackerCurrentPowerSensor(_BaseSensor):
    """当前所有设备实时功率合计 (W)"""

    _attr_name = "Current Power"
    _attr_icon = "mdi:lightning-bolt-circle"
    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = "W"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_current_power"

    @property
    def native_value(self):
        return (self.coordinator.data or {}).get("power_current_w")


class UtilityTrackerPowerTodaySensor(_BaseSensor):
    """今日所有设备耗电合计 (kWh)"""

    _attr_name = "Power Today"
    _attr_icon = "mdi:counter"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = "kWh"
    _attr_state_class = SensorStateClass.TOTAL

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_power_today"

    @property
    def native_value(self):
        return (self.coordinator.data or {}).get("power_today_kwh")


# =====================================================================
# 灯光统计 sensor
# =====================================================================


class UtilityTrackerLightCountTodaySensor(_BaseSensor):
    """今日开灯次数合计"""

    _attr_name = "Light Count Today"
    _attr_icon = "mdi:lightbulb-on"
    _attr_state_class = SensorStateClass.TOTAL

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_light_count_today"

    @property
    def native_value(self):
        return (self.coordinator.data or {}).get("light_today_count")


class UtilityTrackerLightDurationTodaySensor(_BaseSensor):
    """今日亮灯时长合计 (秒 -> 小时)"""

    _attr_name = "Light Duration Today"
    _attr_icon = "mdi:timer-outline"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = "h"
    _attr_state_class = SensorStateClass.TOTAL

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_light_duration_today"

    @property
    def native_value(self):
        sec = (self.coordinator.data or {}).get("light_today_seconds") or 0
        # 秒转小时,保留 2 位小数
        return round(sec / 3600.0, 2)
