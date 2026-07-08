"""M005 agent-runtime four-planes contract lint.

Locks `config/agent/m005-agent-runtime-planes.yaml` to the M005 spec: the branch
struct (E0041), the branch lifecycle states (E0042), the AVX-512 scheduler tick
(E0043), the constraint-automata FSMs (E0044), the auditable replay log (E0045),
and the three big wins (E0046). No minimization.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "agent" / "m005-agent-runtime-planes.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M005-agent-runtime-four-planes.md"


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M005"


def test_branch_struct_eight_fields():
    assert _c()["branch_struct"]["fields"] == ["id", "parent_id", "control", "score",
                                               "budget", "memory_ref", "constraint_mask", "rng"]


def test_lifecycle_nine_states():
    s = _c()["lifecycle_states"]["states"]
    assert s == ["drafted", "verified", "merged", "killed", "expanded", "routed",
                 "summarized", "tool-executed", "committed"]


def test_scheduler_tick_seven_ops():
    assert _c()["scheduler_tick"]["ops"] == ["decrement", "drop", "boost", "route",
                                             "merge", "admit", "evict"]


def test_control_word_nine_fields():
    cw = {x["name"]: x["bits"] for x in _c()["control_word_fields"]["fields"]}
    assert len(cw) == 9
    assert cw["model route"] == "0..3" and cw["lifecycle flags"] == "56..63"


def test_constraint_fsms_five():
    f = _c()["constraint_fsms"]
    assert f["fsms"] == ["JSON", "grammar", "tool", "shell-command", "patch"]
    assert "CPU" in f["runs_on"]


def test_replay_log_eight_stages():
    st = _c()["replay_log"]["stages"]
    assert st == ["input", "chunks", "drafts", "oracle", "tool calls", "patches",
                  "tests", "final"]


def test_three_big_wins():
    assert _c()["three_big_wins"] == ["oracle calls scarce", "4090 specialists",
                                      "CPU constraint automata"]


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M00062", "M00063", "M00064", "M00065", "M00073", "M00074", "M00078"):
        assert mod in body, f"{mod} not in the M005 milestone (must trace to spec)"
