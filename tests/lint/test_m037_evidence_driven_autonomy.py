"""M037 evidence-driven-autonomy contract lint.

Locks `config/agent/m037-evidence-driven-autonomy.yaml` to the M037 spec: the 7
truth anchors (E0349), the methodology sequence (E0350), the 5 Goldilocks
profiles (E0351), and the project-specific tests catalog (E0352). No minimization.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "agent" / "m037-evidence-driven-autonomy.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M037-spec-tdd-agent-evals-evidence-driven-autonomy.md"


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M037"


def test_seven_truth_anchors_verbatim():
    a = [x["anchor"] for x in _c()["truth_anchors"]]
    assert a == ["SPEC.md", "TESTS", "WORKFLOW.md", "EVALS.yaml", "PROFILE.yaml",
                 "MAP.json", "TRACE.log"], f"truth-anchor drift: {a}"
    assert len(a) == 7


def test_methodology_seven_stages_in_order():
    s = _c()["methodology_sequence"]["stages"]
    assert s == ["Map", "Specify", "Test", "Act", "Evaluate", "Commit", "Learn"], (
        f"methodology-sequence drift: {s}")


def test_five_goldilocks_profiles_verbatim():
    p = [x["profile"] for x in _c()["goldilocks_profiles"]]
    assert p == ["Reflex", "Careful", "Experimental", "Production", "Autonomous"], (
        f"Goldilocks-profile drift: {p}")


def test_production_profile_requires_tdd_and_human_gate():
    prod = next(x for x in _c()["goldilocks_profiles"] if x["profile"] == "Production")
    assert "TDD required" in prod["shape"] and "human gate" in prod["shape"]


def test_tests_catalog_eight_types():
    t = _c()["tests_catalog"]["test_types"]
    assert t == ["unit", "integration", "property", "snapshot", "lint-type",
                 "security", "performance", "agent-trajectory"], f"test-catalog drift: {t}"


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M00612", "M00618", "M00619", "M00620", "M00624", "M00625"):
        assert mod in body, f"{mod} not in the M037 milestone (must trace to spec)"
