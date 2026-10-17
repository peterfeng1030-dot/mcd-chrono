# 批次记录 · mcd-chrono 初始实现（工程化落地批次）

| 项 | 值 |
|---|---|
| 批次 | mcd-chrono-initial |
| 主题词 | 麦门作息鉴定 |
| 日期 | 2026-10-16 |
| 台账 | #1（需求池） |
| 来源 | 用户评估确认 WorkBuddy PRD 后决定实施 |

---

## §1 讨论（主 agent）

用户参加麦当劳×WorkBuddy AI 大赛，WorkBuddy 已产出 PRD（`mcaudit/docs/PRD-麦门作息鉴定.md`，v1.0）。
用户指令：先评估，若 ok 则开始做。

主 agent 评估结论（2026-10-16）：

1. 方向成立——「消费数据 → 身份标签」是被反复验证的转发结构；前代审计报告版被用户判定不好玩，转向人格卡是对 Star=社交货币规律的顺应。
2. 复用层验证——主 agent 逐行读了 `mcaudit/mcp_client.py`（MCP Streamable HTTP 客户端，SSE/JSON 双解析、401/429 处理）与 `mcaudit.py` 的 fetch/normalize/容错层（L44-222），质量扎实，平移成立。fixtures 已含小时维度，加星期维度是小改。
3. 两处口径问题——T9 规律度「小时标准差」与阈值「75 分钟」单位不一致；夜宵时段 21-5 跨零点，普通标准差失真。已写入需求 §5，要求设计文档定死口径。
4. 风险——人格卡赛道已有五六个竞品；真实数据人格分布可能集中砸进兜底人格；以上不阻塞，分别由文案专场（10-18）与实测回传（10-18）对冲。

新项目落位 `D:\WorkBuddySpace\AI\mcd-chrono`，前代 mcaudit 保留不动。
需求文档定稿：`docs/requirements/REQ-麦门作息鉴定.md`（v1.1，含对 PRD 的口径修订）。

**状态行**：进行中

附注二（2026-10-17 下午，主 agent 核实）：用户自行用 WorkBuddy 在项目内加了 Token 自检与读取链——scripts/check_token.py（getpass 输入、验证握手/工具/订单三层、可写 .env）、mcp_client.py 的 from_env 加 .env 回退（169→185 行，其余未动）、README.md/workbuddy.md（WorkBuddy 视角的 E7 初稿，与本批次 E7 正式交付物有重叠）。E7 派发时以此现场为起点整合，不推倒。.env 尚未创建（用户 Token 未落盘）。

附注（2026-10-17 主 agent 核实）：eng-designer 交设计稿时已顺手平移 4 个原样复制件到项目根
（mcp_client.py / CONTEST_DECLARATION.md / mcp-config.example.json / .gitignore），
经 `fc /b` 逐字节比对与 mcaudit 原件一致，即 E1/E7 计划物料，实现轮不重抄、逐字核对责任不变（O4）。

---

2026-10-17 补记：评审 pass（🔴0·🟡3·🔵4）+ 修复轮收敛（六号 Fixed，7 号转实现轮）。用户指令「先做个 demo 看看」——实现轮以 demo 范围派发（E1-E6+E9），E7 交付物延后至 demo 反馈后；正式批准（§4）待用户过目 demo 卡后补记。

2026-10-17 晚 live 实测（A4）：用户真实账号经 check_token.py + main.py --live 全链跑通——Token 有效、MCP 握手成功、订单拉取/字段容错/门店名解析全部正确（raw_sample.json 十字段与容错层对齐）；账号仅 1 笔订单（2026-05-15 板烧鸡腿堡），正确触发安慰卡，A3 在 live 模式顺带验证。O3 关闭：探针（.thincoder/tmp/probe_orderlist_schema.py）读出 order-list 的 inputSchema 为空对象——不收任何参数、无分页面，单次调用即全量；mall-order-list（lastId/size 分页）是商城兑换单工具，不在主链路。A4 真实数据人格判定未行使（样本 <5），如需闭环须换 ≥5 单账号实测，可选。

## §2 批次任务与设计（eng-designer）


设计文档：`docs/design/DESIGN-麦门作息鉴定.md`（v1.0，2026-10-16）。
需求依据：`docs/requirements/REQ-麦门作息鉴定.md` v1.1（F1-F7 / A1-A7 / §5 两处口径勘误）。
两处口径在设计 §3.1（夜宵跨零点 = mod 24 落窗、双尾并集不改日期）与 §3.2（T9 = 环形均值方向 + 环形距离 RMS，单位分钟，有界 ≤415.7）定死。

### 批次任务表（条目 ↔ 验收 ↔ 文件映射）

