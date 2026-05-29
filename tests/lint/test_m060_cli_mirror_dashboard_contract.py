"""M060 D-CLI mirror Grafana dashboard — contract test.

Locks the panel surface for the selfdef-side cli-mirror doctor
textfile series so drift between the dashboard, the alert rules,
and the producer's emitted metric names fails fast.

The dashboard at docs/observability/dashboards/sovereign-os-m060-cli-mirror.json
visualizes the same `selfdef_cli_mirror_doctor_*` series that:
  - the selfdef-cli-mirror-doctor.timer systemd unit (selfdef-side)
    emits every 60s into node_exporter's textfile_collector
  - the M060CliMirror{ChainDegraded, ChainBroken, ObserverSilent}
    Prometheus alerts in config/prometheus/alerts/m060-chain-health.rules.yml
    fire on
  - the operator runbook sections in docs/operator/m060-deployment-guide.md
    cross-link from

Drift at any seam (metric rename, panel deleted, threshold tweaked
without alert update) fails this test before it ships.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DASH_PATH = REPO_ROOT / "docs" / "observability" / "dashboards" / "sovereign-os-m060-cli-mirror.json"


def _load() -> dict:
    return json.loads(DASH_PATH.read_text())


def _panel_expressions() -> list[str]:
    """All Prometheus exprs across every panel target in the
    dashboard, preserving order so position-sensitive tests stay
    debuggable."""
    out = []
    for panel in _load()["panels"]:
        for target in panel.get("targets", []):
            expr = target.get("expr")
            if expr:
                out.append(expr)
    return out


def test_dashboard_present_and_parses():
    assert DASH_PATH.is_file(), f"missing dashboard JSON: {DASH_PATH}"
    _load()  # raises if invalid JSON


def test_dashboard_title_uid_and_tags_are_canonical():
    data = _load()
    assert data["title"] == "sovereign-os — M060 D-CLI mirror chain", (
        f"unexpected title: {data['title']!r}"
    )
    assert data["uid"] == "sovereign-os-m060-cli-mirror", (
        f"uid drift would break runbook deep-links: {data['uid']!r}"
    )
    for required_tag in ("sovereign-os", "m060", "cli-mirror", "observability"):
        assert required_tag in data["tags"], (
            f"missing canonical tag {required_tag!r}; got: {data['tags']!r}"
        )


def test_every_producer_metric_appears_on_at_least_one_panel():
    """The 4 textfile series the selfdef-cli-mirror-doctor.timer ships
    must each surface on at least one panel — otherwise the dashboard
    silently drops part of the operator's observability surface."""
    exprs = "\n".join(_panel_expressions())
    for metric in (
        "selfdef_cli_mirror_doctor_worst_severity",
        "selfdef_cli_mirror_doctor_severity",
        "selfdef_cli_mirror_doctor_check_info",
        "selfdef_cli_mirror_doctor_last_run_unix",
    ):
        assert metric in exprs, (
            f"no panel references producer metric {metric!r}; "
            f"the textfile series silently drops out of the dashboard"
        )


def test_observer_age_panel_uses_300s_red_threshold():
    """The observer-age panel's red threshold must match the
    M060CliMirrorObserverSilent alert's `> 300` expression so the
    Grafana panel turns red AT THE SAME TIME the alert fires.
    Drift means the dashboard tells a different story than the
    page."""
    age_panel = next(
        p for p in _load()["panels"]
        if "observer age (s)" in p["title"]
    )
    steps = age_panel["fieldConfig"]["defaults"]["thresholds"]["steps"]
    red = next((s for s in steps if s["color"] == "red"), None)
    assert red is not None, "observer-age panel has no red threshold"
    assert red["value"] == 300, (
        f"observer-age red threshold {red['value']}s must equal 300s "
        f"to match the M060CliMirrorObserverSilent alert's > 300 expression"
    )


