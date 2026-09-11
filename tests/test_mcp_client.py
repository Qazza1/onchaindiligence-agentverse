import httpx
import pytest
import respx

from app import mcp_client
from app.config import OCD_PUBLIC_MCP_URL


@respx.mock
async def test_call_tool_returns_structured_result():
    respx.post(OCD_PUBLIC_MCP_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "content": [{"type": "text", "text": '{"found": true}'}],
                    "structuredContent": {"found": True},
                },
            },
        )
    )
    result = await mcp_client.get_receipt("OCD-RCP-NB51-QG4S-VCAN-Y57F")
    assert result.structured == {"found": True}
    assert result.is_error is False


@respx.mock
async def test_call_tool_raises_on_network_error():
    respx.post(OCD_PUBLIC_MCP_URL).mock(side_effect=httpx.ConnectError("boom"))
    with pytest.raises(mcp_client.McpCallError):
        await mcp_client.get_receipt("OCD-RCP-NB51-QG4S-VCAN-Y57F")


@respx.mock
async def test_call_tool_raises_on_http_error_status():
    respx.post(OCD_PUBLIC_MCP_URL).mock(return_value=httpx.Response(500, text="oops"))
    with pytest.raises(mcp_client.McpCallError):
        await mcp_client.get_receipt("OCD-RCP-NB51-QG4S-VCAN-Y57F")


@respx.mock
async def test_call_tool_raises_on_jsonrpc_error():
    respx.post(OCD_PUBLIC_MCP_URL).mock(
        return_value=httpx.Response(
            200,
            json={"jsonrpc": "2.0", "id": 1, "error": {"message": "unknown tool"}},
        )
    )
    with pytest.raises(mcp_client.McpCallError, match="unknown tool"):
        await mcp_client.get_receipt("OCD-RCP-NB51-QG4S-VCAN-Y57F")


@respx.mock
async def test_call_tool_surfaces_tool_level_error_without_raising():
    respx.post(OCD_PUBLIC_MCP_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "isError": True,
                    "content": [{"type": "text", "text": "bad envelope"}],
                },
            },
        )
    )
    result = await mcp_client.verify_receipt(envelope={"bad": True})
    assert result.is_error is True
    assert result.text == "bad envelope"
