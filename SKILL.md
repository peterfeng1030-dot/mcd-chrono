---
name: mcd-chrono
description: 鉴定麦当劳作息人格。当用户想知道自己是哪种「麦门作息」、想根据汉堡订单时间给自己贴个标签、或想生成一张可分享的麦门人格卡时使用。基于麦当劳官方 MCP 的真实历史订单时间，输出八种作息人格之一，附时段分布、24 小时热力条与一句判词。
---

# 麦门作息鉴定 · mcd-chrono

只看一件事：你什么时候下单。然后给一个称号、一张卡、一句判词。

## 何时使用

用户说「鉴定我的麦门作息」「我是哪种麦门」「麦门作息」「麦当劳人格」「看看我的点餐时间」
这类话时启用。

## 前置条件

需要环境变量 `MCD_MCP_TOKEN`（在 open.mcd.cn 手机号登录，控制台激活后免费获取），
或项目根目录的 `.env` 里有这个值。

没有 Token 时不要报错退出，改用 `--demo` 展示样例，并告诉用户怎么申请 Token。

## 执行

```bash
python main.py --live                  # 真实数据
python main.py --demo                  # 样例（默认 p3 晨间通勤麦）
python main.py --demo --sample p4      # 指定人格的样例（p1-p8）
python main.py --demo --list-samples   # 列出八份样例分别是哪种人格
python main.py --demo --share          # 顺便输出分享文案
```

输出到 `out/chrono_card.html`（卡片，可直接截图）、`out/chrono_report.html`、
`out/chrono_report.md`。

## 完成后

把 `out/chrono_card.html` 用浏览器打开给用户看。汇报时只讲三样：称号、命中的实际数字、
那句判词。不要把整个报告念一遍。

如果用户想发出去，用 `--share` 拿一段现成的分享文案。

## 口径

八条判定线在 `persona.py` 的 `THRESHOLDS` 里，从上往下命中即停，不要主观改写结论。
订单少于 5 笔时不硬判，输出提示卡。

## 边界

- 只做观察与归类，不做健康、营养评价，不给饮食建议。
- 不与其他餐饮品牌做对比。
- 不涉及券、下单、积分兑换。本工具只读订单时间。
- 鉴定结果仅供娱乐与回顾。
