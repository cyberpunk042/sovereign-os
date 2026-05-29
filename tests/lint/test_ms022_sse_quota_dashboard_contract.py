"""MS022 SSE quota Grafana dashboard — contract test."""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DASH_PATH = (
    REPO_ROOT / "docs" / "observability" / "dashboards"
    / "sovereign-os-ms022-sse-quota.json"
)


def _load() -> dict:
    return json.loads(DASH_PATH.read_text())


def _exprs() -> list[str]:
    return [
        t["expr"]
        for p in _load()["panels"]
        for t in p.get("targets", [])
        if t.get("expr")
    ]


def test_dashboard_present_and_parses():
    assert DASH_PATH.is_file()
    _load()


def test_canonical_title_uid_and_tags():
    d = _load()
    assert d["title"] == "sovereign-os — MS022 SSE subscriber quota"
    assert d["uid"] == "sovereign-os-ms022-sse-quota"
    for tag in ("sovereign-os", "ms022", "sse-quota", "observability"):
        assert tag in d["tags"], f"missing canonical tag {tag!r}"


def test_all_producer_metrics_appear_on_at_least_one_panel():
    """Every selfdef_sse_subscribers_* gauge produced by selfdef
    commit 77b4499 must surface on ≥1 panel — drift means the
    producer's metric silently drops out of the dashboard."""
    exprs = "\n".join(_exprs())
    for metric in (
        "selfdef_sse_subscribers_global_active",
        "selfdef_sse_subscribers_global_cap",
        "selfdef_sse_subscribers_global_saturation",
        "selfdef_sse_subscribers_per_token_cap",
        "selfdef_sse_subscribers_per_token",
        "selfdef_sse_subscribers_per_token_saturated",
    ):
        assert metric in exprs, (
            f"no panel references producer metric {metric!r}"
        )


def test_saturation_panel_uses_0_85_red_threshold():
    """The saturation gauge stat panel's red threshold must match
    the MS022SseGlobalQuotaApproaching alert's > 0.85 expression so
    the Grafana panel turns red at the SAME time the alert fires."""
    panel = next(
        p for p in _load()["panels"]
        if p["title"] == "global saturation (0..1)"
    )
    steps = panel["fieldConfig"]["defaults"]["thresholds"]["steps"]
    red = next((s for s in steps if s["color"] == "red"), None)
    assert red is not None, "saturation panel has no red threshold"
    assert red["value"] == 0.85, (
        f"saturation panel red threshold must equal the alert trigger "
        f"(0.85); got {red['value']!r}"
    )


def test_saturation_time_series_uses_alert_threshold_lines():
    """The saturation time-series panel must visually render both
    the 0.85 (warning) and 1.0 (critical) alert thresholds so
    operators see them alongside the value."""
    panel = next(
        p for p in _load()["panels"]
        if p["title"] == "global saturation over time"
    )
    steps = panel["fieldConfig"]["defaults"]["thresholds"]["steps"]
    values = sorted(s.get("value", 0) for s in steps if s.get("value", 0) > 0)
    assert 0.85 in values and 1.0 in values, (
        f"saturation time-series must visualize 0.85 + 1.0 alert "
        f"thresholds; got steps {steps!r}"
    )


def test_per_token_table_uses_topk_and_renames_value_to_subscribers():
    """The per-token table panel uses topk(20, ...) so high-cardinality
    deployments don't blow up Grafana, and renames `Value` to
    `subscribers` so the column header is operator-readable."""
    panel = next(
        p for p in _load()["panels"]
        if "per-token subscriber counts" in p["title"]
    )
    expr = panel["targets"][0]["expr"]
    assert "topk(20" in expr, (
        f"per-token table must use topk(20, ...) for cardinality safety; "
        f"got {expr!r}"
    )
    organize = next(
        t for t in panel["transformations"] if t["id"] == "organize"
    )
    rename = organize["options"]["renameByName"]
    assert rename.get("Value") == "subscribers", (
        f"per-token table must rename the Value column to `subscribers`; "
        f"got rename map {rename!r}"
    )


def test_dashboard_cross_references_producer_source():
    """The dashboard's links list must include a deep-link to the
    selfdef-side producer source so operators drilling into the
    dashboard land on the metric definition."""
    links = _load().get("links", [])
    producer = next(
        (l for l in links if "cyberpunk042/selfdef" in l.get("url", "")),
        None,
    )
    assert producer is not None
    assert "sse_quota_metrics" in producer["url"], (
        f"producer link must reference the sse_quota_metrics source; "
        f"got: {producer['url']!r}"
    )


def test_refresh_interval_is_30s():
    assert _load()["refresh"] == "30s"


def test_panel_count_matches_canonical_layout():
    """Lock at 10 panels: 4 stats (saturation, active, cap, tokens-saturated)
    + 2 timeseries (saturation, active-vs-cap) + 1 table (per-token)
    + 2 timeseries (per-token-saturated, per-token-cap) + 1 companion."""
    panels = _load()["panels"]
    assert len(panels) == 10, (
        f"panel count drift: expected 10 (4 stats + 4 timeseries + 1 table "
        f"+ 1 companion); got {len(panels)}"
    )


def test_companion_view_includes_m060_chain_signal():
    """Cross-context: operators see if SSE saturation correlates
    with chain-wide M060 events."""
    exprs = "\n".join(_exprs())
    assert "sovereign_os_operator_m060_health_api_request_total" in exprs, (
        "dashboard must include the M060 chain-health companion view"
    )
