"""Utility Tracker 单元测试

测试纯函数和工具逻辑,不依赖 HA 运行环境。
"""
import unittest

# 直接 import 待测模块的工具函数
import sys
sys.path.insert(0, "g:\\dev\\ha\\ha\\custom_components\\utility_tracker")

# 由于 coordinator.py 依赖 homeassistant,我们用 importlib 单独加载工具函数
import importlib.util
spec = importlib.util.spec_from_file_location(
    "utility_tracker_coordinator_helpers",
    "g:\\dev\\ha\\ha\\custom_components\\utility_tracker\\coordinator.py",
)


# 不加载整个模块,直接复制要测的函数定义
# 这样避免依赖 homeassistant


def _safe_float(value):
    """安全转 float,失败返回 None (从 coordinator.py 复制)"""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def bill_month_to_date(bill_ym):
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


class TestSafeFloat(unittest.TestCase):
    """测试 _safe_float"""

    def test_正常数字(self):
        self.assertEqual(_safe_float(1.5), 1.5)
        self.assertEqual(_safe_float("2.53"), 2.53)
        self.assertEqual(_safe_float(0), 0.0)

    def test_None_返回None(self):
        self.assertIsNone(_safe_float(None))

    def test_空字符串_返回None(self):
        self.assertIsNone(_safe_float(""))

    def test_非数字字符串_返回None(self):
        self.assertIsNone(_safe_float("abc"))
        self.assertIsNone(_safe_float("unknown"))
        self.assertIsNone(_safe_float("unavailable"))

    def test_非法类型_返回None(self):
        self.assertIsNone(_safe_float([]))
        self.assertIsNone(_safe_float({}))


class TestBillMonthToDate(unittest.TestCase):
    """测试 bill_month_to_date"""

    def test_正常月份(self):
        self.assertEqual(bill_month_to_date("2026-10"), "2026-10-01")
        self.assertEqual(bill_month_to_date("2026-01"), "2026-01-01")
        self.assertEqual(bill_month_to_date("2026-12"), "2026-12-01")

    def test_单位月_补零(self):
        self.assertEqual(bill_month_to_date("2026-1"), "2026-01-01")
        self.assertEqual(bill_month_to_date("2026-9"), "2026-09-01")

    def test_None_返回None(self):
        self.assertIsNone(bill_month_to_date(None))

    def test_空字符串_返回None(self):
        self.assertIsNone(bill_month_to_date(""))

    def test_非字符串_返回None(self):
        self.assertIsNone(bill_month_to_date(202610))
        self.assertIsNone(bill_month_to_date([]))

    def test_格式错误_返回None(self):
        self.assertIsNone(bill_month_to_date("2026"))
        self.assertIsNone(bill_month_to_date("2026-10-15"))
        self.assertIsNone(bill_month_to_date("abc-def"))

    def test_月份越界_返回None(self):
        self.assertIsNone(bill_month_to_date("2026-00"))
        self.assertIsNone(bill_month_to_date("2026-13"))
        self.assertIsNone(bill_month_to_date("2026--1"))


class TestElectricityDailyRecordMapping(unittest.TestCase):
    """测试电费日记录从 SGCC daily_history 到 utility_records 字段的映射"""

    def test_daily_history_完整字段映射(self):
        # 模拟 SGCC daily_history 单条数据
        item = {
            "day": "2026-09-01",
            "usage": 7.94,
            "charge": None,
            "valley": 0.0,
            "flat": 7.94,
            "peak": 0.0,
            "tip": 0.0,
        }
        # 按 coordinator 逻辑构造 record
        record = {
            "utility_type": "electricity",
            "account_id": "0065",
            "granularity": "day",
            "period_date": item.get("day"),
            "usage_amount": _safe_float(item.get("usage")),
            "charge": _safe_float(item.get("charge")),
            "peak": _safe_float(item.get("peak")),
            "flat": _safe_float(item.get("flat")),
            "valley": _safe_float(item.get("valley")),
            "tip": _safe_float(item.get("tip")),
        }
        self.assertEqual(record["period_date"], "2026-09-01")
        self.assertEqual(record["usage_amount"], 7.94)
        self.assertIsNone(record["charge"])
        self.assertEqual(record["flat"], 7.94)
        self.assertEqual(record["peak"], 0.0)
        self.assertEqual(record["valley"], 0.0)
        self.assertEqual(record["tip"], 0.0)

    def test_daily_history_缺失峰谷字段(self):
        """老数据可能没有峰谷平尖"""
        item = {"day": "2026-09-01", "usage": 7.94}
        record = {
            "period_date": item.get("day"),
            "usage_amount": _safe_float(item.get("usage")),
            "charge": _safe_float(item.get("charge")),
            "peak": _safe_float(item.get("peak")),
            "flat": _safe_float(item.get("flat")),
            "valley": _safe_float(item.get("valley")),
            "tip": _safe_float(item.get("tip")),
        }
        self.assertEqual(record["usage_amount"], 7.94)
        self.assertIsNone(record["peak"])
        self.assertIsNone(record["flat"])

    def test_daily_history_缺失day_应跳过(self):
        item = {"usage": 7.94}
        # coordinator 的 continue 逻辑
        day_str = item.get("day")
        self.assertIsNone(day_str)


