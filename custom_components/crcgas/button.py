"""华润燃气 按钮平台（多户版）

提供按钮实体用于手动触发操作：
1. 抓取所有历史记录（每户一个）
2. 刷新数据（每户一个）
"""

import logging
from typing import Any, Dict, Optional

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo

from .const import CONF_CONS_LIST, CONF_CONS_NO, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities,
):
    """设置按钮实体 - 多户版，每户一对按钮"""
    # 构建户号列表
    primary_cons_no = (
        config_entry.data.get(CONF_CONS_NO)
        or config_entry.data.get("consNo")
        or ""
    )
    cons_list_raw = config_entry.data.get(CONF_CONS_LIST) or []

    cons_list = []
    for item in cons_list_raw:
        cn = item.get("cons_no") or item.get("consNo") or ""
        if cn:
            cons_list.append({
                "cons_no": cn,
                "cons_name": item.get("cons_name") or item.get("consName") or "",
                "cons_addr": item.get("cons_addr") or item.get("consAddr") or "",
            })

    if not cons_list and primary_cons_no:
        cons_list = [{"cons_no": primary_cons_no, "cons_name": "", "cons_addr": ""}]

    if not cons_list:
        _LOGGER.error("未找到户号，无法创建按钮")
        return

    # 主户排首位
    cons_list.sort(key=lambda c: 0 if c["cons_no"] == primary_cons_no else 1)

    buttons = []
    for cons_info in cons_list:
        is_primary = (cons_info["cons_no"] == primary_cons_no)
        # 主户保留旧实体ID（cons_info=None），副户带户号后缀
        effective = None if is_primary else cons_info
        buttons.append(FetchHistoryButton(hass, config_entry, effective))
        buttons.append(RefreshDataButton(hass, config_entry, effective))

    async_add_entities(buttons)
    _LOGGER.info(f"华润燃气按钮实体已注册: {len(buttons)}个（{len(cons_list)}户）")


class FetchHistoryButton(ButtonEntity):
    """抓取历史记录按钮（多户版）"""

    _attr_has_entity_name = True
    _attr_icon = "mdi:history"

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry, cons_info: Dict = None):
        self.hass = hass
        self.config_entry = config_entry
        self._cons_info = cons_info or {}
        self._cons_no = self._cons_info.get("cons_no", "")
        self._api: Optional[Any] = None

        if self._cons_no:
            # 副户：unique_id 带户号后缀
            cons_label = self._cons_info.get("cons_name") or self._cons_no
            self._attr_name = f"抓取历史记录 {cons_label}"
            self._attr_unique_id = f"{config_entry.entry_id}_{self._cons_no}_fetch_history"
        else:
            # 主户：保持旧格式
            self._attr_name = "抓取历史记录"
            self._attr_unique_id = f"{config_entry.entry_id}_fetch_history"

    async def async_added_to_hass(self) -> None:
        """添加到 Home Assistant 后获取依赖"""
        await super().async_added_to_hass()
        hass_domain = self.hass.data.get(DOMAIN, {})
        self._api = hass_domain.get(f"{self.config_entry.entry_id}_api")
        # 如果 cons_info 未提供（主户），从 hass.data 获取 cons_no
        if not self._cons_no:
            self._cons_no = (
                hass_domain.get(f"{self.config_entry.entry_id}_cons_no")
                or self.config_entry.data.get("cons_no")
                or self.config_entry.data.get("consNo", "")
            )

    @property
    def device_info(self) -> DeviceInfo:
        if self._cons_no:
            return {
                "identifiers": {(DOMAIN, self.config_entry.entry_id, self._cons_no)},
                "name": f"华润燃气 {self._cons_no}",
                "manufacturer": "华润燃气",
                "model": self._cons_info.get("cons_addr") or "燃气抄表",
            }
        return {
            "identifiers": {(DOMAIN, self.config_entry.entry_id)},
            "name": "华润燃气",
            "manufacturer": "华润燃气",
            "model": "燃气抄表",
        }

    async def async_press(self) -> None:
        """按钮按下时触发"""
        _LOGGER.info(f"用户触发: 抓取历史记录 (户号={self._cons_no or '全部'})")

        # 调用已注册的 crcgas.fetch_history 服务，传入 cons_no
        try:
            service_data = {}
            if self._cons_no:
                service_data["cons_no"] = self._cons_no
            await self.hass.services.async_call(
                DOMAIN, "fetch_history", service_data, blocking=True
            )
        except Exception as e:
            _LOGGER.error(f"抓取历史记录失败: {e}")


class RefreshDataButton(ButtonEntity):
    """刷新数据按钮（多户版）"""

    _attr_has_entity_name = True
    _attr_icon = "mdi:refresh"

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry, cons_info: Dict = None):
        self.hass = hass
        self.config_entry = config_entry
        self._cons_info = cons_info or {}
        self._cons_no = self._cons_info.get("cons_no", "")

        if self._cons_no:
            cons_label = self._cons_info.get("cons_name") or self._cons_no
            self._attr_name = f"刷新数据 {cons_label}"
            self._attr_unique_id = f"{config_entry.entry_id}_{self._cons_no}_refresh_data"
        else:
            self._attr_name = "刷新数据"
            self._attr_unique_id = f"{config_entry.entry_id}_refresh_data"

    @property
    def device_info(self) -> DeviceInfo:
        if self._cons_no:
            return {
                "identifiers": {(DOMAIN, self.config_entry.entry_id, self._cons_no)},
                "name": f"华润燃气 {self._cons_no}",
                "manufacturer": "华润燃气",
                "model": self._cons_info.get("cons_addr") or "燃气抄表",
            }
        return {
            "identifiers": {(DOMAIN, self.config_entry.entry_id)},
            "name": "华润燃气",
            "manufacturer": "华润燃气",
            "model": "燃气抄表",
        }

    async def async_press(self) -> None:
        """按钮按下时触发 - 刷新该户的 coordinator"""
        _LOGGER.info(f"用户触发: 手动刷新数据 (户号={self._cons_no or '主户'})")

        hass_domain = self.hass.data.get(DOMAIN, {})

        # 优先按户号查找 coordinator，缺省时回退到 legacy key
        coordinator = None
        if self._cons_no:
            coordinator = hass_domain.get(f"{self.config_entry.entry_id}_coordinator_{self._cons_no}")
        if not coordinator:
            coordinator = hass_domain.get(f"{self.config_entry.entry_id}_coordinator")

        if not coordinator:
            _LOGGER.error("coordinator 未初始化，请稍后重试或重启 Home Assistant")
            return

        await coordinator.async_request_refresh()
