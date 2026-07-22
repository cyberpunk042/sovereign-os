"""SDD-507 — the token-law fusion data plane contract.

SDD-500…506 built the M00117 engine but left it SEALED (complete_with_token_law
had zero callers outside its tests). SDD-507 opens the M00155 operator surface by
factoring the engine's per-step DECISION — the fused allow-mask — into a
checkpoint-free crate, and exposing it as a data-plane HTTP route. This lint pins:

  * the new crate `sovereign-token-law-fuse` — the fusion primitive
    (CompiledFuse::fused_mask + FuseRequest), depending on the constraint SOURCES
    only, NEVER a transformer/decode-stack (that is the checkpoint-independence);
  * sovereign-llm's complete_with_token_law DELEGATES to fused_mask (generation
    and inspection share one mask definition — no divergence);
  * the route POST /v1/data-plane/token-law/fuse on gatewayd + the F00798 metric,
    DERIVING named layers from sources (not pre-packed bitsets);
  * SDD-507 documents the checkpoint-independence honesty + the 3-fork roadmap.
"""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
FUSE = REPO / "crates" / "sovereign-token-law-fuse" / "src" / "lib.rs"
FUSE_TOML = REPO / "crates" / "sovereign-token-law-fuse" / "Cargo.toml"
LLM = REPO / "crates" / "sovereign-llm" / "src" / "lib.rs"
GW_HTTP = REPO / "crates" / "sovereign-gatewayd" / "src" / "http.rs"
GW_LIB = REPO / "crates" / "sovereign-gatewayd" / "src" / "lib.rs"
SDD = REPO / "docs" / "sdd" / "507-token-law-fusion-data-plane.md"


def test_fuse_crate_is_the_checkpoint_free_primitive():
    src = FUSE.read_text(encoding="utf-8")
    assert "pub struct CompiledFuse" in src
    assert "pub fn fused_mask" in src, "the per-prefix decision"
    assert "pub struct FusedMask" in src
    assert "pub struct FuseRequest" in src, "the owned wire shape a route/CLI deserializes"
    assert "pub fn fuse" in src
    assert "#![forbid(unsafe_code)]" in src


def test_fuse_crate_depends_on_sources_only_not_a_transformer():
    toml = FUSE_TOML.read_text(encoding="utf-8")
    # Scope the check to the [dependencies] table — the prose `description`
    # legitimately names sovereign-llm as the consumer, but it must NOT be a dep.
    deps = toml.split("[dependencies]", 1)[1]
    # It must compose the real constraint sources...
    assert 'path = "../sovereign-token-law-mask"' in deps
    assert 'path = "../sovereign-json-schema-grammar"' in deps
    assert 'path = "../sovereign-regex-constrain"' in deps
    assert 'path = "../sovereign-token-law-deny"' in deps
    # ...but NEVER a decode stack / transformer / the llm hub — that is what makes
    # the fused mask checkpoint-independent (a pure function of sources + vocab).
    assert 'path = "../sovereign-decoder-stack"' not in deps
    assert 'path = "../sovereign-transformer-block"' not in deps
    assert 'path = "../sovereign-llm"' not in deps


def test_llm_delegates_generation_to_the_shared_fusion():
    src = LLM.read_text(encoding="utf-8")
    # complete_with_token_law now builds a CompiledFuse and calls fused_mask, so
    # generation and the data plane share ONE mask definition.
    assert "sovereign_token_law_fuse::CompiledFuse" in src
    assert "fused_mask" in src


def test_gatewayd_exposes_the_fuse_route_and_metric():
    http = GW_HTTP.read_text(encoding="utf-8")
    assert '"/v1/data-plane/token-law/fuse"' in http, "the F00797 route"
    assert "fn token_law_fuse" in http
    assert "FuseRequest" in http, "the route derives named layers from sources"
    lib = GW_LIB.read_text(encoding="utf-8")
    assert "sovereign_data_plane_token_law_mask_layers" in lib, "the F00798 metric"
    assert "record_token_law_fuse" in lib


def test_sdd_507_documents_checkpoint_independence_and_the_roadmap():
    assert SDD.is_file(), "SDD-507 must exist"
    doc = SDD.read_text(encoding="utf-8").lower()
    # the honesty framing: the mask is exact regardless of loaded weights
    assert "checkpoint" in doc
    assert "vocab" in doc
    # the operator surface it opens
    assert "/v1/data-plane/token-law/fuse" in doc
    assert "m00155" in doc
    # the 3-fork roadmap it establishes
    assert "expose" in doc and "connect" in doc and "deepen" in doc