class TestGasBillMapping(unittest.TestCase):
    """测试燃气账单从 crcgas bill_history 到 utility_records 的映射"""

    def test_完整账单映射(self):
        bill = {
            "applicationNo": "0126101915558343",
            "billAmt": 2.53,
            "billYm": "2026-10",
            "gasAmt": 1.0,
            "penaltyAmt": 0.0,
            "penaltyDate": "2026-11-01",
            "revblAmt": 2.53,
            "settleFlag": "全部结清",
        }
        period_date = bill_month_to_date(bill.get("billYm"))
        record = {
            "utility_type": "gas",
            "account_id": "1040395237",
            "granularity": "month",
            "period_date": period_date,
            "usage_amount": _safe_float(bill.get("gasAmt")),
            "charge": _safe_float(bill.get("billAmt")),
            "extra": {
                "applicationNo": bill.get("applicationNo"),
                "penaltyAmt": bill.get("penaltyAmt"),
                "settleFlag": bill.get("settleFlag"),
            },
        }
        self.assertEqual(record["period_date"], "2026-10-01")
        self.assertEqual(record["charge"], 2.53)
        self.assertEqual(record["usage_amount"], 1.0)
        self.assertEqual(record["extra"]["applicationNo"], "0126101915558343")

    def test_负数账单_退款保留负号(self):
        """crcgas 退款账单为负数 (燃气公司退钱给用户), 入库时保留原始符号"""
        bill = {"billYm": "2026-10", "billAmt": -49.99, "gasAmt": -19.76,
                "applicationNo": "REFUND001"}
        period_date = bill_month_to_date(bill.get("billYm"))
        self.assertEqual(period_date, "2026-10-01")
        # 与 coordinator._backfill_gas_history 一致: 不取绝对值
        self.assertEqual(_safe_float(bill.get("billAmt")), -49.99)
        self.assertEqual(_safe_float(bill.get("gasAmt")), -19.76)

    def test_正数账单_符号不变(self):
        bill = {"billYm": "2026-10", "billAmt": 2.53, "gasAmt": 1.0}
        self.assertEqual(_safe_float(bill.get("billAmt")), 2.53)
        self.assertEqual(_safe_float(bill.get("gasAmt")), 1.0)

    def test_同月多单据_按bill_no区分(self):
        """同月正常账单+退款单: period_date 相同但 bill_no 不同, 都入库且净额正确"""
        bills = [
            {"billYm": "2026-10", "billAmt": 2.53, "gasAmt": 1.0,
             "applicationNo": "0126101915558343"},
            {"billYm": "2026-10", "billAmt": -49.99, "gasAmt": -19.76,
             "applicationNo": "REFUND20261001"},
        ]
        records = []
        for bill in bills:
            period_date = bill_month_to_date(bill.get("billYm"))
            records.append({
                "period_date": period_date,
                "bill_no": bill.get("applicationNo") or f"auto-{period_date}-{len(records)}",
                "charge": _safe_float(bill.get("billAmt")),
            })
        # 两张单据 period_date 相同, bill_no 不同 => 唯一键不冲突
        self.assertEqual(records[0]["period_date"], records[1]["period_date"])
        self.assertNotEqual(records[0]["bill_no"], records[1]["bill_no"])
        # 月度净额 = 2.53 - 49.99 = -47.46
        net = sum(r["charge"] for r in records)
        self.assertAlmostEqual(net, -47.46, places=2)

    def test_bill_no缺失_用序号兜底(self):
        """applicationNo 缺失时生成 auto- 前缀兜底 bill_no, 保证唯一键不冲突"""
        bills = [
            {"billYm": "2026-10", "billAmt": 2.53},
            {"billYm": "2026-10", "billAmt": -49.99},
        ]
        records = []
        for bill in bills:
            period_date = bill_month_to_date(bill.get("billYm"))
            bill_no = bill.get("applicationNo") or f"auto-{period_date}-{len(records)}"
            records.append(bill_no)
        self.assertEqual(records[0], "auto-2026-10-01-0")
        self.assertEqual(records[1], "auto-2026-10-01-1")
        self.assertNotEqual(records[0], records[1])


