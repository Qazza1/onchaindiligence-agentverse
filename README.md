# OnChainDiligence — Agentverse Adapter

A thin distribution adapter making OnChainDiligence (OCD) reachable from
Agentverse / ASI:One via the Agent Chat Protocol (ACP). It reimplements
nothing: every reply is the unmodified result of one call to OCD's existing,
public, no-auth MCP surface.

```
Agentverse / ASI:One
        ↓  Agent Chat Protocol
this adapter (FastAPI, stateless)
        ↓  plain HTTPS tools/call
https://mcp.onchaindiligence.com/public/mcp
        ↓
existing OCD backend (same policy / receipt / verification semantics)
```

## Agent profile

- **Name:** OnChainDiligence
- **Handle:** `@onchaindiligence`
- **Short description:** Accountability and reconciliation for autonomous agent payments.
- **About:** OnChainDiligence compares what an agent was permitted to do with provider claims and independently observed evidence, then shows what matched, what disagreed and what remains unknown.

## Summary

OnChainDiligence (OCD) answers one question about an autonomous agent's
payment: did it do what it was authorized to do — and can I prove it? It
inspects a proposed payment against policy before execution, and
independently verifies signed payment receipts against Base settlement
after execution.

## Key Features

- Inspect a proposed payment against a policy (max amount, allowed network/asset)
- Retrieve a public, signed OCD receipt by its exact ID
- Verify a receipt's cryptographic proof: VALID, INVALID, or UNVERIFIABLE
- Free, no account, no wallet connection required for any of the above

## Usage

Ask things like:

```
Inspect a $0.001 USDC payment on Base against a $1 maximum.
Retrieve OCD receipt OCD-RCP-NB51-QG4S-VCAN-Y57F.
Verify that receipt and tell me what it does and doesn't prove.
```

## Use Cases

- An agent developer sanity-checking a payment before it executes
- A support team investigating whether a past agent payment actually settled
- Anyone who received an OCD receipt and wants to independently confirm it

## Limitations

- Read-only: this agent cannot send payments, custody funds, or authorize a
  wallet on your behalf
- Inspection is a deterministic policy comparison only — no sanctions
  screening, no signing
- VALID confirms cryptographic integrity/authenticity under the OCD
  verifier contract, not that the underlying action succeeded or was safe
- "Preflight" requests return a free, unsigned preview via `inspect_payment`
  only; a durable, signed PREFLIGHT receipt requires OCD's paid
  `preflight_payment` tool, which this adapter never calls on your behalf

## Architecture / capabilities exposed

| Intent | OCD tool called | Cost |
|---|---|---|
| `INSPECT_PAYMENT` | `inspect_payment` on `/public/mcp` | Free |
| `GET_RECEIPT` | `get_receipt` on `/public/mcp` | Free |
| `VERIFY_RECEIPT` | `verify_receipt` on `/public/mcp` | Free |
| `PREFLIGHT_INFO` | `inspect_payment` (preview) + a pointer to the paid `preflight_payment` tool | Free |

No new OCD endpoint exists or was added. No OCD API key is required or
held by this adapter — it calls the same free, no-auth surface any external
client (Claude, ChatGPT) already uses.

The intent router (`app/intents.py`) is deterministic keyword/regex
matching — no LLM classifier. Missing required fields (amount, network,
asset, recipient) are always asked for, never guessed. A request to
actually send/sign/authorize a payment is always refused, routed to no
tool — this adapter has no wallet and no payment capability of any kind.

## Local development

```bash
python -m venv venv && source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

`GET /status` and `POST /chat` are then available at `http://127.0.0.1:8000`.

## Testing

```bash
pytest -m "not live"   # unit tests, no network
pytest -m live         # live, read-only calls against the real OCD endpoint
```

## Identity

```bash
python scripts/generate_identity.py
```

Generates exactly one dedicated Agentverse identity for this adapter (a
random seed → a `uagents_core` address). This is a **new** identity —
never the Technocore DID, any OCD signing key, any wallet key, or any API
credential. The seed is written to a local, gitignored `.env` and never
logged or printed; only the resulting public `agent1q...` address is
printed, which is safe to share (it's how other agents address this one).

## Registration (operator step — not run by this repo's automation)

`scripts/register_agentverse.py` is ready to run once you have an
Agentverse.ai account and API key:

```bash
export AGENTVERSE_AGENT_SEED=<from .env>
export AGENTVERSE_API_KEY=<your Agentverse API key>
export ADAPTER_PUBLIC_URL=https://<your-deployed-adapter>/chat
python scripts/register_agentverse.py
```

### Known differences from the D2.10I research

The D2.10I spec (based on 2026-era blog/doc summaries) suggested a uAgents
process could self-register to the testnet Almanac purely from a local
seed, with no Agentverse account. **Checked directly against the currently
installed `uagents-core==0.4.9` source** (not just docs) before writing any
registration code: `register_chat_agent()` — the current, official,
chat-protocol-aware entry point — requires `agentverse_api_key` in every
code path. There is no registration function in this library version that
succeeds without one. **Creating that account/API key is account creation,
which is outside what this build session performs** — it's the one
required operator step before registration (testnet or mainnet) can happen
at all.

### Mainnet cost

Not established by this build — `register_chat_agent()`'s registration
call itself is an Agentverse API call, not a specific on-chain FET spend
visible from the library source. The wider Fetch.ai ecosystem documents a
small, periodically-renewed (~48h) FET fee for Almanac registration
generally; testnet is faucet-funded. **Confirm the exact current mainnet
fee/renewal amount in the Agentverse dashboard before registering on
mainnet** — do not assume a figure from older research.

## Known unknowns

- **Exact `/chat` wire semantics on Agentverse's real external-agent
  adapter path** are not fully pinned down by current public docs. This
  implementation's best-effort reading: POST a `ChatMessage`, receive a
  reply `ChatMessage` as the HTTP response body. Verified correct against
  this adapter's own test suite and a real local HTTP round trip (see
  `tests/test_chat_endpoint.py`); **not yet verified against a live
  Agentverse registration**, since that requires the account above.
  Re-verify this once registered.
- Agentverse's exact avatar technical spec (size/format) is not published
  anywhere found during research — a square PNG reusing OCD's existing
  site seal/mark is the safe default.

## Security

- No OCD credential of any kind is held by this adapter.
- No wallet key, no payment capability — `PREFLIGHT_INFO` deliberately
  never calls the paid `preflight_payment` tool.
- The only new secret this integration introduces is the Agentverse agent
  seed — store and treat it like any other provider secret in this
  project: never in source, never logged.
- Chat input is untrusted text routed through a fixed keyword matcher, not
  given to an LLM with tool-call autonomy over OCD.
- Receipt content and pasted envelopes are treated as untrusted data, not
  instructions — matching OCD's own MCP tool descriptions.
