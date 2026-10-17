"""卡片离线性与输出生成单元断言（设计 §9 test_card_offline）。

A5 机器判据：生成的三份输出源码无 http:// / https://（demo 水印存在、live 无水印）。
运行：python docs/batches/tests/run_all.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import card  # noqa: E402
import features  # noqa: E402
import persona  # noqa: E402


def _demo_result() -> dict:
    orders = [
        {"order_time": "2026-10-13 08:30", "order_type": "麦乐送",
         "store_name": "上海南京西路餐厅", "items": [{"name": "猪柳蛋麦满分", "amount": 14.5}]},
        {"order_time": "2026-10-14 08:35", "order_type": "麦乐送",
         "store_name": "上海南京西路餐厅", "items": [{"name": "猪柳蛋麦满分", "amount": 14.5}]},
        {"order_time": "2026-10-15 08:40", "order_type": "到店取餐",
         "store_name": "上海人民广场餐厅", "items": [{"name": "热香饼", "amount": 12.0}]},
        {"order_time": "2026-10-16 08:20", "order_type": "到店取餐",
         "store_name": "上海人民广场餐厅", "items": [{"name": "豆浆", "amount": 8.0}]},
        {"order_time": "2026-10-17 08:45", "order_type": "麦乐送",
         "store_name": "上海陆家嘴环路餐厅", "items": [{"name": "脆薯饼", "amount": 7.5}]},
        {"order_time": "2026-10-20 08:25", "order_type": "麦乐送",
         "store_name": "上海南京西路餐厅", "items": [{"name": "猪柳蛋麦满分", "amount": 14.5}]},
    ]
    return {
        "source": "demo",
        "features": features.extract(orders),
        "persona": persona.judge(features.extract(orders)),
    }


class TestOffline(unittest.TestCase):
    """A5：输出源码无 http:// / https://。"""

    def setUp(self):
        self.result = _demo_result()

    def test_card_html_no_http(self):
        html = card.render_card(self.result)
        self.assertNotIn("http://", html)
        self.assertNotIn("https://", html)

    def test_report_html_no_http(self):
        html = card.render_report(self.result)
        self.assertNotIn("http://", html)
        self.assertNotIn("https://", html)

    def test_markdown_disclaimer_no_repo_url(self):
        # MD 简版不注入 REPO_URL 占位（share 文案才有；占位含 https://）
        md = card.render_markdown(self.result)
        self.assertNotIn("http://", md)
        self.assertNotIn("https://", md)

    def test_no_script_no_img_tags(self):
        # 无 JS 请求、无图片引用、无 CSS 外链
        for html in (card.render_card(self.result), card.render_report(self.result)):
            self.assertNotIn("<script", html)
            self.assertNotIn("<img", html)
            self.assertNotIn("<iframe", html)
            self.assertNotIn("url(", html)
            self.assertNotIn("@import", html)
            self.assertNotIn("src=", html)

    def test_watermark_demo_present(self):
        self.assertIn("DEMO", card.render_card(self.result))
        self.assertIn("构造数据", card.render_card(self.result))

    def test_watermark_live_absent(self):
        live = dict(self.result, source="live")
        self.assertNotIn("DEMO", card.render_card(live))

    def test_scant_card_same_layout(self):
        # 安慰卡走同一版式（设计 §11.7）：is_scant=True 也能正常渲染
        scant_orders = self.result["features"]
        f = dict(scant_orders, n=4)
        scant_result = {"source": "demo", "features": f,
                        "persona": persona.judge(f)}
        html = card.render_card(scant_result)
        self.assertIn("样本不足安慰卡", html)

    def test_card_size_spec(self):
        html = card.render_card(self.result)
        self.assertIn("750px", html)
        self.assertIn("1100px", html)

    def test_palette(self):
        html = card.render_card(self.result)
        for hexcolor in ("#FFC72C", "#DA291C", "#1C2024", "#5B6570", "#FFFDF5"):
            self.assertIn(hexcolor, html)


if __name__ == "__main__":
    unittest.main()
