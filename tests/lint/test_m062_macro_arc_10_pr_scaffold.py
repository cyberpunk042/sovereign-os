"""M062 Macro-Arc 10-PR foundation-scaffold contract lint.

Locks `config/agent/m062-macro-arc-10-pr-scaffold.yaml` to the M062 spec: the
10-PR foundation scaffold (E0598-E0607), the 5 stage gates (M01047-M01051), and
the critical-decisions surface + trade-off analysis (M01052/M01053). No
minimization.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "agent" / "m062-macro-arc-10-pr-scaffold.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M062-macro-arc-10-pr-foundation-scaffold.md"


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M062"


def test_doctrinal_anchors():
    assert "not a working build" in _c()["doctrinal_anchor"]
    assert "mechanisms are specified before scripts are written" in _c()["sdd_tdd_ordering"]
    assert "ExitPlanMode-style checkpoint" in _c()["gate_doctrine"]
    assert "No PR opens past a gate without operator sign-off" in _c()["gate_doctrine"]


def test_ten_prs_present_and_ordered():
    prs = _c()["prs"]
    assert [x["pr"] for x in prs] == list(range(1, 11)), "PR numbering drift"
    assert prs[0]["name"].startswith("Repo genesis")
    assert "Profile schema SDD" == prs[4]["name"]
    assert prs[9]["name"].endswith("Stage Gate 5")


def test_pr_modules_verbatim():
    mods = [x["module"] for x in _c()["prs"]]
    assert mods == [f"M0{n}" for n in range(1037, 1047)], f"PR module drift: {mods}"


def test_five_stage_gates():
    g = _c()["stage_gates"]
    assert [x["gate"] for x in g] == [1, 2, 3, 4, 5]
    assert [x["dump_line"] for x in g] == [82, 117, 168, 218, 282]


def test_governance_surfaces():
    gs = _c()["governance_surfaces"]
    assert gs["critical_decisions"]["module"] == "M01052"
    assert gs["trade_off_analysis"]["module"] == "M01053"


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M01037", "M01041", "M01046", "M01047", "M01051", "M01052", "M01053"):
        assert mod in body, f"{mod} not in the M062 milestone (must trace to spec)"
