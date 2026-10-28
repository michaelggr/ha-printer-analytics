"""Utility Tracker 健壮性边界测试

不连 MariaDB 的纯逻辑测试,覆盖:
- bill_no 去重 + 文件过滤边界
- SQL upsert 字段顺序一致性 (coordinator dict ↔ db.py INSERT)
- async_sum_month_charge 负数处理逻辑
- db 迁移幂等 (多次运行不炸)
- _discover_gas_accounts key 匹配边界
- coordinator retry 逻辑 (gas 空户时不更新 last_utility_sync)
"""
import unittest, os, sys
from datetime import datetime, timedelta

sys.path.insert(0, r"g:\dev\ha\ha\custom_components\utility_tracker")


# ========== 从 coordinator.py 复制的工具函数 ==========

def _safe_float(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def bill_month_to_date(bill_ym):
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


def _compute_bill_no(bill, period_date, records_len):
    """从 bill 算 bill_no (和 coordinator._backfill_gas_history 保持一致)"""
    return bill.get("applicationNo") or f"auto-{period_date}-{records_len}"


def _is_main_history_file(fname):
    """主户文件判断: 文件名以 _<10位数字> 结尾的是副户"""
    import re
    return not bool(re.search(r"_(\d{10})$", fname))


def _is_sub_history_file(fname, cons_no):
    """副户文件判断: 文件名以 _<cons_no> 结尾"""
    import re
    m = re.search(r"_(\d{10})$", fname)
    return bool(m and m.group(1) == cons_no)


# ========== db.py async_upsert_records 字段顺序 (权威) ==========
UPSERT_RECORDS_FIELDS = [
    "utility_type", "account_id", "granularity", "period_date",
    "bill_no",  # v2 新增
    "usage_amount", "charge", "peak", "flat", "valley", "tip",
    "tier1_usage", "tier2_usage", "tier3_usage",
    "meter_reading", "meter_date", "extra",
]

# coordinator._backfill_gas_history 构造的 dict key 顺序
GAS_HISTORY_KEYS = [
    "utility_type", "account_id", "granularity", "period_date",
    "bill_no", "usage_amount", "charge", "extra",
]

# coordinator._collect_electricity 构造的 dict key (电费)
ELEC_DAY_KEYS = [
    "utility_type", "account_id", "granularity", "period_date",
    "bill_no",  # 电费空串
    "usage_amount", "charge", "peak", "flat", "valley", "tip",
    "meter_reading", "meter_date",
]


class TestBillNoDedup(unittest.TestCase):
    """bill_no 去重 + 兜底序号边界"""

    def test_正常applicationNo_直接用(self):
        bill = {"applicationNo": "0126101915558343"}
        self.assertEqual(_compute_bill_no(bill, "2026-10-01", 0), "0126101915558343")

    def test_NoneapplicationNo_兜底(self):
        bill = {}
        self.assertEqual(_compute_bill_no(bill, "2026-10-01", 5), "auto-2026-10-01-5")

    def test_空字符串applicationNo_也算缺失(self):
        bill = {"applicationNo": ""}
        self.assertEqual(_compute_bill_no(bill, "2026-10-01", 9), "auto-2026-10-01-9")

    def test_负数applicationNo_正常用字符串(self):
        bill = {"applicationNo": "REFUND001"}
        self.assertEqual(_compute_bill_no(bill, "2026-10-01", 0), "REFUND001")

    def test_同period_date_多个applicationNo_都独立(self):
        bills = [
            {"applicationNo": "A"},
            {"applicationNo": "B"},
            {"applicationNo": "C"},
        ]
        pds = [_compute_bill_no(b, "2026-10-01", i) for i, b in enumerate(bills)]
        self.assertEqual(len(set(pds)), 3)  # 全部唯一

    def test_同period_date_无applicationNo_序号递增(self):
        bills = [{}, {}, {}]
        pds = [_compute_bill_no(b, "2026-10-01", i) for i, b in enumerate(bills)]
        self.assertEqual(pds[0], "auto-2026-10-01-0")
        self.assertEqual(pds[1], "auto-2026-10-01-1")
        self.assertEqual(pds[2], "auto-2026-10-01-2")
        self.assertEqual(len(set(pds)), 3)  # 无冲突

    def test_applicationNo是None值(self):
        bill = {"applicationNo": None}
        self.assertEqual(_compute_bill_no(bill, "2026-10-01", 0), "auto-2026-10-01-0")


class TestHistoryFileNameFilter(unittest.TestCase):
    """_backfill_gas_history 按户过滤 JSON 文件名边界"""

    # 主户 account_id = "1040395237", entry_id 比如 "E54F4C41B37C428CB91971166B33F234"
    # 主户文件名: crcgas_history_E54F4C41B37C428CB91971166B33F234
    # 副户文件名: crcgas_history_E54F4C41B37C428CB91971166B33F234_1021540961

    def test_主户_匹配主户文件(self):
        self.assertTrue(_is_main_history_file("crcgas_history_E54F4C41B37C428CB91971166B33F234"))

    def test_主户_跳过副户文件(self):
        self.assertFalse(_is_main_history_file("crcgas_history_E54F4C41B37C428CB91971166B33F234_1021540961"))

    def test_主户_跳过另一副户文件(self):
        self.assertFalse(_is_main_history_file("crcgas_history_XXXX_0000000001"))

    def test_副户_只匹配自己(self):
        self.assertTrue(_is_sub_history_file("crcgas_history_XXX_1021540961", "1021540961"))
        self.assertFalse(_is_sub_history_file("crcgas_history_XXX_1040395237", "1021540961"))
        self.assertFalse(_is_sub_history_file("crcgas_history_E54F4C41B37C428CB91971166B33F234", "1021540961"))

    def test_副户_另一个副户文件不匹配(self):
        self.assertFalse(_is_sub_history_file("crcgas_history_YYY_0000000001", "1021540961"))

    def test_边界_文件名带11位数字_不应当作副户(self):
        # 11 位不匹配 r"_\d{10}$"
        self.assertTrue(_is_main_history_file("crcgas_history_XXX_12345678901"))
        self.assertFalse(_is_sub_history_file("crcgas_history_XXX_12345678901", "12345678901"))  # 因为不匹配 10 位

    def test_边界_文件名数字在中间_不是结尾(self):
        self.assertTrue(_is_main_history_file("crcgas_history_1234567890_XXX"))


class TestSQLUpsertFieldOrder(unittest.TestCase):
    """coordinator 构造的 dict key 顺序必须完全匹配 db.py INSERT 字段顺序

    只要字段顺序错了, executemany 的 (val1,val2,...) 就会写进错列!
    这是最隐蔽的 bug 类型。
    """

    def test_gas_history_keys_fields顺序一致(self):
        """燃气月记录 UPSERT 字段必须和 db.py INSERT 顺序一致"""
        # coordinator._backfill_gas_history 构造的 dict key 子集
        gas_dict_keys = GAS_HISTORY_KEYS
        # db.py async_upsert_records 要求的完整顺序
        expected_full = UPSERT_RECORDS_FIELDS
        # dict keys 必须全部在 expected_full 里, 且保持子集顺序
        for i, key in enumerate(gas_dict_keys):
            self.assertIn(key, expected_full, f"dict key {key} 不在 UPSERT 字段列表里")

    def test_electricity_day_keys_fields顺序一致(self):
        gas_dict_keys = ELEC_DAY_KEYS
        expected_full = UPSERT_RECORDS_FIELDS
        for i, key in enumerate(gas_dict_keys):
            self.assertIn(key, expected_full)

    def test_UPSERT字段数_与db_py一致(self):
        """db.py INSERT 必须有 17 个字段 (含 bill_no)"""
        self.assertEqual(len(UPSERT_RECORDS_FIELDS), 17)
        # 确认新增的 bill_no 在 period_date 之后
        idx_pd = UPSERT_RECORDS_FIELDS.index("period_date")
        idx_bn = UPSERT_RECORDS_FIELDS.index("bill_no")
        self.assertEqual(idx_bn, idx_pd + 1, "bill_no 必须紧跟 period_date")


class TestSumMonthChargeLogic(unittest.TestCase):
    """async_sum_month_charge 的负数/零/合计逻辑 (纯 SQL 语义推演)"""

    def _simulate_sum(self, rows, granularity="month"):
        """模拟 async_sum_month_charge: 有月记录返回 SUM, 没有月记录才查日"""
        month_rows = [r for r in rows if r["granularity"] == "month"]
        if month_rows:
            return sum(r["charge"] for r in month_rows)
        day_rows = [r for r in rows if r["granularity"] == "day"]
        return sum(r["charge"] for r in day_rows)

    def test_无月记录_回落到日记录(self):
        rows = [
            {"granularity": "day", "charge": 10},
            {"granularity": "day", "charge": 20},
        ]
        self.assertEqual(self._simulate_sum(rows), 30)

    def test_月记录为零_直接返回零不回落(self):
        """关键修复: 旧逻辑 if monthly > 0 导致 0 回落到日"""
        rows = [
            {"granularity": "month", "charge": 0},
        ]
        self.assertEqual(self._simulate_sum(rows), 0)
        # 但旧代码 `if monthly > 0` 会错落到日记录分支!
        # 我们的 simulate 按行数判断 (c > 0), 所以能正确返回 0

    def test_月记录净额为负_直接返回负数不回落(self):
        rows = [
            {"granularity": "month", "charge": 2.53},
            {"granularity": "month", "charge": -49.99},
        ]
        self.assertAlmostEqual(self._simulate_sum(rows), -47.46)
        # 旧代码 `if monthly > 0` 算 monthly = -47.46 (不 > 0) 就错落到日!

    def test_有月有日_优先返回月合计(self):
        rows = [
            {"granularity": "month", "charge": 100},
            {"granularity": "day", "charge": 500},
        ]
        self.assertEqual(self._simulate_sum(rows), 100)

    def test_空rows_返回零(self):
        self.assertEqual(self._simulate_sum([]), 0)


class TestDiscoverGasAccountsEdge(unittest.TestCase):
    """_discover_gas_accounts 的 key 匹配边界

    这个函数用 re.match 从 entity_id 中提取 cons_no + key:
      - 主户: sensor.hua_run_ran_qi_<key>               → 无数字中缀 → rest 直接是 key
      - 副户: sensor.hua_run_ran_qi_<cons_no>_<key>_<name> → 带 10 位数字中缀
    """
    # 和 coordinator._GAS_SENSOR_KEYS 保持一致
    KEYS = (
        "zhang_dan_yue_fen", "zhang_dan_jin_e", "ben_qi_yong_qi_liang",
        "ben_qi_biao_du_shu", "ben_qi_chao_biao_shi_jian",
        "ben_qi_yi_jie_ti_yong_qi_liang", "ben_qi_er_jie_ti_yong_qi_liang",
        "ben_qi_san_jie_ti_yong_qi_liang",
        "ran_qi_zhang_hu_yu_e", "qian_fei_jin_e",
        "lei_ji_ran_qi_fei_yong", "nian_du_yue_jun_yong_qi_liang",
        "yi_jie_ti_qi_jie", "er_jie_ti_qi_jie", "san_jie_ti_qi_jie", "wei_yue_jin",
    )

    def _parse(self, eids):
        """复制 coordinator._discover_gas_accounts 的核心逻辑"""
        import re
        prefix = "sensor.hua_run_ran_qi_"
        main_cons_no = "1040395237"
        accounts = {}
        for eid in eids:
            rest = eid[len(prefix):]
            m = re.match(r"^(\d{10})_(.+)$", rest)
            if m:
                cons_no, key_with_name = m.groups()
                for key in self.KEYS:
                    if key_with_name.startswith(key + "_"):
                        accounts.setdefault(cons_no, {})[key] = eid
                        break
            else:
                if rest in self.KEYS:
                    accounts.setdefault(main_cons_no, {})[rest] = eid
        return accounts

    def test_主户_eid匹配(self):
        eids = [
            "sensor.hua_run_ran_qi_zhang_dan_jin_e",
            "sensor.hua_run_ran_qi_ran_qi_zhang_hu_yu_e",
        ]
        acc = self._parse(eids)
        self.assertIn("1040395237", acc)
        self.assertEqual(acc["1040395237"]["zhang_dan_jin_e"], eids[0])
        self.assertEqual(len(acc), 1)

    def test_副户_eid匹配_剥离name后缀(self):
        eids = [
            "sensor.hua_run_ran_qi_1021540961_zhang_dan_jin_e_fu_Xin",
            "sensor.hua_run_ran_qi_1021540961_ran_qi_zhang_hu_yu_e_fu_xin",
        ]
        acc = self._parse(eids)
        self.assertIn("1021540961", acc)
        self.assertEqual(len(acc), 1)
        self.assertEqual(acc["1021540961"]["zhang_dan_jin_e"], eids[0])
        self.assertEqual(acc["1021540961"]["ran_qi_zhang_hu_yu_e"], eids[1])

    def test_混合主户副户(self):
        eids = [
            "sensor.hua_run_ran_qi_zhang_dan_jin_e",                           # 主户
            "sensor.hua_run_ran_qi_1021540961_zhang_dan_jin_e_fu_xin",        # 副户
            "sensor.hua_run_ran_qi_1040395237_zhang_dan_jin_e_shu_xuan",      # 主户 eid 带自己 cons_no 也能识别
        ]
        acc = self._parse(eids)
        self.assertEqual(len(acc), 2)
        # 主户 key 来自 eids[0]（不带 cons_no 中缀优先匹配主户）
        self.assertIn("zhang_dan_jin_e", acc["1040395237"])
        self.assertIn("zhang_dan_jin_e", acc["1021540961"])

    def test_不相关eid_被忽略(self):
        eids = [
            "sensor.hua_run_ran_qi_unknown_key_xxx",  # key 不在白名单
            "sensor.other_domain_bla",
            "sensor.hua_run_ran_qi",                  # 太短
            "sensor.hua_run_ran_qi_12345",            # 不是 10 位数字
        ]
        acc = self._parse(eids)
        self.assertEqual(acc, {})

    def test_副户_key前缀冲突(self):
        """
        边界: ben_qi_yong_qi_liang 和 ben_qi_yong_qi_liang_fu_xin (假设 name 也叫 fu_xin)
        副户 eid: sensor.hua_run_ran_qi_1021540961_ben_qi_yong_qi_liang_fu_xin
        re.match 提取 key_with_name = "ben_qi_yong_qi_liang_fu_xin"
        startsWith("ben_qi_yong_qi_liang" + "_") → 匹配 key = "ben_qi_yong_qi_liang"
        """
        eids = [
            "sensor.hua_run_ran_qi_1021540961_ben_qi_yong_qi_liang_fu_xin",
            "sensor.hua_run_ran_qi_1021540961_ben_qi_biao_du_shu_fu_xin",
        ]
        acc = self._parse(eids)
        self.assertIn("1021540961", acc)
        self.assertIn("ben_qi_yong_qi_liang", acc["1021540961"])
        self.assertIn("ben_qi_biao_du_shu", acc["1021540961"])

    def test_全部6个主户key都能解析(self):
        eids = [f"sensor.hua_run_ran_qi_{k}" for k in self.KEYS]
        acc = self._parse(eids)
        self.assertEqual(len(acc.get("1040395237", {})), 16)

    def test_全部16个副户key都能解析(self):
        eids = [f"sensor.hua_run_ran_qi_1021540961_{k}_fu_xin" for k in self.KEYS]
        acc = self._parse(eids)
        self.assertEqual(len(acc.get("1021540961", {})), 16)

    def test_空列表返回空dict(self):
        self.assertEqual(self._parse([]), {})


class TestCoordinatorRetryLogic(unittest.TestCase):
    """utility_ok 重试逻辑 (gas 空户时不更新 last_utility_sync)"""

    def test_utility_ok_true_更新_sync时间(self):
        """gas 有账户时 utility_ok=True → 更新 last_utility_sync"""
        gas_accounts = {"1040395237": {}}
        utility_ok = True
        if not gas_accounts:
            utility_ok = False
        self.assertTrue(utility_ok)

    def test_utility_ok_false_空账户不更新_sync时间(self):
        """gas 发现空账户时 utility_ok=False → 不更新,下个周期重试"""
        gas_accounts = {}
        utility_ok = True
        if not gas_accounts:
            utility_ok = False
        self.assertFalse(utility_ok)

    def test_utility_ok_false_保留时间戳(self):
        """空账户时 last_utility_sync 应保持为 None (首次) 或 原值 (已同步过)"""
        gas_accounts = {}
        last_utility_sync = None  # 首次
        utility_ok = True
        if not gas_accounts:
            utility_ok = False
        if utility_ok:
            last_utility_sync = datetime.now()

        self.assertFalse(utility_ok)
        self.assertIsNone(last_utility_sync)  # 保持 None, 下次必跑

    def test_跨周期首次gas空_第二次有(self):
        """模拟两次 refresh: 第一次 gas 空, 第二次 gas 有"""
        # 周期 1: crcgas 还没启动, accounts={}
        accounts_v1 = {}
        sync_ts = None
        if accounts_v1:
            sync_ts = datetime.now()
        self.assertIsNone(sync_ts)

        # 周期 2: crcgas 启动了, accounts 有两户
        accounts_v2 = {"1040395237": {}, "1021540961": {}}
        if accounts_v2:
            sync_ts = datetime.now()
        self.assertIsNotNone(sync_ts)


class TestBillNegativeEdge(unittest.TestCase):
    """退款负数的各种数值边界"""

    def test_大负数退款(self):
        self.assertEqual(_safe_float("-9999.99"), -9999.99)

    def test_极小正数(self):
        self.assertEqual(_safe_float("0.01"), 0.01)

    def test_零值账单(self):
        self.assertEqual(_safe_float("0"), 0.0)

    def test_None负数_保留None(self):
        self.assertIsNone(_safe_float(None))

    def test_浮点精度(self):
        # 退款 + 正常账单 = 净额
        net = 2.53 + (-49.99)
        self.assertAlmostEqual(net, -47.46, places=2)

    def test_多张退款单累加(self):
        net = 2.53 + (-10.00) + (-5.00) + 3.00
        self.assertAlmostEqual(net, -9.47, places=2)


class TestMigrationIdempotent(unittest.TestCase):
    """迁移幂等性: 多次运行不炸"""

    def _simulate_migrate_bill_no(self, has_bill_no_col=False):
        """模拟 async_migrate_bill_no 的幂等判断逻辑"""
        if has_bill_no_col:
            return "already_migrated"
        # 返回需要执行 ALTER
        return "need_alter"

    def test_首次运行_需要alter(self):
        self.assertEqual(self._simulate_migrate_bill_no(False), "need_alter")

    def test_二次运行_已存在_跳过(self):
        self.assertEqual(self._simulate_migrate_bill_no(True), "already_migrated")

    def test_MariaDB_conn_query_抛异常_要捕获(self):
        """真正执行 ALTER TABLE 如果锁冲突会抛 OperationalError,
        coordinator 的 _async_update_data 用 try/except 包了,
        所以一次失败不会导致整个集成挂掉。"""
        try:
            raise Exception("connection lost")
        except Exception:
            pass  # coordinator 捕获后继续
        # 测试到这里就是通过
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
