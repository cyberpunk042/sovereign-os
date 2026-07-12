#!/usr/bin/env python3
"""
tests/lint/test_deliberate_reasoning_contract.py — Deliberate-reasoning framework
(docs/standing-directives/2026-07-12-deliberate-reasoning.md).

Guards the reasoning progression the operator made canonical — CoT → ToT → MCTS →
C-MCTS → CoAT — and the sovereign thesis that each maps onto a REAL execution
primitive, not a borrowed metaphor:

  * the standing directive exists, is registered, covers all five techniques, and
    names CoAT as the centerpiece;
  * the directive maps each technique onto the primitive that implements it
    (branch-tree, value-plane, cortex.deliberate, Memory-OS recall);
  * those primitive crates actually exist;
  * the CoT posture is in the reasoning scaffold so external agents adopt it;
  * the engine round: the sovereign-coat crate is one parameterized MCTS that IS
    the whole ladder (a preset per rung), the gateway exposes /v1/coat over the
    live cortex memory, and the /brain/ observatory surfaces it.

Stdlib + pytest only.
"""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DIRECTIVE = REPO / "docs" / "standing-directives" / "2026-07-12-deliberate-reasoning.md"
SCAFFOLD = REPO / "config" / "prompts" / "qcfa-system-prompt.md"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def test_directive_present_registered_and_covers_the_progression():
    assert DIRECTIVE.is_file(), "the deliberate-reasoning directive is missing"
    doc = _read(DIRECTIVE)
    low = doc.lower()
    # every rung of the ladder
    for token in ("chain of thought", "cot", "tree of thoughts", "tot",
                  "monte carlo tree search", "mcts", "c-mcts",
                  "chain-of-associated-thoughts", "coat"):
        assert token in low, f"directive missing technique: {token!r}"
    # the four MCTS phases named
    for phase in ("selection", "expansion", "simulation", "backprop"):
        assert phase in low, f"directive missing MCTS phase: {phase!r}"
    # CoAT is the centerpiece
    assert "centerpiece" in low, "directive must name CoAT the sovereign centerpiece"
    # registered in the index
    idx = _read(REPO / "docs" / "standing-directives" / "INDEX.md")
    assert "deliberate-reasoning.md" in idx, "directive not registered in INDEX.md"


def test_directive_maps_each_technique_onto_a_real_primitive():
    doc = _read(DIRECTIVE)
    # the primitives the progression maps onto must be cited by crate name
    for crate in ("sovereign-branch-tree", "sovereign-value-plane",
                  "sovereign-cortex"):
        assert crate in doc, f"directive must map onto {crate!r}"
    # CoAT's associative memory = the Memory-OS recall
    low = doc.lower()
    assert "recall" in low and "memory-os" in low, \
        "directive must map CoAT's associative memory onto the Memory-OS recall"
    assert "deliberate" in low, "directive must reference Cortex::deliberate"


def test_the_mapped_primitive_crates_exist():
    # the thesis only holds if the crates are real
    for crate in ("sovereign-branch-tree", "sovereign-value-plane", "sovereign-cortex"):
        assert (REPO / "crates" / crate / "src" / "lib.rs").is_file(), \
            f"mapped primitive crate missing: {crate}"
    # branch-tree really is the fork/prune tree the directive claims
    bt = _read(REPO / "crates" / "sovereign-branch-tree" / "src" / "lib.rs")
    for api in ("fn fork", "fn prune", "fn commit", "fn lineage"):
        assert api in bt, f"branch-tree missing the ToT primitive: {api}"
    # cortex.deliberate really forks branches against recalled context
    cx = _read(REPO / "crates" / "sovereign-cortex" / "src" / "lib.rs")
    assert "fn deliberate" in cx and "recalled" in cx, \
        "cortex.deliberate must exist and use recalled memory (CoAT's mechanism)"


def test_cot_posture_is_in_the_reasoning_scaffold():
    sc = _read(SCAFFOLD)
    assert "DELIBERATE REASONING" in sc, "scaffold must carry the deliberate-reasoning posture"
    low = sc.lower()
    for token in ("chain of thought", "step by step", "backtrack",
                  "tree of thoughts", "recall"):
        assert token in low, f"scaffold reasoning posture missing: {token!r}"


# --- the engine round: sovereign-coat + the /v1/coat + /brain/coat surfaces ---

COAT = REPO / "crates" / "sovereign-coat" / "src" / "lib.rs"
GATEWAY = REPO / "crates" / "sovereign-gatewayd" / "src"


def test_coat_engine_crate_is_the_whole_ladder():
    assert COAT.is_file(), "the sovereign-coat engine crate is missing"
    src = _read(COAT)
    # one parameterized MCTS that IS the ladder: a preset per rung.
    for preset in ("fn cot(", "fn tot(", "fn mcts(", "fn coat("):
        assert preset in src, f"coat config missing the ladder preset: {preset!r}"
    # the model-gated inputs are traits, so the harness is testable without a model.
    for trait in ("trait ThoughtSource", "trait AssociativeMemory"):
        assert trait in src, f"coat missing the pluggable trait: {trait!r}"
    # C-MCTS: a bounded action space of exactly five categories.
    assert "enum ThoughtCategory" in src and "ALL: [ThoughtCategory; 5]" in src, \
        "coat must constrain the action space to five categories (C-MCTS)"
    # the four MCTS phases must all be present in the search.
    low = src.lower()
    for phase in ("selection", "expansion", "simulation", "backprop"):
        assert phase in low, f"coat engine missing MCTS phase: {phase!r}"
    # CoAT's mechanism: recall modulates value; and it drives the real branch tree.
    assert "recall_weight" in src, "coat must let recall modulate value (CoAT)"
    assert "sovereign_branch_tree" in src, "coat must search the real M007 branch tree"


def test_gateway_exposes_v1_coat_over_the_live_memory():
    lib = _read(GATEWAY / "lib.rs")
    http = _read(GATEWAY / "http.rs")
    # the request/response variants + the handler wired to the real cortex memory.
    assert "GatewayRequest::Coat" in lib or "Coat {" in lib, "gateway missing the Coat request"
    assert "CoatTrace" in lib, "gateway missing the CoatTrace response"
    assert "CortexRecall" in lib, "gateway must adapt the live Cortex as CoAT's associative memory"
    assert "/v1/coat" in http, "gateway must route POST /v1/coat"
    # the cortex must expose the associative recall the engine pulls.
    cortex = _read(REPO / "crates" / "sovereign-cortex" / "src" / "lib.rs")
    assert "pub fn recall(" in cortex, "cortex must expose recall() for the CoAT engine"


def test_brain_observatory_surfaces_coat():
    api = _read(REPO / "scripts" / "operator" / "brain-api.py")
    assert "/brain/coat" in api and "def coat_deliberate" in api, \
        "brain-api must proxy /brain/coat to the gateway"
    panel = _read(REPO / "webapp" / "brain" / "index.html")
    for token in ("coat-btn", "coatDeliberate", "renderCoat", "/brain/coat"):
        assert token in panel, f"brain panel missing CoAT observatory piece: {token!r}"
