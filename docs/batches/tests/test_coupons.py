"""券匹配单元断言（设计 §10）。

守三条线：
1. 匹配结果可复现（同输入同输出、稳定序）；
2. 没命中就空着，不硬凑；
3. **只读不写**——coupons.py 源码里不得出现任何领取/下单类工具名（合规红线，见模块 docstring）。
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import card  # noqa: E402
import coupons  # noqa: E402
import features  # noqa: E402
import persona  # noqa: E402

PERSONA_KEYS = ["P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "SCANT"]


def _pool() -> list[dict]:
    return coupons.load_demo()


class TestClassify(unittest.TestCase):
    def test_real_coupons(self):
        cases = {
            "巧克力味厚松饼猪柳蛋套餐": ["breakfast", "main"],
            "免费脆薯饼": ["snack", "free"],
            "人气麦旋风买一送一": ["dessert", "bogo"],
            "9.9元中杯冰美式": ["coffee", "discount"],
        }
        for name, expect in cases.items():
            tags = coupons.classify(name)
            for tag in expect:
                self.assertIn(tag, tags, f"{name} 应命中 {tag}，实际 {tags}")

    def test_unknown_name_is_empty(self):
        self.assertEqual(coupons.classify("神秘大礼包"), [])
        self.assertEqual(coupons.classify(""), [])

    def test_delivery_tag(self):
        self.assertIn("delivery", coupons.classify("麦乐送免配送费券"))


class TestRank(unittest.TestCase):
    def setUp(self):
        self.pool = _pool()

    def test_pool_loaded(self):
        self.assertEqual(len(self.pool), 4)
        self.assertTrue(all(c["name"] for c in self.pool))

    def test_every_persona_gets_at_least_one(self):
        for key in PERSONA_KEYS:
            recs = coupons.rank(key, self.pool)
            self.assertGreaterEqual(len(recs), 1, f"{key} 一张都没命中")
            self.assertLessEqual(len(recs), 3)
            self.assertTrue(recs[0]["note"], f"{key} 第一条缺单券说明")
            self.assertTrue(coupons.why_for(key), f"{key} 缺整块理由")
            self.assertTrue(coupons.why_for(key, {"t4": 0.5}), "带特征也应能格式化")

    def test_deterministic(self):
        a = coupons.rank("P3", self.pool)
        b = coupons.rank("P3", list(reversed(self.pool)))
        self.assertEqual([x["name"] for x in a], [x["name"] for x in b])

    def test_empty_pool(self):
        self.assertEqual(coupons.rank("P3", []), [])

    def test_no_hit_returns_empty(self):
        only_unknown = [{"name": "神秘大礼包", "label": "", "status": ""}]
        self.assertEqual(coupons.rank("P3", only_unknown), [])

    def test_matched_tags_intersect_persona_weights(self):
        for key in PERSONA_KEYS:
            weights = coupons.PERSONA_PREF[key]["weights"]
            for r in coupons.rank(key, self.pool):
                for tag in r["hit"]:
                    self.assertIn(tag, weights, f"{key} 出现了不该命中的标签 {tag}")

    def test_breakfast_first_for_morning_persona(self):
        self.assertIn("早餐", coupons.rank("P3", self.pool)[0]["matched"])

    def test_caution_never_empty(self):
        for key in PERSONA_KEYS:
            self.assertTrue(coupons.caution_for(key))


class TestNormalize(unittest.TestCase):
    def test_list_shape(self):
        got = coupons.normalize({"data": [{"couponName": "A", "couponStatus": "CAN_GET", "label": "可领取"}]})
        self.assertEqual(got, [{"name": "A", "status": "CAN_GET", "label": "可领取"}])

    def test_dict_shape(self):
        got = coupons.normalize({"data": {"coupons": [{"couponName": "B"}]}})
        self.assertEqual([x["name"] for x in got], ["B"])

    def test_garbage_is_empty(self):
        for bad in (None, {}, {"data": None}, {"data": "x"}, [], "str"):
            self.assertEqual(coupons.normalize(bad), [])

    def test_name_missing_skipped(self):
        self.assertEqual(coupons.normalize({"data": [{"couponStatus": "X"}, {"couponName": "C"}]}), [
            {"name": "C", "status": "", "label": ""}
        ])


class TestRender(unittest.TestCase):
    """卡片保持干净（只回答「我是谁」），券只出现在报告页。"""

    def _result(self) -> dict:
        d = __import__("json").load(
            open(ROOT / "fixtures" / "demo_orders_p3.json", encoding="utf-8")
        )
        f = features.extract(d["orders"])
        p = persona.judge(f)
        res = {"source": "demo", "features": f, "persona": p}
        res["coupons"] = coupons.rank(p["key"], _pool(), f)
        res["coupon_why"] = coupons.why_for(p["key"], f)
        res["coupon_caution"] = coupons.caution_for(p["key"])
        return res

    def test_card_has_no_coupon(self):
        html = card.render_card(self._result())
        for r in self._result()["coupons"]:
            self.assertNotIn(r["name"], html)

    def test_report_has_coupon_block(self):
        res = self._result()
        html = card.render_report(res)
        self.assertIn("券 · 为什么这几张适合你", html)
        self.assertIn(res["coupons"][0]["name"], html)
        self.assertIn("不代领", html)

    def test_report_without_coupons(self):
        res = self._result()
        res.pop("coupons")
        html = card.render_report(res)
        self.assertNotIn("券 · 为什么这几张适合你", html)

    def test_markdown_has_coupon(self):
        md = card.render_markdown(self._result())
        self.assertIn("## 券 · 为什么这几张适合你", md)


class TestCompliance(unittest.TestCase):
    """合规红线：券模块只读。源码里不得出现任何写操作工具名。"""

    def test_no_write_tools_in_source(self):
        src = (ROOT / "coupons.py").read_text(encoding="utf-8")
        # 模块 docstring 里会提到这些名字（用于声明禁止），所以只检查「被当作工具名调用」的形态
        for forbidden in ("auto-bind-coupons", "create-order", "draw-lottery", "mall-create-order"):
            self.assertNotIn(f'"{forbidden}"', src, f"coupons.py 里出现了写接口调用：{forbidden}")
            self.assertNotIn(f"'{forbidden}'", src, f"coupons.py 里出现了写接口调用：{forbidden}")

    def test_only_available_coupons_called(self):
        src = (ROOT / "coupons.py").read_text(encoding="utf-8")
        self.assertIn('"available-coupons"', src)


if __name__ == "__main__":
    unittest.main()
