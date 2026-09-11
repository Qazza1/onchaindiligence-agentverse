"""Generate exactly one dedicated Agentverse identity for this adapter.

This is a NEW identity, unrelated to any existing OCD signing key, wallet
key, API credential, or the Technocore DID -- per the task's explicit
instruction not to reuse any of those.

The seed is written to a local .env file (already gitignored) and never
printed. Only the derived public agent address is printed -- safe to share,
since an agent address is public by design (it's how other agents/
Agentverse address messages to this one).

Run once:
    python scripts/generate_identity.py
"""
import secrets
from pathlib import Path

from uagents_core.identity import Identity

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def main() -> None:
    if ENV_PATH.exists() and "AGENTVERSE_AGENT_SEED=" in ENV_PATH.read_text():
        print(f"A seed already exists in {ENV_PATH} -- not overwriting.")
        print("Delete that line manually first if you really want a new identity.")
        return

    seed = secrets.token_hex(32)
    identity = Identity.from_seed(seed, 0)

    with ENV_PATH.open("a") as f:
        f.write(f"\nAGENTVERSE_AGENT_SEED={seed}\n")

    print(f"Seed written to {ENV_PATH} (gitignored, never printed here).")
    print(f"Public agent address: {identity.address}")


if __name__ == "__main__":
    main()
