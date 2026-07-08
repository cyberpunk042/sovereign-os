"""M065 five-stage-gates (SG1-SG5) contract lint.

Locks `config/agent/m065-stage-gates.yaml` to the M065 spec: the 5 stage gates
SG1-SG5 (E0628-E0632), the ExitPlanMode-style checkpoint ritual (E0633), the
no-PR-past-unsigned-gate hard rule (E0634), the sign-off audit trail + transport
(E0635/E0636), and gate-blocked parallel work (E0637). No minimization.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "agent" / "m065-stage-gates.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M065-five-stage-gates-sg1-sg5-checkpoint-ritual.md"

# (gate, after_pr, scope) — the spec's exact gate placement table.
EXPECTED = [
    ("SG1", 3, "structural foundation review"),
    ("SG2", 4, "substrate decision"),
    ("SG3", 6, "schema lock-in"),
    ("SG4", 8, "whitelabel mechanism + legal posture confirmed"),
    ("SG5", 10, "foundation-complete gate"),
]


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def _g(gate: str) -> dict:
    return next(x for x in _c()["stage_gates"] if x["gate"] == gate)


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M065"


def test_doctrinal_anchor_exitplanmode():
    a = _c()["doctrinal_anchor"]
    assert "ExitPlanMode-style checkpoint" in a
    assert "No PR opens past a gate without operator sign-off" in a


def test_five_stage_gates_placement_verbatim():
    gates = [x["gate"] for x in _c()["stage_gates"]]
    assert gates == ["SG1", "SG2", "SG3", "SG4", "SG5"]
    for gate, after_pr, scope in EXPECTED:
        g = _g(gate)
        assert g["after_pr"] == after_pr, f"{gate}: after_pr drift {g['after_pr']}"
        assert g["scope"] == scope, f"{gate}: scope drift {g['scope']}"


def test_sg2_resolves_q016_and_q001():
    g = _g("SG2")
    assert "Q-016" in g["detail"] and "Q-001" in g["detail"]


def test_sg3_schema_lock_in_override_only():
    g = _g("SG3")
    assert "locked thereafter" in g["detail"] and "operator-signed override only" in g["detail"]


def test_sg5_authorizes_stage_2():
    g = _g("SG5")
    assert "authorizes Stage 2" in g["detail"]


def test_checkpoint_ritual_three_steps():
    r = _c()["checkpoint_ritual"]["steps"]
    assert r == ["execution pauses", "operator reviews", "explicitly authorizes"]


def test_hard_rule_and_sign_off_transport():
    assert _c()["hard_rule"]["rule"] == "no PR opens past a gate without operator sign-off"
    so = _c()["sign_off"]
    assert so["audit_recorded"] == "timestamp + actor + rationale"
    assert "MS003" in so["transport"]


def test_parallel_work_dependency_permitting():
    assert "dependency-permitting" in _c()["parallel_work"]["rule"]


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M01088", "M01089", "M01092", "M01093", "M01099", "M01100", "M01104"):
        assert mod in body, f"{mod} not in the M065 milestone (must trace to spec)"
