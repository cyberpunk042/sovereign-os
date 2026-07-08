"""M007 execution-model (branch primitive + scheduler) contract lint.

Locks `config/agent/m007-execution-model.yaml` to the M007 spec: the branch
primitive (E0051), the 8-step branch loop (E0052), the SoA branch state arrays +
per-tick ops (E0053), the composable control word + branch queries (E0054), the
epistemic roles (E0055), memory typing (E0056), the MemoryRef struct (E0057), and
the transactional tool call (E0058). No minimization.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "agent" / "m007-execution-model.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M007-execution-model-branch-primitive-scheduler.md"


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M007"


def test_branch_loop_eight_steps():
    assert _c()["branch_loop"]["steps"] == ["Spawn", "Retrieve", "Draft", "Filter",
                                            "Verify", "Act", "Commit", "Learn"]


def test_soa_eight_arrays_and_per_tick_masks():
    assert _c()["soa_arrays"]["arrays"] == ["id", "control", "budget", "score", "flags",
                                            "grammar", "memory", "route"]
    m = _c()["per_tick_ops"]["masks"]
    assert "dead_mask" in m and "oracle_mask" in m and "merge_mask" in m


def test_control_word_and_branch_queries():
    assert _c()["control_word_fields"] == ["route", "task", "risk", "permissions",
                                           "grammar", "priority", "spec_depth", "flags"]
    q = _c()["branch_queries"]["queries"]
    assert len(q) == 6 and "shell-allowed" in q and "network-allowed" in q
    assert "reasoning becomes state transitions" in _c()["psychological_shift"]


def test_epistemic_roles_five():
    r = [x["role"] for x in _c()["epistemic_roles"]]
    assert r == ["Oracle", "Verifier", "Scout", "Specialists", "Law"]


def test_memory_types_six():
    assert _c()["memory_types"] == ["episodic", "semantic", "procedural", "project",
                                    "policy", "trace"]


def test_memory_ref_eight_fields():
    assert _c()["memory_ref"]["fields"] == ["id", "type", "embedding_ref", "trust",
                                            "freshness", "access_count", "decay", "flags"]


def test_transactional_tool_call():
    assert "intent -> CPU permission check" in _c()["transactional_tool_call"]["flow"]


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M00096", "M00098", "M00099", "M00104", "M00106", "M00110", "M00111"):
        assert mod in body, f"{mod} not in the M007 milestone (must trace to spec)"
