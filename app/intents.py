"""Deterministic intent router.

No LLM classifier. Every intent is matched by explicit keywords/patterns,
and every required field is either found in the message or reported as
missing -- this module never guesses payment data (amount, network, asset,
recipient) that wasn't actually present in the request.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum


class Intent(str, Enum):
    INSPECT_PAYMENT = "INSPECT_PAYMENT"
    GET_RECEIPT = "GET_RECEIPT"
    VERIFY_RECEIPT = "VERIFY_RECEIPT"
    PREFLIGHT_INFO = "PREFLIGHT_INFO"
    UNKNOWN = "UNKNOWN"


# Known network aliases -> the CAIP-2 identifier OCD's own tools expect.
# Base is OCD's current, live, strict payment scope -- see the OCD repo's
# own CLAUDE.md. Extending this map is a config change, not new logic.
NETWORK_ALIASES = {
    "base": "eip155:8453",
    "base mainnet": "eip155:8453",
    "eip155:8453": "eip155:8453",
}

# Known asset ticker -> canonical contract address OCD's tools expect
# ("use public addresses ... not tickers", per inspect_payment's own
# description). USDC on Base, the same contract OCD's own live examples use.
ASSET_ALIASES = {
    "usdc": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
    "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
}

RECEIPT_ID_PATTERN = re.compile(
    r"OCD-RCP-[0-9A-Z]{4}-[0-9A-Z]{4}-[0-9A-Z]{4}-[0-9A-Z]{4}", re.IGNORECASE
)
ADDRESS_PATTERN = re.compile(r"0x[a-fA-F0-9]{40}")
KV_PATTERN = re.compile(r"(\w+)\s*[:=]\s*([^\s,]+)")


@dataclass
class RouteResult:
    intent: Intent
    fields: dict[str, str] = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)
    envelope: object | None = None


def _extract_kv(text: str) -> dict[str, str]:
    return {k.lower(): v for k, v in KV_PATTERN.findall(text)}


def _extract_amount(text: str, kv: dict[str, str]) -> str | None:
    if "amount" in kv:
        return kv["amount"].lstrip("$")
    match = re.search(r"\$\s*(\d+(?:\.\d+)?)", text)
    if match:
        return match.group(1)
    match = re.search(r"(\d+(?:\.\d+)?)\s*(?:usdc|USDC)", text)
    if match:
        return match.group(1)
    return None


def _extract_max_amount(text: str, kv: dict[str, str]) -> str | None:
    for key in ("max", "max_amount", "maximum", "limit"):
        if key in kv:
            return kv[key].lstrip("$")
    match = re.search(
        r"(?:against|max(?:imum)?|limit)\D{0,15}\$\s*(\d+(?:\.\d+)?)", text, re.IGNORECASE
    )
    if match:
        return match.group(1)
    return None


def _extract_network(text: str, kv: dict[str, str]) -> str | None:
    if "network" in kv:
        return NETWORK_ALIASES.get(kv["network"].lower())
    lowered = text.lower()
    for alias, canonical in NETWORK_ALIASES.items():
        if alias in lowered:
            return canonical
    return None


def _extract_asset(text: str, kv: dict[str, str]) -> str | None:
    if "asset" in kv:
        return ASSET_ALIASES.get(kv["asset"].lower(), kv["asset"])
    lowered = text.lower()
    for alias, canonical in ASSET_ALIASES.items():
        if alias in lowered:
            return canonical
    return None


def _extract_recipient(text: str, kv: dict[str, str]) -> str | None:
    if "recipient" in kv and ADDRESS_PATTERN.fullmatch(kv["recipient"]):
        return kv["recipient"]
    match = ADDRESS_PATTERN.search(text)
    return match.group(0) if match else None


def _extract_receipt_id(text: str) -> str | None:
    match = RECEIPT_ID_PATTERN.search(text)
    return match.group(0).upper() if match else None


def _extract_envelope(text: str) -> object | None:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def _route_inspection(text: str, is_preflight: bool) -> RouteResult:
    kv = _extract_kv(text)
    fields: dict[str, str] = {}
    missing: list[str] = []

    amount = _extract_amount(text, kv)
    network = _extract_network(text, kv)
    asset = _extract_asset(text, kv)
    recipient = _extract_recipient(text, kv)
    max_amount = _extract_max_amount(text, kv)

    if amount:
        fields["amount"] = amount
    else:
        missing.append("amount (e.g. \"$0.001\")")
    if network:
        fields["network"] = network
    else:
        missing.append("network (currently only \"Base\" is supported)")
    if asset:
        fields["asset"] = asset
    else:
        missing.append("asset (e.g. \"USDC\")")
    if recipient:
        fields["recipient"] = recipient
    else:
        missing.append("recipient address (0x...)")
    if max_amount:
        fields["max_amount"] = max_amount
    # max_amount is optional -- inspect_payment accepts an unconstrained
    # policy via acknowledge_unconstrained; see formatting.py.

    intent = Intent.PREFLIGHT_INFO if is_preflight else Intent.INSPECT_PAYMENT
    return RouteResult(intent=intent, fields=fields, missing=missing)


_EXECUTION_REQUEST_PHRASES = (
    "send a payment", "send the payment", "send this payment",
    "make a payment", "execute this payment", "execute the payment",
    "pay this", "pay for me", "transfer usdc", "send usdc",
    "authorize this payment", "sign this transaction",
)


def route(text: str) -> RouteResult:
    """Deterministically classify one incoming chat message.

    Keyword precedence: an explicit receipt id present anywhere routes to
    GET_RECEIPT unless the message also says "verify", in which case it
    routes to VERIFY_RECEIPT. "preflight"/"durable"/"signed" language routes
    inspection-shaped requests to PREFLIGHT_INFO instead of INSPECT_PAYMENT.
    A request to actually execute/send/sign a payment is always refused,
    never routed to any tool -- this adapter has no wallet and no payment
    capability of any kind.
    """
    lowered = text.lower()

    if any(phrase in lowered for phrase in _EXECUTION_REQUEST_PHRASES):
        return RouteResult(intent=Intent.UNKNOWN, fields={"refusal": "execution"})

    receipt_id = _extract_receipt_id(text)
    envelope = _extract_envelope(text)

    if "verify" in lowered and (receipt_id or envelope):
        return RouteResult(
            intent=Intent.VERIFY_RECEIPT,
            fields={"receipt_id": receipt_id} if receipt_id else {},
            envelope=envelope if not receipt_id else None,
        )
    if receipt_id and "verify" not in lowered:
        return RouteResult(intent=Intent.GET_RECEIPT, fields={"receipt_id": receipt_id})
    if "verify" in lowered and any(w in lowered for w in ("receipt", "envelope", "proof")):
        return RouteResult(intent=Intent.VERIFY_RECEIPT, missing=["a receipt_id or a pasted receipt envelope"])
    if any(w in lowered for w in ("receipt", "retrieve")) and "verify" not in lowered:
        if receipt_id:
            return RouteResult(intent=Intent.GET_RECEIPT, fields={"receipt_id": receipt_id})
        return RouteResult(intent=Intent.GET_RECEIPT, missing=["a receipt_id (OCD-RCP-...)"])

    is_preflight = any(w in lowered for w in ("preflight", "durable", "signed preflight"))
    if any(w in lowered for w in ("inspect", "preflight", "propose", "proposed payment", "check this payment")):
        return _route_inspection(text, is_preflight)

    return RouteResult(intent=Intent.UNKNOWN)
