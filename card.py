"""卡片层：结果字典 → 三输出物 HTML/HTML/MD 字符串（设计 §5）。

750×1100 单文件离线 HTML，无外部资源（无图片、无字体链接、无 JS 请求）。
色板（设计 §5）：麦黄 #FFC72C / 麦红 #DA291C / 深灰 #1C2024 / 次要 #5B6570 / 卡底 #FFFDF5。
"""

from __future__ import annotations

from html import escape

from features import SLOTS

REPO_URL = "https://github.com/<待定>/mcd-chrono"   # O1：10-20 建仓时改此一处

DISCLAIMER = (
    "本鉴定由 mcd-chrono 自动生成，仅供娱乐，基于你本人的麦当劳订单时间数据，"
    "不构成任何健康或饮食建议。本项目为麦当劳程序员创意开发大赛参赛作品，非麦当劳官方产品。"
)


def _fmt_pct(x) -> str:
    return "—" if x is None else f"{x * 100:.1f}%"


def _fmt_num(x) -> str:
    if x is None:
        return "—"
    return f"{x:.1f}" if isinstance(x, float) else str(x)


def _e(v) -> str:
    return escape(str(v)) if v is not None else "—"


# ---------------------------------------------------------------- 六段版式

def _identity_bar() -> str:
    """段① 标识行：MCD CHRONOTYPE REPORT + 麦门作息鉴定所（麦黄底条，下沿麦红线）。"""
    return (
        '<div class="brand">MCD CHRONOTYPE REPORT</div>'
        '<div class="brand-sub">麦门作息鉴定所</div>'
    )


def _hero(p: dict) -> str:
    """段② 称号区：emoji + 称号 + 副行（样本 N 单 · 麦龄 X 天）。"""
    return (
        f'<div class="hero"><div class="big-emoji">{p["emoji"]}</div>'
        f'<h1 class="title">{_e(p["title"])}</h1></div>'
    )


def _hero_sub(f: dict) -> str:
    m = f["meta"]
    return f'<div class="hero-sub">样本 {f["n"]} 单 · 麦龄 {m["span_days"]} 天</div>'


def _slot_bars(f: dict) -> str:
    """段③ 五时段条形图：最高时段条麦红，其余麦黄；占比取一位小数。"""
    t1 = f.get("t1")
    if t1 is None:
        return '<div class="bars-empty">时间数据不足，无法统计时段分布</div>'
    top_slot = max(t1, key=lambda s: t1[s])
    rows = []
    for s in SLOTS:
        ratio = t1[s]
        color = "#DA291C" if s == top_slot else "#FFC72C"
        rows.append(
            f'<div class="bar-row"><span class="bar-label">{s}</span>'
            f'<span class="bar-track"><i class="bar-fill" style="width:{ratio*100:.1f}%;background:{color}"></i></span>'
            f'<span class="bar-val">{ratio*100:.1f}%</span></div>'
        )
    return "".join(rows)


def _stat_grid(f: dict) -> str:
    """段④ 三数字格：累计订单 / 麦龄天数 / 最忠门店+T10。门店名超长省略号截断。"""
    m = f["meta"]
    top_store = m.get("top_store")
    if top_store:
        third_label, third_value = "最忠门店", f"{top_store} · {f['t10']*100:.0f}%"
    else:
        third_label, third_value = "最忠门店", "—"
    return (
        f'<div class="stat">'
        f'<div class="stat-k">累计订单</div><div class="stat-v">{f["n"]}</div></div>'
        f'<div class="stat">'
        f'<div class="stat-k">麦龄天数</div><div class="stat-v">{m["span_days"]}</div></div>'
        f'<div class="stat">'
        f'<div class="stat-k">{third_label}</div><div class="stat-v stat-store">{_e(third_value)}</div></div>'
    )


def _desc_verdict(p: dict) -> str:
    """段⑤ 描述 + 判词。判词加大加粗（截图传播点）。"""
    desc = "".join(f"<p>{_e(line)}</p>" for line in p.get("desc") or [])
    return (
        f'<div class="desc">{desc}</div>'
        f'<div class="verdict">{_e(p["verdict"])}</div>'
    )


def _footer() -> str:
    """段⑥ 免责底行 + GitHub 提示。"""
    return (
        f'<div class="foot-note">{_e(DISCLAIMER)}</div>'
        f'<div class="foot-gh">GitHub · mcd-chrono</div>'
    )


def _watermark(source: str) -> str:
    """demo 模式右上角 45° 半透明角标（合规要求，设计 §5）。"""
    if source != "demo":
        return ""
    return '<div class="watermark">DEMO · 构造数据</div>'