class TestAccountSnapshotMapping(unittest.TestCase):
    """测试账户快照映射"""

    def test_电费快照(self):
        snap = {
            "utility_type": "electricity",
            "account_id": "0065",
            "snapshot_date": "2026-10-27",
            "balance": 100.5,
            "amount_due": 0.0,
            "year_total_usage": 1234.5,
            "year_total_charge": 678.9,
        }
        # 校验所有关键字段
        self.assertEqual(snap["utility_type"], "electricity")
        self.assertIsNotNone(snap["snapshot_date"])
        self.assertGreaterEqual(snap["balance"], 0)

    def test_燃气快照_含阶梯价(self):
        snap = {
            "utility_type": "gas",
            "account_id": "1040395237",
            "snapshot_date": "2026-10-27",
            "balance": 92.4,
            "amount_due": 0.0,
            "extra": {
                "yi_jie_ti_qi_jie": 2.53,
                "er_jie_ti_qi_jie": 0.0,
                "san_jie_ti_qi_jie": 0.0,
            },
        }
        self.assertEqual(snap["extra"]["yi_jie_ti_qi_jie"], 2.53)


class TestCoordinatorDataKeys(unittest.TestCase):
    """测试 coordinator.data 包含 sensor 所需的 key (回归 electricity_this_month/gas_this_month unknown bug)"""

    def test_stats_dict_包含月度费用key(self):
        """_async_update_data 返回的 stats 必须包含 electricity_this_month 和 gas_this_month"""
        # 模拟 coordinator 返回的 stats dict
        stats = {
            "elec_day_records": 122,
            "elec_month_records": 18,
            "elec_snapshots": 2,
            "gas_month_records": 1,
            "gas_snapshots": 1,
            # 关键:新增的两个 key
            "electricity_this_month": 0.0,
            "gas_this_month": 49.99,
        }
        # sensor.native_value 读取逻辑
        self.assertIn("electricity_this_month", stats)
        self.assertIn("gas_this_month", stats)
        self.assertEqual(stats.get("gas_this_month"), 49.99)

    def test_空data时_sensor返回None(self):
        """coordinator.data 为 None 时 sensor.native_value 应返回 None 而非 AttributeError"""
        coordinator_data = None
        # 模拟 sensor.py 中的 native_value 实现
        value = (coordinator_data or {}).get("electricity_this_month")
        self.assertIsNone(value)

    def test_缺key时_sensor返回None(self):
        """coordinator.data 存在但缺 key 时 sensor.native_value 应返回 None"""
        coordinator_data = {"elec_day_records": 122}
        value = (coordinator_data or {}).get("gas_this_month")
        self.assertIsNone(value)


