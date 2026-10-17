"""券层：把鉴定出的人格，翻译成「这几张券为什么适合你」（设计 §10）。

设计前提（务必先读懂这段，改代码前不要越过）：

1. **只读不写。** 本模块只调 `available-coupons`（查询可领券），绝不调用
   `auto-bind-coupons`（自动领取）、`create-order`（下单）、`draw-lottery`（抽奖）、
   `mall-create-order`（商城兑换）。这一条由 `docs/batches/tests/test_coupons.py`
   的源码断言守着，删断言前先想清楚为什么要破这条线。
2. **券接口只给四个字段**：`couponName` / `couponImage` / `couponStatus` / `label`。
   没有面额、没有门槛、没有有效期、没有适用门店、没有是否支持外送。所以这里的「匹配」
   只能是**按券名里的品类与促销字样**去对人格的时段偏好，不是算能省多少钱——
   算不出，也不假装算得出。报告里的文案必须保持这个诚实度。
3. **不给购买建议。** 输出是「这张券的品类落在你的高峰时段」，不是「你应该买这个」。
   免责声明见 `card.DISCLAIMER` 与本模块 `CAUTION_DEFAULT`。

人格 → 偏好标签的权重表是纯数据，改权重不影响任何判定链；顺序稳定（分数降序 + 券名升序），
同一份输入永远给出同一份推荐。
"""

from __future__ import annotations

# ---------------------------------------------------------------- 标签体系

CATEGORY_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("breakfast", ("早餐", "猪柳蛋", "松饼", "油条", "豆浆", "粥", "炒蛋", "蛋堡", "早晨")),
    ("coffee", ("咖啡", "美式", "拿铁", "卡布奇诺", "摩卡", "冷萃")),
    ("dessert", ("麦旋风", "新地", "圣代", "冰淇淋", "甜筒", "派", "提拉米苏", "奶昔")),
    ("snack", ("薯条", "薯饼", "麦乐鸡", "鸡块", "鸡翅", "鸡腿", "小食")),
    ("drink", ("可乐", "雪碧", "柠檬", "奶茶", "果茶", "果汁")),
    ("main", ("巨无霸", "麦辣", "板烧", "双层", "安格斯", "汉堡", "套餐", "饭", "卷")),
    ("delivery", ("外送", "麦乐送", "配送", "到家")),
]

PROMO_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("free", ("免费", "0元", "赠")),
    ("bogo", ("买一送一", "第二份", "加一元", "第二件")),
    ("discount", ("元", "折", "特价", "立减", "直降", "券后")),
]

TAG_CN = {
    "breakfast": "早餐",
    "coffee": "咖啡",
    "dessert": "甜品冰品",
    "snack": "小食",
    "drink": "饮料",
    "main": "正餐",
    "delivery": "外送",
    "free": "免费单品",
    "bogo": "买一送一",
    "discount": "直降特价",
}

# 每张券的单独说明：只解释「它为什么落在你的偏好里」，一句话，不复述人格段落。
# 人格段落（PERSONA_PREF[...]["why"]）在整块开头说一次，避免同一句话重复三遍。
TAG_NOTE = {
    "breakfast": "你的高峰在早上，这类券是你天天用得上的那一种。",
    "coffee": "早上顺带一杯，和你那笔早餐是同一个场景。",
    "dessert": "你偏爱的时段里，点得最多的就是这类。",
    "snack": "小份，不占你正餐的名额。",
    "drink": "随手加一杯，是单笔里最容易用掉的。",
    "main": "一份正经正餐，到点就能用，不用挑。",
    "delivery": "能叠在你外送那一单上，才算真的省。",
    "free": "不用凑单、不用满额，一次就能用掉。",
    "bogo": "两份的量，一次带走，不用等下一次。",
    "discount": "直接减，不用自己算门槛。",
}


def classify(name: str) -> list[str]:
    """券名 → 标签列表（品类标签在前，促销标签在后；未命中返回空列表）。"""
    if not name:
        return []
    tags = [tag for tag, kws in CATEGORY_RULES if any(k in name for k in kws)]
    tags += [tag for tag, kws in PROMO_RULES if any(k in name for k in kws)]
    return tags


