"""人格层：特征字典 → 八人格四件套（设计 §4）。

判定链命中即停，链尾 P8 恒真兜底；任一操作数为 None → 该人格判否，不猜零。
文案合规线（设计 §4.2）：只做观察与归类，不做健康评价、饮食建议，
不出现「应不应该吃」句式；夜宵人格只写生活状态不写身体后果。
"""

from __future__ import annotations

THRESHOLDS = {
    "scant_min": 5,        # N < 5 → 安慰卡
    "t7_nail": 0.40,       # P1：T7 ≥
    "t4_night": 0.25,      # P2：T4 ≥
    "t3_ratio": 0.35,      # P3：t3_ratio ≥
    "t3_std": 45.0,        # P3：t3_std <（分钟）
    "t2_punch": 0.45,      # P4：T2 ≥
    "t9_regular": 75.0,    # P4：T9 <（分钟）
    "t5_weekend": 0.40,    # P5：T5 ≥
    "t6_delivery": 0.50,   # P5：T6 ≥
    "t1_tea": 0.30,        # P6：T1下午茶 ≥
    "t8_sparse": 1.5,      # P7：T8 <（单/月）
}

# 八人格判定链（设计 §4.2 判定表，优先级 1→8，命中即停）。
# 四件套 = title/emoji/desc/verdict；文案为设计 §4.2 v0 基调稿（10-18 文案专场定稿）。
PERSONAS = [
    {
        "key": "P1",
        "title": "麦门初恋体质",
        "emoji": "🍔",
        "condition": lambda f, t: f.get("t7") is not None and f["t7"] >= t["t7_nail"],
        "desc": [
            "点开菜单，你从不浏览，直接搜索那个名字。",
            "一年到头，购物车里都是同一份心动。",
            "这不是懒得换，是认定了。",
        ],
        "verdict": "菜单换了一轮又一轮，你的心动从没换过。",
    },
    {
        "key": "P2",
        "title": "深夜麦门守护者",
        "emoji": "🌙",
        "condition": lambda f, t: f.get("t4") is not None and f["t4"] >= t["t4_night"],
        "desc": [
            "城市慢慢安静下来的时候，你的订单亮了。",
            "加过的班、追过的剧、睡不着的心事，都有麦当劳陪你收尾。",
        ],
        "verdict": "城市睡了，你的麦乐送还醒着。",
    },
    {
        "key": "P3",
        "title": "晨间通勤麦",
        "emoji": "🌅",
        "condition": lambda f, t: (
            f.get("t3_ratio") is not None
            and f.get("t3_std") is not None
            and f["t3_ratio"] >= t["t3_ratio"]
            and f["t3_std"] < t["t3_std"]
        ),
        "desc": [
            "闹钟响第二遍之前，你已经想好了今天的早餐。",
            "固定的时间、固定的搭配，一天从确定感开始。",
        ],
        "verdict": "地铁还没到站，你的猪柳蛋已经在路上了。",
    },
    {
        "key": "P4",
        "title": "卡点特种兵",
        "emoji": "⏰",
        "condition": lambda f, t: (
            f.get("t2") is not None
            and f["t2"] >= t["t2_punch"]
            and f.get("t9") is not None
            and f["t9"] < t["t9_regular"]
        ),
        "desc": [
            "你的午休像瑞士钟表，误差以分钟计。",
            "工位、门店、餐盘，三点一线零废话。",
        ],
        "verdict": "卡点这件事，你对麦当劳比对打卡机认真。",
    },
    {
        "key": "P5",
        "title": "麦乐送头号收件人",
        "emoji": "🛋️",
        "condition": lambda f, t: (
            f.get("t5") is not None
            and f["t5"] >= t["t5_weekend"]
            and f.get("t6") is not None
            and f["t6"] >= t["t6_delivery"]
        ),
        "desc": [
            "工作日你和麦当劳保持礼貌距离，周末才舍得开门。",
            "门铃一响，你的周末就位了。",
            "从第一餐到宵夜，都有人负责送上门。",
        ],
        "verdict": "你周末的第一个访客是骑手，最后一个，也是。",
    },
    {
        "key": "P6",
        "title": "下午茶哲学家",
        "emoji": "☕",
        "condition": lambda f, t: f.get("t1") is not None and f["t1"]["下午茶"] >= t["t1_tea"],
        "desc": [
            "正午的拥挤属于别人，你偏爱下午三点的空档。",
            "在会议与会议的缝隙里，给自己留一个喘息的位置。",
        ],
        "verdict": "只有下午茶的时间，才真正属于你自己。",
    },
    {
        "key": "P7",
        "title": "麦门幸运儿",
        "emoji": "🍀",
        "condition": lambda f, t: f.get("t8") is not None and f["t8"] < t["t8_sparse"],
        "desc": [
            "你一年到不了几次麦当劳，但每次都记得。",
            "低频不代表不真诚，你的每一次光临都带着新鲜感。",
        ],
        "verdict": "一年来不了几次，但每次都是真心的。",
    },
    {
        "key": "P8",
        "title": "全麦自由人",
        "emoji": "🌀",
        "condition": lambda f, t: True,
        "desc": [
            "你的订单时间散落全谱系：清晨有、深夜有、工作日有、周末也有。",
            "不被时段定义，想吃就是唯一指令。",
        ],
        "verdict": "想吃就吃，你的胃不看日历。",
    },
]

# 安慰卡（n < 5 前置分支，不进判定链；卡片走同一版式，称号按设计 §4.2 表）
SCANT_CARD = {
    "key": "SCANT",
    "title": "样本不足安慰卡",
    "emoji": "🍟",
    "desc": [
        "样本还太少，鉴定所不敢妄下结论。",
        "多来几次，你的作息人格自会浮出水面。",
    ],
    "verdict": "你的麦门之缘，才刚刚开场。",
}


def judge(features: dict) -> dict:
    """特征字典 → 人格字典（结构见设计 §2.2；含安慰卡分支）。"""
    t = THRESHOLDS
    if features.get("n", 0) < t["scant_min"]:
        return {
            "key": SCANT_CARD["key"],
            "title": SCANT_CARD["title"],
            "emoji": SCANT_CARD["emoji"],
            "desc": list(SCANT_CARD["desc"]),
            "verdict": SCANT_CARD["verdict"],
            "is_scant": True,
        }
    for p in PERSONAS:
        if p["condition"](features, t):
            return {
                "key": p["key"],
                "title": p["title"],
                "emoji": p["emoji"],
                "desc": list(p["desc"]),
                "verdict": p["verdict"],
                "is_scant": False,
            }
    # P8 兜底恒真，理论不可达；防御性回退仍输出 P8
    p8 = PERSONAS[-1]
    return {
        "key": p8["key"],
        "title": p8["title"],
        "emoji": p8["emoji"],
        "desc": list(p8["desc"]),
        "verdict": p8["verdict"],
        "is_scant": False,
    }
