# 麦门作息鉴定（mcd-chrono）· 设计文档

| 项 | 值 |
|---|---|
| 版本 | v1.1（2026-10-17，评审修复轮） |
| 需求来源 | `docs/requirements/REQ-麦门作息鉴定.md`（v1.1，唯一需求依据） |
| 对齐基线 | `mcaudit/docs/PRD-麦门作息鉴定.md`（v1.0 冻结；冲突处以 REQ §5 修订为准） |
| 批次 | mcd-chrono-initial（`docs/batches/mcd-chrono-initial.md` §2） |
| 复用源 | `D:/WorkBuddySpace/AI/mcaudit`（只读，不写入；已逐行验证可平移） |

---

## 1. 方案与理由

**方案**：Python 3.10+ 纯标准库 CLI 单进程管道。数据源（麦当劳官方 MCP 或内置 fixture）→
规范化订单列表 → 十项时间特征 T1-T10 → 八人格优先级链 → 750×1100 离线单文件 HTML 鉴定卡。
无第三方依赖、无网络渲染、无状态。

**理由**：

1. 零依赖是赛事传播的硬需求——路人 clone 即跑（PRD 第五章：比赛只认 GitHub 仓库）。
2. 数据层已被 mcaudit 验证过真实接口（`mcaudit/mcp_client.py` 握手/SSE/401/429 全处理），
   平移比重写风险低。
3. 全链路纯函数（订单列表进、特征字典出、人格字典出、HTML 字符串出），
   断言式测试即可覆盖，不需要测试框架以外的任何设施。

**最近先例**：本设计 = mcaudit 的管道形态（`mcaudit/mcaudit.py` main 管道：load_demo/build_live →
analyze → render → out/）换分析内核与输出形态。对齐点：CLI 参数与退出码（mcaudit.py L257-303）、
HTML 离线渲染与纯 CSS 条形图（report.py L130-140）、免责底行（report.py L10-14）、
fixture 确定性生成（fixtures/make_fixture.py L85-162）。
偏离点：analyze 换成 features+persona 两级、报告页换成鉴定卡（产品方向变更，REQ v1.1 立项依据）。

## 2. 数据流与模块接口契约

### 2.1 数据流总览

```
--demo:  fixtures/demo_orders_{normal,heavy}.json ──┐
                                                    ├→ 订单列表 list[dict]
--live:  MCP order-list + query-order(逐笔,可失败) ──┘   (normalize_order 结构)
        fetch.py
              │
              ▼
        features.extract(orders) → 特征字典（T1-T10 + meta）
              │
              ▼
        persona.judge(features)  → 人格四件套（或安慰卡）
              │
              ▼
        card.render_*            → out/chrono_card.html
                                  → out/chrono_report.html
                                  → out/chrono_report.md
                                  →（--share）终端分享文案
```

### 2.2 模块契约（六个模块 + fixtures）

| 模块 | 对外接口 | 输入 → 输出 | 来源 |
|---|---|---|---|
| mcp_client.py | `McpClient` / `from_env()` / `McpError` | token → MCP RPC 结果 | 原样平移 `mcaudit/mcp_client.py`（169 行，零改动） |
| fetch.py | `fetch_orders(client)` / `normalize_order(summary, detail)` / `load_demo(profile)` / `_first` / `_dig` / `_as_list` / `_to_float` | client → 规范化订单 | 平移 `mcaudit/mcaudit.py` L36-41、L44-105、L133-184、L216-222（剔除营养函数） |
| features.py | `extract(orders) -> dict` | 规范化订单列表 → 特征字典 | 新增 |
| persona.py | `judge(features) -> dict` / `THRESHOLDS` | 特征字典 → 人格四件套 | 新增 |
| card.py | `render_card(result)` / `render_report(result)` / `render_markdown(result)` | 结果字典 → HTML/MD 字符串 | 新增（CSS 先例 report.py L157-196） |
| main.py | `main() -> int`（CLI 入口） | argparse → 编排 + 落盘 | 自 mcaudit.py L257-303 精简改写 |

**规范化订单结构**（normalize_order 输出，与 mcaudit 逐字段一致，`mcaudit/mcaudit.py` L172-184）：

```python
{
  "order_id": str, "order_time": "YYYY-MM-DD HH:MM[:SS]", "order_type": str,
  "store_name": str, "store_code": str,
  "items": [{"name": str, "category": str, "qty": int, "unit_price": float, "amount": float, …}],
  "gross": float, "discount": float, "delivery_fee": float, "paid": float, "coupon_used": bool,
}
```

