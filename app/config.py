"""Configuration — env vars only, no secrets committed.

OCD_MCP_URL is the existing, already-public, no-auth OnChainDiligence MCP
surface. This adapter never talks to any other OCD endpoint and never holds
an OCD API key -- see README "Architecture".
"""
import os

OCD_PUBLIC_MCP_URL = os.environ.get(
    "OCD_PUBLIC_MCP_URL", "https://mcp.onchaindiligence.com/public/mcp"
)
OCD_PAID_MCP_DOCS_URL = "https://onchaindiligence.com/developers#access-paths"

# Agent identity -- a local seed phrase, never committed, never logged.
# Purely used to derive this adapter's own Agentverse identity (uagents_core
# Identity.from_seed); holds no OCD credential of any kind.
AGENT_SEED_PHRASE = os.environ.get("AGENTVERSE_AGENT_SEED", "")

# HTTP client timeout for calls to the OCD public MCP.
MCP_REQUEST_TIMEOUT_SECONDS = float(os.environ.get("MCP_REQUEST_TIMEOUT_SECONDS", "15"))
