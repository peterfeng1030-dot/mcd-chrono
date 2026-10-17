"""生成 8 份人格样例（一人格一份，确定性随机，结果可复现）。

每个 profile 的时间分布、星期权重、外卖比例、菜单池，都是从 persona.py 的
八条判定线反推出来的，目标是稳定命中对应人格。profile key 与
persona.PERSONAS 的 key 一一对应：p1 → P1 … p8 → P8。

判定链是「优先级 1→8、命中即停」，所以每份样例除了踩中自己的线，还必须
不误踩上游各条线。这也是为什么 p4（卡点特种兵）的订单要全部压在 11-13 点：
一旦撒开，T9 就会超过 75 分钟，反而落不到 P4。

仅供 --demo 演示使用，不访问麦当劳官方接口。
"""

from __future__ import annotations

import calendar
import json
import random
from datetime import date, timedelta
from pathlib import Path

# 名称, 分类, 单价, 千卡, 蛋白质g, 脂肪g, 碳水g, 钠mg
MENU = [
    ("巨无霸", "汉堡", 26.5, 550, 25, 30, 45, 1010),
    ("板烧鸡腿堡", "汉堡", 22.0, 420, 24, 18, 40, 850),
    ("麦辣鸡腿堡", "汉堡", 24.0, 570, 27, 33, 42, 1180),
    ("麦香鱼", "汉堡", 16.5, 340, 15, 14, 39, 620),
    ("双层牛柳汉堡", "汉堡", 20.0, 480, 26, 22, 41, 900),
    ("猪柳蛋麦满分", "早餐系列", 14.5, 480, 22, 26, 36, 900),
    ("热香饼", "早餐系列", 12.0, 350, 7, 12, 52, 480),
    ("脆薯饼", "早餐系列", 7.5, 130, 2, 8, 14, 260),
    ("麦辣鸡翅2块", "小食", 13.5, 250, 14, 17, 10, 620),
    ("麦乐鸡5块", "小食", 14.0, 230, 12, 15, 12, 520),
    ("薯条 大", "小食", 13.0, 430, 5, 22, 53, 350),
    ("薯条 中", "小食", 10.0, 330, 4, 17, 41, 260),
    ("玉米杯", "小食", 8.0, 70, 2, 1, 15, 10),
    ("菠萝派", "甜品", 9.0, 250, 3, 14, 28, 180),
    ("麦旋风", "甜品", 11.5, 330, 6, 12, 48, 150),
    ("可口可乐 中", "饮料", 9.0, 150, 0, 0, 38, 15),
    ("零度可乐 中", "饮料", 9.0, 0, 0, 0, 0, 20),
    ("鲜煮咖啡", "饮料", 11.0, 15, 1, 0, 2, 10),
    ("豆浆", "饮料", 8.0, 100, 8, 4, 8, 90),
    ("冰美式", "饮料", 13.0, 15, 0, 0, 3, 10),
]

MENU_BY_NAME = {m[0]: m for m in MENU}
ALL_NAMES = [m[0] for m in MENU]

# 早餐时段（hour < 10）只在早餐池里选，含咖啡——真实的早餐单很少只点一件主食
BREAKFAST_NAMES = ["猪柳蛋麦满分", "热香饼", "脆薯饼", "鲜煮咖啡", "冰美式"]

# 低价配角池：小食 + 甜品 + 饮料，均价约 11 元。p1 用它把 T7 顶过 0.40
SIDE_NAMES = [
    "麦辣鸡翅2块", "麦乐鸡5块", "薯条 大", "薯条 中", "玉米杯",
    "菠萝派", "麦旋风", "可口可乐 中", "零度可乐 中", "鲜煮咖啡", "豆浆", "冰美式",
]

STORES = [
    ("SH0231", "上海南京西路餐厅"),
    ("SH1180", "上海人民广场餐厅"),
    ("SH0455", "上海陆家嘴环路餐厅"),
]

ORDER_TYPES = [("1", "到店取餐"), ("2", "麦乐送")]