def _card(result: dict) -> str:
    f, p = result["features"], result["persona"]
    parts = [
        '<div class="card">',
        _identity_bar(),
        _hero(p),
        _hero_sub(f),
        '<div class="block"><h2 class="block-title">时段分布</h2>' + _slot_bars(f) + "</div>",
        '<div class="stats">' + _stat_grid(f) + "</div>",
        _desc_verdict(p),
        _footer(),
        _watermark(result.get("source", "")),
        "</div>",
    ]
    return "".join(parts)


# ---------------------------------------------------------------- CSS

_CARD_CSS = """
:root{--gold:#FFC72C;--red:#DA291C;--ink:#1C2024;--sub:#5B6570;--paper:#FFFDF5}
*{box-sizing:border-box;margin:0;padding:0}
body{background:#ECE7DC;padding:24px 0;font-family:-apple-system,"PingFang SC","Microsoft YaHei",Segoe UI,sans-serif;color:var(--ink)}
.card{position:relative;width:750px;min-height:1100px;margin:0 auto;background:var(--paper);
border-radius:16px;overflow:hidden;box-shadow:0 8px 32px rgba(28,32,36,.14);
display:flex;flex-direction:column;padding:0 0 26px}
.brand{background:var(--gold);color:#1C2024;font-size:15px;font-weight:700;letter-spacing:6px;
padding:20px 44px 6px}
.brand-sub{background:var(--gold);color:#5B4A0F;font-size:12px;letter-spacing:4px;
padding:0 44px 14px;border-bottom:4px solid var(--red)}
.hero{padding:34px 44px 6px;text-align:center}
.big-emoji{font-size:96px;line-height:1}
.title{font-size:44px;font-weight:800;letter-spacing:2px;margin-top:10px}
.hero-sub{color:var(--sub);font-size:14px;text-align:center;margin-top:8px}
.block{padding:18px 44px 0}
.block-title{font-size:12px;color:var(--sub);letter-spacing:3px;margin-bottom:12px}
.bar-row{display:flex;align-items:center;gap:10px;margin-bottom:9px}
.bar-label{width:48px;font-size:15px;color:var(--sub);flex:none}
.bar-track{flex:1;height:18px;background:#F0EADC;border-radius:9px;overflow:hidden}
.bar-fill{display:block;height:100%;border-radius:9px}
.bar-val{width:56px;text-align:right;font-size:14px;color:var(--ink);font-variant-numeric:tabular-nums;flex:none}
.bars-empty{color:var(--sub);font-size:13px;padding:8px 0}
.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin:16px 44px 0}
.stat{background:#FFFFFF;border:1px solid #EFE8D8;border-radius:12px;padding:14px 16px;overflow:hidden}
.stat-k{font-size:11px;color:var(--sub);letter-spacing:2px}
.stat-v{font-size:26px;font-weight:800;margin-top:6px;font-variant-numeric:tabular-nums;white-space:nowrap}
.stat-store{font-size:15px;font-weight:700;line-height:1.5;white-space:normal;display:-webkit-box;
-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.desc{padding:20px 44px 0;font-size:15px;line-height:1.7;color:var(--ink)}
.desc p{margin-bottom:8px}
.verdict{margin:14px 44px 0;font-size:20px;font-weight:800;color:var(--red);line-height:1.5}
.foot-note{margin:auto 44px 0;padding-top:18px;font-size:11px;color:var(--sub);line-height:1.6}
.foot-gh{padding:8px 44px 0;font-size:11px;color:var(--sub);letter-spacing:1px}
.watermark{position:absolute;top:88px;right:-34px;transform:rotate(45deg);
background:rgba(28,32,36,.78);color:#FFFDF5;font-size:13px;letter-spacing:3px;
padding:6px 44px;font-weight:700}
"""


def _page(inner: str, title: str, extra_css: str = "") -> str:
    return (
        '<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        f"<title>{escape(title)}</title>\n<style>{_CARD_CSS}{extra_css}</style>\n</head>\n<body>\n"
        f"{inner}\n</body>\n</html>\n"
    )


# ---------------------------------------------------------------- 三个输出物

def render_card(result: dict) -> str:
    """out/chrono_card.html：仅卡片（居中置灰底），直接截图用。"""
    return _page(_card(result), f"{result['persona']['title']} · 麦门作息鉴定")


