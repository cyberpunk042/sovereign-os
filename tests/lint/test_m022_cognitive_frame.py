"""M022 cognitive-frame contract lint.

Locks `config/agent/m022-cognitive-frame.yaml` to the M022 spec: the substrates
(E0199), the CognitiveFrame struct + variants (E0201), the 6-step frame loop
(E0202, order), the expert registry (E0204), the router masks + queues (E0205),
and the 9 system primitives (E0207). No minimization of the spec.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "agent" / "m022-cognitive-frame.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M022-cognitive-frame-system-level-moe.md"


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M022"


def test_cognitive_frame_eight_fields_verbatim():
    f = _c()["cognitive_frame"]["fields"]
    assert f == ["id", "parent", "workflow_node", "control", "capability",
                 "evidence", "memory_ref", "trace_ref"], f"CognitiveFrame drift: {f}"


def test_frame_loop_six_steps_in_order():
    steps = [s["step"] for s in _c()["frame_loop"]["steps"]]
    assert steps == ["READ", "ROUTE", "EVALUATE", "OBSERVE", "COMMIT", "LOOP"], (
        f"frame-loop step drift (order matters): {steps}")


def test_frame_variants_nine():
    v = _c()["frame_variants"]["variants"]
    assert len(v) == 9 and "tool-call" in v and "REPL-execution" in v


def test_router_seven_masks_six_queues():
    masks = _c()["router_masks"]["masks"]
    assert masks == ["alive_mask", "tool_mask", "oracle_mask", "scout_mask",
                     "repl_mask", "memory_mask", "human_mask"], f"mask drift: {masks}"
    assert len(_c()["router_queues"]["queues"]) == 6


def test_expert_registry_eleven():
    e = _c()["expert_registry"]["experts"]
    assert len(e) == 11 and "human-approval" in e and "simdjson-validator" in e


def test_nine_system_primitives_verbatim():
    p = _c()["system_primitives"]["primitives"]
    assert p == ["Frame", "Event", "Expert", "Router", "Workflow", "Policy",
                 "Replay", "Memory", "Eval"], f"system-primitive drift: {p}"


def test_repl_reality_four_decisions():
    d = _c()["repl_reality_routing"]["decisions"]
    assert d == ["can-execute", "can-parse", "can-test", "can-measure"]


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M00354", "M00357", "M00358", "M00359", "M00365", "M00366",
                "M00369", "M00370"):
        assert mod in body, f"{mod} not in the M022 milestone (must trace to spec)"