# ---------------------------------------------------------------- 人格 → 偏好

def _pct(f: dict | None, key: str, default: str = "—") -> str:
    if not f:
        return default
    v = f.get(key)
    return default if v is None else f"{v * 100:.0f}%"


def _tea_pct(f: dict | None) -> str:
    if not f or not f.get("t1"):
        return "—"
    return f"{f['t1']['下午茶'] * 100:.0f}%"


def _t8(f: dict | None, default: str = "—") -> str:
    if not f or f.get("t8") is None:
        return default
    return f"{f['t8']:.1f}"


# 每个模式三项：weights（标签→权重）、why（为什么是这几张，允许引用特征数字）、caution（下单前的提醒）。
PERSONA_PREF: dict[str, dict] = {
    "P1": {
        "weights": {"free": 3, "discount": 3, "bogo": 2},
        "why": lambda f: (
            f"你的单品集中度 {_pct(f, 't7')}，一年点的基本都是同一样。"
            "满减要凑单，对你没用；指定单品的券才是你能用掉的。"
        ),
        "caution": "单品券通常限指定餐品，领之前看清是哪一个。",
    },
    "P2": {
        "weights": {"snack": 3, "dessert": 3, "drink": 2, "discount": 1, "main": 1},
        "why": lambda f: (
            f"你 {_pct(f, 't4')} 的订单落在 21 点之后。夜里点的是陪你熬一会儿的小食和甜品，"
            "不是一份正经正餐，所以优先给你小份的东西。"
        ),
        "caution": "不少券有使用时段限制，深夜能不能用要看券面说明。",
    },
    "P3": {
        "weights": {"breakfast": 4, "coffee": 2, "discount": 1},
        "why": lambda f: (
            f"你的早餐时段占比 {_pct(f, 't3_ratio')}，一天里最确定的一单在那里。"
            "早餐券是你唯一天天都用得上的一类。"
        ),
        "caution": "早餐券多数限上午时段核销，过点就作废。",
    },
    "P4": {
        "weights": {"main": 4, "discount": 2, "snack": 1},
        "why": lambda f: (
            f"你的工作日午市卡点率 {_pct(f, 't2')}，午休那一单几乎不犹豫。"
            "正餐类券对你最有用——不用挑，到点就走。"
        ),
        "caution": "午市高峰核销可能排队，赶时间就别挑需要现做的。",
    },
    "P5": {
        "weights": {"delivery": 4, "main": 2, "bogo": 2},
        "why": lambda f: (
            f"你周末下单占 {_pct(f, 't5')}、外送占 {_pct(f, 't6')}。"
            "能叠加外送的券对你价值最高，其次是适合一次点够的正餐券。"
        ),
        "caution": "券面不标是否支持麦乐送，下单前在门店页确认能否叠加。",
    },
    "P6": {
        "weights": {"dessert": 4, "coffee": 3, "snack": 1},
        "why": lambda f: (
            f"你 {_tea_pct(f)} 的订单落在下午茶时段。"
            "这个时段点的本来就是甜品和咖啡，券也该往这儿配。"
        ),
        "caution": "下午茶的券多与正餐券互斥，同单只能用一张。",
    },
    "P7": {
        "weights": {"free": 3, "bogo": 3, "discount": 2},
        "why": lambda f: (
            f"你月均 {_t8(f)} 单，来得不多。"
            "要挑那种一次就能用掉、不用凑单、不用等下一次的券。"
        ),
        "caution": "券有有效期，低频用户最容易放到过期。",
    },
    "P8": {
        "weights": {"discount": 2, "free": 2, "bogo": 2, "main": 1, "snack": 1},
        "why": lambda f: (
            "你的下单时间散在全天，没有单一高峰，所以不按时段配，"
            "按通用力度配——能用在不同场景的券优先。"
        ),
        "caution": "通用券的适用范围差别大，用之前看清限门店还是限品类。",
    },
    "SCANT": {
        "weights": {"free": 2, "discount": 2, "bogo": 1},
        "why": lambda f: (
            "你的样本还太少，作息没法定型，先按「一次就能用掉」的思路配券，"
            "等订单攒够了再回头看更准的。"
        ),
        "caution": "券有有效期，先领一张就够，别一次领满。",
    },
}

