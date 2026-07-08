"""M036 map-then-act contract lint.

Locks `config/agent/m036-map-then-act.yaml` to the M036 spec: the MAP 3 steps +
SDLC formal sequence (E0339), the Symphony spec-governance artifacts (E0340), the
eval signal catalog + Goldilocks-with-evals (E0341), and the Model Lab catalogs
(E0344). No minimization of the spec.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "agent" / "m036-map-then-act.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M036-map-then-act-paradigm.md"


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M036"


def test_map_three_steps():
    s = _c()["map_steps"]["steps"]
    assert s == ["global-exploration", "task-specific-map",
                 "knowledge-augmented-execution"], f"MAP-step drift: {s}"


def test_sdlc_sequence_eight_stages_in_order():
    s = _c()["sdlc_sequence"]["stages"]
    assert s == ["SPEC", "MAP", "PLAN", "ACT", "TEST", "EVAL", "COMMIT", "LEARN"], (
        f"SDLC-sequence drift: {s}")


def test_spec_governance_five_artifacts_verbatim():
    a = _c()["spec_governance"]["artifacts"]
    names = [x["artifact"] for x in a]
    assert names == ["SPEC.md", "WORKFLOW.md", "TESTS", "EVALS", "PROFILES"], (
        f"spec-governance drift: {names}")


def test_eval_signals_ten():
    s = _c()["eval_signals"]["signals"]
    assert len(s) == 10 and "pass_fail_reason" in s and "trace" in s


def test_goldilocks_just_enough_intelligence():
    p = _c()["goldilocks_with_evals"]["principle"]
    assert "just enough intelligence" in p


def test_model_lab_six_quantizations_and_eight_metrics():
    assert len(_c()["model_lab_benchmarks"]["quantizations"]) == 6
    assert len(_c()["model_lab_scores"]["metrics"]) == 8


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M00595", "M00598", "M00599", "M00603", "M00604", "M00607", "M00608"):
        assert mod in body, f"{mod} not in the M036 milestone (must trace to spec)"