PROFILES = {
    # P1：T7 ≥ 0.40。每单必含巨无霸，其余只点低价配角（薯条可乐派），
    # 期望 T7 ≈ 0.6。时段选午晚市，避开早餐（T3）与夜宵（T4）两条上游线；
    # 15 点留 6% 的零嘴单，免得热力条上下午茶一整段是空的。
    "p1": {
        "persona": "P1 麦门初恋体质",
        "seed": 3001,
        "weeks": 52,
        "per_week": ([0, 1, 2, 3], [15, 40, 30, 15]),
        "hours": ([11, 12, 15, 18, 19], [30, 28, 6, 18, 18]),
        "minute": (0, 60),
        "weekday_w": 90, "weekend_w": 15,
        "delivery": [55, 45],
        "size": ([2, 3], [45, 55]),
        "staple": "巨无霸",
        "pool": SIDE_NAMES,
        "coupon": 0.32,
        "note": "麦门初恋体质：每单必点巨无霸，菜单一年不动",
    },
    # P2：T4 ≥ 0.25。21 点后占 45%。周末过半、外卖过半（顺带也满足 P5，
    # 但 P2 在 P5 之前，命中即停）。
    "p2": {
        "persona": "P2 深夜麦门守护者",
        "seed": 2048,
        "weeks": 52,
        "per_week": ([1, 2, 3, 4, 5], [10, 26, 30, 22, 12]),
        "hours": ([8, 12, 15, 19, 22, 23], [6, 20, 6, 20, 26, 22]),
        "minute": (0, 60),
        "weekday_w": 10, "weekend_w": 25,
        "delivery": [40, 60],
        "size": ([2, 3, 4, 5], [20, 36, 28, 16]),
        "coupon": 0.14,
        "note": "深夜麦门守护者：凌晨的订单比午饭还多",
    },
    # P3：T3 占比 ≥ 0.35 且离散 < 45 分钟。8 点前后下单、工作日 96%，
    # 早餐时刻在 0-59 分均匀铺开，圆周 RMS 约 20 分钟。
    "p3": {
        "persona": "P3 晨间通勤麦",
        "seed": 1024,
        "weeks": 52,
        "per_week": ([0, 1, 2, 3], [16, 44, 28, 12]),
        "hours": ([8, 12, 15, 19, 22], [45, 25, 10, 12, 8]),
        "minute": (0, 60),
        "weekday_w": 96, "weekend_w": 10,
        "delivery": [70, 30],
        "size": ([1, 2, 3, 4], [16, 38, 30, 16]),
        "coupon": 0.38,
        "note": "晨间通勤麦：一天从猪柳蛋开始",
    },
    # P4：T2 ≥ 0.45 且 T9 < 75 分钟。全部订单压在 10-13 点，其中落在窗口
    # [660,780) 的占约 74%。工作日 99.8%——周末一撒开 T9 就会涨上去。
    # 外卖率刻意压低，因为卡点的人是到店吃。
    "p4": {
        "persona": "P4 卡点特种兵",
        "seed": 4004,
        "weeks": 52,
        "per_week": ([1, 2, 3], [20, 55, 25]),
        "hours": ([10, 11, 12, 13], [8, 32, 42, 18]),
        "minute": (0, 60),
        "weekday_w": 200, "weekend_w": 1,
        "delivery": [85, 15],
        "size": ([1, 2, 3], [30, 45, 25]),
        "coupon": 0.25,
        "note": "卡点特种兵：午休 90 分钟，误差 3 分钟",
    },
    # P5：T5 ≥ 0.40 且 T6 ≥ 0.50。周末占 49%、外卖 70%，时段卡在 20 点前
    # （21 点后算夜，会误触 P2）。工作日单少且散，T2 上不去。
    # 早 8% / 下午茶 7% 只是给热力条留点形状，离 T3（0.35）、T1茶（0.30）都还很远。
    "p5": {
        "persona": "P5 麦乐送头号收件人",
        "seed": 5005,
        "weeks": 52,
        "per_week": ([0, 1, 2, 3], [20, 40, 28, 12]),
        "hours": ([8, 11, 12, 15, 17, 18, 19, 20], [8, 18, 18, 7, 13, 13, 13, 10]),
        "minute": (0, 60),
        "weekday_w": 25, "weekend_w": 60,
        "delivery": [30, 70],
        "size": ([2, 3, 4], [30, 45, 25]),
        "coupon": 0.22,
        "note": "麦乐送头号收件人：周末的门是用来收外卖的",
    },
    # P6：T1 下午茶 ≥ 0.30。14-16 点占 45%，其余散在早中晚。
    # 工作日 93%（压 T5）、外卖 22%（压 T6）、午市 15%（压 T2）。
    "p6": {
        "persona": "P6 下午茶哲学家",
        "seed": 6006,
        "weeks": 52,
        "per_week": ([1, 2, 3], [25, 50, 25]),
        "hours": ([9, 12, 14, 15, 16, 19, 22], [10, 15, 15, 15, 15, 20, 10]),
        "minute": (0, 60),
        "weekday_w": 95, "weekend_w": 8,
        "delivery": [78, 22],
        "size": ([1, 2, 3], [25, 50, 25]),
        "coupon": 0.30,
        "note": "下午茶哲学家：三点的那杯咖啡才是自己的",
    },
    # P7：T8 < 1.5。按月撒点，13 个自然月各 1-2 单，T8 ≈ 1.2。
    # 菜单用洗牌轮转（even_menu），避免小样本把某单品堆到 40% 以上误触 P1。
    "p7": {
        "persona": "P7 麦门幸运儿",
        "seed": 7007,
        "mode": "monthly",
        "per_month": ([1, 2], [80, 20]),
        "hours": ([8, 12, 15, 19, 22], [25, 30, 15, 22, 8]),
        "minute": (0, 60),
        "weekday_w": 50, "weekend_w": 25,
        "delivery": [60, 40],
        "size": ([1, 2], [30, 70]),
        "even_menu": True,
        "coupon": 0.45,
        "note": "麦门幸运儿：一年来不了几次，但每次都是真心的",
    },
    # P8：兜底人格，必须一条上游线都不踩。五时段都占一点但每段都不过线：
    # 早 18%（<0.35）、夜 14%（<0.25）、下午茶 18%（<0.30）、周末 29%（<0.40）、
    # 外卖 30%（<0.50），午市 28%（<0.45）。
    "p8": {
        "persona": "P8 全麦自由人",
        "seed": 8008,
        "weeks": 52,
        "per_week": ([1, 2], [60, 40]),
        "hours": ([8, 9, 12, 13, 15, 16, 19, 22], [9, 9, 14, 14, 9, 9, 22, 14]),
        "minute": (0, 60),
        "weekday_w": 40, "weekend_w": 40,
        "delivery": [70, 30],
        "size": ([1, 2, 3, 4], [20, 35, 30, 15]),
        "coupon": 0.28,
        "note": "全麦自由人：想吃就吃，胃不看日历",
    },
}

