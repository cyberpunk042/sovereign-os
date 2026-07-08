"""M013 observability-plane metric-contract lint.

Locks `config/observability/m013-observability-plane-metrics.yaml` (the
spec-materialized metric contract) to the M013 milestone spec: all 6 metric-set
modules (M00201-M00206) present, valid Prometheus names + types + units, and a
fidelity check that the milestone's named metrics are actually declared.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY = REPO_ROOT / "config" / "observability" / "m013-observability-plane-metrics.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M013-observability-as-control-input.md"

EXPECTED_MODULES = {"M00201", "M00202", "M00203", "M00204", "M00205", "M00206"}
VALID_TYPES = {"gauge", "counter", "histogram", "summary"}
PROM_NAME = re.compile(r"^[a-z_][a-z0-9_]*$")

# Fidelity anchors: metric subjects named verbatim in the M013 dump that MUST
# survive materialization (guards against silent minimization of the spec).
SPEC_ANCHORS = [
    "verification_accept_rate", "draft_acceptance_rate", "avx_scheduler_tick",
    "branches_killed_grammar", "kv_prefix_hit", "tool_side_effects_committed",
    "memory_candidates_after_rerank",
]


def _doc() -> dict:
    return yaml.safe_load(REGISTRY.read_text())


def test_registry_present_and_parses():
    assert REGISTRY.is_file(), f"missing {REGISTRY}"
    d = _doc()
    assert d.get("milestone") == "M013"
    assert d.get("metric_sets"), "no metric_sets"


def test_all_six_modules_present():
    mods = {s.get("module") for s in _doc()["metric_sets"]}
    assert mods == EXPECTED_MODULES, (
        f"M013 metric-set module drift: {sorted(mods)} vs {sorted(EXPECTED_MODULES)}")


def test_every_metric_valid_prometheus_shape():
    for s in _doc()["metric_sets"]:
        assert s.get("metrics"), f"{s.get('module')}: no metrics"
        for m in s["metrics"]:
            assert PROM_NAME.match(m["name"]), f"bad metric name: {m['name']!r}"
            assert m["name"].startswith("sovereign_os_"), (
                f"metric {m['name']!r} must be sovereign_os_-namespaced")
            assert m.get("type") in VALID_TYPES, f"{m['name']}: bad type {m.get('type')!r}"
            assert m.get("unit"), f"{m['name']}: missing unit"


def test_metric_names_unique():
    names = [m["name"] for s in _doc()["metric_sets"] for m in s["metrics"]]
    dupes = {n for n in names if names.count(n) > 1}
    assert not dupes, f"duplicate metric names: {sorted(dupes)}"


def test_spec_fidelity_anchors_present():
    """Every verbatim-named metric subject from the M013 dump must appear in the
    materialized contract — no silent minimization."""
    blob = REGISTRY.read_text()
    missing = [a for a in SPEC_ANCHORS if a not in blob]
    assert not missing, f"M013 spec metrics dropped in materialization: {missing}"


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in EXPECTED_MODULES:
        assert mod in body, f"{mod} not in the M013 milestone (registry must trace to spec)"


# ── M013 E0110 feedback-loop rules (M00207-M00211) ───────────────────────────

RULES = REPO_ROOT / "config" / "observability" / "m013-feedback-loop-rules.yaml"
EXPECTED_RULE_MODULES = {"M00207", "M00208", "M00209", "M00210", "M00211"}


def _rules() -> dict:
    return yaml.safe_load(RULES.read_text())


def _all_metric_names() -> set[str]:
    return {m["name"] for s in _doc()["metric_sets"] for m in s["metrics"]}


def test_feedback_rules_present_and_cover_five_modules():
    assert RULES.is_file(), f"missing {RULES}"
    d = _rules()
    assert d.get("milestone") == "M013" and d.get("epic") == "E0110"
    mods = {r.get("module") for r in d["rules"]}
    assert mods == EXPECTED_RULE_MODULES, (
        f"M013 feedback-rule module drift: {sorted(mods)} vs {sorted(EXPECTED_RULE_MODULES)}")


def test_every_rule_trigger_metric_exists_in_contract():
    """The feedback loop is observability-AS-control-input: every rule must react
    to a metric that the metric contract actually declares — no dangling
    triggers."""
    known = _all_metric_names()
    for r in _rules()["rules"]:
        metric = r.get("trigger", {}).get("metric")
        assert metric in known, (
            f"rule {r.get('id')!r} triggers on {metric!r}, which is not in the "
            f"M013 metric contract")


def test_every_rule_has_actions_and_condition():
    for r in _rules()["rules"]:
        assert r.get("id") and r.get("actions"), f"rule {r.get('module')}: missing id/actions"
        assert r.get("trigger", {}).get("condition") in {"high", "low"}, (
            f"rule {r.get('id')!r}: trigger.condition must be high|low")
