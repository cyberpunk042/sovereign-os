"""M026 SLM-swarm + RLM + judges contract lint.

Locks `config/agent/m026-slm-swarm-rlm-judges.yaml` to the M026 spec: the 3 model
roles + judge classes (E0240/E0241), the 11-role SLM swarm (E0242), the RLM loop
+ RLM-vs-RAG (E0243), the RLM subcall control word (E0245), and the reward
taxonomy + reward vector (E0246). No minimization of the spec.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "agent" / "m026-slm-swarm-rlm-judges.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M026-slm-swarm-rlm-engine-rm-prm-judges.md"


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M026"


def test_three_model_roles_LLM_SLM_RLM():
    r = [x["role"] for x in _c()["model_roles"]]
    assert r == ["LLM", "SLM", "RLM"], f"model-role drift: {r}"


def test_judge_classes_RM_RRM_PRM():
    assert _c()["judge_classes"]["classes"] == ["RM", "RRM", "PRM"]


def test_slm_swarm_eleven_roles_verbatim():
    roles = _c()["slm_swarm"]["roles"]
    assert roles == ["intent-classifier", "tool-call-planner", "JSON-fixer",
                     "schema-selector", "risk-tagger", "memory-router",
                     "branch-summarizer", "patch-scout", "GUI-perception-helper",
                     "query-reformulator", "test-failure-classifier"], (
        f"SLM-swarm drift: {roles}")
    assert len(roles) == 11


def test_rlm_loop_six_steps_in_order():
    s = _c()["rlm_loop"]["steps"]
    assert s == ["read-task", "inspect-external-context-via-code",
                 "spawn-sub-call-on-relevant-slice", "aggregate-result", "repeat",
                 "return-answer"], f"RLM-loop drift: {s}"


def test_rlm_vs_rag_navigate_not_retrieve():
    d = _c()["rlm_vs_rag"]["distinction"]
    assert "NAVIGATE" in d and "RAG retrieves" in d


def test_rlm_control_word_eight_fields():
    f = _c()["rlm_subcall_control_word"]["fields"]
    assert f == ["parent_id", "depth", "context_slice_ref", "question_ref",
                 "budget", "uncertainty", "reward_score", "visited_hash"], (
        f"RLM control-word drift: {f}")


def test_four_reward_sources_and_eight_field_vector():
    src = [s["source"] for s in _c()["reward_sources"]["sources"]]
    assert src == ["rule", "process", "model", "system"], f"reward-source drift: {src}"
    v = _c()["reward_vector"]["fields"]
    assert v == ["correctness", "evidence", "risk", "cost", "latency", "novelty",
                 "reuse", "user_preference"], f"reward-vector drift: {v}"


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M00423", "M00426", "M00427", "M00428", "M00434", "M00436", "M00437"):
        assert mod in body, f"{mod} not in the M026 milestone (must trace to spec)"