特征层只消费 `order_time` / `order_type` / `store_name` / `items[].name` / `items[].amount`，
其余字段平移保留（v2 营养维度的零成本接口，也是「原样平移」的复用保证）。

**特征字典结构**（features.extract 输出）：

```python
{
  "n": int,                 # 订单总数
  "n_timevalid": int,       # 时间可解析的订单数（T1-T6/T9 的分母）
  "t1": {"早": f, "午": f, "下午茶": f, "晚": f, "夜": f} | None,
  "t2": float | None, "t3_ratio": float | None, "t3_std": float | None,
  "t4": float | None, "t5": float | None, "t6": float | None,
  "t7": float | None, "t8": float | None, "t9": float | None, "t10": float | None,
  "meta": {"span_days": int, "active_months": int, "first": str, "last": str,
           "top_store": str, "top_item": str},
}
```

`None` 语义 = 分母为零或明细缺失（不可判），人格判定中含 `None` 的条件一律判否，不猜零。

**人格字典结构**（persona.judge 输出）：

```python
{"key": str, "title": str, "emoji": str, "desc": [str, …],  # 2-3 句
 "verdict": str, "is_scant": bool}
```

**结果字典结构**（main.py 组装，card.py 三个渲染函数的输入）：

```python
{"source": "demo" | "live",   # 数据来源；"demo" → 卡片右上角 45° 水印（§5）
 "features": {特征字典},       # features.extract 输出（本节上文）
 "persona": {人格字典}}        # persona.judge 输出（本节上文）
```

**时间解析**：features.py 内置 `parse_time`（先例 `mcaudit/audit.py` L22-28 的三格式 +
`%Y-%m-%dT%H:%M:%S`），解析失败返回 None，该单计入 `n` 但不计入 `n_timevalid`。

## 3. T1-T10 特征精确定义（含 §5 两处口径修订的数学定义）

**基础量**：每单取 `m = 60·hour + minute ∈ [0, 1440)`（分钟数）；星期取订单自然日期的
`weekday()`（周一=0 … 周日=6）；工作日 = weekday() < 5。**星期归属用下单自然日期，不因
21-5 跨零点窗口改日期**（凌晨 1 点的单仍算当天，周末凌晨单算周末）。

### 3.1 §5 修订②：夜宵窗口的跨零点归属（适用于 T1 / T4）

时段划分按分钟数落窗（左闭右开，全天五窗无缝Partition）：

| 时段 | 分钟窗口 | 说明 |
|---|---|---|
| 早 | [300, 600) | 5:00–9:59 |
| 午 | [600, 840) | 10:00–13:59 |
| 下午茶 | [840, 1020) | 14:00–16:59 |
| 晚 | [1020, 1260) | 17:00–20:59 |
| 夜 | [1260, 1440) ∪ [0, 300) | 21:00–23:59 与 0:00–4:59，**两段并集为一窗** |

即 `slot(m) = 夜 当且仅当 m ≥ 1260 或 m < 300`。23:00 与 01:00 同属夜窗，无需拆窗、
无需改日期。此窗口函数与 `mcaudit/audit.py` L31-40、`make_fixture.py` L49-58 的
meal_slot 行为一致（该实现本就覆盖双尾）。

- **T1 五时段分布**：`t1[slot] = #(slot 内订单) / n_timevalid`，五值和为 1。
  `n_timevalid = 0` 时 `t1 = None`。
- **T4 夜宵率**：`#(m ≥ 1260 或 m < 300) / n_timevalid`。

### 3.2 §5 修订①：T9 规律度 = 环形时间 RMS 偏差（单位分钟）

先定义环形时间统计（T3_std 复用同一函数）：

```text
θᵢ = 2π·mᵢ/1440
C = (1/n)·Σcos θᵢ，S = (1/n)·Σsin θᵢ，R = √(C² + S²)
μ = (atan2(S, C) · 1440 / 2π) mod 1440          # 环形均值方向（分钟）
dᵢ = min(|mᵢ − μ|, 1440 − |mᵢ − μ|)             # 每单到 μ 的环形距离（分钟）
T9 = √( (1/n)·Σdᵢ² )                            # 环形 RMS 偏差，单位分钟
```

- 语义：你的下单时刻围绕「典型时刻」平均偏离多少分钟；越小越规律。
- **跨零点正确**：23:59 与 00:01 两单 → μ=0:00、d=1、T9=1.0 分钟（普通标准差会算出
  ≈11.9 小时的荒谬值，即 REQ §5 指出的失真）。
