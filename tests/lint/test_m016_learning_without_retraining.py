"""M016 learning-without-retraining contract lint.

Locks `config/agent/m016-learning-without-retraining.yaml` to the M016 spec: the
learning surface (E0138), the Experience record + reflection fields (E0139), the
failure-code taxonomy (E0140, verbatim hex), the 6-stage Reflexion pipeline
(E0141, order), the skill contract (E0142), the 6-stage skill-promotion pipeline
(E0143), the policy-update record (E0144), and the Learning Plane / 8th plane
(E0145). No minimization of the spec.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "agent" / "m016-learning-without-retraining.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M016-learning-without-retraining.md"


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M016"


def test_experience_record_eight_fields_verbatim():
    e = _c()["experience_record"]
    assert e["fields"] == ["task_type", "branch_policy", "model_route", "tool_mask",
                           "outcome", "failure_code", "latency_bucket", "artifact_ref"], (
        f"Experience record field drift: {e['fields']}")


def test_failure_code_taxonomy_ten_codes_verbatim_hex():
    codes = _c()["failure_codes"]["codes"]
    got = {c["code"]: c["name"] for c in codes}
    expected = {
        0x01: "invalid_schema", 0x02: "bad_tool_args", 0x03: "test_failed",
        0x04: "missing_context", 0x05: "hallucinated_api", 0x06: "permission_denied",
        0x07: "timeout", 0x08: "duplicate_branch", 0x09: "low_oracle_agreement",
        0x0A: "user_rejected",
    }
    assert got == expected, f"failure-code taxonomy drift: {got}"


def test_reflexion_pipeline_six_stages_in_order():
    stages = [s["stage"] for s in _c()["reflexion_pipeline"]["stages"]]
    assert stages == ["collect-objective-outcome", "classify-failure-code",
                      "generate-short-reflection", "validate-reflection-against-trace",
                      "store-typed-lesson-plus-text",
                      "retrieve-only-when-matching-conditions"], (
        f"Reflexion pipeline stage drift (order matters): {stages}")


def test_skill_contract_seven_fields():
    s = _c()["skill_contract"]
    assert s["fields"] == ["name", "inputs", "preconditions", "commands", "risk",
                           "side_effects", "success_metric"], f"skill-contract drift: {s['fields']}"


def test_skill_promotion_pipeline_six_stages():
    stages = _c()["skill_promotion_pipeline"]["stages"]
    assert len(stages) == 6 and stages[0] == "candidate" and stages[3] == "oracle-review"


def test_policy_update_record_seven_fields():
    p = _c()["policy_update_record"]
    assert p["fields"] == ["condition_mask", "old_policy", "new_policy",
                           "evidence_count", "success_delta", "approved_by",
                           "rollback_ref"], f"policy-update drift: {p['fields']}"


def test_learning_plane_is_eighth_mutates_eight():
    lp = _c()["learning_plane"]
    assert lp["plane_number"] == 8
    assert len(lp["mutates"]) == 8 and "human-gate-thresholds" in lp["mutates"]


def test_reflection_fields_six_questions():
    q = _c()["reflection_fields"]["questions"]
    assert len(q) == 6 and "What failed" in q


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M00250", "M00251", "M00253", "M00255", "M00262", "M00263",
                "M00264", "M00267"):
        assert mod in body, f"{mod} not in the M016 milestone (must trace to spec)"