# 兼容旧命令：--sample normal / heavy 仍可用，指向原两个人格
ALIASES = {"normal": "p3", "heavy": "p2"}


def _pick_clock(cfg: dict, rng: random.Random) -> tuple[int, int]:
    """抽一个下单时刻（小时, 分钟）。"""
    hour = rng.choices(cfg["hours"][0], weights=cfg["hours"][1])[0]
    lo, hi = cfg.get("minute", (0, 60))
    return hour, rng.randrange(lo, hi)


def _weekly_points(cfg: dict, rng: random.Random) -> list[tuple[date, int, int]]:
    """按周撒点：先抽目标星期（工作日/周末分开加权），再换算成 [0,6] 内唯一 offset。

    start=2025-10-16 是周五，若把权重直连 offset 会错配星期，所以必须两步走。
    """
    today = date(2026, 10, 15)
    start = today - timedelta(days=364)
    points = []
    for week in range(cfg["weeks"]):
        n = rng.choices(cfg["per_week"][0], weights=cfg["per_week"][1])[0]
        for _ in range(n):
            target_wd = rng.choices(
                [0, 1, 2, 3, 4, 5, 6],
                weights=[cfg["weekday_w"]] * 5 + [cfg["weekend_w"]] * 2,
            )[0]
            offset = (target_wd - start.weekday()) % 7
            day = start + timedelta(days=week * 7 + offset)
            hour, minute = _pick_clock(cfg, rng)
            points.append((day, hour, minute))
    return points


