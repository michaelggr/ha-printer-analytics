"""Utility Tracker 数据聚合协调器

定时从 state_grid (电费) 和 crcgas (燃气费) 实体抓取数据,写入 MariaDB。
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ENABLE_DEVICE_POWER,
    CONF_ENABLE_ELECTRICITY,
    CONF_ENABLE_GAS,
    CONF_ENABLE_LIGHT_STATS,
    CONF_POWER_SAMPLE_MINUTES,
    CONF_RAW_RETENTION_DAYS,
    CONF_SYNC_INTERVAL_HOURS,
    DEFAULT_POWER_SAMPLE_MINUTES,
    DEFAULT_RAW_RETENTION_DAYS,
    DEFAULT_SYNC_INTERVAL_HOURS,
    DOMAIN,
    AREA_STAY_DURATION_ENTITIES,
    GRANULARITY_DAY,
    GRANULARITY_MONTH,
    LIGHT_ACTION_OFF,
    LIGHT_ACTION_ON,
    LIGHT_AREA_DURATION_ENTITIES,
    POWER_DEVICE_CLASSES,
    POWER_LAST_LOOKBACK_HOURS,
    SOURCE_CRCGAS,
    SOURCE_STATE_GRID,
    UTILITY_TYPE_ELECTRICITY,
    UTILITY_TYPE_GAS,
    is_light_entity,
    is_power_outlier,
)
from .db import UtilityDB

_LOGGER = logging.getLogger(__name__)


def hours_state_to_seconds(value: str | float | None) -> int | None:
    """把 history_stats 输出的「小时」值转成秒

    无效值 (None / unknown / unavailable / 非数字 / 负数) 返回 None,
    由调用方跳过,避免把脏数据写进数据库
    """
    if value is None:
        return None
    if isinstance(value, str) and value in ("unknown", "unavailable", ""):
        return None
    try:
        hours = float(value)
    except (TypeError, ValueError):
        return None
    if hours < 0:
        return None
    return int(round(hours * 3600))


def diff_area_stay_seconds(
    current: dict[str, int],
    last_sample: dict[str, tuple[str, int]],
    today: str,
) -> dict[str, int]:
    """计算各区域「本次累计秒数」相对「上次采样」的增量 (用于小时桶累加)

    current:      {entity_id: 今日累计秒数}
    last_sample:  {entity_id: (采样日期, 当时累计秒数)}
    today:        本次采样日期 (YYYY-MM-DD)

    以下情况不产生增量, 只更新基线:
    - 首次采样, 没有基线
    - 跨日: history_stats 每日归零, 基线日期与今天不同
    - 累计值回退: recorder 重启或统计重置导致读数变小
    """
    deltas: dict[str, int] = {}
    for entity_id, sec in current.items():
        base = last_sample.get(entity_id)
        if base is None or base[0] != today:
            continue
        delta = sec - base[1]
        if delta > 0:
            deltas[entity_id] = delta
    return deltas


class UtilityTrackerCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """数据聚合协调器"""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, db: UtilityDB) -> None:
        self.entry = entry
        self.db = db
        self.enable_electricity = entry.data.get(CONF_ENABLE_ELECTRICITY, True)
        self.enable_gas = entry.data.get(CONF_ENABLE_GAS, True)
        self.enable_device_power = entry.data.get(CONF_ENABLE_DEVICE_POWER, True)
        self.enable_light_stats = entry.data.get(CONF_ENABLE_LIGHT_STATS, True)
        hours = int(entry.data.get(CONF_SYNC_INTERVAL_HOURS, DEFAULT_SYNC_INTERVAL_HOURS))
        self.sync_interval = timedelta(hours=max(1, min(hours, 24)))
        self.power_sample_minutes = max(1, int(entry.data.get(
            CONF_POWER_SAMPLE_MINUTES, DEFAULT_POWER_SAMPLE_MINUTES
        )))
        self.raw_retention_days = max(1, int(entry.data.get(
            CONF_RAW_RETENTION_DAYS, DEFAULT_RAW_RETENTION_DAYS
        )))

        self.last_sync: datetime | None = None
        self.last_utility_sync: datetime | None = None
        self.last_error: str | None = None
        self.last_gas_discovery: dict | None = None
        self.last_gas_accounts: dict | None = None
        self.total_records: int = 0
        # 灯光事件队列: 由 state listener 填充,coordinator 定期批量写库
        self.light_event_queue: list[dict] = []
        # 区域停留上次采样基线: {entity_id: (采样日期, 今日累计秒数)}
        # 用于把两次采样之间的差额归入当前小时桶 (area_stay_hourly)
        self._last_area_stay_sec: dict[str, tuple[str, int]] = {}

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            # 采集周期 = min(账单同步周期, 功耗采样周期), 保证 5 分钟采样能跑
            update_interval=min(
                self.sync_interval, timedelta(minutes=self.power_sample_minutes)
            ),
        )

    def queue_light_event(self, event: dict) -> None:
        """由 __init__.py 的 state listener 调用,灯光开关事件入队"""
        self.light_event_queue.append(event)

    async def _async_update_data(self) -> dict[str, Any]:
        """主更新入口

        每次调用(默认 5 分钟): 设备功耗采样 + 灯光事件落库 + 聚合
        按 sync_interval(默认 1 小时): 电费/燃气账单同步
        """
        stats: dict[str, Any] = {
            "elec_day_records": 0,
            "elec_month_records": 0,
            "elec_snapshots": 0,
            "gas_month_records": 0,
            "gas_snapshots": 0,
            "power_samples": 0,
            "light_events": 0,
            "light_durations": 0,
            "area_stays": 0,
        }
        try:
            # HA 容器运行在 UTC,需显式转成本地时区;
            # 去掉 tzinfo 存 naive datetime,供 DB 写入与 MariaDB NOW()/CURDATE() 对齐
            now = dt_util.now().replace(tzinfo=None)

            # ---- 一次性清理: 退款单据改造前的脏数据 (v2) ----
            # 背景: 旧版把退款负数单取绝对值入库, 且同月多单据互相覆盖;
            # v2 起保留原始正负号 + 按 applicationNo (bill_no) 区分单据, 需全量重建燃气月记录
            cleanup_flag = self.hass.config.path(
                ".storage", "utility_tracker_cleanup_v2.done"
            )
            if not os.path.exists(cleanup_flag):
                try:
                    # 1) 删 gas 中所有不在已知 account_id 集合内的脏记录
                    n1 = await self.db.async_delete_unknown_gas_accounts(
                        known=("1040395237", "1021540961")
                    )
                    # 2) 删两户所有 gas 月记录 (含旧 abs 值, 由历史回填按新规则重建)
                    n2 = await self.db.async_delete_utility_records(
                        UTILITY_TYPE_GAS, "1040395237", granularity=GRANULARITY_MONTH
                    )
                    n3 = await self.db.async_delete_utility_records(
                        UTILITY_TYPE_GAS, "1021540961", granularity=GRANULARITY_MONTH
                    )
                    with open(cleanup_flag, "w", encoding="utf-8") as f:
                        f.write(datetime.now().isoformat())
                    _LOGGER.warning(
                        "燃气脏数据清理完成(v2): 未知户 %d 条, 主户月记录 %d 条, 副户月记录 %d 条",
                        n1, n2, n3,
                    )
                    # 强制立刻重跑 _collect_gas 重建
                    self.last_utility_sync = None
                except Exception as e:
                    _LOGGER.warning("脏数据清理失败: %s", e)

            # ---- 高频任务: 设备功耗 + 灯光 ----
            if self.enable_device_power:
                stats["power_samples"] = await self._collect_device_power(now)
            if self.enable_light_stats:
                stats["light_events"] = await self._collect_light_stats(now)
                # 区域主灯每日时长入库 (history_stats 快照, 权威时长来源)
                stats["light_durations"] = await self._collect_light_durations(now)
                # 区域每日停留时长入库 (同灯光方案, 数据源换成「有人」统计)
                stats["area_stays"] = await self._collect_area_stays(now)

            # ---- 低频任务: 电费/燃气 (按 sync_interval 节流) ----
            utility_due = (
                self.last_utility_sync is None
                or (now - self.last_utility_sync) >= self.sync_interval
            )
            if utility_due:
                utility_ok = True
                if self.enable_electricity:
                    stats.update(await self._collect_electricity())
                if self.enable_gas:
                    gas_stats = await self._collect_gas()
                    stats.update(gas_stats)
                    # crcgas 启动慢时 _discover_gas_accounts 返回空,
                    # 不要更新 last_utility_sync, 下个周期重试
                    if not self.last_gas_accounts:
                        utility_ok = False
                        _LOGGER.info("燃气户为空, 5 分钟后重试")
                if utility_ok:
                    self.last_utility_sync = now

            # 月度账单统计 (轻量 SQL SUM, 每次刷新都跑, 避免 sensor unknown)
            # 合计 (向后兼容)
            stats["electricity_this_month"] = await self.db.async_sum_month_charge(
                UTILITY_TYPE_ELECTRICITY, now.year, now.month
            )
            stats["gas_this_month"] = await self.db.async_sum_month_charge(
                UTILITY_TYPE_GAS, now.year, now.month
            )
            # 分户: 自住 (东方新天地) vs 出租 (东方佳园)
            # 电: state_grid account_suffix 为 "0065"(主)/"7061"(租)
            # 气: crcgas cons_no 为 "1040395237"(主)/"1021540961"(租)
            stats["electricity_this_month_main"] = await self.db.async_sum_month_charge(
                UTILITY_TYPE_ELECTRICITY, now.year, now.month, account_id="0065"
            )
            stats["electricity_this_month_rental"] = await self.db.async_sum_month_charge(
                UTILITY_TYPE_ELECTRICITY, now.year, now.month, account_id="7061"
            )
            stats["gas_this_month_main"] = await self.db.async_sum_month_charge(
                UTILITY_TYPE_GAS, now.year, now.month, account_id="1040395237"
            )
            stats["gas_this_month_rental"] = await self.db.async_sum_month_charge(
                UTILITY_TYPE_GAS, now.year, now.month, account_id="1021540961"
            )

            # ---- 汇总指标 (供 sensor 读) ----
            self.total_records = await self.db.async_count_records()
            if self.enable_device_power:
                stats["power_current_w"] = await self.db.async_current_total_power()
                stats["power_today_kwh"] = await self.db.async_sum_power_today()
            if self.enable_light_stats:
                # 开灯次数来自事件流表 light_daily
                on_count, _ = await self.db.async_sum_light_today()
                stats["light_today_count"] = on_count
                # 亮灯时长来自 history_stats 快照表 (与区域灯实体一致)
                stats["light_today_seconds"] = (
                    await self.db.async_sum_light_duration_today()
                )
                # 今日各区域停留时长合计 (同样读快照表, 而非直接读实体)
                stats["area_stay_today_seconds"] = (
                    await self.db.async_sum_area_stay_today()
                )
                stats["area_stay_week_seconds"] = (
                    await self.db.async_sum_area_stay_week()
                )
                stats["area_stay_month_seconds"] = (
                    await self.db.async_sum_area_stay_month()
                )
                # 区域排行榜 (供看板 Ranking sensor 用, 按停留秒数降序)
                stats["area_stay_week_ranking"] = await self.db.async_fetch_area_stays_week()
                stats["area_stay_month_ranking"] = await self.db.async_fetch_area_stays_month()

            self.last_sync = now
            self.last_error = None
        except Exception as e:
            self.last_error = str(e)
            _LOGGER.exception("Utility Tracker 同步失败")
            raise

        return stats

    # =====================================================================
    # 设备功耗 (5 分钟采样 + 聚合)
    # =====================================================================

    async def _collect_device_power(self, now: datetime) -> int:
        """扫描所有 device_class=power/energy 的 sensor, 写原始采样 + 触发聚合"""
        # 采样时间对齐到 5 分钟边界,保证 UNIQUE(entity_id, sampled_at) 幂等
        aligned = now.replace(
            minute=(now.minute // self.power_sample_minutes) * self.power_sample_minutes,
            second=0, microsecond=0,
        )
        sampled_at = aligned.strftime("%Y-%m-%d %H:%M:%S")

        samples: list[dict] = []
        for state in self.hass.states.async_all("sensor"):
            dc = state.attributes.get("device_class")
            if dc not in POWER_DEVICE_CLASSES:
                continue
            # 排除自身传感器(避免反馈回路)和 SGCC 账单传感器(已在 utility_records 跟踪)
            eid = state.entity_id
            if eid.startswith("sensor.utility_tracker_") or "osg_uc_" in eid:
                continue
            # 跳过不可用状态,但保留 state 字符串便于排查
            val = _state_float(state)
            # 单位换算: mWh/Wh -> kWh (energy 传感器)
            if dc == "energy" and val is not None:
                unit = (state.attributes.get("unit_of_measurement") or "").strip()
                if unit == "mWh":
                    val = val / 1_000_000
                elif unit == "Wh":
                    val = val / 1_000
            sample = {
                "entity_id": eid,
                "friendly_name": state.attributes.get("friendly_name"),
                "sampled_at": sampled_at,
                "power_w": val if dc == "power" else None,
                "energy_kwh": val if dc == "energy" else None,
                "state": state.state,
            }
            samples.append(sample)

        # ---- 异常值过滤 ----
        # 先取各实体上一次有效功率用于跳变判定; 首次运行无历史时只做绝对上限判断
        # 被判定为异常的采样仍保留 state 字符串便于排查, 只把 power_w 置空
        # (AVG/MAX/MIN 聚合与 current_power 都基于 power_w, NULL 行会被自然忽略)
        if samples:
            last_values = await self.db.async_fetch_last_power_values(
                POWER_LAST_LOOKBACK_HOURS
            )
            filtered = 0
            for sample in samples:
                new_w = sample["power_w"]
                if new_w is None:
                    continue  # energy 传感器或不可用状态, 无需过滤
                last_w = last_values.get(sample["entity_id"])
                if not is_power_outlier(last_w, new_w):
                    continue
                filtered += 1
                _LOGGER.warning(
                    "功耗异常值已过滤: %s 本次 %.1fW, 上次 %s",
                    sample["entity_id"],
                    new_w,
                    f"{last_w:.1f}W" if last_w is not None else "无记录",
                )
                sample["power_w"] = None
            if filtered:
                _LOGGER.info("功耗采样: 过滤异常值 %d/%d 条", filtered, len(samples))

        if samples:
            await self.db.async_insert_device_power_raw(samples)

        # 聚合上一个完整小时 (避免聚合还在进行中的当前小时)
        prev_hour = aligned - timedelta(hours=1)
        hour_start = prev_hour.replace(minute=0, second=0, microsecond=0)
        hour_end = hour_start + timedelta(hours=1)
        await self.db.async_aggregate_power_hourly(
            hour_start.strftime("%Y-%m-%d %H:%M:%S"),
            hour_end.strftime("%Y-%m-%d %H:%M:%S"),
        )

        # 聚合昨天 (今天可能还没结束,等明天再聚合)
        yesterday = (aligned - timedelta(days=1)).date().isoformat()
        await self.db.async_aggregate_power_daily(yesterday)

        # 清理过期原始数据
        await self.db.async_cleanup_power_raw(self.raw_retention_days)

        return len(samples)

    # =====================================================================
    # 灯光统计 (事件队列落库 + 日聚合)
    # =====================================================================

    async def _collect_light_stats(self, now: datetime) -> int:
        """把队列中的灯光事件批量写库,并聚合昨天的日数据"""
        # 队列落库 (原子地取出并清空)
        events = self.light_event_queue[:]
        self.light_event_queue.clear()
        if events:
            await self.db.async_insert_light_events(events)
            _LOGGER.info("灯光事件落库: %d 条", len(events))

        # 聚合昨天
        yesterday = (now - timedelta(days=1)).date().isoformat()
        await self.db.async_aggregate_light_daily(yesterday)
        # 今天的也聚一次 (允许覆盖,数据当天实时可见)
        today = now.date().isoformat()
        await self.db.async_aggregate_light_daily(today)

        # 检测新增/移除的灯光实体,有变化则重建 state 订阅
        store = self.hass.data.get(DOMAIN, {}).get(self.entry.entry_id, {})
        rebuild = store.get("rebuild_light_sub")
        if rebuild:
            current_ids = {
                s.entity_id
                for s in self.hass.states.async_all()
                if is_light_entity(s.entity_id, s.attributes.get("friendly_name"))
            }
            if current_ids != store.get("light_entity_ids", set()):
                _LOGGER.info("灯光实体变化, 重建订阅")
                rebuild()

        return len(events)

    async def _collect_light_durations(self, now: datetime) -> int:
        """把 13 个区域主灯 history_stats 的今日时长快照写入 light_duration_daily

        与设备功耗同样思路: 每次采样覆盖写「今天」这一行,
        所以重启/漏采样都不会丢历史, 当天最终值即最后一次采样值;
        history_stats 本身从 recorder 历史累计, 不依赖本集成的开关事件流
        """
        today = now.date().isoformat()
        rows: list[dict[str, Any]] = []
        for entity_id, area in LIGHT_AREA_DURATION_ENTITIES.items():
            state = self.hass.states.get(entity_id)
            if state is None:
                continue
            seconds = hours_state_to_seconds(state.state)
            if seconds is None:
                continue
            rows.append({
                "entity_id": entity_id,
                "area_name": area,
                "period_date": today,
                "duration_sec": seconds,
            })
        if not rows:
            return 0
        await self.db.async_upsert_light_durations(rows)
        _LOGGER.debug("区域主灯时长入库: %d 条", len(rows))
        return len(rows)

    async def _collect_area_stays(self, now: datetime) -> int:
        """把 12 个区域停留时长快照写入 area_stay_daily 与 area_stay_hourly

        日表: 每次采样覆盖写「今天」这一行, 当天最终值即最后一次采样值;
        小时表: 用「本次累计 - 上次累计」的差额累加进当前小时桶,
                供 Grafana 热力图按 区域 × 小时时段 展示;
        history_stats 从 recorder 历史累计, 重启/漏采样都不会丢日维度历史,
        小时维度只会缺失进程未运行期间的增量 (下次采样补不回来)
        """
        today = now.date().isoformat()

        # 1) 先采集本次快照: 各区域「今日累计秒数」
        current: dict[str, int] = {}
        for entity_id in AREA_STAY_DURATION_ENTITIES:
            state = self.hass.states.get(entity_id)
            if state is None:
                continue
            seconds = hours_state_to_seconds(state.state)
            if seconds is None:
                continue
            current[entity_id] = seconds

        # 2) 增量必须基于「上次基线」计算, 算完才能刷新基线
        deltas = diff_area_stay_seconds(current, self._last_area_stay_sec, today)
        for entity_id, seconds in current.items():
            self._last_area_stay_sec[entity_id] = (today, seconds)

        if not current:
            return 0

        # 3) 日维度: 覆盖写
        rows = [
            {
                "entity_id": entity_id,
                "area_name": AREA_STAY_DURATION_ENTITIES[entity_id],
                "period_date": today,
                "duration_sec": seconds,
            }
            for entity_id, seconds in current.items()
        ]
        await self.db.async_upsert_area_stays(rows)

        # 4) 小时维度: 把差额累加进当前小时桶
        hourly_rows = [
            {
                "entity_id": entity_id,
                "area_name": AREA_STAY_DURATION_ENTITIES[entity_id],
                "period_date": today,
                "period_hour": now.hour,
                "duration_sec": delta,
            }
            for entity_id, delta in deltas.items()
        ]
        if hourly_rows:
            await self.db.async_upsert_area_stays_hourly(hourly_rows)

        _LOGGER.debug(
            "区域停留时长入库: 日 %d 条 / 小时增量 %d 条", len(rows), len(hourly_rows)
        )
        return len(rows)

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

    # 燃气 sensor key 白名单 (与 crcgas 集成一致)
    _GAS_SENSOR_KEYS = (
        "zhang_dan_yue_fen", "zhang_dan_jin_e", "ben_qi_yong_qi_liang",
        "ben_qi_biao_du_shu", "ben_qi_chao_biao_shi_jian",
        "ben_qi_yi_jie_ti_yong_qi_liang", "ben_qi_er_jie_ti_yong_qi_liang",
        "ben_qi_san_jie_ti_yong_qi_liang",
        "ran_qi_zhang_hu_yu_e", "qian_fei_jin_e",
        "lei_ji_ran_qi_fei_yong", "nian_du_yue_jun_yong_qi_liang",
        "yi_jie_ti_qi_jie", "er_jie_ti_qi_jie", "san_jie_ti_qi_jie", "wei_yue_jin",
    )
    # 主户户号 (crcgas 主户 entity_id 不带 cons_no 中缀)
    _GAS_MAIN_CONS_NO = "1040395237"  # 东方新天地 *淑萱

    def _discover_gas_accounts(self) -> dict[str, dict[str, str]]:
        """扫描所有 hua_run_ran_qi sensor,按户号分组

        返回: {cons_no: {sensor_key: entity_id}}
        - 主户 (1040395237): entity_id = sensor.hua_run_ran_qi_<key>
        - 副户 (1021540961 等): entity_id = sensor.hua_run_ran_qi_<cons_no>_<key>_<name_pinyin>
        """
        accounts: dict[str, dict[str, str]] = {}
        prefix = "sensor.hua_run_ran_qi_"
        all_states = list(self.hass.states.async_all())
        gas_states = [s for s in all_states if s.entity_id.startswith(prefix)]
        # 调试信息暴露到 self
        self.last_gas_discovery = {
            "_total_states": len(all_states),
            "_gas_states": len(gas_states),
            "_sample_eids": [s.entity_id for s in gas_states[:3]],
        }
        for state in gas_states:
            eid = state.entity_id
            rest = eid[len(prefix):]
            # 副户格式: <10位数字cons_no>_<key>_<name_pinyin>
            m = re.match(r"^(\d{10})_(.+)$", rest)
            if m:
                cons_no, key_with_name = m.groups()
                # 剥离尾部 name 拼音, 逐一匹配已知 key
                for key in self._GAS_SENSOR_KEYS:
                    if key_with_name.startswith(key + "_"):
                        accounts.setdefault(cons_no, {})[key] = eid
                        break
            else:
                # 主户: rest 即为 key
                if rest in self._GAS_SENSOR_KEYS:
                    accounts.setdefault(self._GAS_MAIN_CONS_NO, {})[rest] = eid
        # 把最终 accounts 合并进调试信息
        for k, v in accounts.items():
            self.last_gas_discovery[k] = list(v.keys())
        return accounts

    async def _collect_gas(self) -> dict[str, int]:
        """从 crcgas 实体抓数据写库 (多户版)"""
        accounts = self._discover_gas_accounts()
        self.last_gas_accounts = accounts  # 供重试逻辑判断空
        _LOGGER.info("燃气户发现: %s", self.last_gas_discovery)
        if not accounts:
            _LOGGER.warning("未找到 crcgas 实体,跳过燃气同步")
            return {"gas_month_records": 0, "gas_snapshots": 0}

        month_records: list[dict] = []
        snapshots: list[dict] = []
        today = date.today().isoformat()

        for account_id, sensor_map in accounts.items():
            # 工具函数:取该户某个 key 的实体状态
            def _get(key: str, _map=sensor_map) -> State | None:
                eid = _map.get(key)
                return self.hass.states.get(eid) if eid else None

            # ---- 月记录: 全部由历史回填写入 ----
            # 注意: 不再用 live 传感器 (zhang_dan_jin_e 等) 写月记录,
            # 因为 live 账单没有 applicationNo, 会与历史回填的同月单据重复计数;
            # crcgas 历史 JSON 已含当月账单, 是权威数据源
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
            "燃气同步完成: %d 户, 月记录=%d, 快照=%d",
            len(accounts), len(month_records), len(snapshots),
        )
        return {
            "gas_month_records": len(month_records),
            "gas_snapshots": len(snapshots),
        }

    async def _backfill_gas_history(self, account_id: str) -> list[dict]:
        """从 crcgas 历史 JSON 回填历史账单

        文件命名规则:
        - 主户 (cons_no=_GAS_MAIN_CONS_NO): crcgas_history_<entry_id> (不带 cons_no 后缀)
        - 副户: crcgas_history_<entry_id>_<cons_no>
        """
        records: list[dict] = []
        storage_dir = self.hass.config.path(".storage")
        is_main = (account_id == self._GAS_MAIN_CONS_NO)
        try:
            files = [f for f in os.listdir(storage_dir) if f.startswith("crcgas_history_")]
        except Exception as e:
            _LOGGER.warning("读取 .storage 失败: %s", e)
            return records

        for fname in files:
            # 按户过滤文件: 文件名以 _<10位数字> 结尾的是副户
            m = re.search(r"_(\d{10})$", fname)
            if is_main:
                # 主户: 跳过带 cons_no 后缀的副户文件
                if m:
                    continue
            else:
                # 副户: 只读匹配自己 cons_no 的文件
                if not m or m.group(1) != account_id:
                    continue
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
                # 保留原始正负号: 负数 = 燃气公司退款, 参与月度净额合计
                # bill_no 用 applicationNo 区分同月多单据; 缺失时用序号兜底保证唯一键不冲突
                bill_no = bill.get("applicationNo") or f"auto-{period_date}-{len(records)}"
                records.append({
                    "utility_type": UTILITY_TYPE_GAS,
                    "account_id": account_id,
                    "granularity": GRANULARITY_MONTH,
                    "period_date": period_date,
                    "bill_no": bill_no,
                    "usage_amount": _safe_float(bill.get("gasAmt")),
                    "charge": _safe_float(bill.get("billAmt")),
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
