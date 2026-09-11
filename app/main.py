"""FastAPI Agent Chat Protocol (ACP) adapter.

GET  /status -- health check.
POST /chat   -- accepts an ACP ChatMessage, returns a reply ChatMessage.

This process holds no OCD credential and no wallet. Every reply is either:
  (a) the unmodified result of one call to OCD's existing, public, no-auth
      MCP surface (see app/mcp_client.py), or
  (b) a request for missing information, or a scope refusal --
      never a guess, never a fabricated OCD result.

Implementation note: uagents_core's ChatMessage/ChatAcknowledgement models
are built on pydantic.v1.BaseModel (uagents_core.models.Model), which
current FastAPI (>=0.113) no longer accepts directly as a route type
annotation (raises PydanticV1NotSupportedError). This endpoint therefore
accepts/returns plain dict bodies and parses/serializes through the real
ChatMessage model internally via its pydantic-v1 API (parse_obj/dict) --
still full ACP schema validation, just not surfaced through FastAPI's own
OpenAPI generation.

Wire-format note: the exact synchronous request/response shape Agentverse's
external-agent adapter expects for /chat is not fully pinned down by public
docs at the time this was written (see README "Known unknowns"). This
implementation takes the most defensible reading -- POST a ChatMessage,
receive a reply ChatMessage as the HTTP response body -- and should be
re-verified against a real Agentverse registration before being relied on
end-to-end.
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import ValidationError as PydanticV2ValidationError
from pydantic.v1 import ValidationError as PydanticV1ValidationError
from uagents_core.contrib.protocols.chat import ChatMessage, TextContent

from app.intents import route
from app.responder import respond

app = FastAPI(title="OnChainDiligence Agentverse Adapter")


@app.get("/status")
async def status() -> dict:
    return {"status": "ok", "service": "onchaindiligence-agentverse-adapter"}


@app.post("/chat")
async def chat(body: dict) -> dict:
    try:
        message = ChatMessage.parse_obj(body)
    except (PydanticV1ValidationError, PydanticV2ValidationError) as exc:
        raise HTTPException(status_code=422, detail=f"invalid ChatMessage: {exc}") from exc

    text = message.text()
    route_result = route(text)
    reply_text = await respond(route_result)
    reply = ChatMessage(content=[TextContent(text=reply_text)])
    return reply.dict()
