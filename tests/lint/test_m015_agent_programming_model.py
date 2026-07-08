"""M015 agent-programming-model contract lint.

Locks `config/agent/m015-agent-programming-model.yaml` to the M015 spec: the
canonical 12-stage workflow (E0128, verbatim order), the per-node contract +
AgentState struct + typed envelopes (E0129), the 5 node classes (E0130), the
human-gate display/actions (E0131), the optimization metrics + tuning surface
(E0132), and the 7-plane system (E0135). No minimization of the spec.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "agent" / "m015-agent-programming-model.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M015-agent-programming-model.md"


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M015"


def test_canonical_workflow_twelve_stages_in_order():
    stages = _c()["canonical_workflow"]["stages"]
    assert stages == ["Intake", "Classify", "Retrieve", "DraftPlan", "PolicyCheck",
                      "OracleReview", "ToolIntent", "HumanGate?", "ExecuteSandbox",
                      "ValidateResult", "Commit", "SummarizeMemory"], (
        f"canonical workflow drift (order matters): {stages}")


def test_agent_state_ten_fields_verbatim():
    a = _c()["agent_state"]
    assert a["fields"] == ["task_id", "branch_id", "control", "risk", "budget",
                           "memory_refs", "kv_refs", "tool_intents", "artifacts",
                           "trace_id"], f"AgentState field drift: {a['fields']}"


def test_six_output_envelopes():
    t = _c()["output_envelopes"]["types"]
    assert t == ["PlanProposal", "ToolIntent", "PatchProposal", "MemoryWrite",
                 "VerificationResult", "FinalAnswer"], f"envelope drift: {t}"


def test_five_node_classes():
    nc = _c()["node_classes"]
    assert [n["class"] for n in nc] == [1, 2, 3, 4, 5]
    names = [n["name"] for n in nc]
    assert names == ["Deterministic Node", "Scout Node", "Oracle Node",
                     "Tool Node", "Human Gate Node"], f"node-class drift: {names}"


def test_human_gate_display_and_actions():
    hg = _c()["human_gate"]
    assert "approve" in hg["actions"] and "deny" in hg["actions"] and "edit" in hg["actions"]
    assert len(hg["display"]) == 9, "human-gate display must carry all 9 context items"


def test_optimization_ten_metrics_eight_knobs():
    o = _c()["optimization"]
    assert len(o["metrics"]) == 10, "M00245 optimization metric set = 10 metrics"
    assert len(o["tuning_surface"]) == 8, "M00246 tuning surface = 8 knobs"


def test_seven_plane_system_verbatim():
    planes = _c()["seven_plane_system"]["planes"]
    assert planes == ["Inference", "Control", "Memory", "Storage", "Tool",
                      "Observability", "Programming"], f"7-plane drift: {planes}"


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M00234", "M00235", "M00236", "M00237", "M00242", "M00243",
                "M00245", "M00249"):
        assert mod in body, f"{mod} not in the M015 milestone (must trace to spec)"
