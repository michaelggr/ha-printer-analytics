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
        """同步建立连接 (在 executor 中调用)"""
        return pymysql.connect(
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
            "(utility_type, account_id, granularity, period_date, usage_amount, charge, "
            " peak, flat, valley, tip, tier1_usage, tier2_usage, tier3_usage, "
            " meter_reading, meter_date, extra) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
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

    async def async_sum_month_charge(self, utility_type: str, year: int, month: int) -> float:
        """查指定年月的费用合计 (按 granularity=month + 该月 day 记录汇总)"""
        def _q():
            conn = self._get_conn_sync()
            period_start = f"{year:04d}-{month:02d}-01"
            with conn.cursor() as cur:
                # 月记录优先
                cur.execute(
                    "SELECT COALESCE(SUM(charge),0) AS s FROM utility_records "
                    "WHERE utility_type=%s AND granularity='month' AND period_date=%s",
                    (utility_type, period_start),
                )
                row = cur.fetchone()
                monthly = float(row["s"]) if row and row["s"] is not None else 0.0
                if monthly > 0:
                    return monthly
                # 没有月记录则汇总日记录
                cur.execute(
                    "SELECT COALESCE(SUM(charge),0) AS s FROM utility_records "
                    "WHERE utility_type=%s AND granularity='day' "
                    " AND YEAR(period_date)=%s AND MONTH(period_date)=%s",
                    (utility_type, year, month),
                )
                row = cur.fetchone()
                return float(row["s"]) if row and row["s"] is not None else 0.0
        return await self.hass.async_add_executor_job(_q)
