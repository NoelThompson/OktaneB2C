"""JSON-RPC client for the MCP server.

The agent has no database credentials and no direct data access. Every read and
write goes through here, and every call carries an access token whose audience
and scope the MCP server verifies independently. If the wrong token is
presented, the call is refused — and the refusal is surfaced, not swallowed,
because watching it fail is the point.
"""

from __future__ import annotations

import uuid
from typing import Any

import httpx

from .config import settings
from .tokens.base import TraceEvent
from .tokens.factory import token_for

# Which scope each tool demands. This mirrors the MCP server's own map; the
# server is authoritative and re-checks everything.
TOOL_SCOPES: dict[str, str] = {
    "catalog.search": "catalog:read",
    "catalog.sizing_guide": "catalog:read",
    "inventory.check": "inventory:read",
    "orders.list": "orders:read",
    "orders.create": "orders:write",
}


class McpError(RuntimeError):
    def __init__(self, tool: str, code: int, message: str, data: Any = None) -> None:
        super().__init__(f"{tool} failed: {message}")
        self.tool = tool
        self.code = code
        self.error = message
        self.data = data


async def call_tool(
    tool: str,
    params: dict[str, Any],
    *,
    id_token: str,
    subject: str,
    trace: list[TraceEvent],
    scope_override: str | None = None,
) -> dict[str, Any]:
    """Invoke one MCP tool, obtaining the right scoped token first.

    ``scope_override`` exists so the demo can deliberately present the wrong
    token and show the MCP server refusing the call.
    """
    scope = scope_override or TOOL_SCOPES.get(tool)
    if scope is None:
        raise McpError(tool, -32601, f"unknown tool {tool}")

    server = settings.server_for_scope(scope)
    exchange = await token_for(id_token, subject, server.audience, (scope,))
    # The shopper's ID token is the root of the whole chain and appears once per
    # turn, not once per exchange.
    already_rooted = any(event.kind == "user_token" for event in trace)
    trace.extend(
        event
        for event in exchange.trace
        if not (already_rooted and event.kind == "user_token")
    )

    payload = {
        "jsonrpc": "2.0",
        "id": uuid.uuid4().hex[:8],
        "method": tool,
        "params": params,
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            f"{settings.mcp_url}/mcp",
            json=payload,
            headers={"authorization": f"Bearer {exchange.access_token}"},
        )

    body = response.json()

    if "error" in body:
        err = body["error"]
        detail = err.get("data") or {}
        reason = detail.get("reason") or err.get("message")
        trace.append(
            TraceEvent(
                kind="mcp_denied",
                label=f"MCP {tool} refused",
                detail=f"{reason}: {detail.get('detail', '')}".strip(": "),
                ok=False,
                claims={
                    "required_scope": (detail.get("required") or {}).get("scope"),
                    "presented_scopes": detail.get("presented_scopes", []),
                },
            )
        )
        raise McpError(tool, int(err.get("code", -32603)), str(err.get("message")), detail)

    trace.append(
        TraceEvent(
            kind="mcp_call",
            label=f"MCP {tool} 200",
            detail=f"scope={scope} aud={server.audience}",
            claims={"tool": tool, "params": _redact(params)},
        )
    )
    return body.get("result", {})


def _redact(params: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in params.items() if k != "idempotency_key"}


async def public_catalog() -> dict[str, Any]:
    """Unauthenticated product listing, used to render storefront tiles."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(f"{settings.mcp_url}/public/catalog")
        response.raise_for_status()
        return response.json()


async def demo_restock(sku: str, stock: int) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{settings.mcp_url}/demo/restock", json={"sku": sku, "stock": stock}
        )
        response.raise_for_status()
        return response.json()
