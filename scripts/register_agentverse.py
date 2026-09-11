"""Register this adapter on Agentverse -- OPERATOR-RUN ONLY.

This script is NOT run by Claude/the agent that built this repo: it
requires an Agentverse.ai account and an API key, which is account
creation -- explicitly outside what this session performs. It's provided
ready to run so registration is a single command once you have that key.

Confirmed against the currently installed uagents-core==0.4.9 source
(uagents_core/utils/registration.py): register_chat_agent() is the current,
official, chat-protocol-aware registration entry point. It requires
`agentverse_api_key` -- there is no code path in this library version that
registers to Agentverse without one (see README "Known differences from
the D2.10I research" for why this corrects the earlier research).

Usage (testnet-safe -- this call itself doesn't spend FET; see README for
what does):
    export AGENTVERSE_AGENT_SEED=<the seed generate_identity.py wrote to .env>
    export AGENTVERSE_API_KEY=<your Agentverse.ai API key>
    export ADAPTER_PUBLIC_URL=https://<your-deployed-adapter>/chat
    python scripts/register_agentverse.py
"""
import os

from uagents_core.utils.registration import (
    RegistrationRequestCredentials,
    register_chat_agent,
)

README = """## Summary
OnChainDiligence (OCD) answers one question about an autonomous agent's
payment: did it do what it was authorized to do -- and can I prove it? It
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
"Inspect a $0.001 USDC payment on Base against a $1 maximum."
"Retrieve OCD receipt OCD-RCP-NB51-QG4S-VCAN-Y57F."
"Verify that receipt and tell me what it does and doesn't prove."

## Use Cases
- An agent developer sanity-checking a payment before it executes
- A support team investigating whether a past agent payment actually settled
- Anyone who received an OCD receipt and wants to independently confirm it

## Limitations
- Read-only: this agent cannot send payments, custody funds, or authorize
  a wallet on your behalf
- Inspection is a deterministic policy comparison only -- no sanctions
  screening, no signing
- VALID confirms cryptographic integrity/authenticity under the OCD
  verifier contract, not that the underlying action succeeded or was safe
"""

STARTER_PROMPTS = [
    "Inspect a $0.001 USDC payment on Base against a $1 maximum.",
    "Retrieve OCD receipt OCD-RCP-NB51-QG4S-VCAN-Y57F.",
    "Verify OCD-RCP-NB51-QG4S-VCAN-Y57F and tell me what it does and doesn't prove.",
]


def main() -> None:
    seed = os.environ["AGENTVERSE_AGENT_SEED"]
    api_key = os.environ["AGENTVERSE_API_KEY"]
    endpoint = os.environ["ADAPTER_PUBLIC_URL"]

    credentials = RegistrationRequestCredentials(
        agent_seed_phrase=seed,
        agentverse_api_key=api_key,
    )
    register_chat_agent(
        name="OnChainDiligence",
        endpoint=endpoint,
        active=True,
        credentials=credentials,
        description="Accountability and reconciliation for autonomous agent payments.",
        readme=README,
        starter_prompts=STARTER_PROMPTS,
    )
    print("Registered. Check the Agentverse dashboard to confirm Active status.")


if __name__ == "__main__":
    main()
