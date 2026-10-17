"""数据层：调麦当劳 MCP 取订单，压成规范化订单结构（设计 §2.2）。

主链路只依赖 order-list（列表）+ query-order（逐笔补明细，可失败降级）。
平移自 mcaudit/mcaudit.py（load_demo L36-41、_first/_dig/_as_list L44-73、
fetch_orders L76-105、normalize_order L133-184、_to_float L216-222），
剔除营养函数（fetch_nutrition/enrich_nutrition/_fuzzy）。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


# ---------------------------------------------------------------- 取值工具（mcaudit L44-73）

def _first(d: dict, keys, default=None):
    """按候选字段名依次取值，兼容不同版本的返回结构。"""
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return default


def _dig(obj, *keys):
    """层层下钻，找不到返回 None。"""
    cur = obj
    for k in keys:
        if isinstance(cur, dict) and k in cur:
            cur = cur[k]
        else:
            return None
    return cur


def _as_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for key in ("orders", "list", "items", "data", "records", "result"):
            if isinstance(value.get(key), list):
                return value[key]
        return [value]
    return []


def _to_float(value, default=0.0) -> float:
    try:
        if isinstance(value, str):
            value = re.sub(r"[^0-9.\-]", "", value)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


# ---------------------------------------------------------------- 拉取与规范化

def fetch_orders(client, raw_out: list | None = None) -> list[dict]:
    """拉取历史订单并逐笔补明细（平移 mcaudit.py L76-105）。

    query-order 单笔失败 → 降级 items=[]，不阻断整体（设计 §7）。
    raw_out：可选收集列表——调用方传入 list 时，order-list 首个原始条目
    会 append 进去，供 --dump 的 raw_sample 字段使用（设计 §6.1）。
    """
    raw = client.call_tool("order-list", {})
    orders = _as_list(_dig(raw, "data") or _dig(raw, "result") or raw)

    if raw_out is not None and orders:
        raw_out.append(next((o for o in orders if isinstance(o, dict)), None))

    summaries = []
    for o in orders:
        if not isinstance(o, dict):
            continue
        summaries.append(
            {
                "order_id": _first(o, ["orderId", "order_id", "orderNo", "id"]),
                "order_time": _first(o, ["orderTime", "order_time", "createTime", "createdAt"]),
                "paid": _to_float(_first(o, ["payAmount", "paid", "actualAmount", "total", "amount"], 0)),
                "store_name": _first(o, ["storeName", "store_name", "restaurantName"], ""),
                "order_type": _first(o, ["orderType", "order_type", "takeWayName"], ""),
            }
        )

    detailed = []
    for s in summaries:
        if not s["order_id"]:
            continue
        try:
            detail = client.call_tool("query-order", {"orderId": s["order_id"]})
        except Exception as exc:  # noqa: BLE001 单笔失败不影响整体
            print(f"  ! 订单 {s['order_id']} 明细拉取失败：{exc}", file=sys.stderr)
            detail = None
        detailed.append(normalize_order(s, detail))
    return detailed


def normalize_order(summary: dict, detail) -> dict:
    """压成内部统一结构（平移 mcaudit.py L133-184，含营养字段——设计决策 §11.4）。"""
    d = detail if isinstance(detail, dict) else {}
    payload = _dig(d, "data") or _dig(d, "result") or d

    items_raw = _as_list(
        _dig(payload, "items")
        or _dig(payload, "itemList")
        or _dig(payload, "orderItems")
        or _dig(payload, "products")
    )
    items = []
    for it in items_raw:
        if not isinstance(it, dict):
            continue
        qty = int(_to_float(_first(it, ["qty", "quantity", "count", "num"], 1)) or 1)
        price = _to_float(_first(it, ["price", "unitPrice", "salePrice", "amount"], 0))
        items.append(
            {
                "name": str(_first(it, ["name", "itemName", "productName", "goodsName"], "未知名目")),
                "category": str(_first(it, ["category", "categoryName", "type"], "其他")),
                "qty": qty,
                "unit_price": price,
                "amount": _to_float(_first(it, ["totalAmount", "subTotal", "amount"], price * qty)),
                "kcal": _to_float(_first(it, ["kcal", "energy", "热量"], 0)) * qty,
                "protein": _to_float(_first(it, ["protein", "蛋白质"], 0)) * qty,
                "fat": _to_float(_first(it, ["fat", "脂肪"], 0)) * qty,
                "carb": _to_float(_first(it, ["carb", "carbohydrate", "碳水"], 0)) * qty,
                "sodium": _to_float(_first(it, ["sodium", "钠"], 0)) * qty,
            }
        )

    gross = sum(i["amount"] for i in items)
    paid = summary.get("paid") or _to_float(
        _first(payload, ["payAmount", "paid", "actualAmount", "total"], gross)
    )
    discount = _to_float(_first(payload, ["discountAmount", "discount", "promotionAmount"], 0))
    delivery = _to_float(_first(payload, ["deliveryFee", "delivery_fee", "shippingFee"], 0))

    return {
        "order_id": summary.get("order_id") or _first(payload, ["orderId", "order_id"], ""),
        "order_time": str(summary.get("order_time") or _first(payload, ["orderTime", "createTime"], "")),
        "order_type": summary.get("order_type") or _first(payload, ["orderType", "takeWayName"], ""),
        "store_name": summary.get("store_name") or _first(payload, ["storeName"], ""),
        "store_code": _first(payload, ["storeCode", "store_code"], ""),
        "items": items,
        "gross": round(gross or paid, 2),
        "discount": discount,
        "delivery_fee": delivery,
        "paid": round(paid, 2),
        "coupon_used": bool(discount > 0 or _first(payload, ["couponId", "couponIds"])),
    }


# ---------------------------------------------------------------- demo 样例（mcaudit L36-41）

# 八份样例对应八个人格（p1 → P1 … p8 → P8）。
# normal / heavy 是早期两个样例的旧名，保留映射避免旧命令失效。
DEMO_ALIASES = {"normal": "p3", "heavy": "p2"}
DEMO_PROFILES = [f"p{i}" for i in range(1, 9)]


def load_demo(profile: str = "p3") -> dict:
    key = DEMO_ALIASES.get(profile, profile)
    path = ROOT / "fixtures" / f"demo_orders_{key}.json"
    if not path.exists():
        raise SystemExit(
            f"没有这份样例：{profile}。可选 {' / '.join(DEMO_PROFILES)}"
            "（旧名 normal=p3、heavy=p2）\n"
            "若样例文件整体缺失，运行 python fixtures/make_fixture.py 重新生成。"
        )
    return json.loads(path.read_text(encoding="utf-8"))
