"""M013 observability-plane metric-contract + feedback-loop lint.

Locks `config/observability/m013-observability-plane-metrics.yaml` and
`config/observability/m013-feedback-loop-rules.yaml` to the M013 milestone
FEATURE spec (F01028-F01062 metric rows + M00207-M00211 rules): the 5 tier
metric sets + the M00201 plane-subject list present, metric NAMES verbatim from
the feature rows (sovereign_* namespace, `{label}` dimensions), and every
feedback rule triggers on a metric the contract declares.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY = REPO_ROOT / "config" / "observability" / "m013-observability-plane-metrics.yaml"
RULES = REPO_ROOT / "config" / "observability" / "m013-feedback-loop-rules.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M013-observability-as-control-input.md"

EXPECTED_TIER_MODULES = {"M00202", "M00203", "M00204", "M00205", "M00206"}
EXPECTED_RULE_MODULES = {"M00207", "M00208", "M00209", "M00210", "M00211"}
VALID_TYPES = {"gauge", "counter", "histogram", "summary"}
PROM_NAME = re.compile(r"^[a-z_][a-z0-9_]*$")

# Fidelity anchors: metric names taken verbatim from the M013 FEATURE rows that
# MUST survive materialization (guards against silent minimization / renaming).
SPEC_ANCHORS = [
    "sovereign_oracle_verification_accept_rate",   # F01035
    "sovereign_scout_draft_rejection_reason_total",  # F01039 (labeled)
    "sovereign_cpu_branches_killed_total",         # F01043 (labeled, not 3 metrics)
    "sovereign_cpu_avx_scheduler_tick_us",         # F01045
    "sovereign_kv_prefix_hit_rate",                # F01050
    "sovereign_kv_offload_bytes_total",            # F01053 (labeled)
    "sovereign_tool_side_effects_committed_total",  # F01062
]


def _doc() -> dict:
    return yaml.safe_load(REGISTRY.read_text())


def _rules() -> dict:
    return yaml.safe_load(RULES.read_text())


def _all_metric_names() -> set[str]:
    return {m["name"] for s in _doc()["metric_sets"] for m in s["metrics"]}


def test_registry_present_and_parses():
    assert REGISTRY.is_file(), f"missing {REGISTRY}"
    d = _doc()
    assert d.get("milestone") == "M013" and d.get("metric_sets")


def test_plane_subjects_are_M00201_ten_subjects():
    ps = _doc().get("plane_subjects", {})
    assert ps.get("module") == "M00201"
    assert len(ps.get("subjects", [])) == 10, "M00201 lists 10 plane subjects (dump 3076-3087)"


def test_five_tier_modules_present():
    mods = {s.get("module") for s in _doc()["metric_sets"]}
    assert mods == EXPECTED_TIER_MODULES, (
        f"M013 tier metric-set drift: {sorted(mods)} vs {sorted(EXPECTED_TIER_MODULES)}")


def test_every_metric_valid_and_feature_traced():
    for s in _doc()["metric_sets"]:
        assert s.get("metrics"), f"{s.get('module')}: no metrics"
        for m in s["metrics"]:
            assert PROM_NAME.match(m["name"]), f"bad metric name: {m['name']!r}"
            assert m["name"].startswith("sovereign_"), (
                f"{m['name']!r} must be sovereign_-namespaced (feature-spec verbatim)")
            assert m.get("type") in VALID_TYPES, f"{m['name']}: bad type {m.get('type')!r}"
            assert m.get("unit"), f"{m['name']}: missing unit"
            assert re.fullmatch(r"F\d{5}", str(m.get("feature", ""))), (
                f"{m['name']}: must trace to an F##### feature row")


def test_metric_names_unique():
    names = [m["name"] for s in _doc()["metric_sets"] for m in s["metrics"]]
    dupes = {n for n in names if names.count(n) > 1}
    assert not dupes, f"duplicate metric names: {sorted(dupes)}"


def test_spec_fidelity_anchors_present():
    blob = REGISTRY.read_text()
    missing = [a for a in SPEC_ANCHORS if a not in blob]
    assert not missing, f"M013 feature metrics dropped/renamed in materialization: {missing}"


def test_labeled_metrics_declare_labels():
    """Feature rows with `{label}` (e.g. F01043 branches_killed_total{reason})
    must be a SINGLE metric carrying that label — not minimized to a plain
    counter nor expanded into separate metrics."""
    labeled = {m["name"]: m for s in _doc()["metric_sets"] for m in s["metrics"] if m.get("labels")}
    for name in ("sovereign_cpu_branches_killed_total", "sovereign_cpu_branches_sent_total",
                 "sovereign_scout_draft_rejection_reason_total",
                 "sovereign_kv_offload_bytes_total", "sovereign_tool_failures_total"):
        assert name in labeled, f"{name} must be a single labeled metric"


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in EXPECTED_TIER_MODULES | {"M00201"} | EXPECTED_RULE_MODULES:
        assert mod in body, f"{mod} not in the M013 milestone (must trace to spec)"


# ── M013 E0110 feedback-loop rules (M00207-M00211) ───────────────────────────

def test_feedback_rules_present_and_cover_five_modules():
    assert RULES.is_file(), f"missing {RULES}"
    d = _rules()
    assert d.get("milestone") == "M013" and d.get("epic") == "E0110"
    mods = {r.get("module") for r in d["rules"]}
    assert mods == EXPECTED_RULE_MODULES, (
        f"M013 feedback-rule drift: {sorted(mods)} vs {sorted(EXPECTED_RULE_MODULES)}")


def test_every_rule_trigger_metric_exists_in_contract():
    """Observability-AS-control-input: every rule must react to a metric the
    contract actually declares — no dangling triggers."""
    known = _all_metric_names()
    for r in _rules()["rules"]:
        metric = r.get("trigger", {}).get("metric")
        assert metric in known, (
            f"rule {r.get('id')!r} triggers on {metric!r}, not in the M013 metric contract")


def test_every_rule_has_actions_and_condition():
    for r in _rules()["rules"]:
        assert r.get("id") and r.get("actions"), f"rule {r.get('module')}: missing id/actions"
        assert r.get("trigger", {}).get("condition") in {"high", "low"}, (
            f"rule {r.get('id')!r}: trigger.condition must be high|low")


# ── M013 E0111 bit-control + E0112 tracing (M00212-M00215) ───────────────────

BITTRACE = REPO_ROOT / "config" / "observability" / "m013-bit-control-and-tracing.yaml"


def _bt() -> dict:
    return yaml.safe_load(BITTRACE.read_text())


def test_status_word_8_fields_verbatim_nonoverlapping_64bit():
    """M00212: the 8 spec fields present, bit layout packs into 64 without
    overlap (widths are agent-proposed but must be internally consistent)."""
    sw = _bt()["worker_status_word"]
    assert sw["module"] == "M00212" and sw["width_bits"] == 64
    assert sw.get("bit_layout_proposed") is True, "bit widths must be flagged agent-proposed (SB-095)"
    names = [f["name"] for f in sw["fields"]]
    assert names == ["load", "memory", "thermal", "queue", "error", "health",
                     "policy_mode", "flags"], f"M00212 field drift: {names}"
    # non-overlap + within 64
    used = []
    for f in sw["fields"]:
        span = range(f["offset"], f["offset"] + f["bits"])
        assert f["offset"] + f["bits"] <= 64, f"{f['name']} exceeds 64 bits"
        assert not (set(span) & set(used)), f"{f['name']} bit range overlaps another field"
        used += list(span)


def test_routing_masks_verbatim():
    masks = {m["id"]: m for m in _bt()["branch_routing_masks"]}
    assert masks["route_to_oracle"]["expression"] == \
        "value_high & oracle_healthy & not_vram_pressure & branch_needs_verification"
    assert masks["route_to_scout"]["expression"] == \
        "scout_healthy & low_risk & draft_expected_useful & branch_budget_ok"
    for m in masks.values():
        # terms list must match the & -joined expression exactly (no minimization)
        assert m["terms"] == [t.strip() for t in m["expression"].split("&")]


def test_trace_mapping_four_levels_verbatim():
    tm = _bt()["trace_mapping"]
    assert tm["module"] == "M00215"
    got = {l["id"]: l["maps_to"] for l in tm["levels"]}
    assert got == {
        "trace_id": "user request",
        "span_id": "branch step / model call / tool call",
        "branch_id": "runtime object",
        "commit_id": "accepted transition",
    }, f"M00215 trace mapping drift: {got}"
