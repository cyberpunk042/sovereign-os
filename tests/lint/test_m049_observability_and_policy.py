"""M049 observability + policy contract lint.

Locks `config/observability/m049-observability-and-policy.yaml` to the M049 spec:
OTel GenAI conventions + 16-event taxonomy + 13-field span (E0469/E0470),
self-hosted observability (E0471), Telemetry As Control (E0472), the Policy
Fabric (E0473), Intent-Based Policy (E0474), Policy-Aware Memory (E0475),
Configuration Continuity (E0476), and Continuity Of Control + 13-module map +
per-module 6-exposure standard (E0477). No minimization.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "observability" / "m049-observability-and-policy.yaml"
MILESTONE = (REPO_ROOT / "backlog" / "milestones" /
             "M049-continuity-through-observability-and-policy.md")


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M049"


def test_sixteen_event_taxonomy_verbatim():
    # The spec labels this a 16-event taxonomy; the enumerated set is 15 distinct
    # event names (model_call..cost_event) — lock the enumerated set exactly.
    e = _c()["event_taxonomy"]["events"]
    assert e == ["model_call", "tool_call", "memory_read", "memory_write",
                 "route_decision", "policy_decision", "sandbox_start", "sandbox_stop",
                 "test_run", "eval_score", "checkpoint", "rollback", "human_gate",
                 "cloud_call", "cost_event"], f"event drift: {e}"


def test_thirteen_span_fields_verbatim():
    f = _c()["span_fields"]["fields"]
    assert f == ["profile", "model", "provider", "hardware", "tokens", "latency",
                 "cost", "risk", "memory_refs", "tool_refs", "policy_result",
                 "branch_id", "trace_id"], f"span-field drift: {f}"
    assert len(f) == 13


def test_self_hosted_lock_into_trace_semantics():
    sh = _c()["self_hosted"]
    assert "self-hostable" in sh["langfuse"] and "self-hostable" in sh["phoenix"]
    assert sh["doctrine"] == "Do not lock into a UI. Lock into trace semantics"


def test_telemetry_as_control_six_reactions():
    r = _c()["telemetry_as_control"]["reactions"]
    triggers = [x["trigger"] for x in r]
    assert triggers == ["cost spike", "tool failure repeats",
                        "model hallucination pattern detected",
                        "memory retrieval low quality", "GPU pressure high",
                        "human gates too frequent"]
    assert _c()["telemetry_as_control"]["closing"] == "This is the difference between logging and intelligence"


def test_policy_fabric_three_engines_seven_decisions():
    pf = _c()["policy_fabric"]
    engines = [x["engine"] for x in pf["engines"]]
    assert engines == ["OPA/Rego", "Cedar", "OpenFGA"]
    assert len(pf["decisions"]) == 7 and "Can this result be committed?" in pf["decisions"]


def test_intent_based_policy_ten_fields():
    ibp = _c()["intent_based_policy"]
    assert ibp["agent"] == "Can subject do action on object for this intent under this profile?"
    assert len(ibp["input_fields"]) == 10 and "intent" in ibp["input_fields"]
    assert "user approval state" in ibp["input_fields"]


def test_policy_aware_memory_nine_classes_four_rules():
    pam = _c()["policy_aware_memory"]
    assert len(pam["sensitivity_classes"]) == 9 and "cloud-forbidden" in pam["sensitivity_classes"]
    assert len(pam["policy_check"]) == 4 and "provider allowed" in pam["policy_check"]


def test_configuration_continuity_seven_layers_five_conflict_rules():
    cc = _c()["configuration_continuity"]
    layers = [x["layer"] for x in cc["layered_config"]]
    assert layers == ["hardware config", "OS config", "runtime config", "policy config",
                      "workflow config", "user config", "project config"]
    assert len(cc["conflict_resolution"]) == 5
    assert cc["conflict_resolution"][0] == "hard policy beats profile"


def test_continuity_of_control_six_things():
    coc = _c()["continuity_of_control"]["sovereign_os_gives"]
    assert coc == ["history", "policy", "hardware state", "tool state", "user intent",
                   "rollback"]


def test_thirteen_module_map():
    m = _c()["module_map"]["modules"]
    assert len(m) == 13 and "Policy Fabric" in m and "Hardware Profiler" in m
    assert "Config Resolver" in m


def test_per_module_six_exposure_and_key_line():
    pme = _c()["per_module_exposure"]["standard"]
    assert pme == ["state", "events", "policy hooks", "profile knobs", "rollback story",
                   "learning signal"]
    assert "chain from intent to action to consequence to learning" in _c()["key_line"]


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M00817", "M00818", "M00821", "M00822", "M00825", "M00830", "M00832"):
        assert mod in body, f"{mod} not in the M049 milestone (must trace to spec)"