CAUTION_DEFAULT = "券的可用门店、门槛与有效期以麦当劳 App 为准，本项目不代领、不代下单。"


# ---------------------------------------------------------------- 结构归一

def normalize(payload) -> list[dict]:
    """把 available-coupons 的返回归一成 [{name, status, label}]。

    兼容两种形态：`{"data": [...]}` 与 `{"data": {"coupons": [...]}}`。
    字段缺失不抛错——券接口是小接口，字段漂移不该让整份鉴定失败。
    """
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    if isinstance(data, dict):
        data = data.get("coupons")
    if not isinstance(data, list):
        return []
    out = []
    for item in data:
        if not isinstance(item, dict):
            continue
        name = (item.get("couponName") or item.get("name") or "").strip()
        if not name:
            continue
        out.append(
            {
                "name": name,
                "status": item.get("couponStatus") or "",
                "label": item.get("label") or "",
            }
        )
    return out


# ---------------------------------------------------------------- 排序

def score(persona_key: str, name: str) -> int:
    weights = PERSONA_PREF.get(persona_key, PERSONA_PREF["P8"])["weights"]
    return sum(weights.get(tag, 0) for tag in classify(name))


def rank(persona_key: str, coupons: list[dict], features: dict | None = None, top_n: int = 3) -> list[dict]:
    """按人格偏好排序，返回前 top_n 条带理由的推荐。

    `matched` 只列**与该人格权重表相交**的标签：一张券可能同时是「早餐」和「正餐」，
    但对午市人格来说只有「正餐」这一条成立，写全反而会让人看出推荐是乱的。
    只返回分数 > 0 的券：一条都没命中时宁可空着，也不硬凑。
    """
    pref = PERSONA_PREF.get(persona_key) or PERSONA_PREF["P8"]
    weights = pref["weights"]
    if not coupons:
        return []
    scored = []
    for c in coupons:
        s = score(persona_key, c["name"])
        if s > 0:
            tags = classify(c["name"])
            scored.append(
                {
                    "name": c["name"],
                    "label": c.get("label", ""),
                    "tags": tags,
                    "hit": [t for t in tags if t in weights],
                    "score": s,
                }
            )
    scored.sort(key=lambda x: (-x["score"], x["name"]))
    picked = scored[:top_n]
    for item in picked:
        item["matched"] = "、".join(TAG_CN.get(t, t) for t in item["hit"]) or "—"
        item["note"] = TAG_NOTE.get(item["hit"][0], "") if item["hit"] else ""
    return picked


def why_for(persona_key: str, features: dict | None = None) -> str:
    """整块开头那段话：这个人的作息为什么导向这类券（同一份推荐里只说一次）。"""
    pref = PERSONA_PREF.get(persona_key) or PERSONA_PREF["P8"]
    return pref["why"](features)


def caution_for(persona_key: str) -> str:
    pref = PERSONA_PREF.get(persona_key) or PERSONA_PREF["P8"]
    return pref.get("caution") or CAUTION_DEFAULT


# ---------------------------------------------------------------- 取数

def fetch_coupons(client) -> list[dict]:
    """调 available-coupons 取可领券。失败抛 McpError，由调用方决定是否降级。"""
    return normalize(client.call_tool("available-coupons", {}))


def load_demo() -> list[dict]:
    """读 fixtures/demo_coupons.json（2026-10-17 实测抓取的券名，仅作离线样例）。"""
    import json
    from pathlib import Path

    path = Path(__file__).resolve().parent / "fixtures" / "demo_coupons.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return normalize({"data": data.get("coupons", [])})
