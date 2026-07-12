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
  * the CoT posture is in the reasoning scaffold so external agents adopt it.

The CoAT engine (sovereign-coat crate + /v1/coat + /brain/ observatory) is guarded
by its own assertions once that round lands.

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
