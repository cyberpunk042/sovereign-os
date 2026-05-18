"""R458 — §1g/§1h compliance dashboard aggregator contract lint.

Consolidates the 4-tool §1g compliance instrument suite (R453 + R454
+ R456 + R457) into a single operator-discoverable rollup.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CP_PY = REPO_ROOT / "scripts" / "operator" / "compliance.py"
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"

EXPECTED_INSTRUMENTS = [
    "surface-map",
    "doc-coverage",
    "anti-minimization-audit",
    "ux-design-audit",
    "selfdef-discovery",  # R461 cross-repo instrument
    "selfdef-surfaces",   # R463 cross-repo instrument
    "selfdef-ux",         # R464 cross-repo instrument
    "selfdef-audit",      # R466 cross-repo instrument
]


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# --- Structural ---


def test_compliance_script_exists():
    assert CP_PY.is_file(), f"missing {CP_PY}"


def test_compliance_executable():
    assert os.access(CP_PY, os.X_OK), f"{CP_PY} not executable"


def test_python3_shebang():
    body = _read(CP_PY)
    assert body.startswith("#!/usr/bin/env python3")


def test_documents_r458_origin():
    body = _read(CP_PY)
    assert "R458" in body


def test_references_all_eight_instruments():
    """compliance.py MUST reference all 8 R-rounds it consolidates."""
    body = _read(CP_PY)
    for r in ("R453", "R454", "R456", "R457",
              "R461", "R463", "R464", "R466"):
        assert r in body, f"missing reference to {r}"


# --- Instrument catalog ---


def test_instruments_catalog_defined():
    body = _read(CP_PY)
    assert "INSTRUMENTS" in body, "missing INSTRUMENTS catalog"
    for i in EXPECTED_INSTRUMENTS:
        assert f'"{i}"' in body, f"INSTRUMENTS missing {i!r}"


def test_each_instrument_has_round_field():
    body = _read(CP_PY)
    n = body.count('"round":')
    assert n >= 4, f"only {n} 'round' fields (expected ≥4)"


def test_each_instrument_has_script_field():
    body = _read(CP_PY)
    n = body.count('"script":')
    assert n >= 4, f"only {n} 'script' fields (expected ≥4)"


# --- CLI surface (5 verbs) ---


def test_supports_status_verb():
    body = _read(CP_PY)
    assert '"status"' in body


def test_supports_module_verb():
    body = _read(CP_PY)
    assert '"module"' in body


def test_supports_worst_verb():
    body = _read(CP_PY)
    assert '"worst"' in body


def test_supports_history_verb():
    body = _read(CP_PY)
    assert '"history"' in body


def test_supports_snapshot_verb():
    body = _read(CP_PY)
    assert '"snapshot"' in body


def test_snapshot_has_triple_gate():
    """snapshot MUST require --apply + --confirm-snapshot."""
    body = _read(CP_PY)
    assert "--apply" in body
    assert "--confirm-snapshot" in body


def test_json_and_human_format_flags():
    body = _read(CP_PY)
    assert "--json" in body and "--human" in body


# --- DRY-RUN + env overlay ---


def test_supports_dry_run():
    body = _read(CP_PY)
    assert "SOVEREIGN_OS_DRY_RUN" in body


def test_supports_dedicated_dry_run_env():
    body = _read(CP_PY)
    assert "SOVEREIGN_OS_COMPLIANCE_DRY_RUN" in body


def test_snapshot_path_env_overridable():
    body = _read(CP_PY)
    assert "SOVEREIGN_OS_COMPLIANCE_OUT" in body


# --- Metric ---


def test_emits_layer_b_metric():
    body = _read(CP_PY)
    assert "sovereign_os_operator_compliance_query_total" in body


# --- osctl integration ---


def test_osctl_dispatches_compliance():
    body = _read(OSCTL)
    assert "compliance)" in body, (
        "osctl missing compliance) dispatcher"
    )
    assert "compliance.py" in body, (
        "osctl dispatcher doesn't reference compliance.py"
    )


def test_osctl_help_documents_compliance_verbs():
    body = _read(OSCTL)
    for sub in (
        "compliance status",
        "compliance module",
        "compliance worst",
        "compliance history",
        "compliance snapshot",
    ):
        assert sub in body, f"osctl help missing {sub!r}"


def test_osctl_help_references_r458():
    body = _read(OSCTL)
    assert "R458" in body


# --- Smoke tests ---


def test_status_verb_aggregates_eight_instruments():
    """status --json MUST return data from all 8 instruments."""
    result = subprocess.run(
        ["python3", str(CP_PY), "status", "--json"],
        capture_output=True, text=True, timeout=180,
    )
    assert result.returncode == 0, (
        f"status failed: stderr={result.stderr[:500]}"
    )
    data = json.loads(result.stdout)
    keys = ("surface_map", "doc_coverage",
            "anti_minimization_audit", "ux_design_audit",
            "selfdef_discovery", "selfdef_surfaces",
            "selfdef_ux", "selfdef_audit")
    for key in keys:
        assert key in data, f"status missing {key!r}"
    for key in keys:
        assert "available" in data[key], (
            f"{key} missing 'available' field"
        )
    sd = data["selfdef_discovery"]
    for field in ("discovered_count", "errors", "collisions",
                  "manifest_dir"):
        assert field in sd, f"selfdef_discovery missing {field!r}"
    ss = data["selfdef_surfaces"]
    for field in ("discovered_count", "errors", "manifest_dir",
                  "total_shipped_surfaces"):
        assert field in ss, f"selfdef_surfaces missing {field!r}"
    sux = data["selfdef_ux"]
    for field in ("discovered_count", "errors", "manifest_dir",
                  "total_pass", "total_fail"):
        assert field in sux, f"selfdef_ux missing {field!r}"
    # R466 selfdef-audit MUST surface count + errors + manifest_dir +
    # total_findings
    sa = data["selfdef_audit"]
    for field in ("discovered_count", "errors", "manifest_dir",
                  "total_findings"):
        assert field in sa, f"selfdef_audit missing {field!r}"


def test_worst_verb_runs():
    result = subprocess.run(
        ["python3", str(CP_PY), "worst", "--limit", "3", "--json"],
        capture_output=True, text=True, timeout=180,
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert "worst" in data
    assert len(data["worst"]) <= 3


def test_module_verb_runs():
    result = subprocess.run(
        ["python3", str(CP_PY), "module", "auth-tier", "--json"],
        capture_output=True, text=True, timeout=180,
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["module"] == "auth-tier"
    for key in ("surface_gap", "doc_gap", "ux_gap"):
        assert key in data


def test_history_verb_runs():
    result = subprocess.run(
        ["python3", str(CP_PY), "history", "--json"],
        capture_output=True, text=True, timeout=10,
        env={**os.environ, "SOVEREIGN_OS_COMPLIANCE_OUT":
             "/tmp/compliance-noexist.jsonl"},
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert "history" in data


def test_snapshot_preview_mode_runs_without_writing():
    """snapshot without --apply MUST preview, NOT write."""
    target = Path("/tmp/compliance-snapshot-test-noexist.jsonl")
    if target.exists():
        target.unlink()
    result = subprocess.run(
        ["python3", str(CP_PY), "snapshot", "--json"],
        capture_output=True, text=True, timeout=180,
        env={**os.environ,
             "SOVEREIGN_OS_COMPLIANCE_OUT": str(target)},
    )
    assert result.returncode == 0, (
        f"snapshot preview failed: stderr={result.stderr[:300]}"
    )
    data = json.loads(result.stdout)
    assert data.get("preview") is True
    assert not target.exists(), (
        "snapshot preview wrote the journal (should not)"
    )


# --- R489 (R458+) — Grafana dashboard surface ---


CP_DASHBOARD_JSON = (
    REPO_ROOT / "docs" / "observability" / "dashboards"
    / "sovereign-os-compliance.json"
)


def test_dashboard_json_exists():
    """R489 — compliance Grafana dashboard surface registers compliance
    as a first-class module + ships the operator-§1g/§1h accountability
    visualization."""
    assert CP_DASHBOARD_JSON.is_file(), (
        f"missing compliance dashboard: {CP_DASHBOARD_JSON}"
    )


def test_dashboard_json_parseable():
    """The dashboard MUST be valid JSON (Grafana refuses invalid JSON
    on import)."""
    data = json.loads(CP_DASHBOARD_JSON.read_text(encoding="utf-8"))
    assert "panels" in data, "dashboard missing panels"
    assert "title" in data and data["title"], "dashboard missing title"
    assert "uid" in data and data["uid"], "dashboard missing uid"


def test_dashboard_references_compliance_metric():
    """At least one panel MUST query sovereign_os_operator_compliance_
    query_total — otherwise the dashboard isn't visualizing the
    operator-§1g/§1h surface."""
    body = CP_DASHBOARD_JSON.read_text(encoding="utf-8")
    assert "sovereign_os_operator_compliance_query_total" in body, (
        "compliance dashboard doesn't reference the Layer B metric"
    )


def test_dashboard_covers_four_instruments():
    """Per R458 4-instrument suite, dashboard MUST reference all 4
    instrument labels (surface-map / doc-coverage / anti-minimization-audit / ux-design-audit)."""
    body = CP_DASHBOARD_JSON.read_text(encoding="utf-8")
    for inst in ("surface-map", "doc-coverage",
                 "anti-minimization-audit", "ux-design-audit"):
        assert inst in body, (
            f"compliance dashboard missing instrument reference: {inst!r}"
        )


def test_dashboard_covers_all_verbs():
    """Dashboard MUST reference all 5 verbs the operator can invoke
    (status / module / worst / history / snapshot)."""
    body = CP_DASHBOARD_JSON.read_text(encoding="utf-8")
    for verb in ("status", "module", "worst", "history", "snapshot"):
        assert verb in body, (
            f"compliance dashboard missing verb reference: {verb!r}"
        )


def test_dashboard_quotes_operator_minimize_rule_verbatim():
    """Dashboard MUST quote the §1g/§1h standing rule verbatim ('We do
    not minimize anything.') — the operator-sacrosanct anti-minimization
    mandate that the compliance aggregator enforces."""
    body = CP_DASHBOARD_JSON.read_text(encoding="utf-8")
    assert "We do not minimize anything" in body, (
        "compliance dashboard missing §1g/§1h verbatim standing rule"
    )


def test_dashboard_listed_in_readme():
    """README.md MUST list the new dashboard (operator-discoverable
    inventory)."""
    readme = (CP_DASHBOARD_JSON.parent / "README.md").read_text(encoding="utf-8")
    assert "sovereign-os-compliance.json" in readme, (
        "dashboards/README.md missing sovereign-os-compliance.json entry"
    )


def test_dashboard_tagged_sovereign_os():
    """Grafana 'sovereign-os' tag MUST be set — operator's dashboard
    folder filter depends on it."""
    data = json.loads(CP_DASHBOARD_JSON.read_text(encoding="utf-8"))
    assert "sovereign-os" in (data.get("tags") or []), (
        "compliance dashboard missing sovereign-os tag"
    )


def test_compliance_registered_in_surface_map():
    """R489 registers compliance as a first-class module in surface-
    map.py MODULE_COVERAGE. After this round it MUST appear with at
    least 3 shipped surfaces (core/cli/dashboard) — at threshold."""
    sm = (REPO_ROOT / "scripts" / "operator" / "surface-map.py").read_text(encoding="utf-8")
    assert '"compliance":' in sm, (
        "surface-map.py MODULE_COVERAGE missing 'compliance' entry"
    )

    # Verify it's at threshold (3 surfaces minimum)
    result = subprocess.run(
        ["python3", str(REPO_ROOT / "scripts" / "operator" / "surface-map.py"),
         "coverage", "--module", "compliance", "--json"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, (
        f"surface-map coverage compliance failed: {result.stderr[:300]}"
    )
    data = json.loads(result.stdout)
    # `coverage --module X --json` returns {"coverage": [{module: X, ...}]}
    entries = data.get("coverage", [data])
    entry = entries[0] if entries else {}
    surface_count = entry.get("surface_count", 0)
    assert surface_count >= 3, (
        f"compliance must be at threshold (>=3 surfaces); got {surface_count}"
    )
