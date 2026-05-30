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
    "multi_color_ratio": SensorEntityDescription(
        key="multi_color_ratio",
        name="多色模型占比",
        icon="mdi:palette-outline",
    ),
    "prepare_time_by_filament": SensorEntityDescription(
        key="prepare_time_by_filament",
        name="材料准备时间",
        icon="mdi:timer-sand",
    ),
    "slice_mode_distribution": SensorEntityDescription(
        key="slice_mode_distribution",
        name="切片模式分布",
        icon="mdi:cloud-outline",
    ),
    "over_500g_ratio": SensorEntityDescription(
        key="over_500g_ratio",
        name="超500g模型占比",
        icon="mdi:weight",
    ),
    "nozzle_size_distribution": SensorEntityDescription(
        key="nozzle_size_distribution",
        name="喷嘴尺寸分布",
        icon="mdi:circle-outline",
    ),
    "failed_chamber_temp_distribution": SensorEntityDescription(
        key="failed_chamber_temp_distribution",
        name="失败仓温分布",
        icon="mdi:thermometer-alert",
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
        case "multi_color_ratio":
            total = sum(data.multi_color_ratio.values()) if isinstance(data.multi_color_ratio, dict) else 0
            return total
        case "prepare_time_by_filament":
            total = len(data.prepare_time_by_filament) if isinstance(data.prepare_time_by_filament, dict) else 0
            return total
        case "slice_mode_distribution":
            total = sum(data.slice_mode_distribution.values()) if isinstance(data.slice_mode_distribution, dict) else 0
            return total
        case "over_500g_ratio":
            total = sum(data.over_500g_ratio.values()) if isinstance(data.over_500g_ratio, dict) else 0
            return total
        case "nozzle_size_distribution":
            total = sum(data.nozzle_size_distribution.values()) if isinstance(data.nozzle_size_distribution, dict) else 0
            return total
        case "failed_chamber_temp_distribution":
            total = sum(data.failed_chamber_temp_distribution.values()) if isinstance(data.failed_chamber_temp_distribution, dict) else 0
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
        case "multi_color_ratio":
            return data.multi_color_ratio
        case "prepare_time_by_filament":
            return data.prepare_time_by_filament
        case "slice_mode_distribution":
            return data.slice_mode_distribution
        case "over_500g_ratio":
            return data.over_500g_ratio
        case "nozzle_size_distribution":
            return data.nozzle_size_distribution
        case "failed_chamber_temp_distribution":
            return data.failed_chamber_temp_distribution
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
    """构建 print_history 属性（history 已限制为最近50条，通常无需截断）"""
    try:
        history = _sanitize_for_attrs(data.history) or []
        total_count = data.total_prints  # 使用真实总数，而非 len(history)
        current_print = _sanitize_for_attrs(data.current_print)

        # 确保 history 按降序排列（最新在前），方便前端展示
        if history and len(history) > 1:
            first_et = history[0].get("end_time", "") if isinstance(history[0], dict) else ""
            last_et = history[-1].get("end_time", "") if isinstance(history[-1], dict) else ""
            if first_et < last_et:
                history = list(reversed(history))

        result = {"history": history, "current_print": current_print, "total_count": total_count}

        # 检查大小是否超限（HA recorder 16384 字节限制）
        result_size = len(json.dumps(result, ensure_ascii=False).encode('utf-8'))
        if result_size <= MAX_ATTR_BYTES:
            return result

        # 超限时逐步截断
        if current_print and isinstance(current_print, dict):
            compact_print = {
                k: current_print[k] for k in ('status', 'task_name', 'task_name_model', 'task_name_config',
                                               'start_time', 'end_time', 'duration_hours',
                                               'total_weight', 'total_length', 'progress',
                                               'cached_weight', 'cached_length',
                                               'filament_type', 'filament_color', 'cover_image_local',
                                               'colors_used', 'color_changes')
                if k in current_print
            }
            result = {"history": history, "current_print": compact_print, "total_count": total_count}
            if len(json.dumps(result, ensure_ascii=False).encode('utf-8')) <= MAX_ATTR_BYTES:
                return result

        # 仍然超限，精简记录字段后再截断
        slim_keys = ('task_name', 'end_time', 'status', 'filament_type', 'filament_color',
                     'total_weight', 'duration_hours', 'colors_used', 'printer_serial',
                     'start_time', 'print_progress', 'cover_image_local', 'design_id')
        slim_history = [{k: r[k] for k in slim_keys if k in r} for r in history]
        result = {"history": slim_history, "current_print": current_print, "total_count": total_count}
        if len(json.dumps(result, ensure_ascii=False).encode('utf-8')) <= MAX_ATTR_BYTES:
            if len(slim_history) < total_count:
                result["truncated"] = True
            return result

        # 精简后仍超限，降序排列下去掉尾部旧记录
        while len(slim_history) > 5:
            cut = len(slim_history) // 3
            slim_history = slim_history[:-cut] if cut > 0 else slim_history[:5]
            result = {"history": slim_history, "current_print": current_print, "total_count": total_count}
            if len(json.dumps(result, ensure_ascii=False).encode('utf-8')) <= MAX_ATTR_BYTES:
                break

        if len(history) < total_count:
            result["truncated"] = True
        return result
    except Exception as err:
        import logging
        logging.getLogger(__name__).error("print_history 截断失败: %s", err)
        return {"total_count": data.total_prints if data else 0, "truncated": True}


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
        # 所有传感器显式设置英文 entity_id，避免 HA 自动生成拼音 ID
        self._attr_entity_id = f"sensor.{coordinator.printer_name}_{sensor_key}"

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
        attrs = _get_sensor_attrs(self._sensor_key, self.coordinator.data)
        # 为 print_history 传感器添加 entry_id 和 printer_serial，供前端获取
        if self._sensor_key == "print_history" and attrs is not None:
            attrs["entry_id"] = self.coordinator.entry.entry_id
            if self.coordinator.printer_serial:
                attrs["printer_serial"] = self.coordinator.printer_serial
        return attrs

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and self.coordinator.data is not None