| 条目 | 内容 | 新建/改动文件 | 验收映射 |
|---|---|---|---|
| E1 | 数据接入层平移：mcp_client.py 原样复制 169 行；fetch.py 平移 load_demo/_first/_dig/_as_list/_to_float/fetch_orders/normalize_order（剔营养函数） | mcp_client.py、fetch.py | A4 |
| E2 | 特征层 features.py：parse_time + 五时段窗口（设计 §3.1）+ 环形统计（设计 §3.2）+ T1-T10，None 语义（不可判不猜零） | features.py | A2、A4 |
| E3 | 人格层 persona.py：THRESHOLDS 常量表 + 八人格四件套 v0 文案 + 优先级链（命中即停）+ n<5 安慰卡 + T7=None 跳 P1 | persona.py | A2、A3、A7 |
| E4 | 卡片层 card.py：750×1100 六段版式、纯 CSS 条形图、demo 水印、免责底行；三输出物 chrono_card.html / chrono_report.html / chrono_report.md | card.py | A1、A5 |
| E5 | fixtures：make_fixture.py 复制改造（星期权重、外卖权重、早餐紧化），生成 normal（预期 P3）/ heavy（预期 P2）两份 | fixtures/* | A1 |
| E6 | CLI main.py：--demo/--sample/--live/--dump/--share/--out；退出码 0/2；--dump 含 raw_sample 首条原始样本 | main.py | A1、A4 |
| E7 | 比赛交付物：SKILL.md 改写、README 重写（含截图位）、CONTEST_DECLARATION 复制核对、MCP_INTEGRATION 重写、mcp-config.example.json/.gitignore 原样复制、workbuddy.md 续写 | 仓库根交付物 | A6 |
| E8 | 集成验收（主 agent 收尾侧）：--demo 与 --sample heavy 双跑比人格、<5 单安慰卡复跑 | out/* | A1、A3 |
| E9 | 批次单元断言：test_features.py / test_persona.py / test_card_offline.py，归档 docs/batches/tests/，run_all.py 一键跑 | docs/batches/tests/* | A2、A3、A5 |

不在本批次：复合人格/积分彩蛋/营养维度（v1 砍项）；Web/小程序；优惠券人格；mcaudit 目录写入（只读源）。
用户侧待办（非代码范围）：10-17 GitHub 注册+Token、10-18 回传 --live --dump、10-20 提报名 Issue。

### 设计关键口径（一句版）

- T9 规律度：各单分钟时刻求环形均值方向 μ，T9 = 每单到 μ 环形距离 min(|m−μ|,1440−|m−μ|) 的 RMS，单位分钟，范围 [0, 415.7]；n<2 → None，近均匀（R<1e-9）→ 415.7。
- 夜宵窗口：slot(m)=夜 ⟺ m≥1260 或 m<300（21-5 双尾并集，mod 24 落窗）；星期归属用下单自然日期，凌晨单不改日期。

### 遗留（open，均有窗口）

O1 REPO_URL 占位（10-20 建仓定名）；O2 八人格文案 v0 → 10-18 专场（A7）；O3 order-list 分页行为 10-18 回传核对（A4）；O4 CONTEST_DECLARATION 逐字核对 10-19（A6）。

### 评审修复记录（fix 轮，2026-10-17，§3 发现 1-6 逐号落盘）

设计文档升版 v1.1（变更记录一行见该文档尾部）。逐号改动（行号为 v1.1 回读值）：

| 号 | 修复内容 | 落点 |
|---|---|---|
| 1 | 悬空锚点：六段版式表「免责声明一行（§5.2）」改为指向 §5 内「免责底行文案」块（该块保持未编号，不引入新子节编号） | DESIGN:250 |
| 2 | T9 上界表述失准：「有界 ≤415.7」改为「量尺参考」——均匀分布理论值 ≈415.7，按本式对跖双峰可达 ≈455（720·√0.4）、极带极限 ≈509（720/√2）；输出不截断（公式原样），P4 阈值 75 分钟不受影响。§3.2/§7/§11.1 三处口径同步 | DESIGN:157-159、161、317、395 |
| 3 | T8 可判性缺口明写：不可解析时间的单不计入月份；active_months=0 时按下限取 1 → T8=n；span_days 无有效时间时为 0（max/min 只取解析成功的订单）。§3.3 定义、§7 降级、C10 用例三处对齐 | DESIGN:177、181-182、313、434 |
| 4 | normal 早餐小时权重 36→45（hours 权重 [45,25,10,12,8]，t3_ratio≈0.45，对 P3 阈值 0.35 余量 0.10 ≥0.05）；§8 补两 profile 期望 T7<0.40 前提（P1 不抢跑，E5 生成后核对）；C1 期望值同步 | DESIGN:351-352、355-356、425 |
| 5 | §10 A2 行补注「以直接构造字典替代定制 fixture（精确控阈值，见 §8 fixture 设计）」，对 REQ 字面偏差显式可见 | DESIGN:380 |
| 6 | §2.2 补 result 结构块（main.py 组装：source demo|live / features / persona；source 驱动 demo 水印），水印行同步改引 result["source"] | DESIGN:105-111、252 |

7 号（mcaudit 侧坐标与行数、E1-E9 映射 unverified）不归设计轮修复：转实现轮任务书——平移当日对被复制文件逐一核对行数与坐标，列为批次执行项。

注：本节上方「设计关键口径（一句版）」中「有界 ≤415.7」「范围 [0, 415.7]」为 v1.0 口径的初始轮记录（段机制 append-only，不回改），以设计 v1.1 §3.2 量尺表述为准。

## §3 设计评审（advisor）

> 本段由主 agent 代录：advisor 声称已写入但未落盘（2026-10-17 D6 回读发现），以下为评审报告原文逐字转录。

评审范围：`docs/design/DESIGN-麦门作息鉴定.md`（445 行，v1.0）+ `docs/requirements/REQ-麦门作息鉴定.md`（v1.1）。reviewId `cc4a9be4`。

需求覆盖核对（无 🔴 缺口）：F1-F7、§3 边界六条、A1-A7 映射、§5 两处口径修订（修订①→§3.2 环形分钟制、修订②→§3.1 双尾并集窗）、§6 依赖、最近先例行、§8 影响清单（全部新建文件，最大 340 行 < 500 分层线）均有落点；窗口边界表、THRESHOLDS、§4.2 判定表、C4-C7 边界用例四组交叉验证一致。

| # | 类别 | 严重度 | 问题 | 建议 |
|---|---|---|---|---|
| 1 | 清晰度（内部锚点） | 🟡 | §5 六段版式表引用「§5.2」（DESIGN:240「免责声明一行（§5.2）」），但 §5 无编号子节，免责文案实际位于其后未编号的「免责底行文案」块（:245）——锚点悬空 | 将免责文案块编为 §5.2，或把表中锚点改为指向该块 |
| 2 | 清晰度（数学口径） | 🟡 | §3.2「T9 ∈ [0, 415.7]（上界 = 全天均匀分布的理论值 1440/√12 ≈ 415.69）」（:149）不是硬上界：按同节公式，对跖双峰分布（如 60% 单在 0:00、40% 在 12:00）得 720·√0.4 ≈ 455 分钟 > 415.7；415.69 仅是均匀分布的取值，该估计量的真实极带上界 ≈509（720/√2）。无任何阈值落在该量级（P4 用 <75），判定语义不受影响，属表述失准 | 改述为「均匀分布理论值 ≈415.7（量尺参考）」，可注明对跖双峰极限 ≈509，或对输出在 415.7 截断（截断须同步改 §9 对应用例） |
| 3 | 清晰度（口径缺口） | 🟡 | §7「n_timevalid=0 时这些特征全 None，仅 T7/T8/T10 可判」（:303）与 T8 定义（n / active_months，active_months 按 YYYY-MM 去重、下限 1，:168）未对齐：时间全不可解析则无月可去重，唯有按「下限 1」把 active_months=0 钳为 1（→T8=n）才「可判」，该路径未写明；meta.span_days（:172）同依赖解析后日期 | 在 §3.3/§7 明写：不可解析时间的单不计入月份，active_months=0 时按下限取 1（或改判 T8=None），并补 span_days 的空值行为 |
| 4 | 验收（余量） | 🔵 | normal 期望 t3_ratio≈0.36 对 P3 阈值 0.35（:342 对 :194）仅 0.01 余量；且 normal/heavy 两 profile 的 T7<0.40 余量（P1 优先级高于 P3/P2）未在 §8 声明，「预期 P3/P2」对参数估计误差敏感。A1 硬判据（两样例人格不同）不受影响——最坏落 P8 vs P2 仍不同，E4/E5 集成可兜底 | 加大 normal 早餐小时权重拉开余量，并在 §8 补记两 profile 的期望 T7<0.40 |
| 5 | 验收（字面偏差） | 🔵 | REQ A2 括注「阈值边界用定制 fixture 验证」（REQ:49），设计改用单元测试直接构造订单字典控阈值（:346），更精确但与 REQ 字面不同，理由仅见于 §8 行文 | 在 §10 A2 行补注「以直接构造字典替代定制 fixture（精确控阈值）」，使偏差在验收映射处显式可见 |
| 6 | 清晰度 | 🔵 | card.py 三个渲染函数消费的「结果字典」（render_card(result) 等，:64）未像特征字典/人格字典那样给出键表（source/features/meta/persona 的组装仅靠 §2.1 数据流图推断） | §2.2 补一个 result 结构块（含 demo 水印所依赖的 source 键） |
| 7 | 证据边界 | 🔵 | 全部 mcaudit 侧坐标与行数（mcp_client.py 169 行、mcaudit.py 308 行、make_fixture.py 172 行、report.py/audit.py 各 L 引用、「已逐行验证可平移」）及批次条目 E1-E9 均在本次评审范围之外，未能核实（unverified） | 平移当日对被复制文件逐一核对行数与坐标，列为批次执行项 |

评审限制：无 AGENTS.md、无项目规范文档、无文档地图——方法论合规与文档所有权两项按评审准则降级判断；docs/design 与 docs/requirements 同名主题配对一致，未见碎片化或范围内矛盾（PRD 与 mcaudit 均不在范围，未核）。

计数：🔴 0 · 🟡 3 · 🔵 4

VERDICT: pass（token 已发主 agent；designId cc4a9be4-5617-4edb-9b8a-ef573006680f）

## §4 用户批准（主 agent）

（主 agent 填写：批准记录）

## §5 实施记录（eng-coder）
**状态行**：实施完成 2026-10-17（E1-E6+E9 交付：双 demo P3/P2 命中、66 断言全绿、审计+评审收敛 clean）



（eng-coder 填写：逐条目实施记录）

### 实施记录（E1-E6+E9，2026-10-17）

**交付文件**（新建/覆盖，均按设计 v1.1）：main.py 158 行 · fetch.py 164 行 · features.py 194 行 · persona.py 177 行 · card.py 309 行 · mcp_client.py（原样平移，fc /b 与 mcaudit 逐字节一致）· fixtures/make_fixture.py 169 行（+两份生成物 json）· docs/batches/tests/ 四文件（66 断言）。

**验收实测**：
- A1：`python main.py --demo` → 🌅 P3 晨间通勤麦（t3_ratio=0.46 / t3_std=19.8）；`--sample heavy` → 🌙 P2 深夜麦门守护者（T4=0.454）。人格不同 ✓，out/ 三件落盘 ✓。
- 两 profile T7<0.40 前提核对：normal 0.193 / heavy 0.118（设计 L355-356 前提成立，P1 不抢跑）。
- A2/A3/A5：`python docs/batches/tests/run_all.py` 66/66 全绿（T9 环形数学四命题、五窗边界、T2/T3 窗边界、八人格正命中、阈值边界含 T4=0.25 命中/0.2499 不命中、优先级链、n=4/5 分界、None 判否、卡片离线零 http/https）。
- 退出码 2：无 Token `--live` → McpError 中文提示 + 「没有 Token 时可先用 --demo」指引，无崩栈（cmd /v:on 实测 RC=2）。
- 卡片 UI 实测（本地 http.server + 无头浏览器）：750×1100、六段齐备、最高时段条麦红其余麦黄、demo 水印 45° 角标、无横向溢出。

**一处有依据的实现修正（对设计 §8 改造点 1 的字面）**：设计原文「offset 由 rng.choices([0..6], weights=weekdays) 抽取」在 start=2025-10-16（周五）下会把周六/周日错配工作日权重（实测 T5=0.368 ≠ 设计意图工作日 96%）。实现改为「先抽目标星期再换算 offset」，实测 normal T5=0.046、heavy T5=0.487，与设计参数意图（96% 工作日 / 50% 周末）一致。设计 §8 该句文字滞后，已列上抛项待文档层修。

**审计与评审**：内部 explore 差异审计 1 轮——核心六条目与设计逐项一致，唯一 OUT-OF-LIST 为一次写错路径的空目录残留（已删）；advisor 代码评审 1 轮 pass（0🔴·1🟡·6🔵），7 项发现全部当场修复（make_fixture docstring 机制描述失真、--live+--sample 双重告警、_chain_log 复写判定条件、链日志浮点格式不齐、raw_out 全量收集、测试残留别名、--demo --dump 静默忽略→加提示），修后 66/66 复绿 + 双 demo 复跑命中不变。终态 clean。

**发现的设计文档内部矛盾（上抛待裁）**：§13 用例 C1「T9≈两位数分钟」与 §3.2 定义 + §8 normal 多峰小时分布在数学上不相容（实测 ≈281.5 分钟）。实现按 §3.2 公式不受影响，任务书验收判据不含此项。

**旧原型残留（上抛待裁）**：项目根存在 2026-10-16 23:07-23:10 的未入档旧原型残留（6 份非 normal/heavy fixture json、scripts/verify_personas.py、out_all/、out_night/、out/ 旧产物）——与本批交付并存，是否清理由主 agent 裁置。

## §6 验收与收口（主 agent）

（主 agent 填写：验收结论 + 收口）
