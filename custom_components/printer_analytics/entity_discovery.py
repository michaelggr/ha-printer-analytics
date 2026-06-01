"""实体发现模块"""
import logging
import re
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry

from .const import (
    BAMBULAB_ENTITY_KEYS,
    BAMBULAB_IMAGE_KEYS,
    BAMBULAB_CAMERA_KEYS,
    ENTITY_DISCOVERY_DELAY_SECS,
    ENTITY_DISCOVERY_RETRY_SECS,
    INVALID_ENTITY_STATES,
)

if TYPE_CHECKING:
    from .coordinator import PrinterAnalyticsCoordinator

LOGGER = logging.getLogger(__name__)


class EntityDiscovery:
    """实体发现管理器"""

    def __init__(self, coordinator: "PrinterAnalyticsCoordinator") -> None:
        self.coordinator = coordinator
        self.hass = coordinator.hass
        self.printer_name = coordinator.printer_name
        self._entity_map = coordinator._entity_map
        self._discovery_retry_scheduled = False

    async def discover(self) -> None:
        """自动发现BambuLab实体

        实体发现使用两种前缀匹配：
        1. printer_name（用户自定义名称，如"大黑奴"）→ 匹配 friendly_name
        2. 序列号前缀（如"p2s_22e8bj5a2401765"）→ 匹配 entity_id 和 friendly_name

        Bambu Lab 实体的 friendly_name 格式为 "P2S_22E8BJ5A2401765 GCODE文件下载"，
        entity_id 格式为 "sensor.p2s_22e8bj5a2401765_gcode_file_downloaded"。
        用户自定义名称（如"大黑奴"）不会出现在 Bambu Lab 实体中。
        """
        prefix = self.printer_name.lower().replace(" ", "_")
        serial_prefix = ""
        serial = self.coordinator.printer_serial
        if serial:
            serial_prefix = serial.lower()

        discovered = {}

        for state in self.hass.states.async_all():
            eid = state.entity_id
            if not eid.startswith("sensor.") and not eid.startswith("binary_sensor."):
                continue

            friendly_name = state.attributes.get("friendly_name", "")
            if not friendly_name:
                continue

            # 先用 printer_name 前缀匹配
            matched_key = self._match_entity_key(friendly_name, prefix)
            # 如果 printer_name 匹配失败，用序列号前缀匹配
            if not matched_key and serial_prefix:
                matched_key = self._match_entity_key(friendly_name, serial_prefix)
            # 如果 friendly_name 匹配都失败，尝试从 entity_id 匹配
            if not matched_key and serial_prefix and serial_prefix in eid:
                matched_key = self._match_entity_key_by_entity_id(eid, serial_prefix)

            if matched_key:
                discovered[matched_key] = eid

        for key, entity_id in discovered.items():
            if key not in self._entity_map:
                self._entity_map[key] = entity_id

        # 用序列号前缀发现 camera/light/image 实体
        search_prefix = serial_prefix or prefix
        for cam_eid in self.hass.states.async_entity_ids("camera"):
            if cam_eid.startswith(f"camera.{search_prefix}_") and cam_eid.endswith("_camera"):
                self._entity_map.setdefault("camera", cam_eid)
                break

        for light_eid in self.hass.states.async_entity_ids("light"):
            if light_eid.startswith(f"light.{search_prefix}_") and "chamber_light" in light_eid:
                self._entity_map.setdefault("chamber_light", light_eid)
                break

        for img_eid in self.hass.states.async_entity_ids("image"):
            if img_eid.startswith(f"image.{search_prefix}_") and img_eid.endswith("_cover_image"):
                self._entity_map.setdefault("cover_image", img_eid)
                break

        if not self._entity_map.get("print_weight") and not self._discovery_retry_scheduled:
            self._discovery_retry_scheduled = True
            self.hass.loop.call_later(
                ENTITY_DISCOVERY_DELAY_SECS,
                lambda: self.hass.async_create_task(self._retry_discovery()),
            )

        LOGGER.info(
            "实体发现完成 for %s: %s",
            self.printer_name,
            self._entity_map,
        )

    async def _retry_discovery(self) -> None:
        """重试发现（延迟执行）"""
        self._discovery_retry_scheduled = False
        await self.discover()

    def _match_entity_key(self, friendly_name: str, prefix: str) -> str | None:
        """匹配实体键"""
        name_lower = friendly_name.lower()
        prefix_lower = prefix.lower()

        if prefix_lower not in name_lower:
            return None

        name_cleaned = name_lower.replace(f"{prefix_lower}_", "").replace(f"{prefix_lower}", "").strip("_ -")

        for key in list(BAMBULAB_ENTITY_KEYS) + list(BAMBULAB_IMAGE_KEYS) + list(BAMBULAB_CAMERA_KEYS):
            key_cleaned = key.replace("_", " ")
            if key_cleaned in name_cleaned or name_cleaned == key_cleaned or name_cleaned.startswith(key_cleaned + " ") or name_cleaned.endswith(" " + key_cleaned):
                return key

        for key, patterns in self._get_extra_patterns().items():
            for pattern in patterns:
                if re.search(pattern, name_lower):
                    return key

        return None

    def _match_entity_key_by_entity_id(self, entity_id: str, prefix: str) -> str | None:
        """从 entity_id 匹配实体键

        当 friendly_name 匹配失败时，从 entity_id 格式推断实体键。
        entity_id 格式: sensor.{device_prefix}_{key_with_underscores}
        例: sensor.p2s_22e8bj5a2401765_gcode_file_downloaded → gcode_file_downloaded

        prefix 可能是序列号（如 22e8bj5a2401765），而 entity_id 中
        包含的是设备型号+序列号（如 p2s_22e8bj5a2401765）。
        """
        eid_lower = entity_id.lower()
        prefix_lower = prefix.lower()

        parts = eid_lower.split(".")
        if len(parts) < 2:
            return None

        after_domain = parts[1]

        # 查找 prefix 在 entity_id 中的位置，取其后面的部分作为键
        idx = after_domain.find(prefix_lower)
        if idx < 0:
            return None

        # 键部分从 prefix 结束后开始
        key_start = idx + len(prefix_lower)
        if key_start >= len(after_domain):
            return None

        # 跳过下划线分隔符
        if after_domain[key_start] == "_":
            key_start += 1

        key_part = after_domain[key_start:]

        # 直接匹配 BambuLab 实体键
        all_keys = list(BAMBULAB_ENTITY_KEYS) + list(BAMBULAB_IMAGE_KEYS) + list(BAMBULAB_CAMERA_KEYS)
        if key_part in all_keys:
            return key_part

        # 模糊匹配：将 key_part 中的下划线替换为空格，与键名比较
        key_as_name = key_part.replace("_", " ")
        for key in all_keys:
            key_cleaned = key.replace("_", " ")
            if key_cleaned == key_as_name:
                return key

        return None

    def _get_extra_patterns(self) -> dict[str, list[str]]:
        """额外的匹配模式（顺序重要：更具体的 pattern 放前面）"""
        return {
            "serial_number": [r"serial.*number|serial|序列号"],
            "print_status": [r"print.*status|status.*print|打印.*状态|状态"],
            "print_weight": [r"weight|重量"],
            "print_length": [r"length|长度"],
            "nozzle_temp": [r"nozzle.*temp|temp.*nozzle|喷嘴.*温"],
            "bed_temp": [r"bed.*temp|temp.*bed|热床.*温"],
            "chamber_temp": [r"chamber|腔体| enclosure"],
            "progress": [r"progress|进度"],
            "total_layer_count": [r"total.*layer|总.*层|总层数|layer.*count"],
            "layer": [r"layer|层"],
            "start_time": [r"start.*time|开始.*时间"],
            "end_time": [r"end.*time|结束.*时间"],
            "task_name": [r"task.*name|subtask|任务.*名称|任务名|taskname"],
            "gcode_filename": [r"gcode.*file|gcode.*filename|文件名"],
            "gcode_file_downloaded": [r"gcode.*download|下载.*gcode|GCODE文件下载"],
            "active_tray": [r"active.*tray|ams.*tray|活动.*托盘|当前.*托盘|激活.*料盘"],
            "externalspool_active": [r"externalspool.*active|外挂.*激活|外挂.*料盘.*激活"],
            "ams_active": [r"ams_\d+_active|ams.*active"],
            "externalspool_name": [r"externalspool.*external.*spool|外挂.*料盘"],
            "nozzle_type": [r"nozzle.*type|喷嘴.*类型"],
            "nozzle_size": [r"nozzle.*size|喷嘴.*尺寸|喷嘴.*直径|喷嘴直径"],
            "print_bed_type": [r"print.*bed|打印.*床|热床.*类型|打印.*板.*类型|打印板类型"],
            "speed_profile": [r"speed.*profile|速度.*配置"],
            "print_type": [r"print.*type|打印.*类型|打印类型"],
        }

    def get_entity_state(self, entity_id: str, default: Any = None) -> Any:
        """获取实体状态"""
        if not entity_id:
            return default
        state = self.hass.states.get(entity_id)
        return state.state if state and state.state not in INVALID_ENTITY_STATES else default

    def get_entity_attr(self, entity_id: str, attr: str, default: Any = None) -> Any:
        """获取实体属性"""
        if not entity_id:
            return default
        state = self.hass.states.get(entity_id)
        return state.attributes.get(attr, default) if state else default

    def get_float_state(self, entity_id: str, default: float = 0.0) -> float:
        """获取浮点型实体状态"""
        state = self.get_entity_state(entity_id)
        if state is None:
            return default
        try:
            value = float(state)
            return value if value >= 0 else default
        except (ValueError, TypeError):
            return default
