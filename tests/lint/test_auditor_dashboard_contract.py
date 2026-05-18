"""R497 (master spec §§ 10, 17) — Auditor Grafana dashboard contract lint.

Closes the auditor dashboard:FUTURE waiver and registers `auditor` as a
first-class MODULE_COVERAGE entry (4 surfaces: core / cli / service /
dashboard).

Per operator §1g verbatim (sacrosanct):

  "We do not minimize anything."

The Auditor (master spec §§ 10, 17 — Immutable Gatekeeper) is the
operator-§17 Genesis Trinity always-on, kernel-driven, podman-kill-armed
event-loop guardian: tails Tetragon eBPF events, fires podman kill on
perimeter violations, appends to the master spec § 7.1 atomic
append-only audit log.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AUDITOR_DASHBOARD_JSON = (
    REPO_ROOT / "docs" / "observability" / "dashboards"
    / "sovereign-os-auditor.json"
)


def test_dashboard_json_exists():
    assert AUDITOR_DASHBOARD_JSON.is_file(), (
        f"missing auditor dashboard: {AUDITOR_DASHBOARD_JSON}"
    )


def test_dashboard_json_parseable():
    data = json.loads(AUDITOR_DASHBOARD_JSON.read_text(encoding="utf-8"))
    assert "panels" in data
    assert data.get("title")
    assert data.get("uid")


def test_dashboard_references_neutralization_metric():
    body = AUDITOR_DASHBOARD_JSON.read_text(encoding="utf-8")
    assert "sovereign_os_auditor_neutralization_total" in body, (
        "auditor dashboard doesn't reference neutralization_total metric"
    )


def test_dashboard_references_event_parse_metric():
    body = AUDITOR_DASHBOARD_JSON.read_text(encoding="utf-8")
    assert "sovereign_os_auditor_event_parse_total" in body, (
        "auditor dashboard missing event_parse_total metric"
    )


def test_dashboard_references_freshness_gauge():
    body = AUDITOR_DASHBOARD_JSON.read_text(encoding="utf-8")
    assert "sovereign_os_auditor_last_neutralization_timestamp" in body, (
        "auditor dashboard missing last_neutralization_timestamp "
        "freshness gauge"
    )


def test_dashboard_documents_three_parse_outcomes():
    """Master spec § 10.1 3-outcome event-parse vocabulary MUST appear
    verbatim (trigger / benign / bad-json)."""
    body = AUDITOR_DASHBOARD_JSON.read_text(encoding="utf-8")
    for outcome in ("trigger", "benign", "bad-json"):
        assert outcome in body, (
            f"auditor dashboard missing parse outcome: {outcome!r}"
        )


def test_dashboard_documents_neutralization_results():
    """Master spec § 10.1 neutralization-result vocabulary MUST appear
    (success / kill-failed / no-container-id / dry-run)."""
    body = AUDITOR_DASHBOARD_JSON.read_text(encoding="utf-8")
    for result in ("success", "kill-failed", "no-container-id", "dry-run"):
        assert result in body, (
            f"auditor dashboard missing neutralization result: {result!r}"
        )


def test_dashboard_documents_tetragon_event_socket():
    """Master spec § 10 names the Tetragon eBPF UNIX socket; the socket
    path MUST appear in the dashboard markdown so operators know the
    upstream dependency."""
    body = AUDITOR_DASHBOARD_JSON.read_text(encoding="utf-8")
    assert "/var/run/tetragon/tetragon.events" in body, (
        "auditor dashboard missing Tetragon event socket path"
    )


def test_dashboard_quotes_master_spec_section_10_verbatim():
    """Master spec § 10 'autonomous circuit breaker' MUST appear
    verbatim — load-bearing protocol identity."""
    body = AUDITOR_DASHBOARD_JSON.read_text(encoding="utf-8")
    assert "autonomous circuit breaker" in body, (
        "auditor dashboard missing master spec § 10 verbatim quotation"
    )


def test_dashboard_references_genesis_trinity():
    """The Auditor is one of the §17 Genesis Trinity members — placement
    MUST appear so operators understand the role context."""
    body = AUDITOR_DASHBOARD_JSON.read_text(encoding="utf-8")
    assert "Genesis Trinity" in body, (
        "auditor dashboard missing §17 Genesis Trinity placement"
    )


def test_dashboard_quotes_operator_standing_rule_verbatim():
    body = AUDITOR_DASHBOARD_JSON.read_text(encoding="utf-8")
    assert "We do not minimize anything" in body, (
        "auditor dashboard missing §1g verbatim standing rule"
    )


def test_dashboard_listed_in_readme():
    readme = (AUDITOR_DASHBOARD_JSON.parent / "README.md").read_text(encoding="utf-8")
    assert "sovereign-os-auditor.json" in readme, (
        "dashboards/README.md missing sovereign-os-auditor.json entry"
    )


def test_dashboard_tagged_sovereign_os():
    data = json.loads(AUDITOR_DASHBOARD_JSON.read_text(encoding="utf-8"))
    tags = data.get("tags") or []
    assert "sovereign-os" in tags
    assert "auditor" in tags


def test_auditor_registered_in_surface_map():
    """R497 registers `auditor` as a first-class MODULE_COVERAGE entry —
    dashboard MUST appear as a shipped surface, and `service` MUST also
    be shipped (the guardian-core daemon is the load-bearing piece)."""
    sm_path = REPO_ROOT / "scripts" / "operator" / "surface-map.py"
    result = subprocess.run(
        ["python3", str(sm_path), "coverage", "--module",
         "auditor", "--json"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, (
        f"surface-map coverage auditor failed: {result.stderr[:300]}"
    )
    data = json.loads(result.stdout)
    entries = data.get("coverage", [data])
    entry = entries[0] if entries else {}
    surface_count = entry.get("surface_count", 0)
    assert surface_count >= 4, (
        f"auditor must be at >=4 surfaces post-R497; got {surface_count}"
    )
    matrix = entry.get("matrix", [])
    dashboard_row = next(
        (r for r in matrix if r.get("surface") == "dashboard"), None
    )
    assert dashboard_row is not None, (
        "auditor coverage matrix missing 'dashboard' row"
    )
    assert dashboard_row.get("state") == "shipped", (
        f"auditor dashboard surface must be shipped; got {dashboard_row}"
    )
    service_row = next(
        (r for r in matrix if r.get("surface") == "service"), None
    )
    assert service_row is not None, (
        "auditor coverage matrix missing 'service' row"
    )
    assert service_row.get("state") == "shipped", (
        f"auditor service surface must be shipped "
        f"(sovereign-guardian-core.service); got {service_row}"
    )
