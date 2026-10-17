"""八人格判定链单元断言（设计 §9 test_persona）。

A2 八人格覆盖：直接构造特征字典（不走生成器），精确控阈值。
运行：python docs/batches/tests/run_all.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import persona  # noqa: E402


def base_features(**over) -> dict:
    """全 False 底座：n=20，各特征给中性值，不碰任何阈值。"""
    f = {
        "n": 20, "n_timevalid": 20,
        "t1": {"早": 0.2, "午": 0.2, "下午茶": 0.2, "晚": 0.2, "夜": 0.2},
        "t2": 0.2, "t3_ratio": 0.1, "t3_std": 100.0,
        "t4": 0.1, "t5": 0.2, "t6": 0.2, "t7": 0.1,
        "t8": 5.0, "t9": 200.0, "t10": 0.3,
        "meta": {"span_days": 300, "active_months": 4, "first": "", "last": "",
                 "top_store": "店", "top_item": "品"},
    }
    f.update(over)
    return f


class TestAllEightPersonas(unittest.TestCase):
    """P1-P8 各 1 例正命中（设计 §10 A2）。"""

    def test_P1_nail(self):
        f = base_features(t7=0.40)
        self.assertEqual(persona.judge(f)["key"], "P1")

    def test_P2_night(self):
        f = base_features(t4=0.25)
        self.assertEqual(persona.judge(f)["key"], "P2")

    def test_P3_morning(self):
        f = base_features(t3_ratio=0.35, t3_std=44.9)
        self.assertEqual(persona.judge(f)["key"], "P3")

    def test_P4_punctual(self):
        f = base_features(t2=0.45, t9=74.9)
        self.assertEqual(persona.judge(f)["key"], "P4")

    def test_P5_homebody(self):
        f = base_features(t5=0.40, t6=0.50)
        self.assertEqual(persona.judge(f)["key"], "P5")

    def test_P6_tea(self):
        t1 = {"早": 0.1, "午": 0.2, "下午茶": 0.30, "晚": 0.2, "夜": 0.2}
        f = base_features(t1=t1)
        self.assertEqual(persona.judge(f)["key"], "P6")

    def test_P7_rare(self):
        f = base_features(t8=1.49)
        self.assertEqual(persona.judge(f)["key"], "P7")

    def test_P8_fallback(self):
        self.assertEqual(persona.judge(base_features())["key"], "P8")


class TestThresholdBoundaries(unittest.TestCase):
    """关键阈值边界（设计 §9）。"""

    def test_P2_at_threshold_hits(self):
        f = base_features(t4=0.25)
        self.assertEqual(persona.judge(f)["key"], "P2")   # 大于等于含等号

    def test_P2_below_threshold_misses(self):
        f = base_features(t4=0.2499)
        self.assertEqual(persona.judge(f)["key"], "P8")

    def test_P3_std_strict_below(self):
        # t3_std 需严格小于 45：等于 45 不命中
        f = base_features(t3_ratio=0.35, t3_std=45.0)
        self.assertEqual(persona.judge(f)["key"], "P8")
        # t3_ratio 需大于等于 0.35：0.3499 不命中
        f = base_features(t3_ratio=0.3499, t3_std=44.9)
        self.assertEqual(persona.judge(f)["key"], "P8")

    def test_P4_t9_strict_below(self):
        f = base_features(t2=0.45, t9=75.0)
        self.assertEqual(persona.judge(f)["key"], "P8")

    def test_P7_strict_below(self):
        f = base_features(t8=1.5)
        self.assertEqual(persona.judge(f)["key"], "P8")

    def test_P1_t7_at_threshold_hits(self):
        f = base_features(t7=0.40)
        self.assertEqual(persona.judge(f)["key"], "P1")

    def test_P5_at_thresholds(self):
        f = base_features(t5=0.40, t6=0.50)
        self.assertEqual(persona.judge(f)["key"], "P5")
        f = base_features(t5=0.3999, t6=0.50)
        self.assertEqual(persona.judge(f)["key"], "P8")


class TestPriorityChain(unittest.TestCase):
    """优先级链：命中即停（设计 §4.1）。"""

    def test_P1_over_P2(self):
        # P1 与 P2 同满足，取 P1
        f = base_features(t7=0.5, t4=0.5)
        self.assertEqual(persona.judge(f)["key"], "P1")

    def test_P2_over_P3(self):
        f = base_features(t4=0.3, t3_ratio=0.5, t3_std=20)
        self.assertEqual(persona.judge(f)["key"], "P2")

    def test_P4_over_P7(self):
        # P4 命中且 T8=1.49 也会触发 P7，取 P4
        f = base_features(t2=0.5, t9=50, t8=1.49)
        self.assertEqual(persona.judge(f)["key"], "P4")

    def test_P2_wins_over_P4_P5(self):
        f = base_features(t4=0.4, t2=0.6, t9=40, t5=0.5, t6=0.6)
        self.assertEqual(persona.judge(f)["key"], "P2")


class TestScantCard(unittest.TestCase):
    """n 小于 5 安慰卡（设计 §4.1 链前置）。"""

    def test_n4_scant(self):
        p = persona.judge(base_features(n=4))
        self.assertTrue(p["is_scant"])
        self.assertEqual(p["key"], "SCANT")

    def test_n5_enters_chain(self):
        p = persona.judge(base_features(n=5))
        self.assertFalse(p["is_scant"])
        self.assertEqual(p["key"], "P8")

    def test_n0_scant(self):
        self.assertTrue(persona.judge(base_features(n=0))["is_scant"])


class TestNoneSemantics(unittest.TestCase):
    """None 操作数判否，不猜零（设计 §2.2 / §4.1）。"""

    def test_t7_none_skips_P1_falls_to_P2(self):
        # T7=None（全部明细缺失），P1 判否，链继续 P2 起（设计 §7）
        f = base_features(t7=None, t4=0.3)
        self.assertEqual(persona.judge(f)["key"], "P2")

    def test_t7_none_falls_to_P8(self):
        f = base_features(t7=None)
        self.assertEqual(persona.judge(f)["key"], "P8")

    def test_all_time_features_none_only_t7_t8_t10(self):
        # n_timevalid=0：T1-T6/T9=None，仅 T7/T8/T10 可判（设计 §7）
        f = base_features(
            n=6, n_timevalid=0,
            t1=None, t2=None, t3_ratio=None, t3_std=None,
            t4=None, t5=None, t6=0.0, t9=None,
        )
        # T7=0.1、T8=5：P1-P6 全 None 判否，T8 不小于 1.5，落 P8
        self.assertEqual(persona.judge(f)["key"], "P8")

    def test_t4_none_not_zero(self):
        # t4=None 时 P2 判否（不把 None 当 0 参与比较）
        f = base_features(t4=None)
        self.assertEqual(persona.judge(f)["key"], "P8")

    def test_missing_key_judged_false(self):
        # 键缺失与 None 同效（f.get 返回 None 则判否）
        f = base_features()
        del f["t7"]
        self.assertEqual(persona.judge(f)["key"], "P8")


class TestOutputContract(unittest.TestCase):
    """人格字典结构（设计 §2.2）与 THRESHOLDS 完整性（设计 §4.1）。"""

    def test_keys(self):
        p = persona.judge(base_features())
        self.assertEqual(
            set(p.keys()), {"key", "title", "emoji", "desc", "verdict", "is_scant"}
        )
        self.assertIsInstance(p["desc"], list)
        self.assertTrue(2 <= len(p["desc"]) <= 3)

    def test_threshold_values(self):
        t = persona.THRESHOLDS
        self.assertEqual(
            set(t.keys()),
            {"scant_min", "t7_nail", "t4_night", "t3_ratio", "t3_std",
             "t2_punch", "t9_regular", "t5_weekend", "t6_delivery",
             "t1_tea", "t8_sparse"},
        )
        self.assertEqual(t["scant_min"], 5)
        self.assertEqual(t["t7_nail"], 0.40)
        self.assertEqual(t["t4_night"], 0.25)
        self.assertEqual(t["t3_ratio"], 0.35)
        self.assertEqual(t["t3_std"], 45.0)
        self.assertEqual(t["t2_punch"], 0.45)
        self.assertEqual(t["t9_regular"], 75.0)
        self.assertEqual(t["t5_weekend"], 0.40)
        self.assertEqual(t["t6_delivery"], 0.50)
        self.assertEqual(t["t1_tea"], 0.30)
        self.assertEqual(t["t8_sparse"], 1.5)

    def test_scant_card_shape(self):
        p = persona.judge(base_features(n=4))
        self.assertTrue(p["is_scant"])
        self.assertEqual(p["key"], "SCANT")


if __name__ == "__main__":
    unittest.main()
