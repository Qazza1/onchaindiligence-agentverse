"""Thin JSON-RPC client for OCD's existing public MCP surface.

This module makes exactly one kind of call: `tools/call` against
https://mcp.onchaindiligence.com/public/mcp (or OCD_PUBLIC_MCP_URL). It does
not implement, re-derive, or cache any policy/verification/receipt logic --
every result returned here is the OCD backend's own, unmodified.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import MCP_REQUEST_TIMEOUT_SECONDS, OCD_PUBLIC_MCP_URL


class McpCallError(Exception):
    """Raised when the OCD public MCP surface could not be reached or
    returned something other than a well-formed tool result. Never raised
    for a tool's own business-level error (e.g. BLOCK, INVALID) -- those are
    successful calls with an informative result, not failures of this
    client."""


@dataclass
class McpToolResult:
    structured: dict[str, Any] | None
    text: str
    is_error: bool


async def call_tool(name: str, arguments: dict[str, Any]) -> McpToolResult:
    """Call one OCD public MCP tool and return its result, unmodified.

    Raises McpCallError only for genuine connectivity/protocol failures
    (network error, non-2xx, malformed JSON-RPC envelope) -- never for a
    tool's own reported outcome.
    """
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }
    try:
        async with httpx.AsyncClient(timeout=MCP_REQUEST_TIMEOUT_SECONDS) as client:
            response = await client.post(
                OCD_PUBLIC_MCP_URL,
                json=payload,
                headers={"Accept": "application/json, text/event-stream"},
            )
    except httpx.HTTPError as exc:
        raise McpCallError(f"could not reach the OCD public MCP surface: {exc}") from exc

    if response.status_code >= 400:
        raise McpCallError(
            f"OCD public MCP surface returned HTTP {response.status_code}"
        )

    try:
        body = response.json()
    except json.JSONDecodeError as exc:
        raise McpCallError("OCD public MCP surface returned a non-JSON response") from exc

    if "error" in body:
        # JSON-RPC-level error (e.g. unknown tool, malformed params) -- a
        # real protocol failure, distinct from a tool-level isError result.
        message = body["error"].get("message", "unknown JSON-RPC error")
        raise McpCallError(f"OCD public MCP surface reported an error: {message}")

    result = body.get("result", {})
    content = result.get("content", [])
    text = "".join(
        item.get("text", "") for item in content if isinstance(item, dict) and item.get("type") == "text"
    )
    return McpToolResult(
        structured=result.get("structuredContent"),
        text=text,
        is_error=bool(result.get("isError", False)),
    )


async def inspect_payment(action: dict[str, Any], policy: dict[str, Any]) -> McpToolResult:
    return await call_tool("inspect_payment", {"action": action, "policy": policy})


async def get_receipt(receipt_id: str) -> McpToolResult:
    return await call_tool("get_receipt", {"receipt_id": receipt_id})


async def verify_receipt(
    receipt_id: str | None = None, envelope: Any | None = None
) -> McpToolResult:
    arguments: dict[str, Any] = {}
    if receipt_id is not None:
        arguments["receipt_id"] = receipt_id
    if envelope is not None:
        arguments["envelope"] = envelope
    return await call_tool("verify_receipt", arguments)
