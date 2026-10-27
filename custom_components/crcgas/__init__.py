"""华润燃气 Home Assistant 集成"""
import logging

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval

from .api import HuarunGasApi, SessionTimeoutError
from .const import (
    CONF_BO_TOKEN,
    CONF_REFRESH_TOKEN,
    CONF_WX_CODE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    PLATFORMS,
    TOKEN_EXPIRE_THRESHOLD,
)
from . import sensor  # noqa: F401  # 预导入避免 Event Loop 阻塞

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    _LOGGER.info(f"设置华润燃气集成: {entry.title}")
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = dict(entry.data)

    # ========== Token 刷新策略 ==========
    # doRefreshToken 只在 bo-token/refresh-token 真正过期时才返回新 token
    # 平时调返回 COMMON_ERROR + 长数字串（请求错误）
    # 所以只保留"紧急刷新"定时器：token 剩余时间不足阈值时才刷新

    refresh_token = entry.data.get(CONF_REFRESH_TOKEN, "")
    bo_token = entry.data.get(CONF_BO_TOKEN, "")
    wx_code = entry.data.get(CONF_WX_CODE, "")

    async def on_token_refresh(new_refresh_token: str, new_bo_token: str, new_wx_code: str = None):
        """Token刷新后持久化到 config_entry"""
        _LOGGER.info("保存新Token到config_entry")
        new_data = {**entry.data}
        new_data[CONF_REFRESH_TOKEN] = new_refresh_token
        new_data[CONF_BO_TOKEN] = new_bo_token
        if new_wx_code:
            new_data[CONF_WX_CODE] = new_wx_code
        hass.config_entries.async_update_entry(entry, data=new_data)

    session = async_get_clientsession(hass)
    api = HuarunGasApi(refresh_token, bo_token, wx_code, on_token_refresh, session=session)
    hass.data[DOMAIN][f"{entry.entry_id}_api"] = api

    async def _async_refresh_token_urgent(now=None):
        """紧急刷新：Token 剩余时间不足阈值时才调 doRefreshToken"""
        try:
            remaining = api.get_token_remaining_seconds()
            threshold_seconds = int(TOKEN_EXPIRE_THRESHOLD.total_seconds())
            if remaining is None or remaining >= threshold_seconds:
                return
            _LOGGER.info(f"Token剩余{remaining}秒(<{threshold_seconds}秒)，立即刷新...")
            await api.async_refresh_token()
            _LOGGER.info("Token刷新成功")
        except SessionTimeoutError:
            _LOGGER.error("Token刷新失败(会话超时)，需要重新登录")
        except Exception as e:
            _LOGGER.error(f"Token刷新异常: {e}")

    # 每 1 分钟检查一次是否需要紧急刷新
    cancel_timer_urgent = async_track_time_interval(
        hass,
        _async_refresh_token_urgent,
        timedelta(minutes=1),
    )
    hass.data[DOMAIN][f"{entry.entry_id}_token_timer_urgent"] = cancel_timer_urgent
    _LOGGER.info(f"Token紧急刷新定时器已启动，检查间隔: 1分钟")

    # 注意：启动时不调 doRefreshToken（wxCode 是全新的，直接用就行）
    # doRefreshToken 在 token 未过期时调也返回 COMMON_ERROR

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    _LOGGER.info(f"卸载华润燃气集成: {entry.title}")
    cancel_timer_urgent = hass.data[DOMAIN].pop(f"{entry.entry_id}_token_timer_urgent", None)
    if cancel_timer_urgent:
        cancel_timer_urgent()
        _LOGGER.info("Token紧急刷新定时器已取消")
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        hass.data[DOMAIN].pop(f"{entry.entry_id}_coordinator", None)
        hass.data[DOMAIN].pop(f"{entry.entry_id}_api", None)
        hass.data[DOMAIN].pop(f"{entry.entry_id}_cons_no", None)
        # 清理多户 coordinator keys
        cons_list = entry.data.get("cons_list") or []
        for item in cons_list:
            cn = item.get("cons_no") or item.get("consNo") or ""
            if cn:
                hass.data[DOMAIN].pop(f"{entry.entry_id}_coordinator_{cn}", None)
    return unload_ok
