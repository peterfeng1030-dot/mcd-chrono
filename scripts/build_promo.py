"""小红书 / 公众号贴图生成器：封面 + 八人格总览。

两张图都是纯静态 HTML 拼出来再截图，不依赖卡片渲染管线，改文案只改本文件重跑：
    python scripts/build_promo.py

产出（工作区 D:/WorkBuddySpace/AI/promo/img/）：
    cover.png        1080x1440 封面
    personas.png     1080x1440 八人格总览（对号入座用）
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT.parent / "promo" / "img"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

PERSONAS = [
    ("🍔", "麦门初恋体质", "菜单换了一轮又一轮，你的心动从没换过。", "同一个单品占了四成以上的单"),
    ("🌙", "深夜麦门守护者", "城市睡了，你的麦乐送还醒着。", "夜里十点后下单超过四分之一"),
    ("🌅", "晨间通勤麦", "地铁还没到站，你的猪柳蛋已经在路上了。", "早餐占比高，而且时间很准"),
    ("⏰", "卡点特种兵", "卡点这件事，你对麦当劳比对打卡机认真。", "午市扎堆，前后误差不到 75 分钟"),
    ("🛋️", "麦乐送头号收件人", "你周末第一个访客是骑手，最后一个也是。", "周末下单和外卖双双过半"),
    ("☕", "下午茶哲学家", "只有下午茶的时间，才真正属于你自己。", "下午茶时段占了近三成"),
    ("🍀", "麦门幸运儿", "一年来不了几次，但每次都是真心的。", "一个月还不到 1.5 单"),
    ("🌀", "全麦自由人", "想吃就吃，你的胃不看日历。", "以上都不沾，也就不被定义"),
]

BASE = """<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8"><style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{width:1080px;height:1440px;overflow:hidden;
  font-family:"Microsoft YaHei","PingFang SC",-apple-system,sans-serif;
  background:#141414;color:#F5F1E8;position:relative}}
</style></head><body>{body}</body></html>"""

COVER = """
<div style="position:absolute;top:78px;left:78px;font-size:19px;letter-spacing:5px;color:#8C8478">
  MCD CHRONOTYPE
</div>
<div style="position:absolute;top:108px;left:78px;font-size:15px;letter-spacing:2px;color:#5F594F">
  麦当劳订单 · 作息鉴定
</div>

<div style="position:absolute;top:214px;left:78px;right:78px">
  <div style="font-size:99px;font-weight:900;line-height:1.14;letter-spacing:-2px">
    麦当劳订单
  </div>
  <div style="font-size:99px;font-weight:900;line-height:1.14;letter-spacing:-2px;color:#FFC72C">
    能看出你是哪种人
  </div>
</div>

<div style="position:absolute;top:556px;left:78px;right:78px;display:flex;gap:8px;align-items:flex-end;height:196px">
  {bars}
</div>
<div style="position:absolute;top:778px;left:78px;font-size:15px;color:#6E675C;letter-spacing:1px">
  356 天 · 149 单 · 24 小时下单热力
</div>

<div style="position:absolute;top:836px;left:78px;right:78px;height:1px;background:#2A2A2A"></div>

<div style="position:absolute;top:890px;left:78px;right:64px;display:grid;
  grid-template-columns:repeat(2,1fr);gap:54px 24px">
  {chips}
</div>

<div style="position:absolute;bottom:62px;left:78px;right:78px;display:flex;
  justify-content:space-between;align-items:center">
  <div style="font-size:20px;color:#FFC72C;letter-spacing:1px">八种人格，你是哪一种</div>
  <div style="font-size:16px;color:#5F594F;letter-spacing:1px">GitHub · mcd-chrono</div>
