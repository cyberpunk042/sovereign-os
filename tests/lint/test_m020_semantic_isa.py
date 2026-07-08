"""M020 semantic-ISA / orchestration contract lint.

Locks `config/agent/m020-semantic-isa.yaml` to the M020 spec: the 10 own
primitives (E0181), the framework adapters + adapter surface (E0179/E0181), the
8 orchestration operators (E0182), and the 15-instruction Semantic ISA +
per-instruction contract (E0186). No minimization of the spec.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "agent" / "m020-semantic-isa.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M020-orchestration-without-captivity-semantic-isa.md"


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M020"


def test_ten_own_primitives_verbatim():
    p = _c()["own_primitives"]["primitives"]
    assert p == ["Agent", "Tool", "Branch", "Message", "MemoryRef", "Capability",
                 "Policy", "Checkpoint", "Commit", "Trace"], f"primitive drift: {p}"
    assert len(p) == 10


def test_eight_orchestration_operators():
    ops = _c()["orchestration_operators"]
    names = [o["op"] for o in ops]
    assert names == ["sequential", "concurrent", "handoff", "debate", "cascade",
                     "tree-search", "swarm", "human-gate"], f"operator drift: {names}"
    assert all(o.get("form") for o in ops)


def test_semantic_isa_fifteen_instructions_verbatim():
    isa = _c()["semantic_isa"]["instructions"]
    assert isa == ["OBSERVE", "RETRIEVE", "DRAFT", "VERIFY", "CRITIQUE", "PLAN",
                   "CALL_TOOL", "WRITE_MEMORY", "REQUEST_APPROVAL", "COMMIT",
                   "ROLLBACK", "HANDOFF", "SPAWN_BRANCH", "MERGE_BRANCH",
                   "KILL_BRANCH"], f"Semantic ISA drift: {isa}"
    assert len(isa) == 15


def test_instruction_contract_six_fields():
    f = _c()["instruction_contract"]["fields"]
    assert f == ["required_capabilities", "input_schema", "output_schema",
                 "side_effect_level", "checkpoint_behavior", "risk_class"], (
        f"instruction-contract drift: {f}")


def test_framework_adapters_four():
    fa = [a["framework"] for a in _c()["framework_adapters"]]
    assert fa == ["Semantic Kernel", "CrewAI Flows", "AutoGen", "OpenAI Swarm"]


def test_arbiter_k_wraps_probabilistic_in_deterministic():
    ak = _c()["arbiter_k"]["principle"]
    assert "probabilistic" in ak and "deterministic" in ak


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M00320", "M00324", "M00325", "M00326", "M00327", "M00335", "M00336"):
        assert mod in body, f"{mod} not in the M020 milestone (must trace to spec)"
