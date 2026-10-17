"""Token 自检：验证麦当劳 MCP Token 是否可用，并把结果写进本地 .env。

    python scripts/check_token.py

Token 通过 getpass 输入，不回显、不进命令行历史、不打印全量。
验证通过后写入项目根目录的 .env（已在 .gitignore 中排除），
后续 main.py --live 会自动读取，不需要再手动设环境变量。
"""

from __future__ import annotations

import getpass
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from mcp_client import McpClient, McpError  # noqa: E402

ENV_PATH = ROOT / ".env"


def mask(token: str) -> str:
    if len(token) <= 10:
        return "*" * len(token)
    return f"{token[:6]}…{token[-4:]}（共 {len(token)} 位）"


def main() -> int:
    print("把 Token 粘贴进来（不会显示，也不会进命令行历史）")
    token = getpass.getpass("MCP Token: ").strip()
    if not token:
        print("没有输入，退出。")
        return 1
    if token.lower().startswith("bearer "):
        token = token[7:].strip()

    print(f"\n输入长度 {mask(token)}，开始验证…\n")

    client = McpClient(token=token)
    try:
        client.initialize()
        print("  [1/4] 握手成功")
    except McpError as exc:
        print(f"  [1/4] 握手失败：{exc}")
        print("\n常见原因：Token 复制时带了空格、Token 已失效、网络不可达。")
        return 2

    try:
        tools = client.list_tools()
        print(f"  [2/4] 工具列表可取，共 {len(tools)} 个")
        if tools:
            names = [t.get("name", "?") for t in tools][:8]
            print(f"        前几个：{', '.join(names)}")
    except McpError as exc:
        print(f"  [2/4] 工具列表失败：{exc}")
        tools = []

    orders = None
    try:
        raw = client.call_tool("order-list", {})
        payload = raw
        if isinstance(raw, dict):
            payload = raw.get("data") or raw.get("result") or raw
        if isinstance(payload, dict):
            for key in ("orders", "list", "records", "items", "data"):
                if isinstance(payload.get(key), list):
                    orders = payload[key]
                    break
            if orders is None:
                orders = [payload] if payload else []
        elif isinstance(payload, list):
            orders = payload
        print(f"  [3/4] 历史订单可取，共 {len(orders or [])} 笔")
    except McpError as exc:
        print(f"  [3/4] 订单拉取失败：{exc}")

    if orders:
        sample = orders[0]
        keys = list(sample.keys())[:14] if isinstance(sample, dict) else []
        print(f"  [4/4] 首条订单的字段名：{', '.join(keys) if keys else '（非字典结构）'}")
        dump_path = ROOT / "raw_sample.json"
        dump_path.write_text(
            json.dumps(orders[:5], ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"        前 5 笔原始结构已存到 {dump_path}（已脱敏，不含 Token）")
    else:
        print("  [4/4] 没取到订单。可能这个账号没有历史订单，或返回结构需要适配。")

    print()
    answer = input("是否把 Token 写入本地 .env，供后续 --live 使用？[y/N] ").strip().lower()
    if answer == "y":
        ENV_PATH.write_text(f"MCD_MCP_TOKEN={token}\n", encoding="utf-8")
        print(f"已写入 {ENV_PATH}")
        print("这个文件已在 .gitignore 里，不会被提交。")
    else:
        print("未写入。之后可以用环境变量 MCD_MCP_TOKEN 临时提供。")

    print("\n下一步：python main.py --live --dump raw.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