def test_worst_severity_panel_uses_correct_2_step_thresholds():
    """The worst-severity panel's value mappings + thresholds must
    classify 0=ok / 1=warn / 2=fail in lockstep with the alert
    expressions (== 1 = degraded, == 2 = broken)."""
    panel = next(
        p for p in _load()["panels"]
        if p["title"].startswith("worst severity")
    )
    mappings = panel["fieldConfig"]["defaults"]["mappings"]
    flat = mappings[0]["options"]
    assert flat["0"]["text"] == "OK"
    assert flat["1"]["text"] == "WARN"
    assert flat["2"]["text"] == "FAIL"

    steps = panel["fieldConfig"]["defaults"]["thresholds"]["steps"]
    colors = {s["color"]: s.get("value", 0) for s in steps}
    assert colors.get("green") == 0
    assert colors.get("yellow") == 1
    assert colors.get("red") == 2


def test_check_info_panel_is_a_table_with_fix_column():
    """The check-info table is the live triage surface — it must be
    a table panel + include the `fix` column so operators copy-paste
    remediation commands straight from the dashboard."""
    panel = next(
        p for p in _load()["panels"]
        if "fix line" in p["title"]
    )
    assert panel["type"] == "table", (
        f"check-info panel must be type=table, got {panel['type']!r}"
    )
    # The transformations must include the 'fix' column in the rename
    # / index map so it actually shows up.
    transforms = panel.get("transformations", [])
    assert transforms, "check-info table needs an organize transform"
    organize = next(
        (t for t in transforms if t["id"] == "organize"),
        None,
    )
    assert organize is not None, "missing organize transformation"
    index_by_name = organize["options"].get("indexByName", {})
    assert "fix" in index_by_name, (
        f"check-info table must surface the `fix` column; got: "
        f"{list(index_by_name)!r}"
    )


def test_dashboard_links_to_producer_runbook():
    """The selfdef-side producer guide is the canonical document for
    the cli-mirror chain. The dashboard MUST link to it so an operator
    drilling into the dashboard from Grafana lands on the runbook
    without context-switching."""
    links = _load().get("links", [])
    selfdef_link = next(
        (l for l in links if "cyberpunk042/selfdef" in l.get("url", "")),
        None,
    )
    assert selfdef_link is not None, (
        "dashboard must include a link to the selfdef-side producer guide"
    )
    assert "m060-cockpit-mirror-producers" in selfdef_link["url"], (
        f"dashboard link to selfdef must target the producer guide; "
        f"got: {selfdef_link['url']!r}"
    )


def test_companion_view_includes_chain_wide_signal():
    """The M060 D-CLI dashboard is the per-link view; operators
    benefit from seeing the chain-wide rollup beside it so they can
    correlate a D-CLI degradation with a chain-wide event. The
    sovereign_os_operator_m060_health_api_request_total expr must
    appear on at least one panel."""
    exprs = "\n".join(_panel_expressions())
    assert "sovereign_os_operator_m060_health_api_request_total" in exprs, (
        "dashboard must include a companion view of the chain-wide "
        "alert metric so operators see both signals in one place"
    )


def test_refresh_interval_is_30s():
    """30s refresh balances dashboard freshness against scrape cost.
    The doctor timer cadence is 60s, so 30s refresh means a dashboard
    in front of an operator picks up the next textfile sample within
    1 refresh."""
    assert _load()["refresh"] == "30s", (
        f"refresh interval drift; got {_load()['refresh']!r}"
    )


def test_panel_count_matches_canonical_layout():
    """Lock the panel count at 9 so an accidental dashboard-trim
    PR fails this test before merging. Distinct from the per-metric
    asserts above — this catches "panel deleted, metric still
    referenced via the table" kind of regressions."""
    panels = _load()["panels"]
    assert len(panels) == 9, (
        f"M060 D-CLI dashboard panel count drift: expected 9 "
        f"(4 stats + 4 timeseries + 1 table); got {len(panels)}"
    )
