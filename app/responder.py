"""Turns a routed intent into a chat reply.

This is the one place presentation happens. It preserves OCD's own wording
exactly (ALLOW / REQUIRE_APPROVAL / BLOCK / UNKNOWN for inspection;
VALID / INVALID / UNVERIFIABLE for receipt proof) and never re-derives or
softens them -- e.g. VALID is never rendered as "safe", "successful
payment", "compliant", or "service delivered". Any `limitations` present in
a receipt are always surfaced, not summarized away.
"""
from __future__ import annotations

from app import mcp_client
from app.config import OCD_PAID_MCP_DOCS_URL
from app.intents import Intent, RouteResult


def _missing_fields_message(missing: list[str]) -> str:
    bullets = "\n".join(f"- {item}" for item in missing)
    return (
        "I need a bit more before I can check that -- I don't guess payment "
        f"details. Please tell me:\n{bullets}"
    )


def _refusal_message() -> str:
    return (
        "I can't send, authorize, or sign a payment -- I have no wallet and no "
        "payment capability. I can only inspect a proposed payment against your "
        "policy, or retrieve/verify an existing OCD receipt."
    )


def _unknown_message() -> str:
    return (
        "I can help with three things: inspect a proposed payment against a "
        "policy, retrieve a public OCD receipt by ID, or verify a receipt's "
        "proof. Try: \"Inspect a $0.001 USDC payment on Base against a $1 "
        "maximum,\" or \"Retrieve OCD receipt OCD-RCP-....\""
    )


def _inspection_policy(fields: dict[str, str]) -> dict:
    policy: dict = {}
    if "max_amount" in fields:
        policy["max_amount"] = fields["max_amount"]
    else:
        # Never silently treat an unstated policy as unconstrained --
        # inspect_payment itself requires this explicit acknowledgement
        # rather than defaulting to it.
        policy["acknowledge_unconstrained"] = True
    return policy


def _format_inspection_result(result: mcp_client.McpToolResult) -> str:
    if result.is_error:
        return f"Inspection could not run: {result.text}"
    data = result.structured or {}
    decision = (data.get("decision") or {}).get("status", "UNKNOWN")
    reasons = (data.get("decision") or {}).get("reasons") or []
    lines = [f"Decision: {decision}"]
    if reasons:
        lines.append("Reasons: " + "; ".join(reasons))
    lines.append(
        "This is a deterministic policy comparison only -- not wallet "
        "authorization, safety, or compliance."
    )
    return "\n".join(lines)


async def _handle_inspect(fields: dict[str, str], missing: list[str], preflight: bool) -> str:
    if missing:
        return _missing_fields_message(missing)
    action = {
        "kind": "PAYMENT",
        "network": fields["network"],
        "asset": fields["asset"],
        "amount": fields["amount"],
        "recipient": fields["recipient"],
    }
    policy = _inspection_policy(fields)
    try:
        result = await mcp_client.inspect_payment(action, policy)
    except mcp_client.McpCallError as exc:
        return f"Could not reach OCD's inspection service: {exc}"

    reply = _format_inspection_result(result)
    if preflight:
        reply += (
            "\n\nThis is a free, unsigned preview only. A durable, signed "
            "PREFLIGHT receipt (with a recorded, independently verifiable "
            "decision) requires OCD's paid preflight_payment tool -- I never "
            "initiate that call myself. See: " + OCD_PAID_MCP_DOCS_URL
        )
    return reply


async def _handle_get_receipt(fields: dict[str, str], missing: list[str]) -> str:
    if missing:
        return _missing_fields_message(missing)
    try:
        result = await mcp_client.get_receipt(fields["receipt_id"])
    except mcp_client.McpCallError as exc:
        return f"Could not reach OCD's receipt service: {exc}"
    data = result.structured or {}
    if not data.get("found"):
        return (
            f"No public receipt found for {fields['receipt_id']}. Private and "
            "unknown receipt IDs look identical by design -- this doesn't "
            "confirm whether a private receipt exists."
        )
    envelope = data.get("envelope", {})
    receipt = envelope.get("receipt", {})
    lines = [f"Found receipt {fields['receipt_id']}."]
    action = receipt.get("action") or {}
    if action:
        lines.append(
            f"Action: {action.get('amount')} on {action.get('network')} to "
            f"{action.get('recipient')}"
        )
    decision = receipt.get("decision") or {}
    if decision:
        lines.append(f"Decision: {decision.get('status', 'UNKNOWN')}")
    execution = receipt.get("execution") or {}
    if execution:
        lines.append(f"Execution: {execution.get('status', 'UNKNOWN')}")
    settlement = receipt.get("settlement") or {}
    if settlement:
        lines.append(f"Settlement: {settlement.get('status', 'UNKNOWN')}")
    limitations = receipt.get("limitations") or []
    if limitations:
        lines.append("Limitations recorded on this receipt:")
        lines.extend(f"- {item}" for item in limitations)
    lines.append("Ask me to verify this receipt to check its cryptographic proof.")
    return "\n".join(lines)


async def _handle_verify(fields: dict[str, str], envelope: object | None, missing: list[str]) -> str:
    if missing and not envelope and "receipt_id" not in fields:
        return _missing_fields_message(missing)
    try:
        result = await mcp_client.verify_receipt(
            receipt_id=fields.get("receipt_id"), envelope=envelope
        )
    except mcp_client.McpCallError as exc:
        return f"Could not reach OCD's verification service: {exc}"
    data = result.structured or {}
    state = data.get("state", "UNVERIFIABLE")
    message = data.get("message", "")
    lines = [f"Proof: {state}"]
    if message:
        lines.append(message)
    if state == "VALID":
        lines.append(
            "VALID means the receipt's cryptographic integrity and "
            "authenticity checked out under OCD's verifier contract. It does "
            "not mean the payment was safe, successful, compliant, or that "
            "any service was delivered -- check the receipt's own "
            "decision/execution/settlement fields and limitations for that."
        )
    return "\n".join(lines)


async def respond(route_result: RouteResult) -> str:
    if route_result.fields.get("refusal") == "execution":
        return _refusal_message()

    if route_result.intent == Intent.INSPECT_PAYMENT:
        return await _handle_inspect(route_result.fields, route_result.missing, preflight=False)
    if route_result.intent == Intent.PREFLIGHT_INFO:
        return await _handle_inspect(route_result.fields, route_result.missing, preflight=True)
    if route_result.intent == Intent.GET_RECEIPT:
        return await _handle_get_receipt(route_result.fields, route_result.missing)
    if route_result.intent == Intent.VERIFY_RECEIPT:
        return await _handle_verify(route_result.fields, route_result.envelope, route_result.missing)
    return _unknown_message()