def render_report(result: dict) -> str:
    """out/chrono_report.html：完整页 = 卡片 + 附录（T1-T10 数值表 + 判定链过程）。"""
    f, p = result["features"], result["persona"]
    rows = [
        ("T1 五时段分布", _fmt_t1(f.get("t1"))),
        ("T2 工作日午市卡点率", _fmt_pct(f.get("t2"))),
        ("T3 早餐规律率 t3_ratio", _fmt_pct(f.get("t3_ratio"))),
        ("T3 早餐规律度 t3_std", _fmt_minute(f.get("t3_std"))),
        ("T4 夜宵率", _fmt_pct(f.get("t4"))),
        ("T5 周末占比", _fmt_pct(f.get("t5"))),
        ("T6 外卖率", _fmt_pct(f.get("t6"))),
        ("T7 单品集中度", _fmt_pct(f.get("t7"))),
        ("T8 麦频（单/月）", _fmt_num(f.get("t8"))),
        ("T9 规律度（分钟）", _fmt_minute(f.get("t9"))),
        ("T10 忠诚度", _fmt_pct(f.get("t10"))),
    ]
    chain = "\n".join(
        f'<div class="chain-row">{_e(c)}</div>' for c in _chain_log(f, p)
    )
    table = "\n".join(
        f'<tr><td class="k">{escape(k)}</td><td class="v">{escape(v)}</td></tr>'
        for k, v in rows
    )
    return _page(
        _card(result)
        + '<div class="appendix">'
        + '<h2 class="block-title">附录一 · 十项特征数值</h2>'
        + f"<table>{table}</table>"
        + '<h2 class="block-title">附录二 · 判定链逐级过程</h2>'
        + chain
        + "</div>",
        "麦门作息鉴定报告",
        """
.appendix{width:750px;margin:20px auto 0;background:var(--paper);border-radius:16px;
padding:26px 44px 30px;box-shadow:0 8px 32px rgba(28,32,36,.14)}
.appendix table{width:100%;border-collapse:collapse;font-size:14px}
.appendix td{padding:8px 0;border-bottom:1px solid #EFE8D8}
.appendix td.k{color:var(--sub)}
.appendix td.v{text-align:right;font-variant-numeric:tabular-nums}
.chain-row{font-size:13px;color:var(--sub);line-height:1.9}
""",
    )


def _fmt_t1(t1) -> str:
    if t1 is None:
        return "不可判"
    return "　".join(f"{s} {t1[s]*100:.1f}%" for s in SLOTS)


def _fmt_minute(x) -> str:
    return "不可判" if x is None else f"{x:.1f} 分钟"


def _chain_log(f: dict, p: dict) -> list[str]:
    """判定链逐级命中过程（调试与展示用，直接复用 persona.PERSONAS 的条件求值）。"""
    from persona import PERSONAS, THRESHOLDS as T

    exprs = [
        f"T7={_s(f.get('t7'))} ≥ {T['t7_nail']}",
        f"T4={_s(f.get('t4'))} ≥ {T['t4_night']}",
        f"t3_ratio={_s(f.get('t3_ratio'))} ≥ {T['t3_ratio']} 且 t3_std={_s(f.get('t3_std'))} < {T['t3_std']}",
        f"T2={_s(f.get('t2'))} ≥ {T['t2_punch']} 且 T9={_s(f.get('t9'))} < {T['t9_regular']}",
        f"T5={_s(f.get('t5'))} ≥ {T['t5_weekend']} 且 T6={_s(f.get('t6'))} ≥ {T['t6_delivery']}",
        f"T1下午茶={_s(_tea(f))} ≥ {T['t1_tea']}",
        f"T8={_s(f.get('t8'))} < {T['t8_sparse']}",
    ]
    lines = []
    if p.get("is_scant"):
        lines.append(f"n={f['n']} < {T['scant_min']} → 安慰卡（不进判定链）")
        return lines
    for persona, expr in zip(PERSONAS, exprs):
        hit = persona["condition"](f, T)
        verdict = "命中" if hit else "未命中"
        mark = " ← 停" if hit else ""
        lines.append(f"{persona['key']}：{expr} → {verdict}{mark}")
        if hit:
            break
    if not any(persona["condition"](f, T) for persona in PERSONAS[:7]):
        lines.append("P8：兜底恒真 → 命中 ← 停")
    return lines


def _s(x) -> str:
    if x is None:
        return "None（不可判）"
    if isinstance(x, float):
        return f"{x:.4f}"
    return str(x)


def _tea(f: dict):
    return None if f.get("t1") is None else f["t1"]["下午茶"]


def render_markdown(result: dict) -> str:
    """out/chrono_report.md：纯文本简版。"""
    f, p = result["features"], result["persona"]
    m = f["meta"]
    lines = [
        f"# 麦门作息鉴定 · {p['emoji']} {p['title']}",
        "",
        f"- 样本：{f['n']} 单（时间可解析 {f['n_timevalid']} 单）",
        f"- 麦龄：{m['span_days']} 天（{m['first']} ~ {m['last']}）",
        f"- 最忠门店：{m['top_store'] or '—'}",
        "",
        "## 五时段占比",
        "",
    ]
    if f.get("t1"):
        lines += [f"- {s}：{f['t1'][s]*100:.1f}%" for s in SLOTS]
    else:
        lines.append("- 不可判（时间数据不足）")
    lines += ["", "## 鉴定描述", ""]
    lines += [x for x in (p.get("desc") or [])]
    lines += ["", f"**判词：{p['verdict']}**", "", "---", "", DISCLAIMER]
    return "\n".join(lines)
