"""Bambu Cloud API 调用与数据转换模块

负责：
- Bambu Cloud 认证（发送验证码、登录、Token 检查）
- 分页拉取云端打印历史
- 将 Bambu Cloud 数据转换为 HA printer_analytics v3 格式
- Token 持久化存储（HA .storage 目录）

数据转换逻辑移植自 bambu-export-web/src/utils/bambu-transform.ts
"""
import json
import logging
import os
import time

import aiohttp

LOGGER = logging.getLogger(__name__)

API_CN = "https://api.bambulab.cn"
API_GLOBAL = "https://api.bambulab.com"
PAGE_SIZE = 20

_REQUEST_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "X-BBL-Client-Type": "slicer",
    "X-BBL-Language": "zh-CN",
}

_AUTH_STORAGE_KEY = "printer_analytics_bambu_auth"


def _is_phone(account: str) -> bool:
    return "@" not in account


def _get_base_url(account: str) -> str:
    return API_CN if _is_phone(account) else API_GLOBAL


# ---------------------------------------------------------------------------
# Token 存储
# ---------------------------------------------------------------------------

async def load_bambu_token(hass) -> dict | None:
    storage_dir = hass.config.path(".storage")
    filepath = os.path.join(storage_dir, _AUTH_STORAGE_KEY)
    exists = await hass.async_add_executor_job(os.path.isfile, filepath)
    if not exists:
        return None
    try:
        raw = await hass.async_add_executor_job(
            lambda: open(filepath, "r", encoding="utf-8").read()
        )
        return json.loads(raw)
    except Exception as err:
        LOGGER.warning("加载 Bambu 认证信息失败: %s", err)
        return None


async def save_bambu_token(hass, auth_data: dict) -> None:
    storage_dir = hass.config.path(".storage")
    filepath = os.path.join(storage_dir, _AUTH_STORAGE_KEY)

    def _write():
        os.makedirs(storage_dir, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(auth_data, f, ensure_ascii=False, indent=2)

    await hass.async_add_executor_job(_write)


async def delete_bambu_token(hass) -> None:
    storage_dir = hass.config.path(".storage")
    filepath = os.path.join(storage_dir, _AUTH_STORAGE_KEY)

    def _delete():
        if os.path.isfile(filepath):
            os.remove(filepath)

    await hass.async_add_executor_job(_delete)


# ---------------------------------------------------------------------------
# 认证 API
# ---------------------------------------------------------------------------

async def send_code(account: str) -> dict:
    base = _get_base_url(account)
    phone = _is_phone(account)
    url = f"{base}/v1/user-service/user/sendsmscode" if phone else f"{base}/v1/user-service/user/sendemail/code"
    body = {"phone": account, "type": "codeLogin"} if phone else {"email": account, "type": "codeLogin"}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=body, headers=_REQUEST_HEADERS) as resp:
                if resp.status == 429:
                    return {"success": False, "error": "请求过于频繁，请稍后重试"}
                if resp.status == 418:
                    return {"success": False, "error": "需要人机验证，请稍后重试"}
                data = await resp.json()
                status_code = data.get("statusCode")
                if status_code is not None and status_code not in (0, 200):
                    return {"success": False, "error": data.get("message") or data.get("error") or "发送验证码失败"}
                if data.get("error"):
                    return {"success": False, "error": str(data.get("message") or data.get("error") or "发送验证码失败")}
                return {"success": True}
    except Exception as err:
        return {"success": False, "error": f"网络错误: {err}"}


async def login_with_code(account: str, code: str) -> dict:
    base = _get_base_url(account)
    url = f"{base}/v1/user-service/user/login"
    body = {"account": account, "code": code}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=body, headers=_REQUEST_HEADERS) as resp:
                data = await resp.json()
                token = data.get("accessToken")
                if token:
                    return {"success": True, "token": str(token)}
                return {"success": False, "error": str(data.get("message") or data.get("error") or "登录失败")}
    except Exception as err:
        return {"success": False, "error": f"网络错误: {err}"}


async def check_token(token: str) -> bool:
    for base in [API_CN, API_GLOBAL]:
        url = f"{base}/v1/user-service/my/tasks?limit=1&offset=0"
        headers = {**_REQUEST_HEADERS, "Authorization": f"Bearer {token}"}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        return True
                    if resp.status == 401:
                        return False
        except Exception:
            continue
    return False


# ---------------------------------------------------------------------------
# 历史记录 API
# ---------------------------------------------------------------------------

