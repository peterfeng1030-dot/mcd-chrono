"""生成 demo 订单样例（确定性随机，结果可复现）。

复制自 mcaudit/fixtures/make_fixture.py，按设计 §8 三处改造：
  1. 星期维度：先按 [工作日×5 / 周末×2] 权重抽目标星期，再换算成 [0,6] 内
     唯一 offset（start=2025-10-16 为周五，若把权重直连 offset 会错配星期）；
     normal 工作日 96%，heavy 周末 50%；
  2. ORDER_TYPES 外卖权重从全局常量改为每 profile 一项（delivery，外卖率可调）；
  3. normal 早餐小时分钟保持 0-59 均匀（T3_std ≈ 17 < 45，P3 稳定命中）。

仅供 --demo 演示使用，不访问麦当劳官方接口。
"""

from __future__ import annotations

import json
import random
from datetime import date, timedelta
from pathlib import Path

# 名称, 分类, 单价, 千卡, 蛋白质g, 脂肪g, 碳水g, 钠mg（与 mcaudit 菜单一致）
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

STORES = [
    ("SH0231", "上海南京西路餐厅"),
    ("SH1180", "上海人民广场餐厅"),
    ("SH0455", "上海陆家嘴环路餐厅"),
]

ORDER_TYPES = [("1", "到店取餐"), ("2", "麦乐送")]

PROFILES = {
    # 普通用户：一周一两次、早餐为主（预期 P3 晨间通勤麦，设计 §8）
    "normal": {
        "seed": 1024,
        "weeks": 52,
        "per_week": ([0, 1, 2, 3], [16, 44, 28, 12]),          # ≈71 单/年
        "hours": ([8, 12, 15, 19, 22], [45, 25, 10, 12, 8]),   # t3_ratio≈0.45、T4≈0.08
        "weekday_w": 96, "weekend_w": 10,                      # 工作日 96%（周末 ≈4%）
        "delivery": [70, 30],                                   # T6≈0.30
        "size": ([1, 2, 3, 4], [16, 38, 30, 16]),
        "coupon": 0.38,
        "note": "演示样例：普通用户（晨间通勤）",
    },
    # 重度用户：频次高、深夜多（预期 P2 深夜麦门守护者，设计 §8）
    "heavy": {
        "seed": 2048,
        "weeks": 52,
        "per_week": ([1, 2, 3, 4, 5], [10, 26, 30, 22, 12]),   # ≈156 单/年
        "hours": ([8, 12, 15, 19, 22, 23], [6, 20, 6, 20, 26, 22]),  # T4≈0.48
        "weekday_w": 10, "weekend_w": 25,                      # 周末 50%（10×5 : 25×2）
        "delivery": [40, 60],                                   # T6≈0.60
        "size": ([2, 3, 4, 5], [20, 36, 28, 16]),
        "coupon": 0.14,
        "note": "演示样例：重度用户（深夜守护者）",
    },
}


def build(profile: str = "normal") -> dict:
    cfg = PROFILES[profile]
    rng = random.Random(cfg["seed"])
    today = date(2026, 10, 15)
    start = today - timedelta(days=364)

    orders = []
    oid = 100000
    for week in range(cfg["weeks"]):
        n = rng.choices(cfg["per_week"][0], weights=cfg["per_week"][1])[0]
        for _ in range(n):
            oid += 1
            # 改造点 1：星期按日历星期加权抽取（替换原 randint(0,6)）。
            # 先抽目标星期（工作日 weekday_w ×5 / 周末 weekend_w ×2），
            # 再换算成 [0,6] 内唯一 offset，使 day 恰落该星期。
            target_wd = rng.choices(
                [0, 1, 2, 3, 4, 5, 6],
                weights=[cfg["weekday_w"]] * 5 + [cfg["weekend_w"]] * 2,
            )[0]
            offset = (target_wd - start.weekday()) % 7
            day = start + timedelta(days=week * 7 + offset)
            hour = rng.choices(cfg["hours"][0], weights=cfg["hours"][1])[0]
            minute = rng.randrange(0, 60)   # 改造点 3：早餐分钟保持 0-59 均匀

            # 早餐时段只从早餐系列里选
            pool = [m for m in MENU if (m[1] == "早餐系列")] if hour < 10 else MENU
            size = rng.choices(cfg["size"][0], weights=cfg["size"][1])[0]
            picks = rng.sample(pool, min(size, len(pool)))

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
            # 改造点 2：外卖权重按 profile
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
        "generated_at": "2026-10-15",
        "note": f"{cfg['note']}（构造数据，非真实订单）",
        "orders": orders,
    }


if __name__ == "__main__":
    here = Path(__file__).parent
    for name in PROFILES:
        data = build(name)
        out = here / (f"demo_orders_{name}.json")
        out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"已写入 {out.name}，共 {len(data['orders'])} 单")
