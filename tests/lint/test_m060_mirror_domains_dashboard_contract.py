"""M060 mirror-domains Grafana dashboard — contract test.

Locks the panel surface for the selfdef-side chain-wide m060-doctor
textfile series so drift between the dashboard, the alert rules,
and the producer's emitted metric names fails fast.

Sister to test_m060_cli_mirror_dashboard_contract.py (which covers
the D-CLI sub-chain).
"""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DASH_PATH = (
    REPO_ROOT / "docs" / "observability" / "dashboards"
    / "sovereign-os-m060-mirror-domains.json"
)


def _load() -> dict:
    return json.loads(DASH_PATH.read_text())


def _panel_expressions() -> list[str]:
    out = []
    for panel in _load()["panels"]:
        for target in panel.get("targets", []):
            expr = target.get("expr")
            if expr:
                out.append(expr)
    return out


def test_dashboard_present_and_parses():
    assert DASH_PATH.is_file(), f"missing dashboard JSON: {DASH_PATH}"
    _load()


def test_dashboard_title_uid_and_tags_are_canonical():
    data = _load()
    assert data["title"] == "sovereign-os — M060 mirror domains (chain-wide)", (
        f"unexpected title: {data['title']!r}"
    )
    assert data["uid"] == "sovereign-os-m060-mirror-domains", (
        f"uid drift would break runbook deep-links: {data['uid']!r}"
    )
    for required_tag in ("sovereign-os", "m060", "mirror-domains", "observability"):
        assert required_tag in data["tags"], (
            f"missing canonical tag {required_tag!r}; got: {data['tags']!r}"
        )


def test_every_producer_metric_appears_on_at_least_one_panel():
    """All 5 m060-doctor textfile series must surface on at least
    one panel — drift means the textfile silently drops out."""
    exprs = "\n".join(_panel_expressions())
    for metric in (
        "selfdef_m060_doctor_severity",
        "selfdef_m060_doctor_resident_present",
        "selfdef_m060_doctor_published_present",
        "selfdef_m060_doctor_domain_info",
        "selfdef_m060_doctor_worst_severity",
        "selfdef_m060_doctor_last_run_unix",
    ):
        assert metric in exprs, (
            f"no panel references producer metric {metric!r}"
        )


def test_observer_age_panel_uses_300s_red_threshold():
    """The observer-age panels' red threshold must match the
    M060MirrorDomainObserverSilent alert's `> 300`."""
    panels = _load()["panels"]
    age_panels = [
        p for p in panels
        if "observer age (s)" in p["title"]
    ]
    assert age_panels, "no observer-age panels"
    for panel in age_panels:
        steps = panel["fieldConfig"]["defaults"]["thresholds"]["steps"]
        red = next((s for s in steps if s["color"] == "red"), None)
        assert red is not None, f"observer-age panel {panel['title']!r} has no red threshold"
        assert red["value"] == 300, (
            f"observer-age red threshold {red['value']}s in panel "
            f"{panel['title']!r} must equal 300s to match alert"
        )


def test_worst_severity_panel_uses_correct_value_mappings():
    """Same value mappings as the cli-mirror sibling so operators
    reading either dashboard see consistent OK/WARN/FAIL labels."""
    panel = next(
        p for p in _load()["panels"]
        if p["title"].startswith("worst severity")
    )
    mappings = panel["fieldConfig"]["defaults"]["mappings"]
    flat = mappings[0]["options"]
    assert flat["0"]["text"] == "OK"
    assert flat["1"]["text"] == "WARN"
    assert flat["2"]["text"] == "FAIL"


def test_per_domain_state_table_with_note_column():
    """The per-domain-state table is the live triage surface. Must
    be table-type AND include the `note` column via organize."""
    panel = next(
        p for p in _load()["panels"]
        if "current per-domain state" in p["title"]
    )
    assert panel["type"] == "table"
    transforms = panel.get("transformations", [])
    organize = next((t for t in transforms if t["id"] == "organize"), None)
    assert organize is not None
    index_by_name = organize["options"].get("indexByName", {})
    assert "note" in index_by_name, (
        f"per-domain table must surface the `note` column; got: "
        f"{list(index_by_name)!r}"
    )


def test_resident_vs_published_matrix_present():
    """A panel must show resident_present + published_present
    side-by-side per domain so operators see the wedge case
    (resident=1, published=0) at a glance."""
    panels = _load()["panels"]
    matrix = next(
        (p for p in panels if "resident vs published" in p["title"].lower()),
        None,
    )
    assert matrix is not None, "no resident-vs-published matrix panel"
    assert matrix["type"] == "table"
    exprs = [t["expr"] for t in matrix["targets"]]
    assert any("resident_present" in e for e in exprs)
    assert any("published_present" in e for e in exprs)


def test_dashboard_links_to_cli_mirror_sibling():
    """The two sub-chain dashboards must cross-link so operators
    navigating one can jump to the other."""
    links = _load().get("links", [])
    sibling = next(
        (l for l in links if "cli-mirror" in l.get("url", "")),
        None,
    )
    assert sibling is not None, (
        "dashboard must link to the D-CLI sub-chain dashboard"
    )


def test_dashboard_links_to_producer_runbook():
    """Same R10212 boundary: producer-side runbook lives in selfdef."""
    links = _load().get("links", [])
    producer = next(
        (l for l in links if "cyberpunk042/selfdef" in l.get("url", "")),
        None,
    )
    assert producer is not None
    assert "m060-cockpit-mirror-producers" in producer["url"]


def test_refresh_interval_is_30s():
    assert _load()["refresh"] == "30s"


def test_panel_count_matches_canonical_layout():
    """Lock the panel count at 10 (chain-wide has one extra companion-
    view panel for the sovereign-os m060-health-api metric)."""
    panels = _load()["panels"]
    assert len(panels) == 10, (
        f"M060 mirror-domains dashboard panel count: expected 10 "
        f"(4 stats + 4 timeseries + 2 tables); got {len(panels)}"
    )


def test_companion_view_includes_chain_wide_signal():
    """The mirror-domains dashboard must include a companion view of
    the chain-wide sovereign-os m060-health-api metric so operators
    see both signals (selfdef-side per-domain + sovereign-os-side
    chain-wide) in one place."""
    exprs = "\n".join(_panel_expressions())
    assert "sovereign_os_operator_m060_health_api_request_total" in exprs, (
        "dashboard must reference the sovereign-os chain-wide metric"
    )
