# MCP 集成说明

## 使用的 MCP Server

| 项 | 值 |
|---|---|
| 官方账号 | `M-China`（McDonald's China，金拱门（中国）有限公司） |
| Server 地址 | `https://mcp.mcd.cn` |
| 传输协议 | MCP Streamable HTTP |
| 协议版本 | `2025-06-18` |
| 鉴权 | `Authorization: Bearer <MCP Token>` |
| 限流 | 每 Token 600 次/分钟，超限返回 429 |
| 开放平台 | <https://open.mcd.cn/mcp> |
| 接入指南 | <https://github.com/M-China/mcd-mcp-server> |

Token 在 open.mcd.cn 用手机号登录后，在控制台激活获取，免费。本项目通过环境变量
`MCD_MCP_TOKEN` 读取，环境变量缺失时回落到项目根目录的 `.env`（已加入 `.gitignore`）。
配置文件中只使用环境变量占位符，见 `mcp-config.example.json`。

## 实际调用的 Tool

### 1. `order-list`（必需，核心数据源）

**作用**：查询近期的到店与外送历史订单。

**在流程里的位置**：整条链路的入口。这个项目只需要订单的下单时间、就餐方式、金额和门店，
不需要每一笔的品项明细，所以一个接口就能撑起主链路。

**用到的字段**（按优先级容错匹配，兼容不同版本的返回结构）：

| 用途 | 候选字段名 |
|---|---|
| 订单号 | `orderId` / `order_id` / `orderNo` / `id` |
| 下单时间 | `orderTime` / `order_time` / `createTime` / `createdAt` |
| 实付金额 | `payAmount` / `paid` / `actualAmount` / `total` / `amount` |
| 门店名 | `storeName` / `store_name` / `restaurantName` |
| 就餐方式 | `orderType` / `order_type` / `takeWayName` |

字段匹配逻辑在 `fetch.py` 的 `first()` 和 `dig()`。某一层结构变了不会让整份报告崩掉，
缺字段的那一项特征会自动降级。

### 2. `query-order`（已接入，逐笔补明细）

**作用**：按订单号查单笔详情，拿到品项清单。

**在流程里的位置**：`order-list` 只给概要，而单品集中度（T7）需要品项明细，所以每笔订单
都会补一次 `query-order`。一年一百多单就是一百多次调用，远在 600 次/分钟以内。
单笔失败时降级为 `items=[]`，该笔不参与单品判定，其余七条线不受影响。

**业务价值**：有了单品明细，「🍔 单品钉子户」这条判定线才能生效。缺失时该条判定自动跳过，
不影响其余七条。

单笔失败不会中断全局，会打印一条提示并继续处理下一笔。

### 3. 未使用但相关的工具

| 工具 | 为什么不接 |
|---|---|
| `available-coupons` / `auto-bind-coupons` | 比赛版本只做鉴定，不做券的匹配（见 README 的 Roadmap） |
| `create-order` / `mall-create-order` / `draw-lottery` | 本工具不代下单、不代兑换、不代抽奖 |
| `list-nutrition-foods` | v1 不涉及营养维度，作息判定不需要 |
| `now-time-info` | 时间口径统一按订单自身的下单时间计算，不依赖服务器当前时间 |

## 调用流程

```
initialize                       握手，拿 Mcp-Session-Id
  └─ notifications/initialized
       ├─ order-list             → 订单概要列表（时间、类型、金额、门店）
       │    └─ [可选] query-order → 品项明细，用于单品集中度
       └─ (完)
              ↓
   features.py 提取 T1~T10
              ↓
   persona.py  按优先级判定，命中即停
              ↓
   card.py     出卡片与报告
```

一次 `order-list` 加 N 次 `query-order`，N 等于历史订单数。一年 150 笔也只是 151 次调用，
远在 600 次/分钟的限额内。

## 为什么自己写客户端

`mcp_client.py` 只依赖标准库 `urllib`，没有引入 MCP SDK。原因有三：

一是零依赖。`python main.py --demo` 不需要任何安装步骤就能跑，对非开发者更友好。

二是要同时兼容 JSON 和 SSE 两种响应。MCP Streamable HTTP 的服务端可能返回
`application/json`，也可能返回 `text/event-stream`，自己实现能把两条路都走通。

三是要对字段缺失做逐层降级。官方返回结构随版本变化，用 SDK 拿到的是强类型对象，
反而不方便做「有就用、没有就算」的处理。

代价是只实现了 Streamable HTTP 这一条传输路径，不支持 stdio。

## 数据口径说明

- 时段划分：早餐 5:00-10:00，午市 10:00-14:00，下午茶 14:00-17:00，晚市 17:00-21:00，
  夜宵 21:00 至次日 5:00。
- 工作日指周一至周五，用于「午休卡点」与「晨间通勤」两条判定线。
- 时间离散度用圆周均方根（circular RMS），单位为分钟。用圆周统计而不是普通标准差，
  是因为 23:50 和 00:10 在时间上只差 20 分钟，用普通标准差会算成 23 小时 40 分钟。
  「卡点」的定义是时间稳定，不是频次高。
- 订单数少于 5 笔时不作判定，输出「麦门之缘，刚刚开场」的提示卡，避免用小样本硬套人格。
- 所有金额与时间字段在读取时做容错转换，单笔脏数据不会中断整份报告。
