"""麦当劳 MCP 极简客户端（仅用标准库）。

只做三件事：握手、列工具、调工具。
协议为 MCP Streamable HTTP，传输地址 https://mcp.mcd.cn。
限流 600 次/分钟，超出返回 429。
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

DEFAULT_URL = "https://mcp.mcd.cn"
PROTOCOL_VERSION = "2025-06-18"
TIMEOUT = 30


class McpError(RuntimeError):
    """MCP 调用失败。"""


class McpClient:
    def __init__(self, token: str, url: str = DEFAULT_URL) -> None:
        if not token:
            raise McpError("缺少 MCP Token，请设置环境变量 MCD_MCP_TOKEN")
        self.url = url
        self.token = token
        self.session_id: str | None = None
        self._seq = 0

    # ---------- 底层 ----------

    def _post(self, payload: dict, expect_body: bool = True):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": f"Bearer {self.token}",
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id

        req = urllib.request.Request(self.url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                if not expect_body:
                    return None
                raw = resp.read().decode("utf-8", errors="replace")
                sid = resp.headers.get("Mcp-Session-Id")
                if sid:
                    self.session_id = sid
                return self._unwrap(raw)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:400]
            if exc.code == 401:
                raise McpError("401 Token 无效或已过期，检查 MCD_MCP_TOKEN") from exc
            if exc.code == 429:
                raise McpError("429 触发限流，降低调用频率后重试") from exc
            raise McpError(f"MCP HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise McpError(f"网络不可达：{exc.reason}") from exc

    @staticmethod
    def _unwrap(raw: str):
        """响应可能是 JSON，也可能是 SSE 流。"""
        raw = raw.strip()
        if not raw:
            return None
        if raw.startswith("{"):
            return json.loads(raw)
        for line in raw.splitlines():
            if line.startswith("data:"):
                data = line[5:].strip()
                if data and data != "[DONE]":
                    try:
                        return json.loads(data)
                    except json.JSONDecodeError:
                        continue
        return None

    def _rpc(self, method: str, params: dict | None = None, notify: bool = False):
        self._seq += 1
        payload = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            payload["params"] = params
        if not notify:
            payload["id"] = self._seq
        return self._post(payload, expect_body=not notify)

    # ---------- 对外 ----------

    def initialize(self) -> None:
        result = self._rpc(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "mcaudit", "version": "1.0.0"},
            },
        )
        if result and "error" in result:
            raise McpError(f"握手失败：{result['error']}")
        self._rpc("notifications/initialized", notify=True)

    def list_tools(self) -> list[dict]:
        result = self._rpc("tools/list")
        if not result:
            return []
        if "error" in result:
            raise McpError(f"列工具失败：{result['error']}")
        return result.get("result", {}).get("tools", [])

    def call_tool(self, name: str, arguments: dict | None = None):
        """返回工具负载。文本块直接拼成字符串，结构化内容原样返回。"""
        result = self._rpc("tools/call", {"name": name, "arguments": arguments or {}})
        if not result:
            return None
        if "error" in result:
            raise McpError(f"调用 {name} 失败：{result['error']}")
        payload = result.get("result", {})
        if payload.get("isError"):
            return {"error": payload.get("content")}

        content = payload.get("content") or []
        texts = []
        structured = payload.get("structuredContent")
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text":
                texts.append(block.get("text", ""))
            elif block.get("type") == "json" and structured is None:
                structured = block.get("json")
        text = "\n".join(t for t in texts if t).strip()

        parsed = None
        if text:
            parsed = _try_json(text)
        if structured is not None:
            return structured if parsed is None else _merge(parsed, structured)
        return parsed if parsed is not None else text


def _try_json(text: str):
    text = text.strip()
    if not text.startswith(("{", "[")):
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _merge(primary, secondary):
    """两者都是 dict 时合并，否则以结构化内容为准。"""
    if isinstance(primary, dict) and isinstance(secondary, dict):
        merged = dict(secondary)
        merged.update(primary)
        return merged
    return secondary


def _load_dotenv() -> None:
    """读项目根目录的 .env（已在 .gitignore 中排除）。已存在的环境变量优先。"""
    from pathlib import Path

    path = Path(__file__).resolve().parent / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def from_env() -> McpClient:
    """从环境变量构造客户端，环境变量缺失时回落到 .env。"""
    _load_dotenv()
    token = os.environ.get("MCD_MCP_TOKEN", "").strip()
    url = os.environ.get("MCD_MCP_URL", DEFAULT_URL).strip() or DEFAULT_URL
    return McpClient(token=token, url=url)
