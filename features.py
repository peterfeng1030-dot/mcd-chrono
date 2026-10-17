"""特征层：规范化订单列表 → T1-T10 特征字典 + meta（设计 §2.2 / §3）。

None 语义（设计 §2.2）：分母为零或明细缺失 = 不可判，返回 None；
下游人格判定遇到 None 一律判否，不猜零。
"""

from __future__ import annotations

import math
from datetime import datetime

SLOTS = ["早", "午", "下午茶", "晚", "夜"]
TIME_FORMATS = (
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%Y/%m/%d %H:%M",
    "%Y-%m-%dT%H:%M:%S",
)
UNIFORM_T9 = 415.7   # 全天均匀分布的环形 RMS 理论值（1440/√12 ≈ 415.69），量尺参考
R_NEAR_ZERO = 1e-9   # 合向量长度低于此 = 近均匀，均值方向数值上不可定


def parse_time(value) -> datetime | None:
    """解析下单时间；失败返回 None（该单计入 n，不计入 n_timevalid）。"""
    if not value:
        return None
    text = str(value).strip()
    for fmt in TIME_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def slot_of_minute(m: int) -> str:
    """五时段落窗（设计 §3.1，左闭右开）。夜 = [1260,1440) ∪ [0,300)，双尾并集。"""
    if 300 <= m < 600:
        return "早"
    if 600 <= m < 840:
        return "午"
    if 840 <= m < 1020:
        return "下午茶"
    if 1020 <= m < 1260:
        return "晚"
    return "夜"


def circular_rms(minutes) -> float | None:
    """环形 RMS 偏差（设计 §3.2，单位分钟，保留 1 位小数）。

    n < 2 → None；R < 1e-9（近均匀）→ 直接取均匀分布理论值 415.7。
    """
    n = len(minutes)
    if n < 2:
        return None
    cos_sum = sum(math.cos(2 * math.pi * m / 1440.0) for m in minutes) / n
    sin_sum = sum(math.sin(2 * math.pi * m / 1440.0) for m in minutes) / n
    if math.hypot(cos_sum, sin_sum) < R_NEAR_ZERO:
        return UNIFORM_T9
    mean = (math.atan2(sin_sum, cos_sum) * 1440.0 / (2 * math.pi)) % 1440.0
    sq_sum = 0.0
    for m in minutes:
        d = abs(m - mean)
        if d > 720.0:
            d = 1440.0 - d
        sq_sum += d * d
    return round(math.sqrt(sq_sum / n), 1)


def extract(orders: list[dict]) -> dict:
    """规范化订单列表 → 特征字典（结构见设计 §2.2）。"""
    n = len(orders)
    parsed = []
    for o in orders:
        dt = parse_time((o or {}).get("order_time", ""))
        if dt is not None:
            parsed.append((dt, o))
    n_timevalid = len(parsed)

    minutes = [dt.hour * 60 + dt.minute for dt, _ in parsed]
    weekday = [(dt, o) for dt, o in parsed if dt.weekday() < 5]

    # T1 五时段分布（分母 n_timevalid）
    if n_timevalid:
        counts = {s: 0 for s in SLOTS}
        for m in minutes:
            counts[slot_of_minute(m)] += 1
        t1 = {s: counts[s] / n_timevalid for s in SLOTS}
    else:
        t1 = None

    # T2 工作日午市卡点率（分母 = 工作日订单；窗口 [660,780) 左闭右开）
    if weekday:
        t2 = sum(1 for dt, _ in weekday if 660 <= dt.hour * 60 + dt.minute < 780) / len(weekday)
    else:
        t2 = None

    # T3 早餐规律率（窄窗 [330,570)）；t3_std 只取窗内工作日单
    if n_timevalid:
        t3_ratio = sum(1 for m in minutes if 330 <= m < 570) / n_timevalid
    else:
        t3_ratio = None
    bf_weekday = [
        dt.hour * 60 + dt.minute
        for dt, _ in parsed
        if dt.weekday() < 5 and 330 <= dt.hour * 60 + dt.minute < 570
    ]
    t3_std = circular_rms(bf_weekday)

    # T4 夜宵率 / T5 周末占比（分母 n_timevalid；星期按下单自然日期）
    if n_timevalid:
        t4 = sum(1 for m in minutes if m >= 1260 or m < 300) / n_timevalid
        t5 = sum(1 for dt, _ in parsed if dt.weekday() >= 5) / n_timevalid
    else:
        t4 = None
        t5 = None

    # T6 外卖率（分母 = 全部订单；类型缺失按非外卖计；恒可算 ≥0）
    t6 = sum(1 for o in orders if "麦乐送" in str((o or {}).get("order_type") or "")) / n if n else 0.0

    # T7 单品集中度（按 name 聚合金额；明细缺失或 Σ=0 → None）
    item_amount: dict[str, float] = {}
    total_amount = 0.0
    for o in orders:
        for it in (o or {}).get("items") or []:
            amount = float(it.get("amount") or 0)
            if amount <= 0:
                continue
            name = str(it.get("name") or "").strip()
            item_amount[name] = item_amount.get(name, 0.0) + amount
            total_amount += amount
    if item_amount and total_amount > 0:
        t7 = max(item_amount.values()) / total_amount
        top_item = max(item_amount, key=item_amount.get)
    else:
        t7 = None
        top_item = None

    # T8 麦频（活跃自然月数 = 有单自然月去重，下限 1；不可解析的单不计入月份）
    months = {dt.strftime("%Y-%m") for dt, _ in parsed}
    active_months = max(1, len(months))
    t8 = n / active_months

    # T9 规律度（环形 RMS，分钟）
    t9 = circular_rms(minutes)

    # T10 忠诚度（store_name 聚合；空名不参与，全空名 → 0.0）
    store_count: dict[str, int] = {}
    for o in orders:
        name = str((o or {}).get("store_name") or "").strip()
        if name:
            store_count[name] = store_count.get(name, 0) + 1
    if store_count and n:
        t10 = max(store_count.values()) / n
        top_store = max(store_count, key=store_count.get)
    else:
        t10 = 0.0
        top_store = None

    # meta（max/min 只取解析成功的订单时间；无有效时间 → span_days=0）
    if parsed:
        first_dt = min(dt for dt, _ in parsed)
        last_dt = max(dt for dt, _ in parsed)
        span_days = (last_dt - first_dt).days
        first = first_dt.strftime("%Y-%m-%d %H:%M")
        last = last_dt.strftime("%Y-%m-%d %H:%M")
    else:
        span_days, first, last = 0, "", ""
    meta = {
        "span_days": span_days,
        "active_months": active_months,
        "first": first,
        "last": last,
        "top_store": top_store,
        "top_item": top_item,
    }

    return {
        "n": n,
        "n_timevalid": n_timevalid,
        "t1": t1,
        "t2": t2,
        "t3_ratio": t3_ratio,
        "t3_std": t3_std,
        "t4": t4,
        "t5": t5,
        "t6": t6,
        "t7": t7,
        "t8": t8,
        "t9": t9,
        "t10": t10,
        "meta": meta,
    }