- **量尺参考**：均匀分布理论值 ≈415.7（1440/√12 ≈ 415.69）——这是量尺参考，非硬上界：按本式
  对跖双峰分布可达 ≈455（720·√0.4），质量对半分于对跖两点的极限 ≈509（720/√2）。输出不做
  截断（公式原样）；阈值（如 P4 的 75 分钟）远低于该量级，判定语义不受影响。
- 退化保护：`n_timevalid < 2` → T9 = None；`R < 1e-9`（均值方向数值上不可定，近均匀分布）
  → T9 = 415.7（直接取均匀分布理论值，确定性输出）。
- 保留 1 位小数。

被否方案见 §11.1。

### 3.3 T1-T10 逐项定义表

| # | 特征 | 精确定义 | 分母为空时 |
|---|---|---|---|
| T1 | 五时段分布 | 见 §3.1；五键 `早/午/下午茶/晚/夜` 各占比 | None |
| T2 | 工作日午市卡点率 | `#(工作日 ∧ m ∈ [660, 780)) / #工作日订单`；窗口 = 11:00–12:59（左闭右开） | None |
| T3 | 早餐规律率 | `t3_ratio = #(m ∈ [330, 570)) / n_timevalid`（5:30–9:29 窗口，比 T1 早窗更窄）；`t3_std` = **工作日**早餐窗内订单的环形 RMS 偏差（§3.2 同式，分钟） | t3_std：窗内工作日单 < 2 → None |
| T4 | 夜宵率 | 见 §3.1 | None |
| T5 | 周末占比 | `#(周六 ∪ 周日) / n_timevalid`。v1 不含「周五 18 点后」（PRD 标注可选，判定写死：不含） | None |
| T6 | 外卖率 | `#(order_type 含"麦乐送") / n`；分母用全部订单（类型缺失按非外卖计） | 恒可算（≥0） |
| T7 | 单品集中度 | `max(单品金额合计) / Σ全部 items[].amount`，单品按 name 聚合 | 明细缺失或 Σ=0 → None（见 §7 降级） |
| T8 | 麦频 | `n / active_months`，`active_months` = 有 ≥1 单的自然月数（YYYY-MM 去重，下限 1）；不可解析时间的单不计入月份，active_months=0 时按下限取 1（→ T8=n） | 恒可算 |
| T9 | 规律度 | §3.2 环形 RMS 偏差，分钟 | 见 §3.2 |
| T10 | 忠诚度 | `max(门店单数) / n`，门店按 store_name 聚合，空名不参与聚合 | 全空名 → 0.0 |

`meta.span_days` = `(max(时间) − min(时间)).days`（先例 `mcaudit/audit.py` L179-183；
max/min 只取解析成功的订单时间，无有效时间时 span_days=0）；
`meta.top_store` / `meta.top_item` 供卡片三数字格与 report 附录使用。

## 4. 八人格判定引擎（persona.py）

### 4.1 判定链

```python
if features["n"] < THRESHOLDS["scant_min"]:      # < 5 单
    return SCANT_CARD                             # 安慰卡，不进链
for persona in CHAIN:                             # 优先级 1→8
    if persona.match(features):                   # 任一操作数为 None → False
        return persona
```

命中即停；链尾 P8 恒真兜底。阈值全部集中在 `THRESHOLDS` 常量表（改一处即改全局）：

```python
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
```

### 4.2 八人格判定表 + 文案四件套（v0 基调稿，10-18 文案专场定稿，对应 A7）

