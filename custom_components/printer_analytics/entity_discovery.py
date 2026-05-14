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
)

if TYPE_CHECKING:
    from .coordinator import PrinterAnalyticsCoordinator

LOGGER = logging.getLogger(__name__)

_INVALID_ENTITY_STATES = frozenset({"unknown", "unavailable", ""})


class EntityDiscovery:
    """实体发现管理器"""

    def __init__(self, coordinator: "PrinterAnalyticsCoordinator") -> None:
        self.coordinator = coordinator
        self.hass = coordinator.hass
        self.printer_name = coordinator.printer_name
        self._entity_map = coordinator._entity_map
        self._discovery_retry_scheduled = False

    async def discover(self) -> None:
        """自动发现BambuLab实体"""
        prefix = self.printer_name.lower().replace(" ", "_")

        discovered = {}

        for state in self.hass.states.async_all():
            eid = state.entity_id
            if not eid.startswith("sensor.") and not eid.startswith("binary_sensor."):
                continue

            friendly_name = state.attributes.get("friendly_name", "")
            if not friendly_name:
                continue

            matched_key = self._match_entity_key(friendly_name, prefix)
            if matched_key:
                discovered[matched_key] = eid

        for key, entity_id in discovered.items():
            if key not in self._entity_map:
                self._entity_map[key] = entity_id

        for cam_eid in self.hass.states.async_entity_ids("camera"):
            if cam_eid.startswith(f"camera.{prefix}_") and cam_eid.endswith("_camera"):
                self._entity_map.setdefault("camera", cam_eid)
                break

        for img_eid in self.hass.states.async_entity_ids("image"):
            if img_eid.startswith(f"image.{prefix}_") and img_eid.endswith("_cover_image"):
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

        if not any(p in name_lower for p in ["bambu", "printer", "ams"]):
            return None

        name_cleaned = name_lower.replace(f"{prefix_lower}_", "").replace(f"{prefix_lower}", "").strip("_ -")

        for key in list(BAMBULAB_ENTITY_KEYS) + list(BAMBULAB_IMAGE_KEYS) + list(BAMBULAB_CAMERA_KEYS):
            key_cleaned = key.replace("_", " ")
            if name_cleaned == key_cleaned or name_cleaned.startswith(key_cleaned + " ") or name_cleaned.endswith(" " + key_cleaned):
                return key

        for key, patterns in self._get_extra_patterns().items():
            for pattern in patterns:
                if re.search(pattern, name_lower):
                    return key

        return None

    def _get_extra_patterns(self) -> dict[str, list[str]]:
        """额外的匹配模式"""
        return {
            "print_weight": [r"weight|重量"],
            "print_length": [r"length|长度"],
            "nozzle_temp": [r"nozzle.*temp|temp.*nozzle|喷嘴.*温"],
            "bed_temp": [r"bed.*temp|temp.*bed|热床.*温"],
            "chamber_temp": [r"chamber|腔体| enclosure"],
            "progress": [r"progress|进度"],
            "layer": [r"layer|层"],
            "start_time": [r"start.*time|开始.*时间"],
            "end_time": [r"end.*time|结束.*时间"],
        }

    def get_entity_state(self, entity_id: str, default: Any = None) -> Any:
        """获取实体状态"""
        if not entity_id:
            return default
        state = self.hass.states.get(entity_id)
        return state.state if state and state.state not in _INVALID_ENTITY_STATES else default

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
