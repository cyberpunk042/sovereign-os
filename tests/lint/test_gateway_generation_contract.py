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


def test_gateway_uses_worker_pool_for_concurrent_generation():
    """F-2026-083: the primary model loads N independent worker copies
    (SOVEREIGN_GATEWAY_WORKERS) so concurrent requests no longer serialize
    behind a single Arc<Mutex<>>."""
    lib = _read("crates/sovereign-gatewayd/src/lib.rs")
    assert "workers: Vec<Arc<Mutex<Generator>>>" in lib, \
        "must declare a worker pool instead of a single generator"
    assert "SOVEREIGN_GATEWAY_WORKERS" in lib, \
        "must read worker count from env"
    assert "worker_idx: std::sync::atomic::AtomicUsize" in lib, \
        "must track round-robin slot atomically"
    assert "acquire_worker" in lib, \
        "must have a worker-acquisition method"
    assert "try_lock" in lib, \
        "must prefer idle workers via try_lock (F-2026-083)"
    assert "resolve_secondary" in lib, \
        "secondary lookup must be separate from primary worker selection"
    assert "resolve_model" not in lib, \
        "combined resolution advances the primary counter before acquire_worker"
    assert "next_worker_index" in lib, \
        "round-robin progression must be independently unit-testable"


def test_gateway_runs_memory_decay_thread():
    """F-2026-084: a unified monotonic clock stamps every request's `now`, and a
    periodic decay thread ages stale memories so they don't accumulate forever."""
    lib = _read("crates/sovereign-gatewayd/src/lib.rs")
    main = _read("crates/sovereign-gatewayd/src/main.rs")
    assert "born: std::time::Instant" in lib, \
        "must track process birth for unified clock"
    assert "clock_now" in lib, \
        "must expose unified clock method"
    assert "SOVEREIGN_GATEWAY_MAINTAIN_SECS" in main, \
        "must configure decay cadence"
    assert "SOVEREIGN_GATEWAY_MEMORY_TTL" in main, \
        "must configure decay TTL"
    assert "maintainer.maintain" in main, \
        "must spawn a decay thread calling maintain"


def test_gateway_openai_shim_threads_sampling_params():
    """F-2026-086: the OpenAI shim must parse temperature/top_p/top_k from the
    request and thread them into the generation sampler, not ignore them."""
    main = _read("crates/sovereign-gatewayd/src/main.rs")
    lib = _read("crates/sovereign-gatewayd/src/lib.rs")
    assert "generate_chat_with_sampler" in lib, \
        "must expose a sampler-aware generation path"
    assert "extract_sampler_config" in main, \
        "must parse sampling params from the request"
    assert "temperature" in main, \
        "must read temperature from request"
    assert "top_p" in main, \
        "must read top_p from request"
    assert "top_k" in main, \
        "must read top_k from request"
    # F-2026-086 penalties residual: the OpenAI penalties are parsed + threaded.
    assert "frequency_penalty" in main, \
        "must read frequency_penalty from request"
    assert "presence_penalty" in main, \
        "must read presence_penalty from request"
    # F-2026-086 logit_bias residual: parsed into (id, bias) pairs + threaded; a
    # biased request bypasses the completion cache (biased output is not cacheable).
    assert "parse_logit_bias" in main, \
        "must parse logit_bias from request"
    assert "logit_bias.is_empty()" in lib, \
        "a biased request must bypass the unbiased completion cache"
    # SDD-519 response_format: JSON mode enforced by the token-law grammar plane.
    assert "parse_response_format" in main, \
        "must parse response_format into a grammar schema"
    assert "Schema::Any" in main, \
        "json_object mode must map to the any-JSON grammar"
    grammar = _read("crates/sovereign-json-schema-grammar/src/lib.rs")
    assert "Any," in grammar and "fn any(" in grammar, \
        "the grammar crate must provide the recursive any-JSON Schema::Any"
    assert "SamplerConfig" in main, \
        "must construct a SamplerConfig from parsed params"
    assert "generate_chat_with_sampler" in main, \
        "must call the sampler-aware path from the shim"


def test_gateway_openai_shim_supports_non_streaming_json():
    """F-2026-086: the OpenAI shim must return a full JSON object when
    `stream: false` instead of always streaming SSE."""
    main = _read("crates/sovereign-gatewayd/src/main.rs")
    assert "stream" in main, \
        "must inspect the stream parameter"
    assert 'chat.completion' in main, \
        "non-streaming response must use chat.completion object"
    assert "application/json" in main, \
        "non-streaming response must have application/json content type"
    assert '"message"' in main, \
        "non-streaming response must contain a message object"
    assert "choices" in main, \
        "non-streaming response must contain choices array"


def test_gateway_openai_shim_supports_multiple_completions():
    """F-2026-086 (final residual, closes the finding): the OpenAI shim parses
    `n` (number of completions), clamps it, and — non-streaming — returns N
    indexed choices with summed usage. `n>1` + streaming is an honest 400 (a
    single SSE frame carries one choice index)."""
    main = _read("crates/sovereign-gatewayd/src/main.rs")
    assert "fn parse_n(" in main, "must parse the OpenAI `n` parameter"
    assert ".clamp(1, 8)" in main, \
        "`n` must be clamped to bound the per-request generation fan-out"
    assert "n_choices" in main, "must bind the parsed completion count"
    # non-streaming loops N decodes into N indexed choices
    assert "for index in 0..n_choices" in main, \
        "non-streaming must loop N decodes into N indexed choices"
    # streaming with n>1 is refused honestly, not silently downgraded to one
    assert "n_choices > 1" in main, \
        "streaming with n>1 must be an honest 400, not a silent single choice"