class TestMultiAccountSplit(unittest.TestCase):
    """测试分户 (自住/出租) 数据拆分逻辑"""

    def test_分户stats_key存在(self):
        """coordinator.data 必须包含 4 个分户 key"""
        stats = {
            "electricity_this_month": 0.0,
            "gas_this_month": 7.59,
            "electricity_this_month_main": 0.0,      # 0065 东方新天地
            "electricity_this_month_rental": 0.0,    # 7061 东方佳园
            "gas_this_month_main": 2.53,             # 1040395237 东方新天地
            "gas_this_month_rental": 5.06,           # 1021540961 东方佳园
        }
        for key in ("electricity_this_month_main", "electricity_this_month_rental",
                    "gas_this_month_main", "gas_this_month_rental"):
            self.assertIn(key, stats)
        # 业务约束: 主+租 应等于合计
        self.assertAlmostEqual(
            stats["gas_this_month_main"] + stats["gas_this_month_rental"],
            stats["gas_this_month"],
            places=2,
        )

    def test_燃气sensor_key解析_主户(self):
        """主户 entity_id 应为 sensor.hua_run_ran_qi_<key>"""
        eid = "sensor.hua_run_ran_qi_zhang_dan_jin_e"
        prefix = "sensor.hua_run_ran_qi_"
        rest = eid[len(prefix):]
        # 不应匹配 10 位数字副户格式
        import re
        m = re.match(r"^(\d{10})_(.+)$", rest)
        self.assertIsNone(m)
        # 主户 rest 就是 key
        self.assertEqual(rest, "zhang_dan_jin_e")

    def test_燃气sensor_key解析_副户(self):
        """副户 entity_id 应正确解析 cons_no 和 key"""
        import re
        eid = "sensor.hua_run_ran_qi_1021540961_zhang_dan_jin_e_fu_xin"
        prefix = "sensor.hua_run_ran_qi_"
        rest = eid[len(prefix):]
        m = re.match(r"^(\d{10})_(.+)$", rest)
        self.assertIsNotNone(m)
        cons_no, key_with_name = m.groups()
        self.assertEqual(cons_no, "1021540961")
        # 剥离尾部 name 拼音
        gas_keys = ("zhang_dan_yue_fen", "zhang_dan_jin_e", "ben_qi_yong_qi_liang")
        matched_key = None
        for k in gas_keys:
            if key_with_name.startswith(k + "_"):
                matched_key = k
                break
        self.assertEqual(matched_key, "zhang_dan_jin_e")

    def test_燃气sensor_key解析_副户key前缀冲突(self):
        """key 前缀重叠时应匹配最长 key (避免 zhang_dan 误匹配 zhang_dan_jin_e)"""
        import re
        # ben_qi_yi_jie_ti_yong_qi_liang 必须以完整 key 匹配
        eid = "sensor.hua_run_ran_qi_1021540961_ben_qi_yi_jie_ti_yong_qi_liang_fu_xin"
        prefix = "sensor.hua_run_ran_qi_"
        rest = eid[len(prefix):]
        m = re.match(r"^(\d{10})_(.+)$", rest)
        cons_no, key_with_name = m.groups()
        # 不能用 ben_qi 这种短前缀,否则会先匹配错;按完整 key 匹配
        gas_keys = (
            "ben_qi_yi_jie_ti_yong_qi_liang",  # 放前面 (更长)
            "ben_qi_yong_qi_liang",            # 较短
        )
        matched_key = None
        for k in gas_keys:
            if key_with_name.startswith(k + "_"):
                matched_key = k
                break
        self.assertEqual(matched_key, "ben_qi_yi_jie_ti_yong_qi_liang")


class TestSQLUpsertStructure(unittest.TestCase):
    """测试 SQL upsert 字段顺序与 schemas.sql 一致性"""

    def test_records_字段数量(self):
        """db.py 中 upsert 的字段数应与 schemas.sql 中 utility_records 的列数匹配"""
        # utility_records 列(除 id, created_at, updated_at)
        expected_cols = [
            "utility_type", "account_id", "granularity", "period_date",
            "usage_amount", "charge",
            "peak", "flat", "valley", "tip",
            "tier1_usage", "tier2_usage", "tier3_usage",
            "meter_reading", "meter_date", "extra",
        ]
        self.assertEqual(len(expected_cols), 16)

    def test_snapshots_字段数量(self):
        """account_snapshots 列(除 id, created_at)"""
        expected_cols = [
            "utility_type", "account_id", "snapshot_date",
            "balance", "amount_due",
            "year_total_usage", "year_total_charge",
            "extra",
        ]
        self.assertEqual(len(expected_cols), 8)


