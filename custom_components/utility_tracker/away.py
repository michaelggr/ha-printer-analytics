"""出门/回家事件配对与统计（纯函数，不依赖 HA 运行环境）

设计要点：
1. 事件来源是中枢网关虚拟事件，只有「事件名称」一个有效信息，
   名称匹配后转成 away / home 两种类型入库
2. 统计以「行程」为单位：一次 away 到下一次 home 之间算一次出门
3. 短途出门（< 阈值）不计入「次数」，但时长照算
4. 跨零点的行程按自然日切分，保证周/月/年时长不会因为跨夜而算错
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

AWAY = "away"
HOME = "home"


def pair_trips(events: list[dict[str, Any]], now: datetime) -> list[dict[str, Any]]:
    """把事件流配对成「出门行程」

    events: [{"event_time": datetime, "event_type": "away"|"home"}, ...]
            必须按 event_time 升序
    返回: [{"start": datetime, "end": datetime|None, "duration_sec": int}]

    配对规则（防止网关重复上报）：
    - 已在外出状态时再收到 away -> 忽略（保留最早那次）
    - 不在外出状态时收到 home -> 忽略（没有对应的出门）
    - 最后一个 away 未闭合 -> end=None，时长按 now 计算
    """
    trips: list[dict[str, Any]] = []
    open_start: datetime | None = None

    for e in events:
        et = e.get("event_type")
        ts = e.get("event_time")
        if ts is None:
            continue
        if et == AWAY:
            if open_start is None:
                open_start = ts
            continue
        if et == HOME and open_start is not None:
            # 回家时间早于出门时间（数据乱序）时忽略本次 home, 保留 open_start
            if ts < open_start:
                continue
            trips.append({
                "start": open_start,
                "end": ts,
                "duration_sec": int((ts - open_start).total_seconds()),
            })
            open_start = None

    if open_start is not None:
        trips.append({
            "start": open_start,
            "end": None,
            "duration_sec": max(0, int((now - open_start).total_seconds())),
        })
    return trips


def split_trip_by_day(start: datetime, end: datetime) -> list[tuple[date, int]]:
    """把一段行程按自然日切分，返回 [(日期, 该日秒数)]

    例：11-05 23:00 -> 11-06 01:00 => [(11-05, 3600), (11-06, 3600)]
    """
    if end <= start:
        return []
    result: list[tuple[date, int]] = []
    cursor = start
    while cursor < end:
        day = cursor.date()
        next_midnight = datetime.combine(day + timedelta(days=1), datetime.min.time())
        seg_end = min(end, next_midnight)
        result.append((day, int((seg_end - cursor).total_seconds())))
        cursor = seg_end
    return result


def _period_bounds(now: datetime) -> dict[str, tuple[date, date]]:
    """返回各统计周期的起止日期（含首尾）"""
    today = now.date()
    week_start = today - timedelta(days=today.weekday())  # 周一为一周起点
    month_start = today.replace(day=1)
    year_start = today.replace(month=1, day=1)
    return {
        "today": (today, today),
        "week": (week_start, today),
        "month": (month_start, today),
        "year": (year_start, today),
    }


def compute_away_stats(
    events: list[dict[str, Any]],
    now: datetime,
    short_minutes: int = 10,
) -> dict[str, Any]:
    """从事件流算出各周期次数/时长 + 当前状态

    返回字段：
      is_away / current_since / current_duration_sec
      last_out / last_home
      {period}_count  有效出门次数（已排除短途）
      {period}_sec    出门总时长（秒，包含短途与进行中的行程）
    """
    trips = pair_trips(events, now)
    bounds = _period_bounds(now)
    short_sec = max(0, int(short_minutes)) * 60

    # 次数按行程「起始日」归属；时长按自然日切分归属
    counts: dict[str, int] = {k: 0 for k in bounds}
    secs: dict[str, int] = {k: 0 for k in bounds}

    for trip in trips:
        start = trip["start"]
        end = trip["end"] or now
        start_day = start.date()

        if trip["duration_sec"] >= short_sec:
            for period, (lo, hi) in bounds.items():
                if lo <= start_day <= hi:
                    counts[period] += 1

        for day, sec in split_trip_by_day(start, end):
            for period, (lo, hi) in bounds.items():
                if lo <= day <= hi:
                    secs[period] += sec

    ongoing = trips[-1] if trips and trips[-1]["end"] is None else None
    closed = [t for t in trips if t["end"] is not None]

    return {
        "is_away": ongoing is not None,
        "current_since": ongoing["start"] if ongoing else None,
        "current_duration_sec": ongoing["duration_sec"] if ongoing else 0,
        "last_out": trips[-1]["start"] if trips else None,
        "last_home": closed[-1]["end"] if closed else None,
        "trip_count_total": len(trips),
        "today_count": counts["today"],
        "week_count": counts["week"],
        "month_count": counts["month"],
        "year_count": counts["year"],
        "today_sec": secs["today"],
        "week_sec": secs["week"],
        "month_sec": secs["month"],
        "year_sec": secs["year"],
    }


def monthly_breakdown(
    events: list[dict[str, Any]],
    now: datetime,
    months: int = 12,
    short_minutes: int = 10,
) -> list[dict[str, Any]]:
    """近 N 个月的按月汇总，供报表折线/柱状使用

    返回 [{"ym": "2026-11", "count": 3, "duration_sec": 7200}, ...]
    从最早到最新升序，缺失月份补 0
    """
    trips = pair_trips(events, now)
    short_sec = max(0, int(short_minutes)) * 60

    buckets: dict[str, dict[str, int]] = {}
    first_month = (now.date().replace(day=1))
    for i in range(months - 1, -1, -1):
        y = first_month.year
        m = first_month.month - i
        while m <= 0:
            m += 12
            y -= 1
        buckets[f"{y:04d}-{m:02d}"] = {"count": 0, "duration_sec": 0}

    for trip in trips:
        start = trip["start"]
        end = trip["end"] or now
        ym = f"{start.year:04d}-{start.month:02d}"
        if trip["duration_sec"] >= short_sec and ym in buckets:
            buckets[ym]["count"] += 1
        # 时长按天切分后归入所在月份
        for day, sec in split_trip_by_day(start, end):
            key = f"{day.year:04d}-{day.month:02d}"
            if key in buckets:
                buckets[key]["duration_sec"] += sec

    return [{"ym": k, "count": v["count"], "duration_sec": v["duration_sec"]}
            for k, v in buckets.items()]
