"""MariaDB 数据库写入层

用 PyMySQL (同步驱动),所有阻塞操作通过 hass.async_add_executor_job 包装。
单连接 + 自动重连,不需要连接池 (写入频率低)。
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

import pymysql
from pymysql.cursors import DictCursor

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import (
    POWER_INTEGRATION_ENTITIES,
    is_component_power_entity,
    is_derived_energy_entity,
    is_excluded_energy_entity,
    is_excluded_power_entity,
    sum_energy_deltas,
)

_LOGGER = logging.getLogger(__name__)

_SCHEMA_FILE = os.path.join(os.path.dirname(__file__), "schemas.sql")


class UtilityDB:
    """MariaDB 写入层 (单连接,自动重连)"""

    def __init__(
        self,
        hass,
        host: str,
        port: int,
        user: str,
        password: str,
        database: str,
    ) -> None:
        self.hass = hass
        self._host = host
        self._port = port
        self._user = user
        self._password = password
        self._database = database
        self._conn: pymysql.connections.Connection | None = None

    # ---------- 连接管理 ----------

    def _connect_sync(self) -> pymysql.connections.Connection:
        """同步建立连接 (在 executor 中调用)

        连接后将 MariaDB 会话时区对齐到 HA 默认时区,
        保证 SQL 里的 NOW()/CURDATE() 与 Python 写入的本地时间一致。
        """
        conn = pymysql.connect(
            host=self._host,
            port=self._port,
            user=self._user,
            password=self._password,
            database=self._database,
            charset="utf8mb4",
            cursorclass=DictCursor,
            autocommit=True,
            connect_timeout=10,
            read_timeout=30,
            write_timeout=30,
        )
        # 计算 HA 默认时区的 UTC 偏移 (如 +08:00),设置会话时区
        offset = dt_util.get_default_time_zone().utcoffset(dt_util.now())
        if offset is not None:
            total_minutes = int(offset.total_seconds() // 60)
            sign = "+" if total_minutes >= 0 else "-"
            hours, minutes = divmod(abs(total_minutes), 60)
            tz_str = f"{sign}{hours:02d}:{minutes:02d}"
            with conn.cursor() as cur:
                cur.execute(f"SET time_zone = '{tz_str}'")
        return conn

    def _get_conn_sync(self) -> pymysql.connections.Connection:
        """获取可用连接,断开则重连 (在 executor 中调用)"""
        if self._conn is None:
            self._conn = self._connect_sync()
            return self._conn
        try:
            self._conn.ping(reconnect=True)
        except Exception:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = self._connect_sync()
        return self._conn

    async def async_close(self) -> None:
        """关闭连接"""
        def _close():
            if self._conn is not None:
                try:
                    self._conn.close()
                except Exception:
                    pass
                self._conn = None
        await self.hass.async_add_executor_job(_close)

    # ---------- 测试连接 ----------

    async def async_test_connection(self) -> tuple[bool, str]:
        """测试连接,返回 (成功与否, 错误信息)"""
        def _test():
            try:
                conn = self._connect_sync()
                with conn.cursor() as cur:
                    cur.execute("SELECT VERSION() AS v")
                    row = cur.fetchone()
                    version = row["v"] if row else "unknown"
                conn.close()
                return True, f"connected, server version={version}"
            except Exception as e:
                return False, str(e)
        return await self.hass.async_add_executor_job(_test)

    # ---------- 建表 ----------

    async def async_ensure_schema(self) -> None:
        """执行 schemas.sql 建表 (幂等,IF NOT EXISTS)"""
        def _exec():
            with open(_SCHEMA_FILE, "r", encoding="utf-8") as f:
                sql = f.read()
            # 按分号切分语句,过滤空语句和纯注释
            statements = []
            for stmt in sql.split(";"):
                stmt = stmt.strip()
                # 去掉纯注释行后判断是否有实际内容
                lines = [ln for ln in stmt.splitlines() if ln.strip() and not ln.strip().startswith("--")]
                if lines:
                    statements.append(stmt)
            conn = self._get_conn_sync()
            with conn.cursor() as cur:
                for stmt in statements:
                    cur.execute(stmt)
            _LOGGER.info("数据库 schema 已确保 (%d 条语句)", len(statements))
        await self.hass.async_add_executor_job(_exec)

    async def async_migrate_bill_no(self) -> None:
        """v2 迁移: utility_records 加 bill_no 列并扩展唯一键

        背景: 燃气同月可能有多张单据 (正常账单 + 退款负数单),
        旧唯一键 (utility_type,account_id,granularity,period_date) 会互相覆盖。
        幂等: 已存在 bill_no 列则跳过。
        """
        def _exec():
            conn = self._get_conn_sync()
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) AS c FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='utility_records' "
                    "AND COLUMN_NAME='bill_no'"
                )
                row = cur.fetchone()
                if row and int(row["c"]) > 0:
                    return  # 已迁移
                _LOGGER.warning("迁移 utility_records: 添加 bill_no 列并重建唯一键")
                cur.execute(
                    "ALTER TABLE utility_records "
                    "ADD COLUMN bill_no VARCHAR(64) NOT NULL DEFAULT '' "
                    "COMMENT '单据号' AFTER period_date, "
                    "DROP INDEX uniq_record, "
                    "ADD UNIQUE KEY uniq_record "
                    "(utility_type, account_id, granularity, period_date, bill_no)"
                )
        await self.hass.async_add_executor_job(_exec)

    async def async_migrate_light_brightness(self) -> None:
        """v2 迁移: light_events.brightness TINYINT→SMALLINT

        背景: HA brightness 范围 0-255, TINYINT 最大 127,写入越界时整个 coordinator 崩溃。
        幂等: 已改为 SMALLINT 则跳过。
        """
        def _exec():
            conn = self._get_conn_sync()
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT DATA_TYPE FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='light_events' "
                    "AND COLUMN_NAME='brightness'"
                )
                row = cur.fetchone()
                if row and row["DATA_TYPE"].lower() in ("smallint", "int"):
                    return
                _LOGGER.warning("迁移 light_events: brightness TINYINT→SMALLINT")
                cur.execute(
                    "ALTER TABLE light_events MODIFY COLUMN brightness SMALLINT NULL "
                    "COMMENT '亮度 0-255 (开灯时)'"
                )
        await self.hass.async_add_executor_job(_exec)

    # ---------- 记录写入 ----------

    @staticmethod
    def _serialize_extra(extra: Any) -> str | None:
        """把 extra 字段序列化为 JSON 字符串"""
        if extra is None:
            return None
        if isinstance(extra, str):
            return extra
        try:
            return json.dumps(extra, ensure_ascii=False, default=str)
        except Exception:
            return None

    async def async_upsert_records(self, records: list[dict[str, Any]]) -> int:
        """批量 upsert utility_records,返回影响行数"""
        if not records:
            return 0

        sql = (
            "INSERT INTO utility_records "
            "(utility_type, account_id, granularity, period_date, bill_no, usage_amount, charge, "
            " peak, flat, valley, tip, tier1_usage, tier2_usage, tier3_usage, "
            " meter_reading, meter_date, extra) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
            "ON DUPLICATE KEY UPDATE "
            " usage_amount=VALUES(usage_amount), charge=VALUES(charge), "
            " peak=VALUES(peak), flat=VALUES(flat), valley=VALUES(valley), tip=VALUES(tip), "
            " tier1_usage=VALUES(tier1_usage), tier2_usage=VALUES(tier2_usage), tier3_usage=VALUES(tier3_usage), "
            " meter_reading=VALUES(meter_reading), meter_date=VALUES(meter_date), extra=VALUES(extra)"
        )

        def _exec():
            conn = self._get_conn_sync()
            rows = []
            for r in records:
                rows.append((
                    r.get("utility_type"),
                    r.get("account_id"),
                    r.get("granularity"),
                    r.get("period_date"),
                    # bill_no 是唯一键的一部分, NOT NULL, 缺省落空串
                    r.get("bill_no") or "",
                    r.get("usage_amount"),
                    r.get("charge"),
                    r.get("peak"),
                    r.get("flat"),
                    r.get("valley"),
                    r.get("tip"),
                    r.get("tier1_usage"),
                    r.get("tier2_usage"),
                    r.get("tier3_usage"),
                    r.get("meter_reading"),
                    r.get("meter_date"),
                    self._serialize_extra(r.get("extra")),
                ))
            with conn.cursor() as cur:
                affected = cur.executemany(sql, rows)
            return affected
        return await self.hass.async_add_executor_job(_exec)

    async def async_upsert_snapshots(self, snapshots: list[dict[str, Any]]) -> int:
        """批量 upsert account_snapshots"""
        if not snapshots:
            return 0

        sql = (
            "INSERT INTO account_snapshots "
            "(utility_type, account_id, snapshot_date, balance, amount_due, "
            " year_total_usage, year_total_charge, extra) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) "
            "ON DUPLICATE KEY UPDATE "
            " balance=VALUES(balance), amount_due=VALUES(amount_due), "
            " year_total_usage=VALUES(year_total_usage), year_total_charge=VALUES(year_total_charge), "
            " extra=VALUES(extra)"
        )

        def _exec():
            conn = self._get_conn_sync()
            rows = []
            for s in snapshots:
                rows.append((
                    s.get("utility_type"),
                    s.get("account_id"),
                    s.get("snapshot_date"),
                    s.get("balance"),
                    s.get("amount_due"),
                    s.get("year_total_usage"),
                    s.get("year_total_charge"),
                    self._serialize_extra(s.get("extra")),
                ))
            with conn.cursor() as cur:
                affected = cur.executemany(sql, rows)
            return affected
        return await self.hass.async_add_executor_job(_exec)

    # ---------- 统计查询(给 sensor.py 用) ----------

    async def async_count_records(self) -> int:
        """返回 utility_records 总行数"""
        def _q():
            conn = self._get_conn_sync()
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS c FROM utility_records")
                row = cur.fetchone()
                return int(row["c"]) if row else 0
        return await self.hass.async_add_executor_job(_q)

    # =====================================================================
    # 设备功耗 (5 分钟原始 + 小时/日聚合)
    # =====================================================================

    async def async_insert_device_power_raw(self, samples: list[dict[str, Any]]) -> int:
        """批量写入原始采样 (ON DUPLICATE KEY UPDATE 幂等)"""
        if not samples:
            return 0

        sql = (
            "INSERT INTO device_power_raw "
            "(entity_id, friendly_name, sampled_at, power_w, energy_kwh, state) "
            "VALUES (%s,%s,%s,%s,%s,%s) "
            "ON DUPLICATE KEY UPDATE "
            " friendly_name=VALUES(friendly_name), power_w=VALUES(power_w), "
            " energy_kwh=VALUES(energy_kwh), state=VALUES(state)"
        )

        def _exec():
            conn = self._get_conn_sync()
            rows = [
                (
                    s.get("entity_id"),
                    s.get("friendly_name"),
                    s.get("sampled_at"),
                    s.get("power_w"),
                    s.get("energy_kwh"),
                    s.get("state"),
                )
                for s in samples
            ]
            with conn.cursor() as cur:
                return cur.executemany(sql, rows)
        return await self.hass.async_add_executor_job(_exec)

    async def async_aggregate_power_hourly(
        self, hour_start: str, hour_end: str, sample_minutes: int = 5
    ) -> int:
        """把 [hour_start, hour_end) 内的 raw 数据聚合到 device_power_hourly

        energy_kwh 不再用「末值 - 初值」(MAX-MIN): 带电量统计的插座会周期性把
        累计值清零, 一旦清零落在本小时中间, MAX-MIN 会把这个小时的电量算成 0
        甚至负数, 电量凭空丢失。改为「本小时末值 - 上一小时末值」的跨窗口口径,
        由 sum_energy_deltas 识别计数器清零与低分辨率抖动 (见 const.py)。
        对没有可用电量计数器的设备 (见 POWER_INTEGRATION_ENTITIES),
        仍按 AVG(power_w) × 采样点数 × 采样间隔 折算成 kWh 兜底。
        """
        stats_sql = (
            "SELECT entity_id, MAX(friendly_name) AS friendly_name, "
            "       AVG(power_w) AS avg_w, MAX(power_w) AS max_w, MIN(power_w) AS min_w, "
            "       COUNT(*) AS sample_count "
            "FROM device_power_raw "
            "WHERE sampled_at >= %s AND sampled_at < %s "
            "GROUP BY entity_id"
        )
        # 本小时内的电量读数 (时间升序), 用于逐样本求增量
        samples_sql = (
            "SELECT entity_id, energy_kwh FROM device_power_raw "
            "WHERE energy_kwh IS NOT NULL AND sampled_at >= %s AND sampled_at < %s "
            "ORDER BY entity_id, sampled_at"
        )
        # 每个实体在本小时之前的最后一条电量读数, 作为增量基线
        baseline_sql = (
            "SELECT r.entity_id, r.energy_kwh FROM device_power_raw r "
            "INNER JOIN ("
            "  SELECT entity_id, MAX(sampled_at) AS mt FROM device_power_raw "
            "  WHERE energy_kwh IS NOT NULL AND sampled_at < %s GROUP BY entity_id"
            ") m ON r.entity_id=m.entity_id AND r.sampled_at=m.mt"
        )
        insert_sql = (
            "INSERT INTO device_power_hourly "
            "(entity_id, friendly_name, hour_start, avg_w, max_w, min_w, energy_kwh, sample_count) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) "
            "ON DUPLICATE KEY UPDATE "
            " friendly_name=VALUES(friendly_name), avg_w=VALUES(avg_w), "
            " max_w=VALUES(max_w), min_w=VALUES(min_w), "
            " energy_kwh=VALUES(energy_kwh), sample_count=VALUES(sample_count)"
        )

        def _exec():
            conn = self._get_conn_sync()
            with conn.cursor() as cur:
                cur.execute(stats_sql, (hour_start, hour_end))
                stats_rows = cur.fetchall()
                cur.execute(samples_sql, (hour_start, hour_end))
                sample_rows = cur.fetchall()
                cur.execute(baseline_sql, (hour_start,))
                baseline_rows = cur.fetchall()

            # 本小时读数序列 (时间升序) 与跨小时基线分开传给纯函数:
            # 基线只作为参照点, 不参与「是否抖动」的单调性判定
            ref_by_entity = {
                row["entity_id"]: float(row["energy_kwh"]) for row in baseline_rows
            }
            series: dict[str, list[float]] = {}
            for row in sample_rows:
                series.setdefault(row["entity_id"], []).append(float(row["energy_kwh"]))
            energy_by_entity = {
                eid: sum_energy_deltas(values, ref_by_entity.get(eid))
                for eid, values in series.items()
            }

            rows = []
            for row in stats_rows:
                eid = row["entity_id"]
                if energy_by_entity.get(eid) is not None:
                    energy = round(energy_by_entity[eid], 4)
                elif eid in POWER_INTEGRATION_ENTITIES:
                    # 功率积分兜底: 无可用电量计数器 (如取暖器)
                    avg_w = float(row["avg_w"] or 0)
                    energy = round(
                        avg_w * int(row["sample_count"]) * sample_minutes / 60 / 1000, 4
                    )
                else:
                    # 纯功率传感器且不在积分名单: 本小时电量未知
                    energy = None
                rows.append((
                    eid, row["friendly_name"], hour_start,
                    row["avg_w"], row["max_w"], row["min_w"],
                    energy, int(row["sample_count"]),
                ))
            if not rows:
                return 0
            with conn.cursor() as cur:
                return cur.executemany(insert_sql, rows)
        return await self.hass.async_add_executor_job(_exec)

    async def async_aggregate_power_daily(self, day: str) -> int:
        """把 device_power_hourly 中某日数据聚合到 device_power_daily

        过滤口径与 async_sum_power_today 一致: 跳过日/周/月/年派生电量表
        和显式排除实体, 否则同一台设备的 8 张镜像表会被一起累加, 日电量虚高数倍。
        """
        select_sql = (
            "SELECT entity_id, friendly_name, hour_start, avg_w, max_w, min_w, "
            "       energy_kwh, sample_count "
            "FROM device_power_hourly WHERE DATE(hour_start)=%s"
        )
        insert_sql = (
            "INSERT INTO device_power_daily "
            "(entity_id, friendly_name, period_date, avg_w, max_w, min_w, energy_kwh, peak_hour, sample_count) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) "
            "ON DUPLICATE KEY UPDATE "
            " friendly_name=VALUES(friendly_name), avg_w=VALUES(avg_w), "
            " max_w=VALUES(max_w), min_w=VALUES(min_w), "
            " energy_kwh=VALUES(energy_kwh), peak_hour=VALUES(peak_hour), "
            " sample_count=VALUES(sample_count)"
        )

        def _exec():
            conn = self._get_conn_sync()
            with conn.cursor() as cur:
                cur.execute(select_sql, (day,))
                rows = cur.fetchall()

            # 按实体分组, 先剔掉派生电量表与显式排除实体
            grouped: dict[str, list] = {}
            for row in rows:
                eid = row["entity_id"]
                fname = row["friendly_name"]
                if is_derived_energy_entity(eid, fname) or is_excluded_energy_entity(eid):
                    continue
                grouped.setdefault(eid, []).append(row)

            out = []
            for eid, items in grouped.items():
                avgs = [float(r["avg_w"]) for r in items if r["avg_w"] is not None]
                maxs = [float(r["max_w"]) for r in items if r["max_w"] is not None]
                mins = [float(r["min_w"]) for r in items if r["min_w"] is not None]
                energies = [float(r["energy_kwh"]) for r in items if r["energy_kwh"] is not None]
                # 峰值时段取平均功率最大的那个整点
                peak = max(
                    (r for r in items if r["avg_w"] is not None),
                    key=lambda r: float(r["avg_w"]), default=None,
                )
                out.append((
                    eid, items[0]["friendly_name"], day,
                    round(sum(avgs) / len(avgs), 2) if avgs else None,
                    max(maxs) if maxs else None,
                    min(mins) if mins else None,
                    round(sum(energies), 4) if energies else None,
                    peak["hour_start"].hour if peak else None,
                    sum(int(r["sample_count"] or 0) for r in items),
                ))
            if not out:
                return 0
            with conn.cursor() as cur:
                return cur.executemany(insert_sql, out)
        return await self.hass.async_add_executor_job(_exec)

    async def async_cleanup_power_raw(self, retention_days: int) -> int:
        """删除 retention_days 之前的原始采样"""
        sql = "DELETE FROM device_power_raw WHERE sampled_at < DATE_SUB(NOW(), INTERVAL %s DAY)"

        def _exec():
            conn = self._get_conn_sync()
            with conn.cursor() as cur:
                return cur.execute(sql, (retention_days,))
        return await self.hass.async_add_executor_job(_exec)

    async def async_purge_device_data(self) -> dict[str, int]:
        """清空设备功耗/灯光全部数据 (用于异常数据重置)"""
        def _exec():
            conn = self._get_conn_sync()
            result = {}
            with conn.cursor() as cur:
                for table in (
                    "device_power_raw", "device_power_hourly",
                    "device_power_daily", "light_events", "light_daily",
                    "light_duration_daily", "area_stay_daily",
                    "area_stay_hourly",
                ):
                    cur.execute(f"DELETE FROM {table}")
                    result[table] = cur.rowcount
            return result
        return await self.hass.async_add_executor_job(_exec)

    async def async_sum_power_today(self) -> float:
        """返回今日所有设备耗电合计 kWh (查 device_power_hourly)

        按实体分组后过滤派生电量 (日/周/月/年用电量), 只累加各设备的权威电量计数器,
        否则同一设备的日表/周表/月表/年表会被重复求和, 今日电量成倍虚高。
        历史行不做删除, 仅影响本次查询结果, 修复当天立即生效。
        """
        def _q():
            conn = self._get_conn_sync()
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT entity_id, MAX(friendly_name) AS friendly_name, "
                    "       COALESCE(SUM(energy_kwh),0) AS s "
                    "FROM device_power_hourly "
                    "WHERE DATE(hour_start) = CURDATE() "
                    "GROUP BY entity_id"
                )
                rows = cur.fetchall()
            total = 0.0
            for row in rows:
                if is_derived_energy_entity(row["entity_id"], row["friendly_name"]):
                    continue
                if is_excluded_energy_entity(row["entity_id"]):
                    continue
                if row["s"] is not None:
                    total += float(row["s"])
            return total
        return await self.hass.async_add_executor_job(_q)

    async def async_current_total_power(self) -> float:
        """返回当前所有设备实时功率合计 W (取最近 10 分钟内的采样)

        过滤组件级功率 (CPU/GPU/压缩机), 这些部件读数已被整机功率覆盖,
        同时求和会重复计量; 查询侧过滤保证无需等待旧采样过期即立刻生效。
        """
        def _q():
            conn = self._get_conn_sync()
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT latest.entity_id, latest.friendly_name, latest.power_w FROM ("
                    "  SELECT r.entity_id, r.friendly_name, r.power_w FROM device_power_raw r "
                    "  INNER JOIN ("
                    "    SELECT entity_id, MAX(sampled_at) AS mt "
                    "    FROM device_power_raw "
                    "    WHERE sampled_at >= DATE_SUB(NOW(), INTERVAL 10 MINUTE) "
                    "    GROUP BY entity_id"
                    "  ) m ON r.entity_id=m.entity_id AND r.sampled_at=m.mt "
                    ") latest WHERE latest.power_w IS NOT NULL"
                )
                rows = cur.fetchall()
            total = 0.0
            for row in rows:
                if is_component_power_entity(row["entity_id"], row["friendly_name"]):
                    continue
                if is_excluded_power_entity(row["entity_id"]):
                    continue
                total += float(row["power_w"])
            return total
        return await self.hass.async_add_executor_job(_q)

    async def async_fetch_last_power_values(
        self, lookback_hours: int = 24
    ) -> dict[str, float]:
        """取每个实体在回溯窗口内最近一条非空 power_w, 供入库前跳变过滤

        返回 {entity_id: power_w}; 无历史采样的实体不出现在字典中
        """
        def _q():
            conn = self._get_conn_sync()
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT r.entity_id, r.power_w FROM device_power_raw r "
                    "INNER JOIN ("
                    "  SELECT entity_id, MAX(sampled_at) AS mt "
                    "  FROM device_power_raw "
                    "  WHERE power_w IS NOT NULL "
                    "  AND sampled_at >= DATE_SUB(NOW(), INTERVAL %s HOUR) "
                    "  GROUP BY entity_id"
                    " ) m ON r.entity_id=m.entity_id AND r.sampled_at=m.mt",
                    (lookback_hours,),
                )
                rows = cur.fetchall()
            return {
                row["entity_id"]: float(row["power_w"])
                for row in rows
                if row["power_w"] is not None
            }
        return await self.hass.async_add_executor_job(_q)

    # =====================================================================
    # 灯光事件 + 日聚合
    # =====================================================================

    async def async_insert_light_events(self, events: list[dict[str, Any]]) -> int:
        """批量写入灯光事件"""
        if not events:
            return 0

        sql = (
            "INSERT INTO light_events "
            "(entity_id, friendly_name, event_time, action, brightness, color_temp) "
            "VALUES (%s,%s,%s,%s,%s,%s)"
        )

        def _exec():
            conn = self._get_conn_sync()
            rows = [
                (
                    e.get("entity_id"),
                    e.get("friendly_name"),
                    e.get("event_time"),
                    e.get("action"),
                    e.get("brightness"),
                    e.get("color_temp"),
                )
                for e in events
            ]
            with conn.cursor() as cur:
                return cur.executemany(sql, rows)
        return await self.hass.async_add_executor_job(_exec)

    async def async_last_light_event_time(self) -> str | None:
        """返回最近一次已记录的事件时间 (用于增量采集)"""
        def _q():
            conn = self._get_conn_sync()
            with conn.cursor() as cur:
                cur.execute("SELECT MAX(event_time) AS t FROM light_events")
                row = cur.fetchone()
                if not row or row["t"] is None:
                    return None
                t = row["t"]
                return t.strftime("%Y-%m-%d %H:%M:%S") if hasattr(t, "strftime") else str(t)
        return await self.hass.async_add_executor_job(_q)

    async def async_aggregate_light_daily(self, day: str) -> int:
        """聚合某日灯光事件到 light_daily

        亮灯时长用 LEAD 窗口函数把每个 on 配对其后第一个 off
        """
        # MariaDB 10.2+ 支持 LEAD 窗口函数
        sql = (
            "INSERT INTO light_daily "
            "(entity_id, friendly_name, period_date, on_count, on_duration_sec, "
            " first_on_time, last_off_time, avg_brightness) "
            "SELECT entity_id, MAX(friendly_name), %s, "
            " SUM(action='on'), "
            " COALESCE(SUM(CASE WHEN action='on' AND next_action='off' "
            "   THEN TIMESTAMPDIFF(SECOND, event_time, next_time) END), 0), "
            " MIN(CASE WHEN action='on' THEN event_time END), "
            " MAX(CASE WHEN action='off' THEN event_time END), "
            " AVG(CASE WHEN action='on' THEN brightness END) "
            "FROM ("
            "  SELECT entity_id, friendly_name, event_time, action, brightness, "
            "    LEAD(action) OVER (PARTITION BY entity_id ORDER BY event_time) AS next_action, "
            "    LEAD(event_time) OVER (PARTITION BY entity_id ORDER BY event_time) AS next_time "
            "  FROM light_events WHERE DATE(event_time)=%s"
            ") t "
            "GROUP BY entity_id "
            "ON DUPLICATE KEY UPDATE "
            " friendly_name=VALUES(friendly_name), on_count=VALUES(on_count), "
            " on_duration_sec=VALUES(on_duration_sec), "
            " first_on_time=VALUES(first_on_time), last_off_time=VALUES(last_off_time), "
            " avg_brightness=VALUES(avg_brightness)"
        )

        def _exec():
            conn = self._get_conn_sync()
            with conn.cursor() as cur:
                # SQL 有 2 个 %s: SELECT 中的 period_date 和子查询 WHERE DATE(event_time)
                return cur.execute(sql, (day, day))
        return await self.hass.async_add_executor_job(_exec)

    async def async_sum_light_today(self) -> tuple[int, int]:
        """返回今日 (开灯次数, 亮灯秒数) 合计"""
        def _q():
            conn = self._get_conn_sync()
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COALESCE(SUM(on_count),0) AS c, COALESCE(SUM(on_duration_sec),0) AS s "
                    "FROM light_daily WHERE period_date = CURDATE()"
                )
                row = cur.fetchone()
                if not row:
                    return 0, 0
                return int(row["c"]), int(row["s"])
        return await self.hass.async_add_executor_job(_q)

    async def async_upsert_light_durations(self, rows: list[dict[str, Any]]) -> int:
        """批量写入区域主灯每日亮灯时长 (同上一天覆盖更新)

        rows 元素: {entity_id, area_name, period_date, duration_sec}
        """
        if not rows:
            return 0

        sql = (
            "INSERT INTO light_duration_daily "
            "(entity_id, area_name, period_date, duration_sec) "
            "VALUES (%s,%s,%s,%s) "
            "ON DUPLICATE KEY UPDATE "
            " area_name=VALUES(area_name), duration_sec=VALUES(duration_sec)"
        )
        params = [
            (r["entity_id"], r["area_name"], r["period_date"], r["duration_sec"])
            for r in rows
        ]

        def _exec():
            conn = self._get_conn_sync()
            with conn.cursor() as cur:
                return cur.executemany(sql, params)
        return await self.hass.async_add_executor_job(_exec)

    async def async_sum_light_duration_today(self) -> int:
        """返回今日 13 个区域主灯亮灯秒数合计 (来自 history_stats 快照表)"""
        def _q():
            conn = self._get_conn_sync()
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COALESCE(SUM(duration_sec),0) AS s "
                    "FROM light_duration_daily WHERE period_date = CURDATE()"
                )
                row = cur.fetchone()
                return int(row["s"]) if row and row["s"] is not None else 0
        return await self.hass.async_add_executor_job(_q)

    async def async_upsert_area_stays(self, rows: list[dict[str, Any]]) -> int:
        """批量写入区域每日停留时长 (同一天覆盖更新)

        rows 元素: {entity_id, area_name, period_date, duration_sec}
        """
        if not rows:
            return 0

        sql = (
            "INSERT INTO area_stay_daily "
            "(entity_id, area_name, period_date, duration_sec) "
            "VALUES (%s,%s,%s,%s) "
            "ON DUPLICATE KEY UPDATE "
            " area_name=VALUES(area_name), duration_sec=VALUES(duration_sec)"
        )
        params = [
            (r["entity_id"], r["area_name"], r["period_date"], r["duration_sec"])
            for r in rows
        ]

        def _exec():
            conn = self._get_conn_sync()
            with conn.cursor() as cur:
                return cur.executemany(sql, params)
        return await self.hass.async_add_executor_job(_exec)

    async def async_upsert_area_stays_hourly(self, rows: list[dict[str, Any]]) -> int:
        """把区域停留增量累加进小时桶 (同一天同一小时多次采样累加)

        rows 元素: {entity_id, area_name, period_date, period_hour, duration_sec}
        duration_sec 是「相对上次采样」的增量, 所以冲突时用 + 而不是覆盖
        """
        if not rows:
            return 0

        sql = (
            "INSERT INTO area_stay_hourly "
            "(entity_id, area_name, period_date, period_hour, duration_sec) "
            "VALUES (%s,%s,%s,%s,%s) "
            "ON DUPLICATE KEY UPDATE "
            " area_name=VALUES(area_name), "
            " duration_sec=duration_sec+VALUES(duration_sec)"
        )
        params = [
            (
                r["entity_id"], r["area_name"], r["period_date"],
                r["period_hour"], r["duration_sec"],
            )
            for r in rows
        ]

        def _exec():
            conn = self._get_conn_sync()
            with conn.cursor() as cur:
                return cur.executemany(sql, params)
        return await self.hass.async_add_executor_job(_exec)

    async def async_sum_area_stay_today(self) -> int:
        """返回今日各区域停留秒数合计 (来自 history_stats 快照表)"""
        def _q():
            conn = self._get_conn_sync()
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COALESCE(SUM(duration_sec),0) AS s "
                    "FROM area_stay_daily WHERE period_date = CURDATE()"
                )
                row = cur.fetchone()
                return int(row["s"]) if row and row["s"] is not None else 0
        return await self.hass.async_add_executor_job(_q)

    async def async_fetch_area_stays_today(self) -> list[dict[str, Any]]:
        """返回今日各区域停留明细 (区域名/秒数), 供看板或诊断使用"""
        def _q():
            conn = self._get_conn_sync()
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT area_name, duration_sec FROM area_stay_daily "
                    "WHERE period_date = CURDATE() ORDER BY duration_sec DESC"
                )
                return [
                    {"area_name": r["area_name"], "duration_sec": int(r["duration_sec"])}
                    for r in cur.fetchall()
                ]
        return await self.hass.async_add_executor_job(_q)

    async def async_sum_area_stay_week(self) -> int:
        """近 7 日 (含今日) 各区域停留秒数合计"""
        def _q():
            conn = self._get_conn_sync()
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COALESCE(SUM(duration_sec),0) AS s "
                    "FROM area_stay_daily "
                    "WHERE period_date BETWEEN DATE_SUB(CURDATE(), INTERVAL 6 DAY) AND CURDATE()"
                )
                row = cur.fetchone()
                return int(row["s"]) if row and row["s"] is not None else 0
        return await self.hass.async_add_executor_job(_q)

    async def async_sum_area_stay_month(self) -> int:
        """本月 1 日至今 各区域停留秒数合计"""
        def _q():
            conn = self._get_conn_sync()
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COALESCE(SUM(duration_sec),0) AS s "
                    "FROM area_stay_daily "
                    "WHERE period_date >= DATE_SUB(CURDATE(), INTERVAL DAY(CURDATE())-1 DAY)"
                )
                row = cur.fetchone()
                return int(row["s"]) if row and row["s"] is not None else 0
        return await self.hass.async_add_executor_job(_q)

    async def async_fetch_area_stays_week(self) -> list[dict[str, Any]]:
        """近 7 日各区域停留合计 (区域名/秒数), 供看板对比"""
        def _q():
            conn = self._get_conn_sync()
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT area_name, SUM(duration_sec) AS total_sec "
                    "FROM area_stay_daily "
                    "WHERE period_date BETWEEN DATE_SUB(CURDATE(), INTERVAL 6 DAY) AND CURDATE() "
                    "GROUP BY area_name ORDER BY total_sec DESC"
                )
                return [
                    {"area_name": r["area_name"], "duration_sec": int(r["total_sec"])}
                    for r in cur.fetchall()
                ]
        return await self.hass.async_add_executor_job(_q)

    async def async_fetch_area_stays_month(self) -> list[dict[str, Any]]:
        """本月 1 日至今 各区域停留合计 (区域名/秒数), 供看板排行榜"""
        def _q():
            conn = self._get_conn_sync()
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT area_name, SUM(duration_sec) AS total_sec "
                    "FROM area_stay_daily "
                    "WHERE period_date >= DATE_SUB(CURDATE(), INTERVAL DAY(CURDATE())-1 DAY) "
                    "GROUP BY area_name ORDER BY total_sec DESC"
                )
                return [
                    {"area_name": r["area_name"], "duration_sec": int(r["total_sec"])}
                    for r in cur.fetchall()
                ]
        return await self.hass.async_add_executor_job(_q)

    async def async_delete_utility_records(
        self, utility_type: str, account_id: str, granularity: str | None = None
    ) -> int:
        """删除指定户的所有 utility_records (用于分户改造前的脏数据清理)"""
        def _q():
            conn = self._get_conn_sync()
            sql = "DELETE FROM utility_records WHERE utility_type=%s AND account_id=%s"
            params: tuple = (utility_type, account_id)
            if granularity:
                sql += " AND granularity=%s"
                params = (utility_type, account_id, granularity)
            with conn.cursor() as cur:
                cur.execute(sql, params)
                affected = cur.rowcount
            conn.commit()
            return affected
        return await self.hass.async_add_executor_job(_q)

    async def async_delete_unknown_gas_accounts(self, known: tuple[str, ...]) -> int:
        """删除 utility_type='gas' 且 account_id 不在已知集合内的所有记录"""
        if not known:
            return 0
        def _q():
            conn = self._get_conn_sync()
            placeholders = ",".join(["%s"] * len(known))
            sql = (
                f"DELETE FROM utility_records WHERE utility_type='gas' "
                f"AND account_id NOT IN ({placeholders})"
            )
            with conn.cursor() as cur:
                cur.execute(sql, known)
                affected = cur.rowcount
            conn.commit()
            return affected
        return await self.hass.async_add_executor_job(_q)

    async def async_sum_month_charge(
        self,
        utility_type: str,
        year: int,
        month: int,
        account_id: str | None = None,
    ) -> float:
        """查指定年月的费用合计 (按 granularity=month + 该月 day 记录汇总)

        account_id 为 None 时合计所有户; 指定时只算该户 (用于分户显示)"""
        def _q():
            conn = self._get_conn_sync()
            period_start = f"{year:04d}-{month:02d}-01"
            # 按户过滤的 SQL 片段
            acct_sql = " AND account_id=%s" if account_id else ""
            acct_params = (account_id,) if account_id else ()
            with conn.cursor() as cur:
                # 月记录优先 (只要有月记录就返回其合计, 允许负数=退款净额)
                cur.execute(
                    "SELECT COALESCE(SUM(charge),0) AS s, COUNT(*) AS c FROM utility_records "
                    "WHERE utility_type=%s AND granularity='month' AND period_date=%s" + acct_sql,
                    (utility_type, period_start) + acct_params,
                )
                row = cur.fetchone()
                if row and int(row["c"]) > 0:
                    return float(row["s"]) if row["s"] is not None else 0.0
                # 没有月记录则汇总日记录
                cur.execute(
                    "SELECT COALESCE(SUM(charge),0) AS s FROM utility_records "
                    "WHERE utility_type=%s AND granularity='day' "
                    " AND YEAR(period_date)=%s AND MONTH(period_date)=%s" + acct_sql,
                    (utility_type, year, month) + acct_params,
                )
                row = cur.fetchone()
                return float(row["s"]) if row and row["s"] is not None else 0.0
        return await self.hass.async_add_executor_job(_q)
