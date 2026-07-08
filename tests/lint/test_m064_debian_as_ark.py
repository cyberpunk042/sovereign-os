"""M064 "Debian as Ark" + Q-016 contract lint.

Locks `config/agent/m064-debian-as-ark.yaml` to the M064 spec: the "Debian as
Ark" doctrinal frame (E0618), the working hypothesis (E0619), honest alternative
evaluation + trade-off documentation (E0620/E0621), the Q-016 open question +
timeline + resolution (E0622-E0624), and the substrate evaluation criteria +
operator decision authority (E0625-E0627). No minimization.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "agent" / "m064-debian-as-ark.yaml"
MILESTONE = (REPO_ROOT / "backlog" / "milestones" /
             "M064-debian-as-ark-and-q-016-distro-base-reconsideration.md")


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M064"


def test_debian_as_ark_doctrine():
    d = _c()["debian_as_ark"]
    assert d["doctrine"] == "Debian 13 is the starting boat, not the destination"
    assert "sovereign-os" in d["destination"]


def test_working_hypothesis_stay_and_customize():
    wh = _c()["working_hypothesis"]
    assert wh["hypothesis"] == "stay on Debian + customize the boat"
    assert len(wh["customizations"]) == 3
    assert any("znver5" in c for c in wh["customizations"])
    assert any("ZFS-root" in c for c in wh["customizations"])


def test_alternative_survey_nine_candidates():
    a = _c()["alternative_survey"]
    assert len(a["candidates"]) == 9
    assert "Ubuntu 24 LTS" in a["candidates"]
    assert any("NixOS" in c for c in a["candidates"])
    assert any("Gentoo" in c for c in a["candidates"])
    assert any("buildroot" in c for c in a["candidates"])


def test_q016_open_question_timeline_resolution():
    q = _c()["q_016"]
    assert "substrate-base reconsideration" in q["question"]
    assert q["open_through"] == "PR 4 substrate survey"
    assert "Stage Gate 2" in q["resolved_at"] and "Q-001" in q["resolved_at"]


def test_operator_decision_authority():
    assert _c()["operator_decision_authority"] == "operator picks, never SDD"


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M01071", "M01073", "M01074", "M01076", "M01078", "M01080", "M01081"):
        assert mod in body, f"{mod} not in the M064 milestone (must trace to spec)"