</div>
"""

CHIP = ('<div style="display:flex;align-items:center;gap:13px;height:52px">'
        '<span style="font-size:31px">{e}</span>'
        '<span style="font-size:29px;font-weight:700;letter-spacing:.5px">{t}</span></div>')

BAR = ('<div style="flex:1;height:100%;display:flex;align-items:flex-end">'
       '<div style="width:100%;height:{h}%;border-radius:3px;background:{c}"></div></div>')

PEOPLE = """
<div style="position:absolute;top:62px;left:78px">
  <div style="font-size:54px;font-weight:900;letter-spacing:-1px">八种麦门作息</div>
  <div style="margin-top:16px;font-size:18px;color:#8C8478;letter-spacing:1px">
    命中即停，从第一条往下对，先中的就是你的
  </div>
</div>

<div style="position:absolute;top:206px;left:78px;right:78px">
  {rows}
</div>

<div style="position:absolute;bottom:46px;left:78px;right:78px;font-size:15px;
  color:#7A7367;letter-spacing:.6px;line-height:1.6">
  判定只看下单时间、频次和重复度，不看金额 · 开源工具 mcd-chrono
</div>
"""

ROW = """
<div style="display:flex;align-items:flex-start;gap:24px;padding:23px 0;
  border-bottom:1px solid #242424">
  <div style="width:72px;height:72px;flex:none;border-radius:50%;background:#1F1F1F;
    display:flex;align-items:center;justify-content:center;font-size:34px">{e}</div>
  <div style="flex:1;padding-top:2px">
    <div style="font-size:33px;font-weight:800;letter-spacing:.5px">{t}</div>
    <div style="margin-top:10px;font-size:22px;color:#B8B0A2;line-height:1.4">{v}</div>
  </div>
  <div style="width:246px;flex:none;text-align:right;padding-top:12px;
    font-size:16px;color:#8C8478;line-height:1.5">{c}</div>
</div>
"""

# 24 格热力，形状是深夜那张卡的真实分布（峰值 22 点）
HEAT = [6, 3, 2, 1, 1, 2, 5, 9, 14, 17, 22, 46, 30, 12, 8, 7, 10, 24, 58, 46, 33, 72, 100, 61]


def heat_bars() -> str:
    out = []
    for i, v in enumerate(HEAT):
        # 峰值前后用黄，其余砖红，末段淡
        if i == 22:
            c = "#FFC72C"
        elif v > 45:
            c = "linear-gradient(180deg,#FF6B4A,#E03C1F)"
        else:
            c = "linear-gradient(180deg,#5A2A22,#3A1D18)"
        out.append(BAR.format(h=max(v, 4), c=c))
    return "".join(out)


def build(name: str, body: str) -> Path:
    html = OUT / f"{name}.html"
    html.write_text(BASE.format(body=body), encoding="utf-8")
    return html


def shoot(html: Path, png: Path) -> None:
    """Chrome headless 偶发静默失败（exit 0 但不出文件），重试到落地为止。"""
    args = [
        CHROME, "--headless", "--disable-gpu", "--hide-scrollbars",
        "--force-device-scale-factor=1", "--virtual-time-budget=4000",
        f"--window-size=1080,1440", f"--screenshot={png.as_posix()}",
        f"file:///{html.as_posix()}",
    ]
    for _ in range(4):
        subprocess.run(args, capture_output=True)
        if png.exists() and png.stat().st_size > 20_000:
            return
        time.sleep(0.6)
    raise SystemExit(f"截图失败：{png}")


def main() -> None:
    if not CHROME:
        raise SystemExit("找不到 Chrome")
    OUT.mkdir(parents=True, exist_ok=True)

    cover = COVER.format(
        bars=heat_bars(),
        chips="".join(CHIP.format(e=e, t=t) for e, t, *_ in PERSONAS),
    )
    people = PEOPLE.format(
        rows="".join(ROW.format(e=e, t=t, v=v, c=c) for e, t, v, c in PERSONAS)
    )

    for name, body in (("cover", cover), ("personas", people)):
        html = build(name, body)
        shoot(html, OUT / f"{name}.png")
        print(f"ok  {(OUT / f'{name}.png').as_posix()}")


if __name__ == "__main__":
    main()
