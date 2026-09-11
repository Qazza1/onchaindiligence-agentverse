import uuid
from datetime import datetime, timezone

import httpx
import respx
from fastapi.testclient import TestClient

from app.config import OCD_PUBLIC_MCP_URL
from app.main import app

client = TestClient(app)


def chat_message(text: str) -> dict:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "msg_id": str(uuid.uuid4()),
        "content": [{"type": "text", "text": text}],
    }


def _mcp_result(structured: dict, is_error: bool = False) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "isError": is_error,
            "content": [{"type": "text", "text": str(structured)}],
            "structuredContent": structured,
        },
    }


def test_status_ok():
    response = client.get("/status")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@respx.mock
def test_chat_inspect_payment_round_trips_to_mcp():
    route = respx.post(OCD_PUBLIC_MCP_URL).mock(
        return_value=httpx.Response(
            200,
            json=_mcp_result({"decision": {"status": "ALLOW", "reasons": ["All configured policy checks passed."]}}),
        )
    )
    response = client.post(
        "/chat",
        json=chat_message(
            "Inspect a $0.001 USDC payment on Base to "
            "0x52E29e0d2Aa49bfBfC548C0A9F2196F4aa51f3ea against a $1 maximum."
        ),
    )
    assert response.status_code == 200
    body = response.json()
    text = "".join(c["text"] for c in body["content"] if c["type"] == "text")
    assert "ALLOW" in text
    assert route.called
    sent = route.calls.last.request.content
    assert b"inspect_payment" in sent


@respx.mock
def test_chat_get_receipt():
    respx.post(OCD_PUBLIC_MCP_URL).mock(
        return_value=httpx.Response(
            200,
            json=_mcp_result(
                {
                    "found": True,
                    "envelope": {
                        "receipt": {
                            "action": {"amount": "0.001", "network": "eip155:8453", "recipient": "0x52E2..."},
                            "decision": {"status": "ALLOW"},
                            "execution": {"status": "CONFIRMED"},
                            "settlement": {"status": "CONFIRMED"},
                            "limitations": ["service-delivery-verification is NOT_CHECKED"],
                        }
                    },
                }
            ),
        )
    )
    response = client.post("/chat", json=chat_message("Retrieve OCD receipt OCD-RCP-NB51-QG4S-VCAN-Y57F."))
    text = "".join(c["text"] for c in response.json()["content"])
    assert "CONFIRMED" in text
    assert "service-delivery-verification" in text


@respx.mock
def test_chat_verify_receipt_valid_never_becomes_safe_language():
    respx.post(OCD_PUBLIC_MCP_URL).mock(
        return_value=httpx.Response(
            200,
            json=_mcp_result({"state": "VALID", "code": "ok", "message": "receipt content, id, digest and signature are all consistent"}),
        )
    )
    response = client.post("/chat", json=chat_message("Verify OCD-RCP-NB51-QG4S-VCAN-Y57F."))
    text = "".join(c["text"] for c in response.json()["content"])
    assert "VALID" in text
    # The disclaimer must explicitly name what VALID does NOT mean, in the
    # exact terms the task prohibits translating it into.
    assert "does not mean the payment was safe, successful, compliant" in text


def test_chat_preflight_info_never_calls_paid_endpoint():
    with respx.mock:
        route = respx.post("https://mcp.onchaindiligence.com/public/mcp").mock(
            return_value=httpx.Response(200, json=_mcp_result({"decision": {"status": "ALLOW", "reasons": []}}))
        )
        paid_route = respx.post("https://mcp.onchaindiligence.com/mcp").mock(
            return_value=httpx.Response(200, json=_mcp_result({}))
        )
        response = client.post(
            "/chat",
            json=chat_message(
                "I need a durable preflight for $0.001 USDC on Base to "
                "0x52E29e0d2Aa49bfBfC548C0A9F2196F4aa51f3ea against a $1 maximum."
            ),
        )
        text = "".join(c["text"] for c in response.json()["content"])
        assert "paid preflight_payment" in text
        assert route.called
        assert paid_route.called is False


def test_chat_missing_payment_fields_asks_instead_of_guessing():
    response = client.post("/chat", json=chat_message("Inspect a payment for me"))
    text = "".join(c["text"] for c in response.json()["content"])
    assert "I need a bit more" in text
    assert "recipient" in text


@respx.mock
def test_chat_invalid_receipt_id_not_found():
    respx.post(OCD_PUBLIC_MCP_URL).mock(
        return_value=httpx.Response(200, json=_mcp_result({"found": False, "reason": "not-found"}))
    )
    response = client.post("/chat", json=chat_message("Retrieve OCD receipt OCD-RCP-0000-0000-0000-0000."))
    text = "".join(c["text"] for c in response.json()["content"])
    assert "No public receipt found" in text


@respx.mock
def test_chat_mcp_error_is_surfaced_not_silently_swallowed():
    respx.post(OCD_PUBLIC_MCP_URL).mock(return_value=httpx.Response(500, text="down"))
    response = client.post("/chat", json=chat_message("Retrieve OCD receipt OCD-RCP-NB51-QG4S-VCAN-Y57F."))
    text = "".join(c["text"] for c in response.json()["content"])
    assert "Could not reach OCD's receipt service" in text


def test_chat_execution_request_is_refused():
    response = client.post("/chat", json=chat_message("Can you send a payment for me?"))
    text = "".join(c["text"] for c in response.json()["content"])
    assert "can't send, authorize, or sign a payment" in text
