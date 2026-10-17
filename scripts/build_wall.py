"""八人格墙生成器：把 8 份样例卡片拼成 README 首图的数据源。

背景：README 顶部那张 `docs/assets/persona-wall.png` 不是手拼的，是这个脚本生成的
`out/wall.html` 再截图得到的。人格称号会随文案迭代变，所以标签不能写死——这里直接从
卡片 HTML 里读真实称号和订单数，改完文案重跑一次即可，不会出现图里还是旧名字的情况。

用法（在仓库根目录）：
    python fixtures/make_fixture.py      # 重新生成 8 份样例数据（可选）
    python scripts/build_wall.py         # 出 8 张卡 + 生成 out/wall.html
    # 截图（Chrome 路径按本机调整）：
    #   chrome --headless --disable-gpu --hide-scrollbars --virtual-time-budget=3000 \
    #          --window-size=1296,762 --screenshot=docs/assets/persona-wall.png \
    #          file:///<仓库绝对路径>/out/wall.html

零依赖，只用标准库；不需要 MCP Token。
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
SAMPLES = [f"p{i}" for i in range(1, 9)]

CARD_TPL = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<style>
  *{{margin:0;padding:0;box-sizing:border-box}}
  body{{width:1296px;background:#141414;font-family:-apple-system,"Segoe UI","Microsoft YaHei",sans-serif;padding:26px 24px 30px}}
  h1{{color:#FFC72C;font-size:30px;font-weight:800;letter-spacing:2px;text-align:center}}
  .sub{{color:#9C9488;font-size:13px;text-align:center;margin-top:8px;letter-spacing:.6px}}
  .grid{{display:grid;grid-template-columns:repeat(4,300px);gap:16px;margin-top:22px}}
  .cell{{width:300px;height:302px;background:#1E1E1E;border-radius:10px;overflow:hidden;
        box-shadow:0 6px 22px rgba(0,0,0,.5)}}
  .shot{{width:300px;height:278px;background-size:300px 440px;background-position:top center;background-repeat:no-repeat}}
  .name{{height:24px;line-height:24px;text-align:center;color:#D8D2C6;font-size:11.5px;letter-spacing:.5px;background:#232323}}
</style>
</head>
<body>
  <h1>八 种 麦 门 作 息</h1>
  <div class="sub">同一个工具 · 八份样例 · 八张鉴定卡</div>
  <div class="grid">
{rows}
  </div>
</body>
</html>
"""

ROW_TPL = '    <div class="cell"><div class="shot" style="background-image:url({png})"></div><div class="name">{label}</div></div>'

TITLE_RE = re.compile(r'<h1 class="title">([^<]+)</h1>')
SUB_RE = re.compile(r'<div class="hero-sub">样本 (\d+) 单')


def build_cards() -> dict[str, tuple[str, int]]:
    """逐份样例出卡，返回 {样例: (称号, 单数)}。"""
    meta: dict[str, tuple[str, int]] = {}
    for s in SAMPLES:
        proc = subprocess.run(
            [sys.executable, "main.py", "--demo", "--sample", s, "--out", str(OUT / s)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if proc.returncode != 0:
            raise SystemExit(f"{s} 出卡失败：{proc.stderr.strip()[-300:]}")
        html = (OUT / s / "chrono_card.html").read_text(encoding="utf-8")
        m_title, m_sub = TITLE_RE.search(html), SUB_RE.search(html)
        if not (m_title and m_sub):
            raise SystemExit(f"{s} 的卡片 HTML 里读不到称号或订单数，模板可能改过了")
        meta[s] = (m_title.group(1).strip(), int(m_sub.group(1)))
    return meta


def main() -> None:
    meta = build_cards()
    rows = "\n".join(
        ROW_TPL.format(png=f"{s}.png", label=f"{s.upper()} {meta[s][0]} · {meta[s][1]} 单")
        for s in SAMPLES
    )
    wall = OUT / "wall.html"
    wall.write_text(CARD_TPL.format(rows=rows), encoding="utf-8")
    print(f"已生成 {wall.relative_to(ROOT)}")
    for s in SAMPLES:
        print(f"  {s}: {meta[s][0]} · {meta[s][1]} 单")


if __name__ == "__main__":
    main()
