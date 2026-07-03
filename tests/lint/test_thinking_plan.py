"""SDD-043 Phase 4 — thinking-router planner lockstep.

Locks scripts/inference/thinking-plan.py: the plan is deterministic, it
reuses the shipped router's tier classification (never diverges from
where a request actually routes), simple requests are NOT escalated,
oracle-bound / reasoning requests ARE (CoT + validator), and the
policy fields (validate.mode, self_consistency, moe) drive the steps —
so Q-3/Q-4 stay configurable, not hardcoded.
"""
from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PLANNER = REPO_ROOT / "scripts" / "inference" / "thinking-plan.py"
ROUTER = REPO_ROOT / "scripts" / "inference" / "router.py"


def _mod(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _planner():
    return _mod(PLANNER, "thinking_plan")


def _body(text: str, **kw) -> dict:
    b = {"messages": [{"role": "user", "content": text}]}
    b.update(kw)
    return b


def test_planner_present_and_executable():
    assert PLANNER.is_file()
    assert PLANNER.stat().st_mode & 0o111


def test_simple_request_not_escalated():
    p = _planner()
    plan = p.plan(_body("what time is it"))
    assert plan["escalated"] is False
    assert plan["steps"] == []


def test_reasoning_escalates_with_cot_and_validator():
    p = _planner()
    plan = p.plan(_body("prove that sqrt(2) is irrational, step by step"))
    assert plan["escalated"] is True
    kinds = [s["step"] for s in plan["steps"]]
    assert "think" in kinds, kinds
    assert "validate" in kinds, kinds  # default validate.mode = pass


def test_route_tier_matches_shipped_router():
    """The plan's route_tier is the SHIPPED router's classification — the
    planner never invents its own routing."""
    p = _planner()
    router = _mod(ROUTER, "router")
    for text in ("hi", "prove sqrt(2) irrational", "write a python function"):
        b = _body(text)
        assert p.plan(b)["route_tier"] == router.classify(b)


def test_deterministic():
    p = _planner()
    b = _body("prove sqrt(2) irrational")
    assert p.plan(b) == p.plan(b)


def test_explicit_flag_forces_escalation():
    p = _planner()
    plan = p.plan(_body("hello", sovereign_os_think=True))
    assert plan["escalated"] is True
    assert any(s["step"] == "think" for s in plan["steps"])


def test_validate_mode_off_drops_validator():
    p = _planner()
    pol = copy.deepcopy(p.DEFAULT_POLICY)
    pol["validate"]["mode"] = "off"
    plan = p.plan(_body("prove sqrt(2) irrational"), pol)
    assert plan["escalated"] is True
    assert all(s["step"] != "validate" for s in plan["steps"])


def test_validate_mode_tier_is_carried():
    p = _planner()
    pol = copy.deepcopy(p.DEFAULT_POLICY)
    pol["validate"]["mode"] = "tier"
    plan = p.plan(_body("prove sqrt(2) irrational"), pol)
    v = [s for s in plan["steps"] if s["step"] == "validate"]
    assert v and v[0]["mode"] == "tier"


def test_self_consistency_and_moe_are_policy_driven():
    p = _planner()
    pol = copy.deepcopy(p.DEFAULT_POLICY)
    pol["self_consistency"]["samples"] = 5
    pol["moe"] = {"enabled": True, "top_k": 3}
    # a mixture-class request so moe applies
    plan = p.plan(_body("prove sqrt(2) irrational", sovereign_os_class="mixture"), pol)
    kinds = {s["step"] for s in plan["steps"]}
    assert "self_consistency" in kinds
    assert "moe" in kinds


def test_think_model_classes_are_valid_taxonomy():
    """The default policy's think/validate classes are real catalog
    model-classes (so a plan resolves against the catalog)."""
    import yaml
    p = _planner()
    schema = yaml.safe_load(
        (REPO_ROOT / "schemas" / "model-catalog.schema.yaml").read_text())
    class_enum = set(
        schema["$defs"]["model"]["properties"]["class"]["enum"])
    for c in p.DEFAULT_POLICY["think"]["model_class"] + p.DEFAULT_POLICY["validate"]["model_class"]:
        assert c in class_enum, f"policy class {c!r} not in catalog taxonomy"