| 序 | 人格 | emoji | 条件 | 描述（2-3 句，v0） | 判词（v0） |
|---|---|---|---|---|---|
| P1 | 巨无霸钉子户 | 🍔 | T7 ≥ 0.40 | 在你的麦当劳宇宙里，其他产品都是路人。菜单换了几轮，你的购物车纹丝不动。这种专注放在哪里都是稀缺品质。 | 你不是在吃麦当劳，你是在吃那一样东西。 |
| P2 | 深夜麦门守护者 | 🌙 | T4 ≥ 0.25 | 城市慢慢安静下来的时候，你的订单亮了。加过的班、追过的剧、睡不着的心事，都有麦当劳陪你收尾。 | 城市睡了，你的麦乐送还醒着。 |
| P3 | 晨间通勤麦 | 🌅 | t3_ratio ≥ 0.35 且 t3_std < 45 | 闹钟响第二遍之前，你已经想好了今天的早餐。固定的时间、固定的搭配，一天从确定感开始。 | 地铁还没到站，你的猪柳蛋已经在路上了。 |
| P4 | 卡点特种兵 | ⏰ | T2 ≥ 0.45 且 T9 < 75 | 你的午休像瑞士钟表，误差以分钟计。工位、门店、餐盘，三点一线零废话。 | 老板还没起身，你已经到店了。 |
| P5 | 周末宅家派 | 🛋️ | T5 ≥ 0.40 且 T6 ≥ 0.50 | 工作日的你和麦当劳保持礼貌距离，周末才大方打开家门。你的周末从一份外卖开始，也常常由它结束。 | 周末的门，是用来收外卖开的。 |
| P6 | 下午茶哲学家 | ☕ | T1下午茶 ≥ 0.30 | 正午的拥挤属于别人，你偏爱下午三点的空档。在会议与会议的缝隙里，给自己留一个喘息的位置。 | 只有下午茶的时间，才真正属于你自己。 |
| P7 | 麦门幸运儿 | 🍀 | T8 < 1.5 单/月 | 你一年到不了几次麦当劳，但每次都记得。低频不代表不真诚，你的每一次光临都带着新鲜感。 | 一年来不了几次，但每次都是真心的。 |
| P8 | 全麦自由人 | 🌀 | 兜底（恒真） | 你的订单时间散落全谱系：清晨有、深夜有、工作日有、周末也有。不被时段定义，想吃就是唯一指令。 | 想吃就吃，你的胃不看日历。 |
| — | 样本不足安慰卡 | 🍟 | n < 5（先于链） | 样本还太少，鉴定所不敢妄下结论。多来几次，你的作息人格自会浮出水面。 | 你的麦门之缘，才刚刚开场。 |

文案合规线（PRD 第十章，硬约束）：只做观察与归类；不出现健康评价、饮食建议、
「应不应该吃」句式；夜宵人格只写生活状态不写身体后果；零出现其他品牌；
不触碰优惠券维度。安慰卡 `is_scant = true`，卡片走同一版式（§5）。

## 5. 鉴定卡版式规格（card.py）

**规格**：750 × 1100 px 单文件离线 HTML，无任何外部资源（无图片、无字体链接、无 JS 请求；
条形图纯 CSS，先例 `mcaudit/report.py` L130-140）。字体栈
`-apple-system,"PingFang SC","Microsoft YaHei",Segoe UI,sans-serif`（先例 report.py L167）。
色板：麦黄 `#FFC72C`（主点缀/条形填充）、麦红 `#DA291C`（强调/最高时段条/判词）、
正文深灰 `#1C2024`、次要 `#5B6570`、卡底 `#FFFDF5`。

**七段版式（自上而下，PRD 第四章；③b 为 2026-10-17 追加）**：

| 段 | 内容 | 规格要点 |
|---|---|---|
| ① 标识行 | `MCD CHRONOTYPE REPORT`（字距加宽小字）+ `麦门作息鉴定所` | 高约 64px 麦黄底条，下沿 4px 麦红线 |
| ② 称号区 | emoji（约 96px）+ 称号（约 44px 粗体）；副行 `样本 N 单 · 麦龄 X 天` 小字 | 居中 |
| ③ 五时段条形图 | 5 行：时段名（48px 标签）+ CSS 条（高 18px 圆角）+ 占比百分数 | 最高时段条用麦红，其余麦黄；占比取一位小数 |
| ③b 24 小时热力条 | 24 根柱：柱高与色深同时编码该钟点密度（`height = 12% + 88%·ratio`，`alpha = 0.12 + 0.88·ratio`）；底轨 `#F2ECDD`；下接 0/6/12/18/23 刻度与峰值行 | 数据取 `features["hour_hist"]`（长度 24，分母 `n_timevalid`）；仅展示用，**不参与人格判定** |
| ④ 三数字格 | 累计订单 `n` / 麦龄天数 `span_days` / 最忠门店 `top_store` + T10 百分比 | 三列 grid；门店名超长省略号截断 |
| ⑤ 描述 + 判词 | 描述 15px 行高 1.7 深灰；判词约 20px 麦红粗体，金句位 | 判词加大加粗，是截图传播点 |
| ⑥ 免责底行 | 免责声明一行（§5「免责底行文案」）+ `GitHub · mcd-chrono` 提示 | 11px 次要色 |

**水印**：demo 模式（`result["source"] == "demo"`，结构见 §2.2）右上角 45° 半透明角标 `DEMO · 构造数据`
（合规要求，PRD 第十章）。live 模式无水印。

