"""M024 adaptive-programming contract lint.

Locks `config/agent/m024-adaptive-programming.yaml` to the M024 spec: the 6
budget tiers (E0224), the 9-stage compiler pipeline (E0225, order), the 5
registries with verbatim fields (E0226), and the adaptive router + plan-selector
counts (E0227). No minimization; count-only entries record counts, not fabricated
names.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "agent" / "m024-adaptive-programming.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M024-adaptive-programming-profiles-as-reward-weights.md"


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M024"


def test_six_budget_tiers_verbatim():
    t = [x["tier"] for x in _c()["budget_tiers"]]
    assert t == ["reflex", "normal", "deliberate", "research", "autonomous",
                 "scientific"], f"budget-tier drift: {t}"


def test_compiler_pipeline_nine_stages_in_order():
    stages = _c()["compiler_pipeline"]["stages"]
    assert stages == ["user-intent", "task-classifier", "constraints", "recipe",
                      "routing", "workflow-graph", "capability-plan", "execution",
                      "eval-and-memory-update"], f"compiler-pipeline drift: {stages}"


def test_five_registries_with_verbatim_fields():
    r = _c()["registries"]
    names = [x["name"] for x in r]
    assert names == ["Model Registry", "Tool Registry", "Recipe Registry",
                     "Memory Registry", "Eval Registry"], f"registry drift: {names}"
    model = next(x for x in r if x["name"] == "Model Registry")
    assert model["fields"] == ["name", "size", "modality", "context", "speed",
                               "quality", "memory_cost", "backend", "trust"], (
        f"Model Registry field drift: {model['fields']}")


def test_adaptive_router_and_plan_selector_counts():
    ar = _c()["adaptive_router"]
    assert ar["input_count"] == 11 and ar["output_count"] == 7
    ps = _c()["plan_selector"]
    assert ps["candidate_plan_field_count"] == 9 and ps["utility_score_term_count"] == 6


def test_profile_registry_and_weighting_counts():
    assert _c()["profile_registry"]["living_policy_entry_count"] == 10
    assert _c()["weighting_set"]["axis_count"] == 9


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M00390", "M00392", "M00398", "M00399", "M00403", "M00404", "M00405"):
        assert mod in body, f"{mod} not in the M024 milestone (must trace to spec)"
