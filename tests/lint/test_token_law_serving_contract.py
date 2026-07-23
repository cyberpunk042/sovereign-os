"""SDD-512 — the token-law serving-boundary (CONNECT) contract.

The Expose arc (SDD-507 route → SDD-510 osctl/profile/env → SDD-511 dashboard)
made the M00117 decision inspectable, configurable, and visualized, but it never
APPLIED the mask to a served token: `complete_with_token_law` drove the mask over
a `DecoderStack`, while production `/v1/messages` self-generates on a DIFFERENT
stack (`sovereign-quant-model`'s `QuantModel`, static-mask only), and proxy
backends expose no logits at all. This lint pins the CONNECT wiring:

  * the serving model gains a per-step dynamic-mask decode primitive mirroring
    DecoderStack's (`QuantModel::generate_dynamic_token_law_until[_with]`);
  * an optional `token_law` constraint on /v1/messages (`ServingTokenLaw`) that
    compiles against the model's REAL vocab and drives the SAME `fused_mask`;
  * the honesty boundary: a law-carrying request against a PROXY backend is
    REFUSED (no logit access), never served unconstrained;
  * the safety spine (StreamGuard redaction) still wraps the constrained path;
  * SDD-512 documents the no-logit-access boundary + the Connect arc.
"""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
QUANT = REPO / "crates" / "sovereign-quant-model" / "src" / "lib.rs"
QUANT_TOML = REPO / "crates" / "sovereign-quant-model" / "Cargo.toml"
GW_LIB = REPO / "crates" / "sovereign-gatewayd" / "src" / "lib.rs"
GW_HTTP = REPO / "crates" / "sovereign-gatewayd" / "src" / "http.rs"
GW_TOML = REPO / "crates" / "sovereign-gatewayd" / "Cargo.toml"
SDD = REPO / "docs" / "sdd" / "512-token-law-serving-boundary.md"


def test_quant_model_gains_a_dynamic_token_law_decode_primitive():
    src = QUANT.read_text(encoding="utf-8")
    # The streaming primitive the gateway drives + the non-streaming convenience.
    assert "pub fn generate_dynamic_token_law_until_with" in src
    assert "pub fn generate_dynamic_token_law_until" in src
    # The per-step hook shape: given the ids so far, return the allow-bitset or
    # None to STOP (never sample an all-masked row).
    assert "FnMut(&[usize]) -> Option<Vec<u64>>" in src
    # It -inf-masks via the same kernel DecoderStack uses (checkpoint-free).
    assert "sovereign_token_law_mask::mask_logits" in src
    # A confinement + a stop test travel with the primitive.
    assert "dynamic_token_law_confines_every_step_to_the_allowed_bitset" in src
    assert "dynamic_token_law_stops_when_the_hook_returns_none" in src


def test_quant_model_deps_the_masking_kernel():
    deps = QUANT_TOML.read_text(encoding="utf-8").split("[dependencies]", 1)[1]
    assert 'path = "../sovereign-token-law-mask"' in deps


def test_serving_token_law_compiles_over_the_real_vocab():
    src = GW_LIB.read_text(encoding="utf-8")
    assert "pub struct ServingTokenLaw" in src
    # The same planes the fuse route inspects — but NOT a client-supplied vocab
    # (serving masks over the model's real tokenizer) and NOT `generated` (the
    # decode loop supplies the running prefix).
    for field in ("schema", "regex", "denylist", "regex_denylist", "policy_planes", "mask_layers"):
        assert f"pub {field}" in src, f"ServingTokenLaw must carry `{field}`"
    assert "pub vocab" not in src.split("pub struct ServingTokenLaw", 1)[1].split("}", 1)[0]
    # Compiles against the model's real vocab into the checkpoint-free primitive.
    assert "CompiledFuse::compile" in src
    assert "fn is_unconstrained" in src
    # The per-step hook decodes ids -> text and fuses (same `fused_mask`).
    assert "fn token_law_step" in src
    assert "compiled.fused_mask" in src


def test_serving_path_is_law_aware_and_preserves_the_safety_spine():
    src = GW_LIB.read_text(encoding="utf-8")
    # The law-carrying serving method; the static one delegates to it.
    assert "pub fn generate_chat_with_sampler_law" in src
    assert "law: Option<&ServingTokenLaw>" in src
    # The constrained path drives the dynamic loop...
    assert "generate_dynamic_token_law_until_with" in src
    # ...and the output-side safety spine (StreamGuard redaction) still wraps it
    # (the constrained decode is inside the same guarded body).
    assert "StreamGuard::new" in src


def test_v1_messages_parses_refuses_on_proxy_and_reports():
    src = GW_HTTP.read_text(encoding="utf-8")
    # Parses the optional constraint.
    assert "ServingTokenLaw" in src
    assert 'req.get("token_law")' in src
    # The honesty boundary: a law-carrying request to a proxy backend is REFUSED
    # with 422 (no logit access), never forwarded unconstrained.
    assert "422" in src
    assert "resolve_proxy" in src
    # The reply reports which laws bit.
    assert '"enforced"' in src
    assert "layers_active" in src


def test_gatewayd_deps_the_schema_grammar_type():
    deps = GW_TOML.read_text(encoding="utf-8").split("[dependencies]", 1)[1]
    assert 'path = "../sovereign-json-schema-grammar"' in deps


def test_sdd_512_documents_the_no_logit_access_boundary():
    assert SDD.is_file(), "SDD-512 must exist"
    text = SDD.read_text(encoding="utf-8")
    assert text.startswith("# SDD-512 —"), "H1 must be the canonical SDD-512 heading"
    low = text.lower()
    assert "no-logit-access" in low or "no logit access" in low
    assert "connect" in low
    assert "proxy" in low and "refus" in low, "the proxy-refuse boundary must be documented"
    assert "quantmodel" in low or "quant-model" in low
