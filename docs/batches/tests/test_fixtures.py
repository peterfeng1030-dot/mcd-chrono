"""八份样例与人格的对应关系（设计 §9 test_fixtures）。

这份断言不测"代码逻辑对不对"，测的是"样例还能不能讲出它该讲的那个故事"。
八份样例是靠时间分布、星期权重、外卖比例、菜单池一起压出来的，判定链又是
优先级 1→8 命中即停——只要改了任一阈值或任一 profile 参数，某份样例就可能
滑到上游人格去。这里让它在第一时间响。

运行：python docs/batches/tests/run_all.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import features  # noqa: E402
import persona  # noqa: E402
from fetch import DEMO_ALIASES, DEMO_PROFILES, load_demo  # noqa: E402


class TestFixturesHitPersona(unittest.TestCase):
    """每份样例稳定命中它对应的那个人格。"""

    def test_eight_samples_exist_and_are_nonempty(self):
        self.assertEqual(len(DEMO_PROFILES), 8)
        for key in DEMO_PROFILES:
            with self.subTest(sample=key):
                data = load_demo(key)
                # 低于 5 单会掉进安慰卡分支，就不再是"某个人格的样例"了
                self.assertGreaterEqual(len(data["orders"]), persona.THRESHOLDS["scant_min"])
                self.assertEqual(data["source"], "demo")
                self.assertTrue(data["orders"][0]["order_id"])

    def test_each_sample_hits_its_own_persona(self):
        for key in DEMO_PROFILES:
            with self.subTest(sample=key):
                f = features.extract(load_demo(key)["orders"])
                p = persona.judge(f)
                self.assertEqual(p["key"], key.upper(), f"{key} 应命中 {key.upper()}，实际 {p['key']} {p['title']}")

    def test_orders_sorted_by_time(self):
        for key in DEMO_PROFILES:
            with self.subTest(sample=key):
                times = [o["order_time"] for o in load_demo(key)["orders"]]
                self.assertEqual(times, sorted(times))

    def test_legacy_aliases_still_point_somewhere(self):
        """normal / heavy 是早期两个样例的旧名，仍应可用。"""
        self.assertEqual(DEMO_ALIASES["normal"], "p3")
        self.assertEqual(DEMO_ALIASES["heavy"], "p2")
        self.assertEqual(features.extract(load_demo("normal")["orders"])["n"],
                         features.extract(load_demo("p3")["orders"])["n"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
