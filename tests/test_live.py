"""Live, read-only validation against the real OCD public MCP surface.

Not run by default (marked `live`) -- these make real network calls to
https://mcp.onchaindiligence.com/public/mcp. No payment, no write, no
private data: every call here is one already-live, no-auth, free tool call,
identical to what the deployed adapter itself will make. Run explicitly with:

    pytest -m live
"""
import pytest

from app import mcp_client

pytestmark = pytest.mark.live

REAL_RECEIPT_ID = "OCD-RCP-NB51-QG4S-VCAN-Y57F"


async def test_live_inspect_payment_allow():
    result = await mcp_client.inspect_payment(
        action={
            "kind": "PAYMENT",
            "network": "eip155:8453",
            "asset": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
            "amount": "0.001",
            "recipient": "0x52E29e0d2Aa49bfBfC548C0A9F2196F4aa51f3ea",
        },
        policy={"max_amount": "1.00", "allowed_networks": ["eip155:8453"]},
    )
    assert result.is_error is False
    assert result.structured["decision"]["status"] == "ALLOW"


async def test_live_get_real_receipt():
    result = await mcp_client.get_receipt(REAL_RECEIPT_ID)
    assert result.structured["found"] is True


async def test_live_verify_real_receipt_valid():
    result = await mcp_client.verify_receipt(receipt_id=REAL_RECEIPT_ID)
    assert result.structured["state"] == "VALID"


async def test_live_get_receipt_not_found():
    result = await mcp_client.get_receipt("OCD-RCP-0000-0000-0000-0000")
    assert result.structured["found"] is False
