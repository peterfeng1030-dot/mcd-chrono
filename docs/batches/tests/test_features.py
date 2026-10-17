"""T1-T10 特征层单元断言（设计 §9 test_features）。

直接构造订单字典，不走 fixture 生成器。日期均选好星期：
工作日 = 周二/周三（2026-10-13/14），周末 = 周六/周日（2026-10-17/18）。
运行：python docs/batches/tests/run_all.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import features  # noqa: E402

TUE = "2026-10-13"   # 周二
WED = "2026-10-14"   # 周三
SAT = "2026-10-17"   # 周六
SUN = "2026-10-18"   # 周日


def order(time: str, **kw) -> dict:
    o = {"order_time": time, "order_type": "到店取餐", "store_name": "测试门店", "items": []}
    o.update(kw)
    return o


class TestParseTime(unittest.TestCase):
    def test_formats(self):
        self.assertIsNotNone(features.parse_time("2026-10-13 08:30"))
        self.assertIsNotNone(features.parse_time("2026-10-13 08:30:45"))
        self.assertIsNotNone(features.parse_time("2026/10/13 08:30"))
        self.assertIsNotNone(features.parse_time("2026-10-13T08:30:45"))
        self.assertIsNone(features.parse_time(""))
        self.assertIsNone(features.parse_time("garbage"))
        self.assertIsNone(features.parse_time(None))


class TestSlots(unittest.TestCase):
    """窗口边界（设计 §3.1）：20:59→晚、21:00→夜、04:59→夜、05:00→早、09:59/10:00、13:59/14:00、16:59/17:00。"""

    def test_slot_boundaries(self):
        cases = {
            "04:59": "夜", "05:00": "早", "09:59": "早", "10:00": "午",
            "13:59": "午", "14:00": "下午茶", "16:59": "下午茶", "17:00": "晚",
            "20:59": "晚", "21:00": "夜", "23:59": "夜", "00:00": "夜",
        }
        for hhmm, expect in cases.items():
            self.assertEqual(
                features.slot_of_minute(int(hhmm[:2]) * 60 + int(hhmm[3:])),
                expect,
                hhmm,
            )


class TestT9Circular(unittest.TestCase):
    """T9 环形 RMS（设计 §3.2）。"""

    def test_same_moment_zero(self):
        self.assertEqual(features.circular_rms([750, 750, 750]), 0.0)

    def test_across_midnight(self):
        # 23:59 与 00:01 → μ=0:00、d=1 → T9=1.0（普通标准差会算出 ≈11.9 小时）
        self.assertAlmostEqual(features.circular_rms([1439, 1]), 1.0)

    def test_uniform_near_415_7(self):
        # 全天近似均匀（97 个等距点）→ ≈415.7
        pts = [int(i * 1440 / 97) % 1440 for i in range(97)]
        self.assertAlmostEqual(features.circular_rms(pts), 415.7, delta=0.05)

    def test_near_uniform_exact_415_7(self):
        # R < 1e-9（近均匀，均值方向数值上不可定）→ 直接取均匀分布理论值
        # 1440 个整分点两两相消 → C=S=0
        pts = list(range(1440))
        self.assertEqual(features.circular_rms(pts), 415.7)

    def test_n_lt_2_none(self):
        self.assertIsNone(features.circular_rms([100]))
        self.assertIsNone(features.circular_rms([]))


class TestT2LunchWindow(unittest.TestCase):
    """T2 窗 [660,780) 左闭右开（设计 §3.3 T2 行）。"""

    def test_boundaries(self):
        # 4 单工作日：10:59 出窗、11:00 入窗、12:59 入窗、13:00 出窗 → T2 = 2/4
        orders = [
            order(f"{TUE} 10:59"), order(f"{TUE} 11:00"),
            order(f"{WED} 12:59"), order(f"{WED} 13:00"),
        ]
        f = features.extract(orders)
        self.assertEqual(f["n_timevalid"], 4)
        self.assertAlmostEqual(f["t2"], 0.5)

    def test_weekend_not_counted(self):
        # 周末 11:00 不计入分子也不计入分母（分母 = 工作日订单）
        orders = [order(f"{SAT} 11:00"), order(f"{TUE} 09:00")]
        f = features.extract(orders)
        self.assertAlmostEqual(f["t2"], 0.0)


class TestT3BreakfastWindow(unittest.TestCase):
    """T3 窗 [330,570)（设计 §3.3 T3 行）。"""

    def test_boundaries(self):
        orders = [
            order(f"{TUE} 05:29"), order(f"{TUE} 05:30"),
            order(f"{TUE} 09:29"), order(f"{TUE} 09:30"),
            order(f"{TUE} 12:00"),
        ]
        f = features.extract(orders)
        self.assertAlmostEqual(f["t3_ratio"], 2 / 5)   # 05:30、09:29 入窗

    def test_t3_std_weekday_only_lt2_none(self):
        # 窗内工作日单 < 2 → t3_std = None
        orders = [order(f"{SAT} 08:00"), order(f"{TUE} 08:30"), order(f"{TUE} 15:00")]
        f = features.extract(orders)
        self.assertIsNone(f["t3_std"])

    def test_t3_std_weekday(self):
        # 窗内工作日单 ≥2 → 可算
        orders = [order(f"{TUE} 08:00"), order(f"{WED} 08:30"), order(f"{SAT} 08:10")]
        f = features.extract(orders)
        self.assertIsNotNone(f["t3_std"])


class TestNightWindowUnion(unittest.TestCase):
    """夜宵跨零点双尾并集（设计 §3.1）。"""

    def test_two_tails_one_slot(self):
        orders = [order(f"{TUE} 23:00"), order(f"{WED} 01:00")]
        f = features.extract(orders)
        self.assertAlmostEqual(f["t1"]["夜"], 1.0)
        self.assertAlmostEqual(f["t4"], 1.0)

    def test_weekend_early_morning_stays_weekend(self):
        # 周日凌晨单算周末（自然日期不改，设计 §3）
        orders = [order(f"{SAT} 23:00"), order(f"{SUN} 01:00")]
        f = features.extract(orders)
        self.assertAlmostEqual(f["t5"], 1.0)
        self.assertAlmostEqual(f["t4"], 1.0)


class TestT6Delivery(unittest.TestCase):
    def test_substring_match(self):
        orders = [
            order(f"{TUE} 12:00", order_type="麦乐送"),
            order(f"{TUE} 12:00", order_type="到店取餐"),
            order(f"{TUE} 12:00", order_type=""),
            order(f"{TUE} 12:00"),
        ]
        f = features.extract(orders)
        self.assertAlmostEqual(f["t6"], 0.25)

    def test_empty_orders_t6_zero(self):
        self.assertEqual(features.extract([])["t6"], 0.0)


class TestT7Aggregation(unittest.TestCase):
    def test_amount_aggregation(self):
        items = [
            {"name": "巨无霸", "amount": 30.0},
            {"name": "巨无霸", "amount": 30.0},
            {"name": "薯条", "amount": 15.0},
        ]
        f = features.extract([order(f"{TUE} 12:00", items=items)])
        self.assertAlmostEqual(f["t7"], 60 / 75)
        self.assertEqual(f["meta"]["top_item"], "巨无霸")

    def test_no_items_none(self):
        f = features.extract([order(f"{TUE} 12:00", items=[])])
        self.assertIsNone(f["t7"])

    def test_zero_amounts_none(self):
        items = [{"name": "A", "amount": 0}, {"name": "B", "amount": None}]
        f = features.extract([order(f"{TUE} 12:00", items=items)])
        self.assertIsNone(f["t7"])


class TestT8ActiveMonths(unittest.TestCase):
    """T8 = n / 有单自然月数（YYYY-MM 去重，下限 1），不按跨度/30.44（设计 §11.3）。"""

    def test_month_dedup_floor_one(self):
        # 3 单全在同一个月 → active_months 下限 1 → T8 = 3
        orders = [order(f"{TUE} 12:00"), order(f"{WED} 13:00"), order("2026-10-20 18:00")]
        f = features.extract(orders)
        self.assertEqual(f["meta"]["active_months"], 1)
        self.assertAlmostEqual(f["t8"], 3.0)

    def test_span_over_30_not_inflate(self):
        # 2 单跨 60 天但都在 2 个自然月 → T8 = 1.0（span/30.44 口径会得 ≈0.99 → 虚高月数）
        orders = [order("2026-01-05 12:00"), order("2026-02-10 12:00")]
        f = features.extract(orders)
        self.assertEqual(f["meta"]["active_months"], 2)
        self.assertAlmostEqual(f["t8"], 1.0)

    def test_all_unparseable_t8_equals_n(self):
        # 不可解析的单不计入月份，active_months=0 按下限取 1 → T8 = n（设计 §7）
        orders = [order("bad"), order("bad2"), order("bad3"), order("bad4"), order("bad5")]
        f = features.extract(orders)
        self.assertEqual(f["n"], 5)
        self.assertEqual(f["n_timevalid"], 0)
        self.assertAlmostEqual(f["t8"], 5.0)
        self.assertEqual(f["meta"]["span_days"], 0)


class TestT10Loyalty(unittest.TestCase):
    def test_single_store(self):
        orders = [order(f"{TUE} 12:00")] * 5
        f = features.extract(orders)
        self.assertAlmostEqual(f["t10"], 1.0)

    def test_all_empty_store_names_zero(self):
        orders = [order(f"{TUE} 12:00", store_name="")] * 5
        f = features.extract(orders)
        self.assertEqual(f["t10"], 0.0)
        self.assertIsNone(f["meta"]["top_store"])


class TestNTimevalidShrinkage(unittest.TestCase):
    """不可解析时间的单：计入 n、不计入 n_timevalid（设计 §7）。"""

    def test_mixed(self):
        orders = [
            order(f"{TUE} 08:00"), order("bad"), order(f"{WED} 09:00"), order(""),
        ]
        f = features.extract(orders)
        self.assertEqual(f["n"], 4)
        self.assertEqual(f["n_timevalid"], 2)
        self.assertAlmostEqual(f["t1"]["早"], 1.0)


class TestMetaSpanDays(unittest.TestCase):
    def test_span(self):
        orders = [order("2026-01-05 12:00"), order("2026-02-10 12:00")]
        f = features.extract(orders)
        self.assertEqual(f["meta"]["span_days"], 36)

    def test_no_valid_time_span_zero(self):
        orders = [order("bad")] * 3
        f = features.extract(orders)
        self.assertEqual(f["meta"]["span_days"], 0)


if __name__ == "__main__":
    unittest.main()
