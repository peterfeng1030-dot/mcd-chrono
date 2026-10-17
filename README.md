# 麦门作息鉴定 · mcd-chrono

把你一年在麦当劳的下单时间，鉴定成一种打工人作息人格。

同样一份套餐，早上七点半吃和凌晨一点吃，说的是两种人生。mcd-chrono 调麦当劳官方 MCP
拉你自己的历史订单，只看一件事：你**什么时候**下的单。然后给出一张鉴定卡，一个称号，
一句判词。

一行命令，不需要 Token 也能先看效果。

```bash
python main.py --demo
```

## 为什么只看时间

麦当劳的 App 已经回答了"我吃了什么"。没人回答的是另一个问题：这一年的订单落在哪些钟点，
能不能看出你过的是什么日子。

早上七点十分出现在同一家店的人，和晚上十一点下单的人，工作性质、作息、甚至城市里的位置
都不一样。订单时间是这个城市里最容易被忽略、又最诚实的一类行为数据。

八种人格，规则全部公开，阈值写死在 `persona.py` 的 `THRESHOLDS` 里，改数字就能改松紧。

## 八种人格

| | 称号 | 判定条件 |
|---|---|---|
| 🍔 | 单品钉子户 | 单个品项金额占比 ≥ 40% |
| 🌙 | 深夜守护者 | 21 点后订单占比 ≥ 25% |
| 🌅 | 晨间通勤麦 | 早餐时段占比 ≥ 35%，且时间离散 ≤ 45 分钟 |
| ⏰ | 午休卡点特种兵 | 工作日午市卡点率 ≥ 45%，且下单时刻离散 < 75 分钟 |
| 🛋️ | 周末宅家派 | 周末占比 ≥ 40%，且外送占比 ≥ 50% |
| ☕ | 下午茶哲学家 | 14 点到 17 点订单占比 ≥ 30% |
| 🍀 | 麦门幸运儿 | 月均下单 < 1.5 单 |
| 🌀 | 全麦自由人 | 以上都不满足（兜底） |

判定从上往下，命中即停。每份报告都会写明命中的是哪条线、实际数字是多少，不做黑箱。

## 快速开始

只需要 Python 3.10+，不装任何第三方包。

```bash
python main.py --demo                    # 内置样例
python main.py --demo --sample heavy     # 换一份样例
python main.py --demo --share            # 顺便输出分享文案
```

`--sample` 可选 `normal` 和 `heavy` 两份，都在 `fixtures/` 下。两份的时段分布差别很大，
跑出来的通常是两种不同人格。

运行完在 `out/` 下得到三个文件：

| 文件 | 用途 |
|---|---|
| `chrono_card.html` | 只有卡片，直接截图发出去 |
| `chrono_report.html` | 完整报告，含判定依据明细 |
| `chrono_report.md` | 纯文本版 |

## 用你自己的真实数据

**第一步，申请 MCP Token。** 打开 [open.mcd.cn/mcp](https://open.mcd.cn/mcp)，手机号登录，
控制台点「激活」，复制 Token。免费，限流 600 次/分钟。

**第二步，验证并保存 Token。**

```bash
python scripts/check_token.py
```

Token 用不回显的方式输入，不会进命令行历史。验证通过后会写进项目根目录的 `.env`
（已在 `.gitignore` 里排除），之后不用每次设置环境变量。

**第三步，跑。**

```bash
python main.py --live
```

## 它输出什么

一张卡片上只有五样东西：称号、时段分布、24 格下单时刻热力条、三个数字、一句判词。

热力条值得单说。它把一年几百笔订单压成 24 个格子，颜色越深表示那个钟点下单越密集。
很多人第一次看到自己那张图会说「原来我都在这个点吃」。

报告页里还有判定依据明细：样本量、区间、累计消费、命中依据、峰值时刻、最忠门店。
所有数字都可追溯，没有一句是编的。

## 用了哪些 MCP 工具

| 工具 | 用途 | 必需性 |
|---|---|---|
| `order-list` | 拉近一年历史订单（时间、类型、金额、门店） | 必需 |
| `query-order` | 逐笔补明细，算单品集中度 | 已接入，单笔失败自动降级 |

`order-list` 定骨架，`query-order` 补细节。一年一百多单也就一百多次调用，离每分钟
600 次的限额很远。单笔明细拉不到时自动降级，不影响其余七条判定线。

## 目标用户

- 想知道自己这一年到底在几点吃麦当劳的人
- 想给年度消费留一张能发出去的图的人
- 想看 MCP 工具链怎么被编排成一个小而完整的产品的开发者

## 项目结构

```
mcd-chrono/
├── main.py                    CLI 入口
├── mcp_client.py              MCP Streamable HTTP 客户端（urllib 实现）
├── fetch.py                   取数与字段容错
├── features.py                T1~T10 特征提取
├── persona.py                 八人格判定引擎与全部文案
├── card.py                    卡片 / 报告 / Markdown 渲染
├── fixtures/                  八份构造样例及其生成器
├── scripts/
│   └── check_token.py         Token 验证与本地保存
├── docs/
│   ├── requirements/          需求文档
│   ├── design/                设计文档
│   └── batches/tests/         单元测试（66 例，八人格判定链与卡片离线渲染）
└── out/                       输出目录（不提交）
```

## Roadmap

比赛版本只做鉴定。下一步打算做的是把鉴定结果接上券的匹配：不是告诉你「这些券能省多少」，
而是告诉你「这张券为什么适合你这种人」。夜宵党需要的是免配送费，通勤党需要的是早餐套餐，
周末宅家派需要的是外送满减，三类人对同一张券的反应完全不同。技术上用
`available-coupons` 和 `calculate-price` 就能做，放在比赛之后。

## 免责声明

本项目为麦当劳程序员创意开发大赛参赛作品，由参赛者独立开发，**非麦当劳官方产品**，
未获麦当劳授权或认可。鉴定结果基于你自己的历史订单时间，仅供娱乐与回顾，不构成营养、
医疗或其他专业建议。餐品信息、价格及供应状态以麦当劳官方渠道的实时结果为准。

---

## Quick Start (English)

mcd-chrono reads your McDonald's China order history through the official MCP server and
turns **when** you order into a working-person chronotype: a title, a distribution chart,
a 24-hour heat strip, and one verdict line.

Standard library only. No `pip install` needed.

```bash
python main.py --demo                    # built-in sample, no token required
python main.py --demo --sample heavy     # two sample profiles shipped
```

For your own data, get a free MCP token at [open.mcd.cn/mcp](https://open.mcd.cn/mcp), then:

```bash
python scripts/check_token.py            # verify and store the token locally
python main.py --live                    # run on your real order history
```

Eight personas, all rules public in `persona.py`.

This is an entry for the McDonald's Developer Innovation Challenge. Not an official
McDonald's product. If you find it interesting, a star helps it rank.
