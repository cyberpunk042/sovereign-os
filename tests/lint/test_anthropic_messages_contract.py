#!/usr/bin/env python3
"""
tests/lint/test_anthropic_messages_contract.py — the Anthropic Messages API surface
(docs/sdd/205-anthropic-messages-api.md).

Guards that sovereign-gatewayd speaks the Anthropic Messages API so VS Code /
Claude Code / Cline can drive the box's local model:

  * POST /v1/messages generates the Anthropic message shape (non-stream in http.rs);
  * stream:true is served as the Anthropic SSE event sequence (in main.rs);
  * GET /v1/models + POST /v1/messages/count_tokens exist;
  * the sovereign DECISION moved to /v1/infer (not /v1/messages);
  * the wiring how-to (ANTHROPIC_BASE_URL) is documented.

Stdlib + pytest only (source-level contract; the live behaviour is exercised by
the gateway's own Rust lib + transport tests, verified end-to-end with a model).
"""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HTTP = REPO / "crates" / "sovereign-gatewayd" / "src" / "http.rs"
MAIN = REPO / "crates" / "sovereign-gatewayd" / "src" / "main.rs"
SDD = REPO / "docs" / "sdd" / "205-anthropic-messages-api.md"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def test_messages_endpoint_is_the_anthropic_api():
    http = _read(HTTP)
    assert '("POST", "/v1/messages") => anthropic_message' in http, \
        "/v1/messages must route to the Anthropic generator"
    assert "fn anthropic_prompt" in http and "fn anthropic_message" in http, \
        "the Anthropic prompt flattener + message handler must exist"
    # the Anthropic non-stream response shape
    for tok in ('"type": "message"', '"role": "assistant"', '"stop_reason": "end_turn"',
                '"input_tokens"', '"output_tokens"'):
        assert tok in http, f"Anthropic message shape missing: {tok!r}"
    # honest error envelope + loopback (no fabricated output)
    assert "fn anthropic_err" in http and '"type": "error"' in http, "Anthropic error envelope required"
    assert "has_generator()" in http, "no model → an honest error, never fabricated"


def test_streaming_is_the_anthropic_sse_sequence():
    main = _read(MAIN)
    assert "fn stream_anthropic_messages" in main, "the Anthropic SSE handler must exist"
    assert 'route == "/v1/messages"' in main and "wants_stream" in main, \
        "main.rs must intercept /v1/messages for SSE when stream:true"
    for event in ("message_start", "content_block_start", "content_block_delta",
                  "text_delta", "content_block_stop", "message_delta", "message_stop"):
        assert event in main, f"Anthropic SSE event missing: {event}"


def test_companion_endpoints_and_decision_moved():
    http = _read(HTTP)
    assert '("GET", "/v1/models") => anthropic_models' in http, "GET /v1/models must exist"
    assert '"/v1/messages/count_tokens") => anthropic_count_tokens' in http, "count_tokens must exist"
    # the sovereign DECISION is /v1/infer now — /v1/messages is NOT in the decision group
    assert '("POST", "/v1/infer")' in http, "/v1/infer must remain the decision endpoint"
    # /v1/messages must not be grouped with the CortexRequest decision arm
    decision_arm = http.split('("POST", "/v1/infer")')[1].split("=>")[0]
    assert "/v1/messages" not in decision_arm, "/v1/messages must not route to the decision engine"


def test_wiring_how_to_is_documented():
    assert SDD.is_file(), "the Anthropic Messages API SDD is missing"
    doc = _read(SDD)
    assert "ANTHROPIC_BASE_URL" in doc, "must document how to point Claude Code at the box"
    for tool in ("VS Code", "Claude Code", "Cline"):
        assert tool in doc, f"the wiring how-to must mention {tool}"
    idx = _read(REPO / "docs" / "sdd" / "INDEX.md")
    assert "205-anthropic-messages-api.md" in idx or "SDD-205" in idx, "SDD-205 not registered in INDEX"
