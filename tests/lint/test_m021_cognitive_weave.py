"""M021 cognitive-weave contract lint.

Locks `config/agent/m021-cognitive-weave.yaml` to the M021 spec: the primitive
loop + 7 common cores (E0188/E0189), typed thoughts + workflow shell (E0191), the
MoE expert registry (E0192), the M021 Semantic ISA + per-instruction contract
(E0193), the 6-layer architecture (E0194), and the hot-state SoA + branch word
(E0195). No minimization of the spec.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "agent" / "m021-cognitive-weave.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M021-repl-cot-moe-workflow-logic-intelligence-weave.md"


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M021"


def test_seven_common_cores_verbatim():
    cores = [c["core"] for c in _c()["common_cores"]]
    assert cores == ["REPL", "CoT", "ReAct", "Workflow", "MoE", "Logic",
                     "Intelligence"], f"common-core drift: {cores}"
    assert all(c.get("shape") for c in _c()["common_cores"])


def test_primitive_loop_six_steps():
    assert _c()["primitive_loop"]["steps"] == ["state", "proposal", "evaluation",
                                               "action", "observation", "updated-state"]


def test_semantic_isa_m021_thirteen_verbatim():
    isa = _c()["semantic_isa_m021"]["instructions"]
    assert isa == ["OBSERVE", "RETRIEVE", "DRAFT", "REASON", "EXECUTE_REPL",
                   "VERIFY", "CRITIQUE", "ROUTE", "MERGE", "COMMIT", "ROLLBACK",
                   "WRITE_MEMORY", "ASK_HUMAN"], f"M021 ISA drift: {isa}"
    assert len(isa) == 13


def test_moe_expert_registry_seven():
    e = _c()["moe_expert_registry"]["experts"]
    assert len(e) == 7 and "human-gate" in e and "ZFS-replay" in e


def test_six_layer_architecture_verbatim():
    layers = _c()["six_layer_architecture"]["layers"]
    assert layers == ["REPL", "Thought", "Workflow", "MoE", "Logic", "Intelligence"], (
        f"6-layer drift: {layers}")


def test_branch_word_nine_fields_flagged_proposed():
    b = _c()["branch_word_encoding"]
    assert b["width_bits"] == 64 and b.get("bit_layout_proposed") is True
    assert b["fields"] == ["route", "workflow_node", "expert_choice",
                           "tool_permission", "risk", "budget", "grammar",
                           "memory_policy", "flags"], f"branch-word drift: {b['fields']}"


def test_hot_state_soa_eight_arrays():
    a = _c()["hot_state_soa"]["arrays"]
    assert a == ["branch_id", "control_word", "budget", "risk", "route",
                 "grammar_state", "memory_ref", "score"], f"SoA drift: {a}"


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M00337", "M00338", "M00345", "M00348", "M00349", "M00351",
                "M00352", "M00353"):
        assert mod in body, f"{mod} not in the M021 milestone (must trace to spec)"
