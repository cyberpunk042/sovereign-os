"""M025 cognitive-compiler contract lint.

Locks `config/agent/m025-cognitive-compiler.yaml` to the M025 spec: the compiler
I/O contracts + DAG node schema (E0231), the 5-profile catalog (E0232), the
8-axis scheduler + ready queues (E0234), the BFCL-V4 8-failure taxonomy +
tool-use profile (E0235), the recompile triggers (E0236), and the 10-stage
compiler pipeline (E0237, order). No minimization of the spec.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "agent" / "m025-cognitive-compiler.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M025-cognitive-compiler-intent-to-dag.md"


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M025"


def test_compiler_seven_inputs_five_outputs_verbatim():
    assert _c()["compiler_inputs"]["inputs"] == ["user_goal", "policies",
        "available_tools", "model_registry", "memory_state", "hardware_telemetry",
        "risk_profile"]
    assert _c()["compiler_outputs"]["outputs"] == ["typed_workflow_dag",
        "capability_plan", "model_routing_plan", "cache_plan", "eval_verification_plan"]


def test_dag_node_seven_fields_verbatim():
    f = _c()["dag_node"]["fields"]
    assert f == ["id", "type", "depends_on", "parallel", "output", "model_role",
                 "sandbox"], f"DAG-node drift: {f}"


def test_five_profile_catalog_verbatim():
    p = _c()["profile_catalog"]["profiles"]
    assert p == ["Fast", "Careful", "Exploratory", "Private", "Autonomous"], (
        f"profile-catalog drift: {p}")


def test_scheduler_eight_axes_and_six_ready_queues():
    assert len(_c()["scheduler_ready_axes"]["axes"]) == 8
    q = _c()["ready_queues"]["queues"]
    assert len(q) == 6 and "ready_human_gate" in q


def test_bfcl_eight_failure_taxonomy_verbatim():
    f = _c()["failure_taxonomy"]["failures"]
    assert f == ["wrong-function", "wrong-argument", "wrong-order", "lost-context",
                 "ignoring-prior-tool-output", "format-drift", "unnecessary-tool-call",
                 "missing-tool-call"], f"failure-taxonomy drift: {f}"


def test_compiler_pipeline_ten_stages_in_order():
    stages = _c()["compiler_pipeline"]["stages"]
    assert stages == ["Intent-Parse", "Context-Build", "Plan-Synthesis",
                      "Plan-Validation", "Plan-Optimization", "Execution",
                      "Observation", "Recompile", "Commit", "Learn"], (
        f"compiler-pipeline drift: {stages}")


def test_recompile_triggers_five():
    t = _c()["recompile_triggers"]["triggers"]
    assert t == ["test-failed", "missing-file", "tool-denied", "oracle-disagreement",
                 "memory-conflict"], f"recompile-trigger drift: {t}"


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M00406", "M00410", "M00412", "M00413", "M00416", "M00418",
                "M00420", "M00421"):
        assert mod in body, f"{mod} not in the M025 milestone (must trace to spec)"
