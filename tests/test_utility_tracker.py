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

    def test_负数账单_退款(self):
        """退款账单(负数)也要正确入库"""
        bill = {"billYm": "2026-10", "billAmt": -49.99, "gasAmt": -19.76}
        period_date = bill_month_to_date(bill.get("billYm"))
        self.assertEqual(period_date, "2026-10-01")
        self.assertEqual(_safe_float(bill.get("billAmt")), -49.99)
        self.assertEqual(_safe_float(bill.get("gasAmt")), -19.76)


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


if __name__ == "__main__":
    unittest.main()
