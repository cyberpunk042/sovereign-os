"""Selfdef module-catalog Grafana dashboard — contract test.

Locks the structural shape of
`docs/observability/dashboards/sovereign-os-selfdef-modules.json` —
the cockpit panel rendering the selfdef-side `selfdef_modules_*`
gauges shipped by selfdef-modules-textfile.{service,timer}
(selfdef commits `1ce88c7` + `b2f2e20`).

Same drift-protection pattern as the four-watchdog + M060
dashboard contracts — every canonical gauge appears on ≥1 panel,
thresholds match the alert rules + cross-surface lockstep, panel
count locked.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_PATH = (
    REPO_ROOT / "docs" / "observability" / "dashboards"
    / "sovereign-os-selfdef-modules.json"
)

CANONICAL_GAUGES = {
    "selfdef_modules_total",
    "selfdef_modules_by_category",
    "selfdef_modules_by_phase",
    "selfdef_modules_last_run_unix",
    "selfdef_modules_textfile_emit_failed",
}


def _load() -> dict:
    return json.loads(DASHBOARD_PATH.read_text())


def _all_panel_exprs(dash: dict) -> str:
    return " ".join(
        t.get("expr", "")
        for p in dash["panels"]
        for t in p.get("targets", [])
    )


def test_dashboard_file_present_and_valid_json():
    assert DASHBOARD_PATH.is_file(), f"missing dashboard: {DASHBOARD_PATH}"
    _load()


def test_dashboard_title_locked():
    dash = _load()
    assert dash["title"] == "sovereign-os — selfdef module-catalog"


def test_dashboard_uid_canonical():
    dash = _load()
    assert dash["uid"] == "sovereign-os-selfdef-modules"


def test_dashboard_tags_include_canonical_markers():
    dash = _load()
    tags = set(dash["tags"])
    for required in (
        "sovereign-os", "selfdef", "modules-catalog", "observability",
    ):
        assert required in tags, (
            f"dashboard tags missing required marker {required!r}"
        )


def test_every_canonical_gauge_appears_on_at_least_one_panel():
    dash = _load()
    all_exprs = _all_panel_exprs(dash)
    for gauge in CANONICAL_GAUGES:
        assert gauge in all_exprs, (
            f"dashboard missing canonical gauge {gauge!r} on any panel"
        )


def test_observer_age_panel_red_threshold_at_300s():
    """Cross-surface lockstep with M060 + four-watchdog observer-
    silent thresholds."""
    dash = _load()
    found = False
    for panel in dash["panels"]:
        title = panel.get("title", "").lower()
        if "observer age" not in title:
            continue
        steps = (
            panel.get("fieldConfig", {})
            .get("defaults", {})
            .get("thresholds", {})
            .get("steps", [])
        )
        for s in steps:
            if s.get("color") == "red" and s.get("value") == 300:
                found = True
                break
    assert found, (
        "observer-age panel must have red threshold at 300s "
        "(matches cross-surface lockstep)"
    )


def test_count_low_panel_threshold_at_100():
    """The total-modules panels MUST render the 100-floor red
    threshold matching the SelfdefModulesCountLow alert."""
    dash = _load()
    found = False
    for panel in dash["panels"]:
        targets = [t.get("expr", "") for t in panel.get("targets", [])]
        if not any("selfdef_modules_total" in e for e in targets):
            continue
        steps = (
            panel.get("fieldConfig", {})
            .get("defaults", {})
            .get("thresholds", {})
            .get("steps", [])
        )
        for s in steps:
            if s.get("color") == "yellow" and s.get("value") == 100:
                found = True
                break
        if found:
            break
    assert found, (
        "total-modules panel must mark the 100-floor threshold "
        "(matches SelfdefModulesCountLow alert)"
    )


def test_emit_failed_panel_has_failed_mapping():
    dash = _load()
    for panel in dash["panels"]:
        title = panel.get("title", "").lower()
        if "emit-failed" not in title and "emit_failed" not in title:
            continue
        mappings = (
            panel.get("fieldConfig", {})
            .get("defaults", {})
            .get("mappings", [])
        )
        for m in mappings:
            opts = m.get("options", {})
            if opts.get("1", {}).get("text", "").upper() == "FAILED":
                return  # found
    raise AssertionError(
        "emit-failed panel must map value=1 → text='FAILED'"
    )


def test_per_category_panel_uses_category_legend_format():
    """The per-category panel MUST format legends with the
    `{{category}}` label so operators see category names directly
    in Grafana legend instead of raw metric labels."""
    dash = _load()
    for panel in dash["panels"]:
        title = panel.get("title", "").lower()
        if "by category" not in title:
            continue
        legend = " ".join(
            t.get("legendFormat", "")
            for t in panel.get("targets", [])
        )
        assert "{{category}}" in legend, (
            "per-category panel legendFormat must include {{category}}"
        )
        return
    raise AssertionError(
        "dashboard missing the per-category timeseries panel"
    )


def test_dashboard_links_to_selfdef_producer_source():
    dash = _load()
    all_urls = " ".join(link.get("url", "") for link in dash.get("links", []))
    assert "selfdef-modules-textfile.sh" in all_urls, (
        "dashboard must link to the selfdef producer source"
    )
    assert "selfdef" in all_urls.lower()


def test_dashboard_refresh_interval_30s():
    """Matches the M060 + MS022 + four-watchdog dashboards for
    operator-cockpit visual consistency."""
    dash = _load()
    assert dash["refresh"] == "30s"


def test_dashboard_panel_count_locked():
    dash = _load()
    assert len(dash["panels"]) == 9, (
        f"dashboard panel count drift: expected 9, got {len(dash['panels'])}"
    )


def test_dashboard_links_to_deployment_guide_runbook():
    dash = _load()
    all_urls = " ".join(link.get("url", "") for link in dash.get("links", []))
    assert "m060-deployment-guide.md" in all_urls


def test_dashboard_anchors_to_selfdef_producer_commits():
    dash = _load()
    comment = dash.get("_comment", "")
    assert "1ce88c7" in comment or "b2f2e20" in comment, (
        "dashboard comment must cite the selfdef-side producer commits"
    )
