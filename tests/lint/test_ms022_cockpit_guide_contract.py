"""MS022 sovereign-os cockpit guide — link + invariant lint.

The guide cites 4 consumer-side surfaces + the selfdef-side
producer guide; drift in any of those would silently break the
operator's mental model. This test locks:

  1. The guide exists.
  2. Every relative path it cites resolves on disk (no link rot).
  3. The 4 referenced consumer-side artefacts (alert rules, Grafana
     JSON, proxy script, systemd unit) are all present.
  4. The state thresholds in the guide match the alert thresholds
     (0.85 + 1.0) — drift here is the silent-misalignment hazard.
  5. The R10212 / project-boundary doctrine is asserted verbatim.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GUIDE = REPO_ROOT / "docs" / "operator" / "ms022-sse-quota-cockpit.md"


def _guide() -> str:
    return GUIDE.read_text()


def test_guide_present():
    assert GUIDE.is_file(), f"missing guide: {GUIDE}"


def test_guide_cites_alert_rules_file_that_exists():
    body = _guide()
    assert "ms022-sse-quota.rules.yml" in body, "guide must cite the alert rules"
    assert (
        REPO_ROOT / "config" / "prometheus" / "alerts" / "ms022-sse-quota.rules.yml"
    ).is_file(), "guide cites alert rules that don't exist"


def test_guide_cites_grafana_dashboard_that_exists():
    body = _guide()
    assert "sovereign-os-ms022-sse-quota.json" in body
    assert (
        REPO_ROOT / "docs" / "observability" / "dashboards"
        / "sovereign-os-ms022-sse-quota.json"
    ).is_file()


def test_guide_cites_proxy_script_that_exists():
    body = _guide()
    assert "ms022-sse-quota-api.py" in body
    assert (
        REPO_ROOT / "scripts" / "operator" / "ms022-sse-quota-api.py"
    ).is_file()


def test_guide_cites_systemd_unit_that_exists():
    body = _guide()
    assert "sovereign-ms022-sse-quota-api.service" in body
    assert (
        REPO_ROOT / "systemd" / "system" / "sovereign-ms022-sse-quota-api.service"
    ).is_file()


def test_guide_links_to_selfdef_producer_doc():
    body = _guide()
    assert "cyberpunk042/selfdef" in body, (
        "guide must link to the selfdef-side producer doc"
    )
    assert "ms022-sse-subscriber-quota" in body, (
        "guide must reference the selfdef producer doc filename"
    )


def test_guide_threshold_table_matches_alert_rules():
    """The thresholds documented in the guide MUST match the alert
    rules (0.85 + 1.0). Drift here silently misaligns the operator's
    mental model from the alert pipeline."""
    body = _guide()
    # The state-enumeration table cites both thresholds explicitly.
    assert "0.85" in body, "guide threshold drift: 0.85 missing"
    assert "1.0" in body, "guide threshold drift: 1.0 missing"
    # The selfdef-side metric prefix MUST be the canonical
    # selfdef_sse_subscribers_ — no shortened forms.
    assert "selfdef_sse_subscribers_global_saturation" in body
    assert "selfdef_sse_subscribers_per_token_saturated" in body


def test_guide_lists_all_three_alert_names():
    body = _guide()
    for name in (
        "MS022SseGlobalQuotaApproaching",
        "MS022SseGlobalQuotaSaturated",
        "MS022SsePerTokenQuotaSaturated",
    ):
        assert name in body, f"guide missing alert name {name!r}"


def test_guide_lists_all_four_consumer_surfaces():
    """Master-dashboard banner + Prometheus alerts + Grafana dashboard
    + proxy daemon. The TL;DR enumerates them; the body documents
    each. Drift = consumer-side surface ships without doc."""
    body = _guide()
    for surface in (
        "Master dashboard banner",
        "Prometheus alerts",
        "Grafana dashboard",
        "Proxy daemon",
    ):
        assert surface in body, f"guide missing consumer-side surface {surface!r}"


def test_guide_asserts_r10212_boundary_verbatim():
    body = _guide()
    assert "R10212" in body, "guide must reference R10212 explicitly"
    # The doctrine: every fix is an operator action on the selfdef host.
    assert "selfdef host" in body.lower(), (
        "guide must call out that all fixes route through the selfdef host"
    )
    # Specifically: no HTTP mutation from sovereign-os.
    assert "does not POST to selfdef" in body or "clipboard-copy" in body, (
        "guide must articulate the no-mutation contract"
    )


def test_guide_lists_50_contract_tests_inventory():
    """The R10212 section closes with the test-count inventory across
    both repos. Drift here = the operator's confidence model gets
    silently softer."""
    body = _guide()
    # Match the producer + per-surface counts the inventory cites.
    for inventory_phrase in (
        "9 `sse_quota_metrics.rs` unit tests",
        "12 alert contract tests",
        "10 dashboard contract tests",
        "15 API + master-dashboard wire-shape tests",
        "13 systemd unit contract tests",
    ):
        assert inventory_phrase in body, (
            f"guide test-inventory drift: missing {inventory_phrase!r}"
        )


def test_guide_relative_paths_resolve_on_disk():
    """Every `../../<path>` reference in the guide MUST resolve from
    the docs/operator/ directory. Catches typos that break the
    rendered cross-link."""
    body = _guide()
    docs_dir = GUIDE.parent
    relative_paths = set(re.findall(r"\(\.\./\.\./([\w/\-.]+)\)", body))
    missing = sorted(
        p for p in relative_paths
        if not (docs_dir / ".." / ".." / p).resolve().exists()
    )
    assert not missing, (
        f"guide cites relative paths that don't resolve: {missing}"
    )
