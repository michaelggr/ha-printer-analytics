"""Utility Tracker 数据聚合协调器

定时从 state_grid (电费) 和 crcgas (燃气费) 实体抓取数据,写入 MariaDB。
"""
from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_ENABLE_ELECTRICITY,
    CONF_ENABLE_GAS,
    CONF_SYNC_INTERVAL_HOURS,
    DEFAULT_SYNC_INTERVAL_HOURS,
    DOMAIN,
    GRANULARITY_DAY,
    GRANULARITY_MONTH,
    SOURCE_CRCGAS,
    SOURCE_STATE_GRID,
    UTILITY_TYPE_ELECTRICITY,
    UTILITY_TYPE_GAS,
)
from .db import UtilityDB

_LOGGER = logging.getLogger(__name__)


class UtilityTrackerCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """数据聚合协调器"""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, db: UtilityDB) -> None:
        self.entry = entry
        self.db = db
        self.enable_electricity = entry.data.get(CONF_ENABLE_ELECTRICITY, True)
        self.enable_gas = entry.data.get(CONF_ENABLE_GAS, True)
        hours = int(entry.data.get(CONF_SYNC_INTERVAL_HOURS, DEFAULT_SYNC_INTERVAL_HOURS))

        self.last_sync: datetime | None = None
        self.last_error: str | None = None
        self.total_records: int = 0

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(hours=max(1, min(hours, 24))),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """主更新入口"""
        stats = {
            "elec_day_records": 0,
            "elec_month_records": 0,
            "elec_snapshots": 0,
            "gas_month_records": 0,
            "gas_snapshots": 0,
        }
        try:
            if self.enable_electricity:
                elec_stats = await self._collect_electricity()
                stats.update(elec_stats)
            if self.enable_gas:
                gas_stats = await self._collect_gas()
                stats.update(gas_stats)

            self.total_records = await self.db.async_count_records()
            self.last_sync = datetime.now()
            self.last_error = None
        except Exception as e:
            self.last_error = str(e)
            _LOGGER.exception("Utility Tracker 同步失败")
            raise

        return stats

    # =====================================================================
    # 电费 (state_grid)
    # =====================================================================

    async def _collect_electricity(self) -> dict[str, int]:
        """从 state_grid 实体抓数据写库"""
        # 按户号分组所有 SGCC 实体
        accounts: dict[str, dict[str, State]] = {}
        for state in self.hass.states.async_all():
            if "osg_uc_" not in state.entity_id:
                continue
            account_suffix = state.attributes.get("account_suffix")
            if not account_suffix:
                continue
            # 识别实体类型(取 entity_id 最后一段)
            for key in (
                "previous_daily_usage",
                "previous_settled_month_usage",
                "previous_settled_month_charge",
                "current_month_usage",
                "current_year_usage",
                "current_year_charge",
                "account_balance",
                "amount_due",
                "last_month_meter_reading",
            ):
                if state.entity_id.endswith(f"_{key}"):
                    accounts.setdefault(account_suffix, {})[key] = state
                    break

        day_records: list[dict] = []
        month_records: list[dict] = []
        snapshots: list[dict] = []
        today = date.today().isoformat()

        for account_id, sensors in accounts.items():
            # ---- 日记录 (含峰谷平尖) ----
            daily_state = sensors.get("previous_daily_usage")
            if daily_state:
                daily_history = daily_state.attributes.get("daily_history") or []
                for item in daily_history:
                    day_str = item.get("day")
                    if not day_str:
                        continue
                    day_records.append({
                        "utility_type": UTILITY_TYPE_ELECTRICITY,
                        "account_id": account_id,
                        "granularity": GRANULARITY_DAY,
                        "period_date": day_str,
                        "usage_amount": _safe_float(item.get("usage")),
                        "charge": _safe_float(item.get("charge")),
                        "peak": _safe_float(item.get("peak")),
                        "flat": _safe_float(item.get("flat")),
                        "valley": _safe_float(item.get("valley")),
                        "tip": _safe_float(item.get("tip")),
                    })

            # ---- 月记录 ----
            monthly_state = sensors.get("previous_settled_month_usage")
            if monthly_state:
                monthly_history = monthly_state.attributes.get("monthly_bill_history") or []
                for item in monthly_history:
                    month_str = item.get("month")  # "2026-01"
                    if not month_str:
                        continue
                    # period_date 用月第一天
                    period_date = f"{month_str}-01"
                    month_records.append({
                        "utility_type": UTILITY_TYPE_ELECTRICITY,
                        "account_id": account_id,
                        "granularity": GRANULARITY_MONTH,
                        "period_date": period_date,
                        "usage_amount": _safe_float(item.get("usage")),
                        "charge": _safe_float(item.get("charge")),
                        "extra": {
                            "start_date": item.get("start_date"),
                            "end_date": item.get("end_date"),
                        },
                    })

            # ---- 当日快照 ----
            balance_state = sensors.get("account_balance")
            amount_due_state = sensors.get("amount_due")
            year_usage_state = sensors.get("current_year_usage")
            year_charge_state = sensors.get("current_year_charge")
            meter_state = sensors.get("last_month_meter_reading")

            snapshots.append({
                "utility_type": UTILITY_TYPE_ELECTRICITY,
                "account_id": account_id,
                "snapshot_date": today,
                "balance": _state_float(balance_state),
                "amount_due": _state_float(amount_due_state),
                "year_total_usage": _state_float(year_usage_state),
                "year_total_charge": _state_float(year_charge_state),
                "extra": {
                    "last_month_meter_reading": _state_float(meter_state),
                    "history_owe": (balance_state.attributes.get("history_owe") if balance_state else None),
                    "penalty": (balance_state.attributes.get("penalty") if balance_state else None),
                },
            })

        # 写库
        if day_records:
            await self.db.async_upsert_records(day_records)
        if month_records:
            await self.db.async_upsert_records(month_records)
        if snapshots:
            await self.db.async_upsert_snapshots(snapshots)

        _LOGGER.info(
            "电费同步完成: %d 户号, 日记录=%d, 月记录=%d, 快照=%d",
            len(accounts), len(day_records), len(month_records), len(snapshots),
        )
        return {
            "elec_day_records": len(day_records),
            "elec_month_records": len(month_records),
            "elec_snapshots": len(snapshots),
        }

    # =====================================================================
    # 燃气费 (crcgas)
    # =====================================================================

    async def _collect_gas(self) -> dict[str, int]:
        """从 crcgas 实体抓数据写库"""
        # 通过 entity_id 前缀过滤,简单可靠
        crcgas_entities = [
            s for s in self.hass.states.async_all()
            if s.entity_id.startswith("sensor.hua_run_ran_qi_")
               or s.entity_id.startswith("button.hua_run_ran_qi_")
        ]

        if not crcgas_entities:
            _LOGGER.warning("未找到 crcgas 实体,跳过燃气同步")
            return {"gas_month_records": 0, "gas_snapshots": 0}

        # 找户号(用 config_entry.title 里的户号或 friendly_name 里的)
        # 简化:用主户号 1040395237 作为 account_id
        # 实际从 sensor.hua_run_ran_qi_biao_hao 读
        biao_hao_state = self.hass.states.get("sensor.hua_run_ran_qi_biao_hao")
        account_id = (biao_hao_state.state if biao_hao_state else "default").strip() or "default"

        # 工具函数:取某个实体的状态值
        def _get(entity_id_suffix: str) -> State | None:
            full_id = f"sensor.hua_run_ran_qi_{entity_id_suffix}"
            return self.hass.states.get(full_id)

        month_records: list[dict] = []
        snapshots: list[dict] = []
        today = date.today().isoformat()

        # ---- 月记录:本期账单 ----
        bill_month_state = _get("zhang_dan_yue_fen")  # "2026-10"
        bill_amount_state = _get("zhang_dan_jin_e")
        ben_qi_yong_qi_state = _get("ben_qi_yong_qi_liang")
        ben_qi_biao_du_state = _get("ben_qi_biao_du_shu")
        ben_qi_chao_biao_state = _get("ben_qi_chao_biao_shi_jian")
        tier1_state = _get("ben_qi_yi_jie_ti_yong_qi_liang")
        tier2_state = _get("ben_qi_er_jie_ti_yong_qi_liang")
        tier3_state = _get("ben_qi_san_jie_ti_yong_qi_liang")

        if bill_month_state and bill_month_state.state:
            bill_month = bill_month_state.state.strip()  # "2026-10"
            try:
                year, month = bill_month.split("-", 1)
                period_date = f"{year}-{month.zfill(2)}-01"
                month_records.append({
                    "utility_type": UTILITY_TYPE_GAS,
                    "account_id": account_id,
                    "granularity": GRANULARITY_MONTH,
                    "period_date": period_date,
                    # crcgas 把欠费账单记为负数,业务上应转为正数入库
                    "usage_amount": _abs_or_none(_state_float(ben_qi_yong_qi_state)),
                    "charge": _abs_or_none(_state_float(bill_amount_state)),
                    "tier1_usage": _state_float(tier1_state),
                    "tier2_usage": _state_float(tier2_state),
                    "tier3_usage": _state_float(tier3_state),
                    "meter_reading": _state_float(ben_qi_biao_du_state),
                    "meter_date": (ben_qi_chao_biao_state.state if ben_qi_chao_biao_state else None),
                })
            except (ValueError, AttributeError) as e:
                _LOGGER.warning("燃气账单月份解析失败: %s, err=%s", bill_month, e)

        # ---- 历史账单回填(从 crcgas history_storage 的 JSON) ----
        backfilled = await self._backfill_gas_history(account_id)
        month_records.extend(backfilled)

        # ---- 当日快照 ----
        snapshots.append({
            "utility_type": UTILITY_TYPE_GAS,
            "account_id": account_id,
            "snapshot_date": today,
            "balance": _state_float(_get("ran_qi_zhang_hu_yu_e")),
            "amount_due": _state_float(_get("qian_fei_jin_e")),
            "year_total_charge": _state_float(_get("lei_ji_ran_qi_fei_yong")),
            "year_total_usage": _state_float(_get("nian_du_yue_jun_yong_qi_liang")),
            "extra": {
                "yi_jie_ti_qi_jie": _state_float(_get("yi_jie_ti_qi_jie")),
                "er_jie_ti_qi_jie": _state_float(_get("er_jie_ti_qi_jie")),
                "san_jie_ti_qi_jie": _state_float(_get("san_jie_ti_qi_jie")),
                "wei_yue_jin": _state_float(_get("wei_yue_jin")),
            },
        })

        if month_records:
            await self.db.async_upsert_records(month_records)
        if snapshots:
            await self.db.async_upsert_snapshots(snapshots)

        _LOGGER.info(
            "燃气同步完成: 户号=%s, 月记录=%d, 快照=%d",
            account_id, len(month_records), len(snapshots),
        )
        return {
            "gas_month_records": len(month_records),
            "gas_snapshots": len(snapshots),
        }

    async def _backfill_gas_history(self, account_id: str) -> list[dict]:
        """从 crcgas 历史 JSON 回填历史账单"""
        records: list[dict] = []
        storage_dir = self.hass.config.path(".storage")
        try:
            files = [f for f in os.listdir(storage_dir) if f.startswith("crcgas_history_")]
        except Exception as e:
            _LOGGER.warning("读取 .storage 失败: %s", e)
            return records

        for fname in files:
            fpath = os.path.join(storage_dir, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    payload = json.load(f)
            except Exception as e:
                _LOGGER.warning("读取 %s 失败: %s", fname, e)
                continue

            bill_history = (payload.get("data") or {}).get("bill_history") or []
            for bill in bill_history:
                period_date = bill_month_to_date(bill.get("billYm"))
                if not period_date:
                    continue
                records.append({
                    "utility_type": UTILITY_TYPE_GAS,
                    "account_id": account_id,
                    "granularity": GRANULARITY_MONTH,
                    "period_date": period_date,
                    # crcgas 把欠费账单记为负数,业务上应转为正数入库
                    "usage_amount": _abs_or_none(_safe_float(bill.get("gasAmt"))),
                    "charge": _abs_or_none(_safe_float(bill.get("billAmt"))),
                    "extra": {
                        "applicationNo": bill.get("applicationNo"),
                        "penaltyAmt": bill.get("penaltyAmt"),
                        "penaltyDate": bill.get("penaltyDate"),
                        "settleFlag": bill.get("settleFlag"),
                        "revblAmt": bill.get("revblAmt"),
                    },
                })
        return records


# =====================================================================
# 工具函数
# =====================================================================

def _safe_float(value: Any) -> float | None:
    """安全转 float,失败返回 None"""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _abs_or_none(value: float | None) -> float | None:
    """对 float 取绝对值, None 透传 (crcgas 把欠费账单记为负数,业务上应为正数)"""
    return abs(value) if value is not None else None


def _state_float(state: State | None) -> float | None:
    """从实体状态取 float 值,unavailable/unknown 返回 None"""
    if state is None:
        return None
    if state.state in ("unavailable", "unknown", "none", ""):
        return None
    return _safe_float(state.state)


def bill_month_to_date(bill_ym: str | None) -> str | None:
    """'2026-10' → '2026-10-01'"""
    if not bill_ym or not isinstance(bill_ym, str):
        return None
    parts = bill_ym.split("-")
    if len(parts) != 2:
        return None
    try:
        year = int(parts[0])
        month = int(parts[1])
        if not (1 <= month <= 12):
            return None
        return f"{year:04d}-{month:02d}-01"
    except (ValueError, TypeError):
        return None
