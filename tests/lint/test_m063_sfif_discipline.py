"""M063 SFIF-discipline contract lint.

Locks `config/agent/m063-sfif-discipline.yaml` to the M063 spec: the 5 SFIF
phases mapped to PR ranges (E0608-E0612), the IaC Quality Bar (E0613/E0614), and
the SFIF transition gates + cross-repo applicability + audit trail (E0615-E0617).
No minimization.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "agent" / "m063-sfif-discipline.yaml"
MILESTONE = (REPO_ROOT / "backlog" / "milestones" /
             "M063-sfif-discipline-scaffold-foundation-infrastructure-features.md")


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M063"


def test_doctrinal_anchor_sfif_pr_mapping():
    a = _c()["doctrinal_anchor"]
    assert "Scaffold -> Foundation -> Infrastructure -> Features" in a
    assert "PRs 1-3 = Scaffold" in a and "PRs 4-8 = Foundation" in a


def test_five_sfif_phases_verbatim():
    p = _c()["sfif_phases"]
    assert [x["phase"] for x in p] == [1, 2, 3, 4, 5]
    names = [x["name"] for x in p]
    assert names == ["Scaffold", "Foundation", "Infrastructure begins",
                     "Infrastructure continues", "Features"]
    assert p[0]["prs"] == "1-3" and p[1]["prs"] == "4-8" and p[2]["prs"] == "9-10"


def test_iac_quality_bar_seven_checklist_two_pipeline():
    q = _c()["iac_quality_bar"]
    assert q["per_pr_checklist"] == ["scripts", "libs", "configuration", "easily tweakable",
                                     "customisable", "env-var-driven", "restart-from-state"]
    assert q["pipeline_properties"] == ["resumable", "observable"]
    assert "not one-shot" in q["doctrine"]


def test_transition_gates_operator_acknowledged():
    assert _c()["transition_gates"]["rule"] == "phase-to-phase transitions are operator-acknowledged"


def test_cross_repo_three_repos():
    cr = _c()["cross_repo_applicability"]
    assert cr["repos"] == ["selfdef", "sovereign-os", "info-hub"]


def test_audit_trail_per_pr_label():
    at = _c()["audit_trail"]
    assert "SFIF phase" in at["rule"] and "IaC quality bar checklist passed" in at["rule"]


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M01054", "M01058", "M01060", "M01066", "M01068", "M01069", "M01070"):
        assert mod in body, f"{mod} not in the M063 milestone (must trace to spec)"
