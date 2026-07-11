#!/usr/bin/env python3
"""
tests/lint/test_gateway_generation_contract.py — Phase-3 "the gateway generates"
contract.

Guards the wiring that turns sovereign-gatewayd from a pure decision surface into
a local generation brain (the OpenAI chat shim) and repoints the cockpit chat
console at it:

  * the gateway serves POST /v1/chat/completions as OpenAI SSE (the shape
    scripts/inference/prompt.py consumes) and generates via a locally-loaded
    model (SOVEREIGN_GATEWAY_MODEL), flipping the OpenAiShim surface Live;
  * the DecoderLayer trait is Send (so a built model can be owned by the
    thread-per-connection daemon);
  * prompt.py targets the gateway (:8787) first with a graceful tier-router
    (:8080) fallback, and still carries the honest-error phrases the console
    relies on;
  * the daemon and the serve CLI share the one real tokenizer crate.

Stdlib + pytest only; no build, no running daemon.
"""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (REPO / rel).read_text(encoding="utf-8")


def test_gateway_serves_openai_chat_shim_as_sse():
    main = _read("crates/sovereign-gatewayd/src/main.rs")
    assert "/v1/chat/completions" in main, "no chat-completions route"
    assert "stream_chat_completions" in main, "no streaming handler"
    assert "text/event-stream" in main, "must respond as SSE"
    assert "[DONE]" in main, "SSE must terminate with the OpenAI [DONE] sentinel"
    assert "completion_tokens" in main, "final chunk must carry usage"


def test_gateway_generates_from_a_local_model():
    lib = _read("crates/sovereign-gatewayd/src/lib.rs")
    assert "SOVEREIGN_GATEWAY_MODEL" in lib, "model dir must be env-configured"
    assert "generate_chat" in lib, "no generation method"
    assert "has_generator" in lib, "no generator presence check"
    # the OpenAI shim goes Live only when a model is loaded
    assert "GatewaySurface::OpenAiShim if gen_live" in lib, \
        "OpenAiShim must flip Live only when a generator is loaded"


def test_decoder_layer_is_send_for_the_threaded_daemon():
    dl = _read("crates/sovereign-decoder-layer/src/lib.rs")
    assert "pub trait DecoderLayer: std::fmt::Debug + Send" in dl, \
        "DecoderLayer must be Send so a model can be owned by a daemon thread"


def test_prompt_console_repointed_to_gateway_with_fallback():
    p = _read("scripts/inference/prompt.py")
    assert '"http://127.0.0.1:8787"' in p, "prompt.py must default to the gateway"
    assert "FALLBACK_URL" in p and "8080" in p, \
        "prompt.py must fall back to the tier router (:8080)"
    # the honest-error contract the console + unit tests depend on (SB-077)
    assert "router unreachable" in p and "inference start router" in p, \
        "the honest-error phrases must survive the repoint"


def test_serve_and_gateway_share_the_one_tokenizer_crate():
    for manifest in ("crates/sovereign-gatewayd/Cargo.toml",
                     "crates/sovereign-serve/Cargo.toml"):
        assert "sovereign-hf-tokenizer" in _read(manifest), \
            f"{manifest} must load real models via sovereign-hf-tokenizer"
