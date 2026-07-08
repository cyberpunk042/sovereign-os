"""M027 value-plane contract lint.

Locks `config/agent/m027-value-plane.yaml` to the M027 spec: the Value-Plane
7-question contract (E0250), the 12-axis reward vector (E0251), the PRM
branch-critic I/O + authority law (E0252), the 9 search modes (E0253), and the
adaptive compute ladder + budget formula (E0254). No minimization of the spec.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "agent" / "m027-value-plane.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M027-value-plane-reward-vector-prm-as-branch-critic.md"


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M027"


def test_value_plane_seven_questions():
    q = _c()["value_plane_questions"]["questions"]
    assert q == ["thought-expand", "branch-correct", "tool-plan-safe",
                 "memory-trustworthy", "answer-return", "profile-choose",
                 "compute-justified"], f"value-plane question drift: {q}"


def test_reward_vector_twelve_axis_verbatim():
    a = _c()["reward_vector_12axis"]["axes"]
    assert a == ["correctness", "evidence", "schema_validity", "tool_success",
                 "test_success", "risk", "latency", "cost", "novelty",
                 "user_preference", "cache_reuse", "confidence_calibration"], (
        f"12-axis reward-vector drift: {a}")
    assert len(a) == 12


def test_prm_branch_critic_five_in_five_out():
    c = _c()["prm_branch_critic"]
    assert c["inputs"] == ["branch_state", "partial_reasoning", "tool_observations",
                           "memory_evidence", "candidate_next_step"]
    assert c["outputs"] == ["step_score", "risk_score", "uncertainty",
                            "failure_mode", "suggested_next_action"]


def test_authority_law_prm_proposes_cpu_applies_oracle_verifies():
    law = _c()["authority_law"]["law"]
    assert "PRM proposes" in law and "CPU applies" in law and "Oracle verifies" in law


def test_nine_search_modes_verbatim():
    m = _c()["search_modes"]["modes"]
    assert m == ["Greedy", "Best-of-N", "Self-consistency", "Beam", "Diverse-beam",
                 "MCTS", "RLM-recursion", "Debate", "Program-of-thought"], (
        f"search-mode drift: {m}")


def test_adaptive_compute_ladder_five_rungs():
    r = _c()["adaptive_compute_ladder"]["rungs"]
    diffs = [x["difficulty"] for x in r]
    assert diffs == ["easy", "medium", "hard", "long-context", "high-risk"]


def test_intelligence_budget_formula_verbatim():
    f = _c()["intelligence_budget_formula"]["formula"]
    assert f == "expected_gain > compute_cost + latency_penalty + risk_penalty"


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M00441", "M00447", "M00448", "M00450", "M00452", "M00453",
                "M00454", "M00456"):
        assert mod in body, f"{mod} not in the M027 milestone (must trace to spec)"