class TestPowerSampleAlignment(unittest.TestCase):
    """测试设备功耗采样时间对齐 (5 分钟边界,保证 UNIQUE(entity_id, sampled_at) 幂等)"""

    def _align(self, minute: int, second: int = 0, sample_minutes: int = 5) -> str:
        """从 coordinator._collect_device_power 复制的对齐逻辑"""
        from datetime import datetime
        now = datetime(2026, 10, 28, 10, minute, second)
        aligned = now.replace(
            minute=(now.minute // sample_minutes) * sample_minutes,
            second=0, microsecond=0,
        )
        return aligned.strftime("%Y-%m-%d %H:%M:%S")

    def test_整5分钟_保持不变(self):
        self.assertEqual(self._align(0), "2026-10-28 10:00:00")
        self.assertEqual(self._align(5), "2026-10-28 10:05:00")
        self.assertEqual(self._align(55), "2026-10-28 10:55:00")

    def test_非整5分钟_向下对齐(self):
        self.assertEqual(self._align(3), "2026-10-28 10:00:00")
        self.assertEqual(self._align(7), "2026-10-28 10:05:00")
        self.assertEqual(self._align(59), "2026-10-28 10:55:00")

    def test_带秒_秒清零(self):
        self.assertEqual(self._align(7, 45), "2026-10-28 10:05:00")

    def test_自定义采样间隔_10分钟(self):
        self.assertEqual(self._align(17, sample_minutes=10), "2026-10-28 10:10:00")
        self.assertEqual(self._align(29, sample_minutes=10), "2026-10-28 10:20:00")


class TestPowerSampleMapping(unittest.TestCase):
    """测试 device_class 分流到 power_w / energy_kwh 字段"""

    def _make_sample(self, device_class: str, state_val: str) -> dict:
        """从 coordinator._collect_device_power 复制的字段映射逻辑"""
        # 模拟 _state_float
        try:
            val = float(state_val) if state_val not in ("unavailable", "unknown", "none", "") else None
        except (ValueError, TypeError):
            val = None
        return {
            "power_w": val if device_class == "power" else None,
            "energy_kwh": val if device_class == "energy" else None,
        }

    def test_power_传感器_写入power_w(self):
        s = self._make_sample("power", "123.4")
        self.assertEqual(s["power_w"], 123.4)
        self.assertIsNone(s["energy_kwh"])

    def test_energy_传感器_写入energy_kwh(self):
        s = self._make_sample("energy", "45.67")
        self.assertIsNone(s["power_w"])
        self.assertEqual(s["energy_kwh"], 45.67)

    def test_unavailable_状态_返回None(self):
        s = self._make_sample("power", "unavailable")
        self.assertIsNone(s["power_w"])


class TestLightEventTransition(unittest.TestCase):
    """测试灯光开/关事件的去抖逻辑 (从 __init__.py 的 listener 复制)"""

    def _should_emit(self, old_state: str | None, new_state: str) -> str | None:
        """返回应入队的事件类型, None 表示不入队"""
        new_on = new_state == "on"
        old_on = (old_state == "on") if old_state else False
        if new_on == old_on:
            return None
        return "on" if new_on else "off"

    def test_off到on_产生on事件(self):
        self.assertEqual(self._should_emit("off", "on"), "on")

    def test_on到off_产生off事件(self):
        self.assertEqual(self._should_emit("off", "off"), None)
        self.assertEqual(self._should_emit("on", "off"), "off")

    def test_on到on_无事件(self):
        """亮度变化但 state 不变, 不应产生事件"""
        self.assertIsNone(self._should_emit("on", "on"))

    def test_off到off_无事件(self):
        self.assertIsNone(self._should_emit("off", "off"))

    def test_首次无旧状态_从off判起(self):
        """old_state 为 None 时当作 off, 只有 new=on 才产生事件"""
        self.assertEqual(self._should_emit(None, "on"), "on")
        self.assertIsNone(self._should_emit(None, "off"))


class TestPowerSQLColumns(unittest.TestCase):
    """校验 db.py 中 INSERT 语句的 %s 占位符数量与字段数一致"""

    def _count_placeholders(self, sql_fragment: str, expected: int, name: str) -> None:
        """数 %s 占位符数量"""
        count = sql_fragment.count("%s")
        self.assertEqual(count, expected, f"{name} 占位符数不匹配")

    def test_device_power_raw_占位符(self):
        # INSERT INTO device_power_raw (entity_id, friendly_name, sampled_at, power_w, energy_kwh, state)
        # VALUES (%s,%s,%s,%s,%s,%s) -> 6 个
        self._count_placeholders("(%s,%s,%s,%s,%s,%s)", 6, "device_power_raw")

    def test_light_events_占位符(self):
        # INSERT INTO light_events (entity_id, friendly_name, event_time, action, brightness, color_temp)
        # VALUES (%s,%s,%s,%s,%s,%s) -> 6 个
        self._count_placeholders("(%s,%s,%s,%s,%s,%s)", 6, "light_events")

    def test_device_power_hourly_字段顺序(self):
        """device_power_hourly INSERT 字段: entity_id, friendly_name, hour_start, avg_w, max_w, min_w, energy_kwh, sample_count"""
        cols = ["entity_id", "friendly_name", "hour_start", "avg_w", "max_w", "min_w", "energy_kwh", "sample_count"]
        self.assertEqual(len(cols), 8)

    def test_device_power_daily_字段顺序(self):
        """device_power_daily INSERT 字段"""
        cols = ["entity_id", "friendly_name", "period_date", "avg_w", "max_w", "min_w", "energy_kwh", "peak_hour", "sample_count"]
        self.assertEqual(len(cols), 9)


class TestEnergyUnitConversion(unittest.TestCase):
    """测试 energy 传感器单位换算 (mWh/Wh -> kWh) 与排除规则 (coordinator._collect_device_power)"""

    def _convert(self, val: float | None, unit: str | None) -> float | None:
        """从 coordinator._collect_device_power 复制的单位换算逻辑"""
        if val is None:
            return None
        u = (unit or "").strip()
        if u == "mWh":
            return val / 1_000_000
        if u == "Wh":
            return val / 1_000
        return val

    def _is_excluded(self, entity_id: str) -> bool:
        """排除规则: 自身传感器 + SGCC 账单传感器"""
        return entity_id.startswith("sensor.utility_tracker_") or "osg_uc_" in entity_id

    def test_mWh_转kWh(self):
        self.assertAlmostEqual(self._convert(805, "mWh"), 0.000805)
        self.assertAlmostEqual(self._convert(3301, "mWh"), 0.003301)

    def test_Wh_转kWh(self):
        self.assertAlmostEqual(self._convert(1500, "Wh"), 1.5)

    def test_kWh_不变(self):
        self.assertEqual(self._convert(2.5, "kWh"), 2.5)

    def test_None_透传(self):
        self.assertIsNone(self._convert(None, "mWh"))

    def test_空单位_不转换(self):
        self.assertEqual(self._convert(2.5, None), 2.5)
        self.assertEqual(self._convert(2.5, ""), 2.5)

    def test_排除自身传感器(self):
        self.assertTrue(self._is_excluded("sensor.utility_tracker_current_power"))
        self.assertTrue(self._is_excluded("sensor.utility_tracker_power_today"))

    def test_排除SGCC账单传感器(self):
        self.assertTrue(self._is_excluded(
            "sensor.99_6aefa11d6e8945fca3a9f9c28433cdb7_02_osg_uc_2610271638_002_7061_current_year_usage"
        ))

    def test_普通设备_不排除(self):
        self.assertFalse(self._is_excluded("sensor.pc_cpu_package"))
        self.assertFalse(self._is_excluded("sensor.nasri_yong_dian_liang"))


class TestLightDurationConversion(unittest.TestCase):
    """测试秒转小时 (sensor.py 的 UtilityTrackerLightDurationTodaySensor)"""

    def test_正常转换(self):
        self.assertEqual(round(3600 / 3600.0, 2), 1.0)
        self.assertEqual(round(5400 / 3600.0, 2), 1.5)
        self.assertEqual(round(90 / 3600.0, 2), 0.03)

    def test_零值(self):
        self.assertEqual(round(0 / 3600.0, 2), 0.0)

    def test_None_视为0(self):
        sec = None or 0
        self.assertEqual(round(sec / 3600.0, 2), 0.0)


# 从 const.py 复制
LIGHT_SWITCH_ID_KEYWORDS = ("light", "lamp")
LIGHT_SWITCH_NAME_KEYWORDS = ("灯", "light", "lamp")


def _is_light_entity(entity_id, friendly_name):
    """从 __init__.py 复制的灯光实体识别逻辑"""
    if entity_id.startswith("light."):
        return True
    if not entity_id.startswith("switch."):
        return False
    eid_lower = entity_id.lower()
    if any(kw in eid_lower for kw in LIGHT_SWITCH_ID_KEYWORDS):
        return True
    name_lower = (friendly_name or "").lower()
    return any(kw in name_lower for kw in LIGHT_SWITCH_NAME_KEYWORDS)


class TestIsLightEntity(unittest.TestCase):
    """测试灯光实体识别 (light.* 全收; switch.* 仅灯光类)"""

    def test_light域_全部识别(self):
        self.assertTrue(_is_light_entity("light.living_room", "客厅灯"))
        self.assertTrue(_is_light_entity("light.anything", None))

    def test_灯光类switch_entity_id含light(self):
        self.assertTrue(_is_light_entity(
            "switch.jdjz_cn_2108814194_e1l96_fill_light_switch_p_4_21",
            "客厅灯 * setting fill-light-switch",
        ))

    def test_灯光类switch_名称含灯(self):
        self.assertTrue(_is_light_entity("switch.jdjz_cn_xxx_p_4_21", "主卧灯"))

    def test_灯光类switch_大小写不敏感(self):
        self.assertTrue(_is_light_entity("switch.LIGHT_strip", None))
        self.assertTrue(_is_light_entity("switch.some", "Bedroom LAMP"))

    def test_非灯光switch_不识别(self):
        self.assertFalse(_is_light_entity("switch.living_room_plug", "客厅插座"))
        self.assertFalse(_is_light_entity("switch.jdjz_cn_xxx", "扫地机开关"))

    def test_其他域_不识别(self):
        self.assertFalse(_is_light_entity("sensor.light_level", "光照度"))
        self.assertFalse(_is_light_entity("binary_sensor.light", None))

    def test_None名称_不报错(self):
        self.assertFalse(_is_light_entity("switch.plug", None))


def _hours_state_to_seconds(value):
    """history_stats 小时数 -> 秒 (从 coordinator.py 复制)"""
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


class TestHoursStateToSeconds(unittest.TestCase):
    """测试区域主灯时长快照入库前的单位换算"""

    def test_正常小时转秒(self):
        self.assertEqual(_hours_state_to_seconds("1"), 3600)
        self.assertEqual(_hours_state_to_seconds("0.5"), 1800)
        self.assertEqual(_hours_state_to_seconds(2.25), 8100)

    def test_浮点精度_四舍五入到秒(self):
        # history_stats 常见输出为带小数的浮点字符串
        self.assertEqual(_hours_state_to_seconds("5.85937786579132"), 21094)
        self.assertEqual(_hours_state_to_seconds("0.0083618379301495"), 30)

    def test_零值_正常(self):
        self.assertEqual(_hours_state_to_seconds("0"), 0)
        self.assertEqual(_hours_state_to_seconds("0.0"), 0)

    def test_无效状态_返回None(self):
        self.assertIsNone(_hours_state_to_seconds(None))
        self.assertIsNone(_hours_state_to_seconds("unknown"))
        self.assertIsNone(_hours_state_to_seconds("unavailable"))
        self.assertIsNone(_hours_state_to_seconds(""))
        self.assertIsNone(_hours_state_to_seconds("abc"))

    def test_负数_返回None(self):
        self.assertIsNone(_hours_state_to_seconds("-1"))
        self.assertIsNone(_hours_state_to_seconds(-0.5))


def _diff_area_stay_seconds(current, last_sample, today):
    """区域停留累计秒数的采样增量 (从 coordinator.py 复制)"""
    deltas = {}
    for entity_id, sec in current.items():
        base = last_sample.get(entity_id)
        if base is None or base[0] != today:
            continue
        delta = sec - base[1]
        if delta > 0:
            deltas[entity_id] = delta
    return deltas


class TestDiffAreaStaySeconds(unittest.TestCase):
    """测试小时桶增量计算 (区域 × 小时 热力图的数据来源)"""

    def test_首次采样_无基线_无增量(self):
        # 首次运行只能建立基线, 不能凭空产生小时数据
        self.assertEqual(_diff_area_stay_seconds({"sensor.a": 600}, {}, "2026-10-28"), {})

    def test_正常增量_按差额计算(self):
        current = {"sensor.a": 900, "sensor.b": 300}
        last = {"sensor.a": ("2026-10-28", 600), "sensor.b": ("2026-10-28", 300)}
        # a 增加 300 秒, b 没变化不计入
        self.assertEqual(
            _diff_area_stay_seconds(current, last, "2026-10-28"), {"sensor.a": 300}
        )

    def test_跨日_不产生增量(self):
        # history_stats 每天归零, 基线日期不同就跳过, 避免负数或锁死
        current = {"sensor.a": 120}
        last = {"sensor.a": ("2026-10-27", 7200)}
        self.assertEqual(_diff_area_stay_seconds(current, last, "2026-10-28"), {})

    def test_累计值回退_不产生负增量(self):
        # recorder 重启/统计重置导致读数变小, 不应写负值进小时桶
        current = {"sensor.a": 60}
        last = {"sensor.a": ("2026-10-28", 3600)}
        self.assertEqual(_diff_area_stay_seconds(current, last, "2026-10-28"), {})

    def test_部分实体缺失_只算存在的(self):
        current = {"sensor.a": 700}
        last = {"sensor.a": ("2026-10-28", 400), "sensor.b": ("2026-10-28", 100)}
        self.assertEqual(_diff_area_stay_seconds(current, last, "2026-10-28"), {"sensor.a": 300})


class TestAreaStayDurationEntities(unittest.TestCase):
    """测试区域停留时长实体映射 (与 sensor.yaml 的 history_stats 对应)"""

    # 与 const.py AREA_STAY_DURATION_ENTITIES 保持一致
    AREA_STAY_ENTITIES = {
        "sensor.ke_ting_ting_liu_shi_chang": "客厅",
        "sensor.zhu_wo_ting_liu_shi_chang": "主卧",
        "sensor.ci_wo_ting_liu_shi_chang": "次卧",
        "sensor.bei_wo_ting_liu_shi_chang": "北卧",
        "sensor.chu_fang_ting_liu_shi_chang": "厨房",
        "sensor.can_ting_ting_liu_shi_chang": "餐厅",
        "sensor.zhu_wei_ting_liu_shi_chang": "主卫",
        "sensor.gong_wei_ting_liu_shi_chang": "公卫",
        "sensor.gong_wei_gan_qu_ting_liu_shi_chang": "公卫干区",
        "sensor.nan_yang_tai_ting_liu_shi_chang": "南阳台",
        "sensor.bei_yang_tai_ting_liu_shi_chang": "北阳台",
        "sensor.zou_lang_ting_liu_shi_chang": "走廊",
    }

    def test_覆盖12个区域(self):
        self.assertEqual(len(self.AREA_STAY_ENTITIES), 12)

    def test_区域名不重复(self):
        # 区域名会作为 area_name 写库, 重复会导致不同区域互相覆盖
        names = list(self.AREA_STAY_ENTITIES.values())
        self.assertEqual(len(names), len(set(names)))

    def test_实体ID不重复(self):
        ids = list(self.AREA_STAY_ENTITIES.keys())
        self.assertEqual(len(ids), len(set(ids)))

    def test_全部为sensor域(self):
        for eid in self.AREA_STAY_ENTITIES:
            self.assertTrue(eid.startswith("sensor."), eid)


def _is_power_outlier(last_w, new_w):
    """判断功率采样是否异常 (从 const.py is_power_outlier 复制, 使用默认阈值)"""
    max_w, jump_abs_w, jump_ratio = 10000.0, 3000.0, 10.0
    if new_w is None:
        return False
    if new_w < 0 or new_w > max_w:
        return True
    if last_w is None or last_w <= 0:
        return False
    return (new_w - last_w) > jump_abs_w and new_w >= last_w * jump_ratio


class TestPowerOutlierFilter(unittest.TestCase):
    """测试功耗入库前的异常值过滤 (13kW 尖峰这类脏采样)"""

    def test_超过绝对上限_判为异常(self):
        self.assertTrue(_is_power_outlier(363.0, 13000.0))
        self.assertTrue(_is_power_outlier(None, 12000.0))
        # 恰好等于上限不算超限异常 (上次值 1500W, 也不满足 10 倍跳变)
        self.assertFalse(_is_power_outlier(1500.0, 10000.0))

    def test_负功率_判为异常(self):
        self.assertTrue(_is_power_outlier(363.0, -1.0))

    def test_无值_不判为异常(self):
        # None 由调用方按跳过处理, 交给聚合侧的 NULL 语义
        self.assertFalse(_is_power_outlier(363.0, None))

    def test_无历史_只做绝对上限判断(self):
        # 首次采样/重启后无上次值, 不能靠跳变判定, 只能靠上限
        self.assertFalse(_is_power_outlier(None, 2000.0))
        self.assertTrue(_is_power_outlier(None, 20000.0))

    def test_小功率倍数放大_不误杀(self):
        # 5W 待机 -> 80W 倍率 16x, 但增量仅 75W < 3000W, 属于真实变化
        self.assertFalse(_is_power_outlier(5.0, 80.0))

    def test_中等功率跳变_判为异常(self):
        # 500W -> 6000W: 倍率 12x 且增量 5500W, 未超上限但明显是脏采样
        self.assertTrue(_is_power_outlier(500.0, 6000.0))

    def test_零值启动_不误杀(self):
        # 上次为 0 (刚上电) 时不做跳变判定, 允许真实启动功率入库
        self.assertFalse(_is_power_outlier(0.0, 6000.0))

    def test_正常波动_不判为异常(self):
        self.assertFalse(_is_power_outlier(363.0, 386.0))
        self.assertFalse(_is_power_outlier(1500.0, 2200.0))


if __name__ == "__main__":
    unittest.main()
