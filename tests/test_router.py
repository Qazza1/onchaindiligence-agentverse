from app.intents import Intent, route


def test_inspect_allow_shaped_request_extracts_all_fields():
    r = route(
        "Inspect a $0.001 USDC payment on Base to "
        "0x52E29e0d2Aa49bfBfC548C0A9F2196F4aa51f3ea against a $1 maximum."
    )
    assert r.intent == Intent.INSPECT_PAYMENT
    assert r.missing == []
    assert r.fields["amount"] == "0.001"
    assert r.fields["network"] == "eip155:8453"
    assert r.fields["asset"] == "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
    assert r.fields["recipient"] == "0x52E29e0d2Aa49bfBfC548C0A9F2196F4aa51f3ea"
    assert r.fields["max_amount"] == "1"


def test_inspect_missing_fields_are_reported_not_guessed():
    r = route("Inspect a payment for me")
    assert r.intent == Intent.INSPECT_PAYMENT
    assert "amount (e.g. \"$0.001\")" in r.missing
    assert "recipient address (0x...)" in r.missing
    assert "amount" not in r.fields


def test_preflight_language_routes_to_preflight_info_not_inspect():
    r = route(
        "I need a durable preflight for $0.001 USDC on Base to "
        "0x52E29e0d2Aa49bfBfC548C0A9F2196F4aa51f3ea against a $1 maximum."
    )
    assert r.intent == Intent.PREFLIGHT_INFO
    assert r.missing == []


def test_get_receipt_by_id():
    r = route("Retrieve OCD receipt OCD-RCP-NB51-QG4S-VCAN-Y57F.")
    assert r.intent == Intent.GET_RECEIPT
    assert r.fields["receipt_id"] == "OCD-RCP-NB51-QG4S-VCAN-Y57F"


def test_get_receipt_missing_id():
    r = route("Retrieve a receipt for me")
    assert r.intent == Intent.GET_RECEIPT
    assert r.missing


def test_verify_receipt_by_id():
    r = route("Verify OCD-RCP-NB51-QG4S-VCAN-Y57F and tell me if it's valid.")
    assert r.intent == Intent.VERIFY_RECEIPT
    assert r.fields["receipt_id"] == "OCD-RCP-NB51-QG4S-VCAN-Y57F"


def test_verify_receipt_by_pasted_envelope():
    r = route('Verify this receipt: {"schema": "x", "receipt": {}, "proof": {}}')
    assert r.intent == Intent.VERIFY_RECEIPT
    assert r.envelope == {"schema": "x", "receipt": {}, "proof": {}}


def test_verify_receipt_missing_both_id_and_envelope():
    r = route("Please verify a receipt for me")
    assert r.intent == Intent.VERIFY_RECEIPT
    assert r.missing


def test_execution_request_is_refused_not_routed_to_a_tool():
    r = route("Can you send a payment for me?")
    assert r.intent == Intent.UNKNOWN
    assert r.fields.get("refusal") == "execution"


def test_unrelated_message_is_unknown():
    r = route("What's the weather like today?")
    assert r.intent == Intent.UNKNOWN
    assert r.fields.get("refusal") is None