**免责底行文案**（先例 report.py L10-14，改写为鉴定语义）：

> 本鉴定由 mcd-chrono 自动生成，仅供娱乐，基于你本人的麦当劳订单时间数据，
> 不构成任何健康或饮食建议。本项目为麦当劳程序员创意开发大赛参赛作品，非麦当劳官方产品。

**三个输出物**：

| 文件 | 内容 |
|---|---|
| `out/chrono_card.html` | 仅卡片（居中置灰底），直接截图用 |
| `out/chrono_report.html` | 完整页 = 卡片 + 附录（T1-T10 十项数值表 + 判定链逐级命中过程），调试与展示用 |
| `out/chrono_report.md` | 纯文本简版：称号/emoji/三数字/五时段占比/描述/判词/免责，终端党用 |

## 6. CLI 契约（main.py）

```
python main.py --demo [--sample normal|heavy] [--share] [--out DIR]
python main.py --live [--dump PATH] [--share] [--out DIR]
```

| 参数 | 语义 | 备注 |
|---|---|---|
| `--demo` / `--live` | 互斥必选（argparse mutually exclusive group，先例 mcaudit.py L259-261） | |
| `--sample` | demo 样例类型 normal/heavy，默认 normal | 与 `--live` 同给：stderr 提示后忽略 |
| `--dump PATH` | 仅 live：落盘 JSON（见 §6.1） | 字段核对机制（A4） |
| `--share` | 生成后向 stdout 打印分享文案（§6.2） | demo/live 均可用 |
| `--out DIR` | 输出目录，默认 `./out` | |

退出码：`0` 成功；`2` MCP 连接/Token 失败（先例 mcaudit.py L275-279）；无订单时
`SystemExit` 带提示（先例 mcaudit.py L230-231）。成功时终端打印摘要块
（称号 + 三数字 + 生成文件路径，形态同 mcaudit.py L294-302）。

### 6.1 `--dump` 内容（对 mcaudit 的一处有意扩展）

```json
{"source": "live", "orders": [规范化订单…], "raw_sample": order-list 首个原始条目}
```

mcaudit 只落规范化结构（mcaudit.py L250-253）；本设计加 `raw_sample` 保留一份
未清洗的原始字段（限首条，控制体积）。理由：PRD 第十章把「字段结构与预期不符」列为风险，
仅规范化结构会丢失原始字段线索，10-18 回传核对需要原始样本。

### 6.2 分享文案模板（F5）

```text
我在麦当劳下了 {n} 单，被鉴定为「{emoji} {称号}」。
{判词}
你是哪种麦门作息？→ {REPO_URL}
```

`REPO_URL` 为 card.py 常量，当前占位 `https://github.com/<待定>/mcd-chrono`
（仓库 10-20 由用户定名，open 项见 §14）。安慰卡模式下输出友好版（不输出人格称号）。

## 7. 降级路径与边界情况

| 情况 | 行为 |
|---|---|
| query-order 明细逐笔拉取失败 | 单笔降级（先例 mcaudit.py L99-103 try/except），该单 items=[]；**全部明细缺失 → T7=None → P1 跳过**，链继续 P2 起 |
| 订单时间字段不可解析 | 该单不进 n_timevalid；T1-T6/T9 分母自动收缩。n_timevalid=0 时这些特征全 None，仅 T7/T8/T10 可判（T8：不可解析的单不计入月份，active_months=0 按下限取 1 → T8=n；span_days=0）；stderr 提示「时间字段缺失，建议 --live --dump 回传字段结构核对」（PRD F2 边界条款） |
| n < 5 | 安慰卡（§4.2 末行），不进判定链 |
| 订单数为 0 | SystemExit：没有取到订单，提示用 --demo（先例 mcaudit.py L230-231） |
| 单一门店 / 单一单品 | T10=1.0 / T7=最大占比，正常判定 |
| 全天均匀分布 | T9=415.7（均匀分布理论值，量尺参考，见 §3.2） |
| MCP 401/429 | McpError 带中文提示，退出码 2（mcp_client.py L57-60 已处理） |
| order-list 分页行为未知 | open 项：10-18 `--live --dump` 回传后核对（§14）；当前按单次全量处理（mcaudit 同假设，已跑通过真实接口） |

## 8. 文件规划与影响清单（PRD 第八章对齐）

mcaudit 目录只读；下表全部为 mcd-chrono 新建文件。「来源」列标注复用坐标与预计行数。

