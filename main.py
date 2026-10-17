"""麦门作息鉴定 · mcd-chrono CLI 入口（设计 §6）。

    python main.py --demo                          内置样例出卡（默认 p3 晨间通勤麦）
    python main.py --demo --sample p4              指定人格样例（p1-p8 对应八个人格）
    python main.py --demo --list-samples           列出八份样例分别是哪种人格
    python main.py --live                          调麦当劳 MCP 拉真实订单（需 MCD_MCP_TOKEN）
    python main.py --live --dump raw.json          额外落盘原始返回（字段核对，§6.1）
    python main.py --demo --share                  追加打印分享文案
    python main.py --demo --no-coupons             只鉴定，不推荐券

退出码：0 成功；2 MCP 连接/Token 失败。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import card
import coupons
import features
import persona
from fetch import DEMO_PROFILES, fetch_orders, load_demo

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "out"


def share_text(result: dict) -> str:
    """分享文案模板（设计 §6.2）。安慰卡输出友好版（不输出人格称号）。"""
    f, p = result["features"], result["persona"]
    head = (
        f"我在麦当劳下了 {f['n']} 单，被鉴定为「{p['emoji']} {p['title']}」。"
        if not p.get("is_scant")
        else f"我在麦当劳下了 {f['n']} 单，鉴定所说样本还太少，故事才刚开场。"
    )
    return f"{head}\n{p['verdict']}\n你是哪种麦门作息？→ {card.REPO_URL}"


def _emit(result: dict, out: Path) -> list[Path]:
    """三个输出物落盘，返回路径列表。"""
    out.mkdir(parents=True, exist_ok=True)
    paths = [
        out / "chrono_card.html",
        out / "chrono_report.html",
        out / "chrono_report.md",
    ]
    paths[0].write_text(card.render_card(result), encoding="utf-8")
    paths[1].write_text(card.render_report(result), encoding="utf-8")
    paths[2].write_text(card.render_markdown(result), encoding="utf-8")
    return paths


def _summary(result: dict, paths: list[Path]) -> None:
    f, p = result["features"], result["persona"]
    m = f["meta"]
    print()
    print(f"  {p['emoji']}  {p['title']}")
    print(f"     样本 {f['n']} 单 · 麦龄 {m['span_days']} 天 · 最忠门店 {m['top_store'] or '—'}")
    print(f"     判词：{p['verdict']}")
    recs = result.get("coupons") or []
    if recs:
        print(f"     选券：{len(recs)} 张适合你 —— {recs[0]['name']}")
    print()
    for path in paths:
        print(f"  已生成  {path.resolve()}")


def _list_samples() -> None:
    """列出八份样例（人格名读各文件的 persona 字段，不在此处硬编码）。"""
    print("\n  可用样例（与 persona.py 的判定链一一对应）\n")
    for key in DEMO_PROFILES:
        try:
            data = load_demo(key)
        except SystemExit:
            print(f"  {key}   （样例文件缺失）")
            continue
        print(f"  {key}   {data.get('persona', '—'):<20} {len(data['orders']):>4} 单")
    print("\n  用法：python main.py --demo --sample p4")
    print("  旧名仍可用：normal = p3，heavy = p2\n")


def run(args) -> int:
    if args.list_samples:
        _list_samples()
        return 0

    # ---- 数据源（--demo / --live 互斥必选）
    coupon_pool: list[dict] = []
    if args.demo:
        if args.dump:
            print("--dump 仅 live 模式生效，已忽略。", file=sys.stderr)
        data = load_demo(args.sample or "p3")
        orders = data["orders"]
        source = "demo"
        if not args.no_coupons:
            coupon_pool = coupons.load_demo()
    else:
        from mcp_client import McpError, from_env

        raw_first: list = []
        try:
            client = from_env()
            client.initialize()
            print("正在拉取历史订单…", file=sys.stderr)
            orders = fetch_orders(client, raw_out=raw_first)
        except McpError as exc:
            print(f"MCP 连接失败：{exc}", file=sys.stderr)
            print("提示：没有 Token 时可先用 --demo 查看效果。", file=sys.stderr)
            return 2
        if not orders:
            raise SystemExit("没有取到订单。若账号无历史订单，可先用 --demo 查看效果。")
        print(f"取到 {len(orders)} 笔。", file=sys.stderr)
        source = "live"
        if not args.no_coupons:
            try:
                coupon_pool = coupons.fetch_coupons(client)
                print(f"取到 {len(coupon_pool)} 张可领券。", file=sys.stderr)
            except McpError as exc:  # 券挂了不影响鉴定本身
                print(f"券列表取不到（{exc}），鉴定结果不受影响。", file=sys.stderr)
        if args.dump:
            dump = {
                "source": "live",
                "orders": orders,
                "raw_sample": raw_first[0] if raw_first else None,
            }
            Path(args.dump).write_text(
                json.dumps(dump, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(f"原始结构已保存至 {args.dump}", file=sys.stderr)

    # ---- 管道：特征 → 人格 → 券匹配 → 组装
    f = features.extract(orders)
    p = persona.judge(f)
    result = {"source": source, "features": f, "persona": p}
    if coupon_pool:
        recs = coupons.rank(p["key"], coupon_pool, f)
        if recs:
            result["coupons"] = recs
            result["coupon_why"] = coupons.why_for(p["key"], f)
            result["coupon_caution"] = coupons.caution_for(p["key"])

    if f["n_timevalid"] == 0:
        print(
            "时间字段缺失，建议 --live --dump 回传字段结构核对。",
            file=sys.stderr,
        )

    # ---- 落盘 + 摘要
    paths = _emit(result, Path(args.out))
    _summary(result, paths)

    if args.share:
        print()
        print("  ── 分享文案 ──")
        for line in share_text(result).splitlines():
            print(f"  {line}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="麦门作息鉴定：把你一年在麦当劳的下单时间，鉴定成一种打工人作息人格。",
    )
    mode = ap.add_mutually_exclusive_group(required=False)
    mode.add_argument("--demo", action="store_true", help="用内置样例数据出卡")
    mode.add_argument("--live", action="store_true", help="调用麦当劳 MCP 拉真实订单")
    ap.add_argument(
        "--list-samples",
        action="store_true",
        help="列出八份样例对应的人格（单独用或与 --demo 同给均可，优先执行）",
    )
    ap.add_argument(
        "--sample",
        choices=DEMO_PROFILES + ["normal", "heavy"],
        default=None,
        help="样例类型（配合 --demo）：p1-p8 对应八个人格，默认 p3；旧名 normal=p3、heavy=p2",
    )
    ap.add_argument("--dump", metavar="PATH", help="仅 live：落盘 JSON（含 raw_sample 首条原始样本）")
    ap.add_argument(
        "--no-coupons",
        action="store_true",
        help="不做选券推荐（默认会按人格给 1-3 张券的理由，只读不代领）",
    )
    ap.add_argument("--share", action="store_true", help="生成后向 stdout 打印分享文案")
    ap.add_argument("--out", default=str(OUT_DIR), help="输出目录，默认 ./out")
    args = ap.parse_args()

    if not (args.demo or args.live or args.list_samples):
        ap.error("必须指定 --demo、--live 或 --list-samples")

    if args.live and args.sample:
        print("--sample 与 --live 同给：已忽略 --sample。", file=sys.stderr)

    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