def _monthly_points(cfg: dict, rng: random.Random) -> list[tuple[date, int, int]]:
    """按月撒点：13 个自然月（2025-10 至 2026-10），每月 1-2 单。

    首尾两个月只取落在 365 天窗口内的日子，避免生成未来订单。
    """
    points = []
    y, m = 2025, 10
    while (y, m) <= (2026, 10):
        lo = 16 if (y, m) == (2025, 10) else 1
        hi = 15 if (y, m) == (2026, 10) else calendar.monthrange(y, m)[1]
        n = rng.choices(cfg["per_month"][0], weights=cfg["per_month"][1])[0]
        for _ in range(n):
            day = date(y, m, rng.randint(lo, hi))
            hour, minute = _pick_clock(cfg, rng)
            points.append((day, hour, minute))
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return points


def _pool(hour: int, cfg: dict) -> list[tuple]:
    """这一单的可选菜单池。早餐时段只开早餐池。"""
    if hour < 10:
        return [MENU_BY_NAME[n] for n in BREAKFAST_NAMES]
    return [MENU_BY_NAME[n] for n in cfg.get("pool", ALL_NAMES)]


def _draw(pool: list[tuple], size: int, rng: random.Random, deck: list | None) -> list[tuple]:
    """从菜单池抽 size 件。

    deck 非 None 时走洗牌轮转：一副牌抽完再洗，各 SKU 出现次数被拉平，
    避免小样本（p7 只有十几单）把某个单品堆到 40% 以上而误触 P1。
    """
    if deck is None:
        return rng.sample(pool, min(size, len(pool)))
    if len(deck) < size:
        deck.extend(ALL_NAMES)
        rng.shuffle(deck)
    return [MENU_BY_NAME[deck.pop(0)] for _ in range(size)]


def build(profile: str = "p3") -> dict:
    cfg = PROFILES[ALIASES.get(profile, profile)]
    rng = random.Random(cfg["seed"])
    points = _monthly_points(cfg, rng) if cfg.get("mode") == "monthly" else _weekly_points(cfg, rng)

    orders = []
    oid = 100000
    deck: list = []
    for day, hour, minute in points:
        oid += 1
        pool = _pool(hour, cfg)
        size = rng.choices(cfg["size"][0], weights=cfg["size"][1])[0]

        # even_menu 只对非早餐时段生效：早餐池本来就小，轮转没意义
        use_deck = deck if (cfg.get("even_menu") and hour >= 10) else None

        # p1 每单必含招牌单品，其余名额从配角池抽
        staple = cfg.get("staple")
        if staple:
            picks = [MENU_BY_NAME[staple]] + _draw(pool, size - 1, rng, use_deck)
        else:
            picks = _draw(pool, size, rng, use_deck)

        items = []
        for name, cat, price, kcal, p, f, c, na in picks:
            qty = 1 if rng.random() < 0.85 else 2
            items.append(
                {
                    "name": name,
                    "category": cat,
                    "qty": qty,
                    "unit_price": price,
                    "amount": round(price * qty, 2),
                    "kcal": kcal * qty,
                    "protein": p * qty,
                    "fat": f * qty,
                    "carb": c * qty,
                    "sodium": na * qty,
                }
            )

        gross = round(sum(i["amount"] for i in items), 2)
        has_coupon = rng.random() < cfg["coupon"]
        discount = round(rng.choice([3, 5, 6, 8, 10, 12]), 2) if has_coupon else 0.0
        delivery = 0.0
        otype_code, otname = rng.choices(ORDER_TYPES, weights=cfg["delivery"])[0]
        if otype_code == "2":
            delivery = 6.0 if gross < 40 else 0.0

        store_code, store_name = rng.choice(STORES)
        orders.append(
            {
                "order_id": f"MC{oid}",
                "order_time": f"{day.isoformat()} {hour:02d}:{minute:02d}",
                "order_type": otname,
                "store_code": store_code,
                "store_name": store_name,
                "items": items,
                "gross": gross,
                "discount": discount,
                "delivery_fee": delivery,
                "paid": round(gross - discount + delivery, 2),
                "coupon_used": has_coupon,
            }
        )

    orders.sort(key=lambda o: o["order_time"])
    return {
        "source": "demo",
        "profile": profile,
        "persona": cfg["persona"],
        "generated_at": "2026-10-15",
        "note": f"{cfg['note']}（构造数据，非真实订单）",
        "orders": orders,
    }


if __name__ == "__main__":
    here = Path(__file__).parent
    for name in PROFILES:
        data = build(name)
        out = here / f"demo_orders_{name}.json"
        out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"已写入 {out.name}，共 {len(data['orders'])} 单 —— {data['persona']}")