| 文件 | 来源 / 性质 | 预计行数 |
|---|---|---|
| main.py | 自 mcaudit.py（308 行）精简改写：去营养/积分链，加 --share | ≈150 |
| mcp_client.py | 原样平移 mcaudit/mcp_client.py（169 行，零改动） | 169 |
| fetch.py | 平移 mcaudit.py L36-41（load_demo）、L44-73（_first/_dig/_as_list）、L76-105（fetch_orders）、L133-184（normalize_order）、L216-222（_to_float）；剔除 fetch_nutrition/enrich_nutrition/_fuzzy | ≈210 |
| features.py | 新增：parse_time + 时段窗 + §3.2 环形统计 + T1-T10 | ≈220 |
| persona.py | 新增：THRESHOLDS + 八人格四件套 + 安慰卡 + 判定链 | ≈210 |
| card.py | 新增：三渲染函数 + HTML/CSS 模板（CSS 先例 report.py L157-196） | ≈340 |
| fixtures/make_fixture.py | 复制 make_fixture.py（172 行）改造：PROFILES 加 weekday 权重、order_type 权重、早餐分钟紧化 | ≈210 |
| fixtures/demo_orders_normal.json | 生成物（构造数据，note 字段注明） | 生成 |
| fixtures/demo_orders_heavy.json | 生成物 | 生成 |
| SKILL.md | 改写（触发词：「鉴定我的麦门作息」「我是哪种麦门」「麦门作息」「麦当劳人格」；汇报口径 = 称号 + 三数字 + 卡片路径） | ≈55 |
| README.md | 重写（含成品卡截图位） | ≈130 |
| CONTEST_DECLARATION.md | 复制 mcaudit 同名文件，提交前逐字核对官方版 | 复制 |
| MCP_INTEGRATION.md | 重写（工具只剩 order-list 必需 + query-order 可选） | ≈70 |
| mcp-config.example.json | 原样复制（11 行） | 11 |
| workbuddy.md | 复制 mcaudit 版 + 续写 mcd-chrono 章 | 复制+ |
| .gitignore | 原样复制（含 out/、raw.json、*.token） | 8 |
| docs/batches/tests/*.py | 批次单元断言文件（§9；随批次归档，不进项目 test/ 树） | ≈320 |

**fixture 参数设计**（make_fixture.py 改造，确定性种子不变式）：

- 改造点 1（星期维度）：先按 `rng.choices([0..6], weights=profile["weekdays"])` 抽目标星期
  （替换原 randint(0,6)，L97），再由日期反推 week*7+offset 定位到该星期（直接 offset=权重抽取在
  start 为周五时会把周末错配工作日权重——实现按参数意图修正，T5 实测 0.046/0.487 符合 96%/50%）。
- 改造点 2：`ORDER_TYPES` 权重从全局常量改为每 profile 一项（外卖率可调，喂 P5 边界）。
- 改造点 3：normal 的早餐小时分钟保持 0-59 均匀（T3_std ≈ 17 < 45，P3 稳定命中）。
- `normal`：per_week ([0,1,2,3],[16,44,28,12])≈71 单/年；hours ([8,12,15,19,22],[45,25,10,12,8])
  → t3_ratio≈0.45（对 P3 阈值 0.35 余量 0.10）、T4≈0.08；weekdays 工作日 96%；外卖 [70,30] → T6≈0.30。**预期 P3 晨间通勤麦**。
- `heavy`：per_week ([1,2,3,4,5],[10,26,30,22,12])≈156 单/年；hours
  ([8,12,15,19,22,23],[6,20,6,20,26,22]) → T4≈0.48；weekdays 周末 50%；外卖 [40,60]。**预期 P2 深夜麦门守护者**。
- 两 profile 期望 T7 < 0.40（多单品金额聚合分散，P1 不抢跑）——上两条「预期 P3/P2」的前提
  （E5 生成后核对）。
- 两样例人格不同 = A1 的 fixture 侧保证；A2 的八人格全覆盖用单元测试直接构造订单字典
  （精确控阈值），不走生成器。

## 9. 测试策略（零依赖，断言式）

单元断言文件随批次归档于 `docs/batches/tests/`（开发期反馈回路，不进项目 test/ 树，
不挂任何门禁）；运行方式 `python docs/batches/tests/run_all.py`（脚本内注入仓库根到
sys.path 后跑 unittest）。

| 文件 | 覆盖 | 对应验收 |
|---|---|---|
| test_features.py | T9 环形：同一时刻→0；23:59+00:01→≈1.0；全天均匀→≈415.7；R<1e-9→415.7。窗口边界：20:59→晚、21:00→夜、04:59→夜、05:00→早、09:59/10:00、13:59/14:00、16:59/17:00；T2 窗 10:59/11:00/12:59/13:00；T3 窗 05:29/05:30/09:29/09:30。T8 自然月数、T10 单店=1.0、T7 聚合、T6 类型子串 | A2、A4 |
| test_persona.py | 八人格各 ≥1 例正命中 + 关键阈值边界（T4=0.25 命中 / 0.2499 不命中）；优先级（P1∧P2 同满足→P1）；n=4→安慰卡、n=5→进链；T7=None→P1 跳过落 P2；None 操作数判否 | A2、A3 |
| test_card_offline.py | 对生成的三份 HTML 断言源码无 `http://`/`https://`（A5 机器判据）；demo 水印存在、live 无水印 | A5 |

收尾集成（主 agent 侧，一次）：A1 三跑（`--demo`、`--demo --sample heavy`、人格比对）+
A3（4 单样例）+ A4（真实 Token，10-18 回传后）。单元文件不转集成、不挂门禁。

## 10. 验收映射表（REQ A1-A7 ← 设计章节 ← 批次条目）

| 验收 | 判据（REQ §4） | 设计落点 | 批次条目 |
|---|---|---|---|
| A1 | --demo 与 --demo --sample heavy 各出卡、人格不同 | §6 CLI、§8 fixture 参数（P3/P2 预期）、§5 卡片 | E4/E5/E8 |
| A2 | 八人格各触发 ≥1 次（定制样例） | §3 定义、§4 判定链、§9 test_persona；以直接构造字典替代定制 fixture（精确控阈值，见 §8 fixture 设计） | E2/E3/E9 |
| A3 | <5 单安慰卡 | §4.1 链前置、§7 | E3/E9 |
| A4 | --live 跑通 + 容错生效（10-18 回传核对） | §2 fetch 平移、§6.1 dump、§7 降级 | E1/E2 |
| A5 | 卡片离线（源码无 http/https） | §5 规格、§9 test_card_offline | E4/E9 |
| A6 | 交付物齐备合规 | §8 文件清单（SKILL/README/CONTEST_DECLARATION/MCP_INTEGRATION/mcp-config/workbuddy/.gitignore） | E6/E7 |
| A7 | 8 条判词过用户验收（10-18 专场） | §4.2 v0 基调稿 + 合规线 | E3 |

REQ §5 两处口径的落点：修订①（T9 分钟制环形）→ §3.2；修订②（21-5 跨零点归属）→ §3.1。

## 11. 关键决策记录（含被否方案）

1. **T9 用「环形均值方向 + 环形距离 RMS」。**
   被否：①普通标准差（REQ §5 明示失真，直接否决）；②窗口拆分后分段标准差
   （拆窗位置任意、边界跳变，21-5 窗拆在哪都引入人为断点）；③ Mardia-Jupp 的
   `√(−2lnR)` 圆标准差（均匀分布时发散无上界，75 分钟这类阈值语义不稳）。
   选用式均匀分布下取稳定有限值（≈415.7，不发散；量尺口径见 §3.2）、跨零点正确、一句话可解释（「围绕典型时刻平均偏 X 分钟」）。
2. **夜宵归属用 mod 24 落窗（双尾并集），不改日期。**
   被否：把 0-5 点单记入「前一日」（改变自然日期语义，污染 T5 周末判定——周日凌晨单应算周末）。
3. **T8 活跃月数 = 有单自然月数（下限 1）。**
   被否：跨度/30.44（mcaudit/audit.py L129 先例）——单周爆单会算出虚高月频，
   与「活跃月」字面不符。稀疏用户（P7 关心的群体）两口径结论一致，取字面忠实的。
4. **normalize_order 原样平移（含营养字段）。**
   被否：裁掉 kcal/protein 等字段（REQ F1 写明整体平移；裁剪引入平移差异面，
   保留是 v2 营养维度的零成本接口）。
5. **MCP 工具面收窄：必需 order-list，可选 query-order；不调 nutrition/account/now-time。**
   依据 REQ F1（主链路仅 order-list）压过 PRD F1 的四工具表述；PRD 第七章表自身也将
   nutrition 标为暂不接，两文档不冲突，REQ 为准。
6. **--dump 加 raw_sample 首条原始样本。**
   被否：照抄 mcaudit 仅规范化结构（丢失字段核对线索，违背 PRD 第十章该机制的本意）。
7. **安慰卡走同一卡片版式。**
   被否：独立简版模板（两套模板两份维护；同版式 + is_scant 文案切换成本低且观感一致）。

## 12. 边界（不做什么，REQ §3 逐条对齐）

- 不提供 Web 服务、不提供微信小程序。
- 不做复合人格、积分彩蛋、营养维度（v1 砍项）。
- 文案不做健康评价、不做饮食建议、不出现「应不应该吃」句式；夜宵人格不写身体后果。
- 卡片与文案零出现其他品牌。
- 不触碰优惠券维度人格。
- 不引入任何第三方依赖；不写入 mcaudit 目录任何文件。

## 13. 用例表（正常 / 边界 / 错误）

| # | 类型 | 输入 | 预期输出 |
|---|---|---|---|
| C1 | 正常 | 71 单 normal fixture | P3 卡，t3_ratio≈0.45，T9 多峰小时分布下为大量值（实测 ≈280 分钟，仍远超 P4 阈值 75，不触发） |
| C2 | 正常 | 156 单 heavy fixture | P2 卡，T4≈0.48 |
| C3 | 边界 | 23:59 与 00:01 各一单（+3 单白日） | T9≈1.0 分钟，两单同落夜窗 |
| C4 | 边界 | 20:59 单 vs 21:00 单 | 前者晚窗、后者夜窗 |
| C5 | 边界 | 04:59 单 vs 05:00 单 | 前者夜窗、后者早窗 |
| C6 | 边界 | 10:59/11:00/12:59/13:00 各 1 单（均工作日） | T2 = 2/4（11:00、12:59 入窗 [660,780)） |
| C7 | 边界 | T4 = 0.25 整（4/16 单夜宵） | P2 命中（≥ 含等号） |
| C8 | 边界 | 4 单 | 安慰卡，is_scant=true，demo 带水印 |
| C9 | 错误 | live 且全部明细拉取失败 | orders 全 items=[]，T7=None，P1 跳过，链从 P2 起 |
| C10 | 错误 | order_time 全部不可解析 | n_timevalid=0，T1-T6/T9=None，T8=n、span_days=0，stderr 提示 --dump 回传 |
| C11 | 错误 | order-list 返回空 | SystemExit「没有取到订单…--demo」提示 |
| C12 | 错误 | MCD_MCP_TOKEN 未设/无效 | 退出码 2，McpError 中文提示（mcp_client.py L27、L58） |
| C13 | 边界 | 单一门店 100% | T10=1.0，三数字格正常展示 |

## 14. UI/交互决策落位与 open 项

已全部落位：卡片六段版式与色板（§5）、三输出物（§5）、demo 水印（§5）、分享文案模板（§6.2）、
终端摘要块（§6）、安慰卡同版式（§11.7）、README 成品卡截图位（§8）。

open 项（不阻塞实现，均有明确解决窗口）：

| # | 事项 | 解决窗口 |
|---|---|---|
| O1 | REPO_URL 占位（GitHub 仓库 10-20 由用户定名） | 10-20 建仓时改 card.py 常量一处 |
| O2 | 八人格文案为 v0 基调稿 | 10-18 文案专场逐条过（A7） |
| O3 | order-list 分页行为未知 | 10-18 --live --dump 回传核对（A4） |
| O4 | CONTEST_DECLARATION 与官方逐字一致 | 10-19 提交前核对（A6） |

## 变更记录

- 2026-10-16 v1.0：initial 轮定稿。REQ §5 两处口径定死（§3.1 / §3.2）；八人格阈值与
  v0 文案；卡片版式；CLI 契约；降级路径；测试策略；验收映射。
- 2026-10-17 v1.1：评审修复轮（批次记录 §3 发现 1-6）：免责锚点改指 §5 内文案块；T9 上界
  表述改「均匀分布理论值（量尺参考）」并注明 ≈455/≈509 极值、不截断；T8 与 span_days
  可判口径明写；normal 早餐权重 36→45（t3_ratio≈0.45）并补两 profile T7<0.40 前提；
  A2 行补构造字典偏差注；§2.2 补 result 结构块。
- 2026-10-17 v1.2：实现轮同步（eng-coder 报告遗留 1/2 号，父代直改·小改豁免）：C1 期望值改实测口径
  （T9 多峰分布下 ≈280 分钟，远超 P4 阈值 75 不触发）；§8 改造点 1 机制文字与实现对齐
  （先抽目标星期再换算日期，修正 start=周五的周末错配）。