async def _fetch_page(token: str, base_url: str, offset: int = 0) -> tuple[list | None, int]:
    url = f"{base_url}/v1/user-service/my/tasks?limit={PAGE_SIZE}&offset={offset}"
    headers = {**_REQUEST_HEADERS, "Authorization": f"Bearer {token}"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 401:
                    return None, -1
                if resp.status != 200:
                    return [], 0
                data = await resp.json()
                hits = data.get("hits") or data.get("tasks") or []
                total = data.get("total") or data.get("count") or 0
                return hits, total
    except Exception:
        return [], 0


async def fetch_all_history(token: str) -> list[dict]:
    all_items: list[dict] = []

    for base_url in [API_CN, API_GLOBAL]:
        items, total = await _fetch_page(token, base_url, 0)
        if items is None:
            return []
        if not items:
            continue

        all_items.extend(items)
        offset = PAGE_SIZE
        retry = 0

        while offset < total:
            page_items, page_total = await _fetch_page(token, base_url, offset)
            if page_items is None:
                return []
            if not page_items:
                retry += 1
                if retry >= 3:
                    break
                continue
            retry = 0
            all_items.extend(page_items)
            offset += PAGE_SIZE

        if all_items:
            break

    return all_items


# ---------------------------------------------------------------------------
# 数据转换（移植自 bambu-export-web/src/utils/bambu-transform.ts）
# ---------------------------------------------------------------------------

def _parse_color(color_str: str | None) -> str:
    if not color_str:
        return ""
    s = str(color_str).strip()
    if s.startswith("#"):
        hex_part = s[1:]
        return f"#{hex_part[:6].upper()}" if len(hex_part) >= 6 else s.upper()
    if s.startswith("rgb"):
        try:
            inner = s[s.index("(") + 1:s.rindex(")")]
            parts = [p.strip() for p in inner.split(",")]
            r, g, b = int(parts[0]), int(parts[1]), int(parts[2])
            return f"#{r:02X}{g:02X}{b:02X}"
        except (ValueError, IndexError):
            return s
    if "," in s:
        try:
            parts = [p.strip() for p in s.split(",")]
            r, g, b = int(parts[0]), int(parts[1]), int(parts[2])
            return f"#{r:02X}{g:02X}{b:02X}"
        except (ValueError, IndexError):
            pass
    if len(s) >= 6:
        try:
            int(s[:6], 16)
            return f"#{s[:6].upper()}"
        except ValueError:
            pass
    return s


def _parse_time(iso_str: str | None) -> str:
    if not iso_str:
        return ""
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return iso_str[:16] if len(iso_str) >= 16 else iso_str


def _parse_status(status_code: int) -> str:
    mapping = {2: "finish", 3: "failed", 1: "cancelled", 4: "cancelled"}
    return mapping.get(status_code, "cancelled")


def _extract_colors_used(item: dict) -> list[str]:
    colors: list[str] = []
    ams_list = item.get("amsDetailMapping")
    if isinstance(ams_list, list):
        for ams in ams_list:
            if ams and ams.get("sourceColor"):
                parsed = _parse_color(ams["sourceColor"])
                if parsed and parsed not in colors:
                    colors.append(parsed)
    if not colors:
        filament = item.get("filament")
        if isinstance(filament, dict):
            for fil in filament.values():
                if isinstance(fil, dict) and fil.get("color"):
                    parsed = _parse_color(fil["color"])
                    if parsed and parsed not in colors:
                        colors.append(parsed)
    if not colors and item.get("filamentColor"):
        for c in str(item["filamentColor"]).split(";"):
            parsed = _parse_color(c.strip())
            if parsed and parsed not in colors:
                colors.append(parsed)
    return colors


def _extract_filament_info(item: dict) -> tuple[str, str]:
    fil_type = ""
    fil_color = ""
    ams_list = item.get("amsDetailMapping")
    if isinstance(ams_list, list) and ams_list:
        first = ams_list[0]
        if isinstance(first, dict):
            fil_type = first.get("filamentType", "")
            fil_color = _parse_color(first.get("sourceColor")) if first.get("sourceColor") else ""
    if not fil_type:
        filament = item.get("filament")
        if isinstance(filament, dict):
            for key in sorted(filament.keys()):
                fil = filament[key]
                if isinstance(fil, dict):
                    if not fil_type:
                        fil_type = fil.get("type", "")
                    if not fil_color:
                        fil_color = _parse_color(fil.get("color")) if fil.get("color") else ""
                    if fil_type and fil_color:
                        break
    if not fil_type:
        fil_type = item.get("filamentType", "")
    if not fil_color:
        fil_color = _parse_color(item.get("filamentColor"))
    return fil_type, fil_color


def _extract_weight_and_length(item: dict) -> tuple[float, float]:
    total_weight = 0.0
    total_length = 0.0
    # 优先从 amsDetailMapping 汇总
    ams_list = item.get("amsDetailMapping")
    if isinstance(ams_list, list):
        for ams in ams_list:
            if isinstance(ams, dict):
                total_weight += float(ams.get("weight") or 0)
                total_length += float(ams.get("length") or 0) / 1000
    # 回退：从 filament 字段汇总
    if total_weight == 0 and total_length == 0:
        filament = item.get("filament")
        if isinstance(filament, dict):
            for fil in filament.values():
                if isinstance(fil, dict):
                    total_weight += float(fil.get("weight") or 0)
                    total_length += float(fil.get("length") or 0) / 1000
    # 再回退到顶层字段
    if total_weight == 0:
        total_weight = float(item.get("weight") or 0)
    if total_length == 0:
        total_length = float(item.get("length") or 0) / 1000
    return round(total_weight, 1), round(total_length, 1)


def _extract_types_used(item: dict) -> list[str]:
    types: list[str] = []
    ams_list = item.get("amsDetailMapping")
    if isinstance(ams_list, list):
        for ams in ams_list:
            if isinstance(ams, dict) and ams.get("filamentType") and ams["filamentType"] not in types:
                types.append(ams["filamentType"])
    if not types:
        filament = item.get("filament")
        if isinstance(filament, dict):
            for fil in filament.values():
                if isinstance(fil, dict) and fil.get("type") and fil["type"] not in types:
                    types.append(fil["type"])
    if not types and item.get("filamentType"):
        types.append(item["filamentType"])
    return types


def _extract_color_usage(item: dict) -> list[dict]:
    ams_list = item.get("amsDetailMapping")
    if not isinstance(ams_list, list) or not ams_list:
        return []
    result = []
    for ams in ams_list:
        if not isinstance(ams, dict):
            continue
        result.append({
            "color": _parse_color(ams.get("sourceColor")),
            "type": ams.get("filamentType", ""),
            "weight_g": round(float(ams.get("weight") or 0), 2),
            "length_m": round(float(ams.get("length") or 0) / 1000, 2),
        })
    return result


def _extract_nozzle_type(item: dict) -> str:
    nozzle_infos = item.get("nozzleInfos")
    if isinstance(nozzle_infos, list) and nozzle_infos:
        return str(nozzle_infos[0].get("type", "")) if isinstance(nozzle_infos[0], dict) else ""
    return ""


def _extract_nozzle_size(item: dict) -> str:
    nozzle_infos = item.get("nozzleInfos")
    if isinstance(nozzle_infos, list) and nozzle_infos:
        first = nozzle_infos[0]
        if isinstance(first, dict) and first.get("diameter"):
            return str(first["diameter"])
    return str(item.get("nozzleSize", "0.4"))


def _parse_task_name(task_name: str) -> tuple[str, str]:
    if not task_name:
        return "", ""
    parts = task_name.split("_", 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return task_name, ""


def convert_to_ha_format(items: list[dict]) -> dict:
    ha_records = []
    for item in items:
        fil_type, fil_color = _extract_filament_info(item)
        total_weight, total_length = _extract_weight_and_length(item)
        colors_used = _extract_colors_used(item)
        types_used = _extract_types_used(item)
        color_usage = _extract_color_usage(item)
        cost_seconds = float(item.get("costTime") or 0)
        duration_hours = round(cost_seconds / 3600, 2)
        task_name = item.get("designTitle") or item.get("title") or ""
        name_model, name_config = _parse_task_name(task_name)
        total_colors = len(colors_used)

        ha_records.append({
            "id": str(item.get("id", "")),
            "task_name": task_name,
            "config_name": task_name,
            "task_name_model": name_model,
            "task_name_config": name_config,
            "design_id": item.get("designId", ""),
            "gcode_task_id": None,
            "status": _parse_status(item.get("status", 0)),
            "printer_serial": str(item.get("deviceId", "")),
            "start_time": _parse_time(item.get("startTime")),
            "end_time": _parse_time(item.get("endTime")),
            "duration_hours": duration_hours,
            "prepare_time_minutes": None,
            "filament_type": fil_type,
            "filament_color": fil_color,
            "total_weight": total_weight,
            "total_length": total_length,
            "colors_used": colors_used,
            "types_used": types_used,
            "total_colors": total_colors,
            "multi_color": total_colors > 1,
            "over_500g": total_weight > 500,
            "color_usage": color_usage,
            "color_changes_count": None,
            "multi_color_summary": None,
            "energy_kwh": None,
            "nozzle_type": _extract_nozzle_type(item),
            "nozzle_size": _extract_nozzle_size(item),
            "print_bed_type": item.get("bedType", ""),
            "speed_profile": None,
            "slice_mode": item.get("mode", ""),
            "ams_used": item.get("useAms", False),
            "total_layer_count": None,
            "progress": 100 if item.get("status") == 2 else (int(item.get("progress") or 0)),
            "cover_image_url": item.get("cover", ""),
            "cover_image_local": None,
            "snapshot_image_local": None,
            "chamber_temp_final": None,
            "chamber_temp_last5min": None,
            "full_print_info_path": None,
        })

    return {"version": 3, "history": ha_records}
