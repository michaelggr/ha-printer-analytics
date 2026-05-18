from __future__ import annotations

import json
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfEnergy, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PrinterAnalyticsCoordinator, PrinterStats

_LOGGER = logging.getLogger(__name__)
MAX_ATTR_BYTES = 14000


SENSORS: dict[str, SensorEntityDescription] = {
    "total_prints": SensorEntityDescription(
        key="total_prints",
        name="总打印次数",
        icon="mdi:chart-timeline-variant",
        native_unit_of_measurement="次",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "success_rate": SensorEntityDescription(
        key="success_rate",
        name="成功率",
        icon="mdi:check-circle",
        native_unit_of_measurement=PERCENTAGE,
    ),
    "average_duration": SensorEntityDescription(
        key="average_duration",
        name="平均打印时长",
        icon="mdi:clock-outline",
        native_unit_of_measurement=UnitOfTime.HOURS,
    ),
    "total_online_duration": SensorEntityDescription(
        key="total_online_duration",
        name="总打印时长",
        icon="mdi:clock",
        native_unit_of_measurement=UnitOfTime.HOURS,
    ),
    "total_print_duration": SensorEntityDescription(
        key="total_print_duration",
        name="打印总时长",
        icon="mdi:timer-outline",
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "material_stats_lifetime": SensorEntityDescription(
        key="material_stats_lifetime",
        name="终身耗材统计",
        icon="mdi:printer-3d-nozzle-outline",
    ),
    "material_stats_7d": SensorEntityDescription(
        key="material_stats_7d",
        name="7天耗材统计",
        icon="mdi:printer-3d-nozzle-outline",
    ),
    "material_stats_30d": SensorEntityDescription(
        key="material_stats_30d",
        name="30天耗材统计",
        icon="mdi:printer-3d-nozzle-outline",
    ),
    "total_energy": SensorEntityDescription(
        key="total_energy",
        name="总能耗",
        icon="mdi:flash",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "duration_distribution": SensorEntityDescription(
        key="duration_distribution",
        name="打印时长分布",
        icon="mdi:chart-bar",
    ),
    "activity_heatmap": SensorEntityDescription(
        key="activity_heatmap",
        name="打印活动热力图",
        icon="mdi:heatmap",
    ),
    "failure_stage_distribution": SensorEntityDescription(
        key="failure_stage_distribution",
        name="失败阶段分布",
        icon="mdi:chart-donut",
    ),
    "filament_success_stats": SensorEntityDescription(
        key="filament_success_stats",
        name="耗材成功率统计",
        icon="mdi:file-chart-outline",
    ),
    "print_history": SensorEntityDescription(
        key="print_history",
        name="打印历史",
        icon="mdi:history",
    ),
    "print_status": SensorEntityDescription(
        key="print_status",
        name="打印状态",
        icon="mdi:chart-timeline",
    ),
}


def _get_sensor_value(sensor_key: str, data: PrinterStats) -> Any:
    if data is None:
        return None
    match sensor_key:
        case "total_prints":
            return data.total_prints
        case "success_rate":
            return data.success_rate
        case "average_duration":
            return data.average_duration_hours
        case "total_online_duration":
            return data.total_duration_hours if data.total_duration_hours else 0
        case "total_print_duration":
            return data.total_duration_hours
        case "material_stats_lifetime":
            if data.total_weight_g or data.total_length_m:
                return f"总重量 {data.total_weight_g}g, 总长度 {data.total_length_m}m"
            return "暂无数据"
        case "material_stats_7d":
            if data.stats_7d.get("total_prints", 0) > 0:
                return f"总重量 {data.stats_7d.get('total_weight_g', 0)}g, 总长度 {data.stats_7d.get('total_length_m', 0)}m"
            return "暂无数据"
        case "material_stats_30d":
            if data.stats_30d.get("total_prints", 0) > 0:
                return f"总重量 {data.stats_30d.get('total_weight_g', 0)}g, 总长度 {data.stats_30d.get('total_length_m', 0)}m"
            return "暂无数据"
        case "total_energy":
            return data.total_energy_kwh
        case "duration_distribution":
            total = sum(data.duration_distribution.values()) if isinstance(data.duration_distribution, dict) else 0
            return total
        case "activity_heatmap":
            total = sum(data.activity_heatmap.values()) if isinstance(data.activity_heatmap, dict) else 0
            return total
        case "failure_stage_distribution":
            total = sum(data.failure_stage_distribution.values()) if isinstance(data.failure_stage_distribution, dict) else 0
            return total
        case "filament_success_stats":
            total = len(data.filament_success_stats) if isinstance(data.filament_success_stats, dict) else 0
            return total
        case "print_history":
            return data.last_update or "暂无数据"
        case "print_status":
            return "打印中" if data.is_printing else "空闲"
        case _:
            return None


def _get_sensor_attrs(sensor_key: str, data: PrinterStats) -> dict | None:
    if data is None:
        return None
    match sensor_key:
        case "material_stats_lifetime":
            return data.stats_lifetime
        case "material_stats_7d":
            return data.stats_7d
        case "material_stats_30d":
            return data.stats_30d
        case "duration_distribution":
            return data.duration_distribution
        case "activity_heatmap":
            return data.activity_heatmap
        case "failure_stage_distribution":
            return data.failure_stage_distribution
        case "filament_success_stats":
            return data.filament_success_stats
        case "print_history":
            return _truncate_history_attrs(data)
        case _:
            return None


def _sanitize_for_attrs(obj):
    """递归清理数据，移除内部字段（以_开头），确保值类型安全"""
    if obj is None:
        return None
    if isinstance(obj, dict):
        return {k: _sanitize_for_attrs(v) for k, v in obj.items()
             if isinstance(k, str) and not k.startswith('_')}
    if isinstance(obj, list):
        return [_sanitize_for_attrs(item) for item in obj]
    if isinstance(obj, (str, int, float, bool)):
        return obj
    return str(obj)


def _truncate_history_attrs(data: PrinterStats) -> dict:
    """构建 print_history 属性，确保不超过 HA recorder 的 16384 字节限制"""
    try:
        history = _sanitize_for_attrs(data.history) or []
        total_count = len(history) if isinstance(history, list) else 0
        current_print = _sanitize_for_attrs(data.current_print)

        full_result = {"history": history, "current_print": current_print, "total_count": total_count}
        full_size = len(json.dumps(full_result, ensure_ascii=False).encode('utf-8'))

        if full_size <= MAX_ATTR_BYTES:
            return full_result

        # 尝试压缩 current_print
        if current_print and isinstance(current_print, dict):
            compact_print = {
                k: current_print[k] for k in ('status', 'task_name', 'start_time', 'end_time',
                                               'duration_hours', 'total_weight', 'total_length',
                                               'progress', 'filament_type', 'cover_image_local')
                if k in current_print
            }
            full_result = {"history": history, "current_print": compact_print, "total_count": total_count}
            full_size = len(json.dumps(full_result, ensure_ascii=False).encode('utf-8'))
            if full_size <= MAX_ATTR_BYTES:
                return full_result

        # 计算可用空间并截断 history
        overhead_result = {"history": [], "current_print": current_print, "total_count": total_count}
        overhead_size = len(json.dumps(overhead_result, ensure_ascii=False).encode('utf-8'))
        available = MAX_ATTR_BYTES - overhead_size

        if available <= 0:
            return {"current_print": current_print, "total_count": total_count, "truncated": True}

        if isinstance(history, list) and len(history) > 0:
            sample = history[-10:] if len(history) >= 10 else history
            sample_size = len(json.dumps(sample, ensure_ascii=False).encode('utf-8'))
            avg_size = sample_size / max(len(sample), 1)
            estimated_count = max(int(available / avg_size * 0.85), 1)
            truncated = history[-estimated_count:]
        else:
            truncated = []

        result = {"history": truncated, "current_print": current_print, "total_count": total_count}
        if len(json.dumps(result, ensure_ascii=False).encode('utf-8')) > MAX_ATTR_BYTES:
            truncated = truncated[:len(truncated) // 2]
            result = {"history": truncated, "current_print": current_print, "total_count": total_count}

        if len(truncated) < total_count:
            result["truncated"] = True
        return result
    except Exception as err:
        import logging
        logging.getLogger(__name__).error("print_history 截断失败: %s", err)
        return {"total_count": len(data.history) if data.history else 0, "truncated": True}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: PrinterAnalyticsCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        PrinterAnalyticsSensor(coordinator, key, desc)
        for key, desc in SENSORS.items()
    ]
    async_add_entities(entities)


class PrinterAnalyticsSensor(CoordinatorEntity[PrinterAnalyticsCoordinator], SensorEntity):

    def __init__(
        self,
        coordinator: PrinterAnalyticsCoordinator,
        sensor_key: str,
        description: SensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._sensor_key = sensor_key
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{sensor_key}"
        self._attr_name = f"{coordinator.printer_name} {description.name}"
        self._attr_has_entity_name = True
        if sensor_key == "print_history":
            self._attr_entity_id = f"sensor.{coordinator.printer_name}_print_history"
        elif sensor_key == "print_status":
            self._attr_entity_id = f"sensor.{coordinator.printer_name}_print_status"

    @property
    def device_info(self) -> dict:
        return {
            "identifiers": {(DOMAIN, self.coordinator.entry.entry_id)},
            "name": self.coordinator.printer_name,
            "manufacturer": "Printer Analytics",
            "model": "3D Printer Analytics",
        }

    @property
    def native_value(self) -> Any:
        return _get_sensor_value(self._sensor_key, self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        return _get_sensor_attrs(self._sensor_key, self.coordinator.data)

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and self.coordinator.data is not None
