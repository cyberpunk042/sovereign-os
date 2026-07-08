"""M057 12-step task-lifecycle contract lint.

Locks `config/execution/m057-task-lifecycle.yaml` to the M057 spec: the 12-step
Task Lifecycle (E0548) with per-step detail (E0549-E0556), and the Critical Data
Flow Law + end-to-end example (E0557). No minimization.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "execution" / "m057-task-lifecycle.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M057-data-flow-and-lifecycle-12-step.md"


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M057"


def test_twelve_lifecycle_steps_verbatim():
    s = _c()["lifecycle_steps"]
    assert [x["step"] for x in s] == list(range(1, 13))
    names = [x["name"] for x in s]
    assert names == ["Intake", "Normalize", "Profile Resolve", "Map", "Plan / Compile",
                     "Route", "Execute", "Observe", "Evaluate", "Commit / Rollback",
                     "Learn", "Resume / Archive"], f"step drift: {names}"


def test_intake_ten_sources_six_fields():
    i = _c()["intake"]
    assert len(i["sources"]) == 10 and "file watcher" in i["sources"]
    assert i["gateway_fields"] == ["request_id", "trace_id", "client_id", "profile_hint",
                                   "privacy_context", "budget_hint"]


def test_normalize_five_formats_profile_eight_postures_seven_fields():
    n = _c()["normalize"]
    assert len(n["external_formats"]) == 5 and "MCP tool call" in n["external_formats"]
    pr = _c()["profile_resolve"]
    assert len(pr["postures"]) == 8 and "experimental" in pr["postures"]
    assert len(pr["resolved_fields"]) == 7 and "human gate threshold" in pr["resolved_fields"]


def test_map_four_domain_maps():
    d = [x["domain"] for x in _c()["map"]["domain_maps"]]
    assert d == ["code", "research", "GUI", "OS/admin"]
    assert _c()["map"]["doctrine"] == "MAP prevents blind action"


def test_plan_eight_node_types_route_six_examples_eight_factors():
    p = _c()["plan_compile"]
    assert len(p["node_types"]) == 8 and "policy gate" in p["node_types"]
    r = _c()["route"]
    assert len(r["examples"]) == 7  # 6 documented + high-stakes external claim
    assert len(r["factors"]) == 8 and "hardware pressure" in r["factors"]


def test_execute_nine_environments_observe_ten_categories():
    e = _c()["execute"]
    assert len(e["environments"]) == 9 and "symbolic planner" in e["environments"]
    o = _c()["observe"]
    assert len(o["categories"]) == 10 and "files changed" in o["categories"]
    assert o["note"] == "Observation is ground truth for the workflow"


def test_evaluate_eight_axes_five_outcomes():
    ev = _c()["evaluate"]
    assert len(ev["axes"]) == 8 and "trajectory quality" in ev["axes"]
    assert ev["outcomes"] == ["continue", "retry", "escalate", "rollback", "commit"]


def test_commit_five_evidence_four_rollback():
    cr = _c()["commit_rollback"]
    assert len(cr["commit_evidence_code"]) == 5 and "snapshot exists" in cr["commit_evidence_code"]
    assert cr["rollback_steps"] == ["rollback", "archive branch", "store failure", "replan"]


def test_learn_seven_before_four_later():
    lr = _c()["learn"]
    assert len(lr["before_weights"]) == 7 and "tag model failure" in lr["before_weights"]
    assert lr["later_with_weights"] == ["curate dataset", "train LoRA", "evaluate adapter",
                                        "promote adapter"]


def test_resume_nine_states_five_requires():
    ra = _c()["resume_archive"]
    assert len(ra["states"]) == 9 and "rolled_back" in ra["states"]
    assert len(ra["resume_requires"]) == 5 and "staleness check" in ra["resume_requires"]


def test_data_flow_law_and_eight_real_state():
    dfl = _c()["data_flow_law"]
    assert dfl["law"] == "Text is not the system state. Text is payload inside typed state"
    assert len(dfl["real_state"]) == 8 and "eval results" in dfl["real_state"]
    ex = _c()["end_to_end_example"]
    assert ex["user_input"] == "fix failing parser test"
    assert ex["closing"] == "That is the practical flow"


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M00952", "M00953", "M00956", "M00961", "M00963", "M00965", "M00967"):
        assert mod in body, f"{mod} not in the M057 milestone (must trace to spec)"
