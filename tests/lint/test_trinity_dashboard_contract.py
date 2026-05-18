"""R494 (R290-R299+ E5) — Trinity Grafana dashboard contract lint.

Closes the trinity dashboard:FUTURE waiver and extends trinity surface-
map registration to 5 surfaces (core/cli/api/service/dashboard).

Per operator §1g verbatim (sacrosanct):

  "We do not minimize anything."

The Trinity is the operator-§1g 3-tier local inference stack:
  pulse        (8081, fast tier — 7B-class, default first-touch)
  logic-engine (8082, reasoning tier — chain-of-thought)
  oracle-core  (8083, deep tier — frontier-class)
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TRINITY_DASHBOARD_JSON = (
    REPO_ROOT / "docs" / "observability" / "dashboards"
    / "sovereign-os-trinity.json"
)


def test_dashboard_json_exists():
    assert TRINITY_DASHBOARD_JSON.is_file(), (
        f"missing trinity dashboard: {TRINITY_DASHBOARD_JSON}"
    )


def test_dashboard_json_parseable():
    data = json.loads(TRINITY_DASHBOARD_JSON.read_text(encoding="utf-8"))
    assert "panels" in data
    assert data.get("title")
    assert data.get("uid")


def test_dashboard_references_inference_route_metric():
    body = TRINITY_DASHBOARD_JSON.read_text(encoding="utf-8")
    assert "sovereign_os_inference_route_total" in body, (
        "trinity dashboard doesn't reference inference route metric"
    )


def test_dashboard_references_three_tiers():
    """All 3 Trinity tiers MUST appear (pulse / logic_engine / oracle_core)
    — operator-§17.1 sacrosanct identity."""
    body = TRINITY_DASHBOARD_JSON.read_text(encoding="utf-8")
    for tier in ("pulse", "logic_engine", "oracle_core"):
        assert tier in body, (
            f"trinity dashboard missing tier reference: {tier!r}"
        )


def test_dashboard_references_operator_named_tiers():
    """The operator-named module names (Pulse / Logic Engine / Oracle
    Core, dashed forms allowed) MUST appear — load-bearing identity."""
    body = TRINITY_DASHBOARD_JSON.read_text(encoding="utf-8")
    for name in ("pulse", "logic-engine", "oracle-core"):
        assert name in body, (
            f"trinity dashboard missing operator-named module: {name!r}"
        )


def test_dashboard_references_backend_lifecycle_metric():
    body = TRINITY_DASHBOARD_JSON.read_text(encoding="utf-8")
    assert "sovereign_os_inference_backend_start_total" in body, (
        "trinity dashboard missing backend_start_total — lifecycle "
        "visibility required"
    )


def test_dashboard_quotes_operator_standing_rule_verbatim():
    body = TRINITY_DASHBOARD_JSON.read_text(encoding="utf-8")
    assert "We do not minimize anything" in body, (
        "trinity dashboard missing §1g verbatim standing rule"
    )


def test_dashboard_listed_in_readme():
    readme = (TRINITY_DASHBOARD_JSON.parent / "README.md").read_text(encoding="utf-8")
    assert "sovereign-os-trinity.json" in readme, (
        "dashboards/README.md missing sovereign-os-trinity.json entry"
    )


def test_dashboard_tagged_sovereign_os():
    data = json.loads(TRINITY_DASHBOARD_JSON.read_text(encoding="utf-8"))
    tags = data.get("tags") or []
    assert "sovereign-os" in tags, (
        "trinity dashboard missing sovereign-os tag"
    )
    assert "trinity" in tags, (
        "trinity dashboard missing trinity tag"
    )


def test_trinity_surface_map_extended_to_dashboard():
    """R494 extends trinity surface-map registration to 5 surfaces —
    dashboard MUST be in the shipped surfaces list, NOT a FUTURE
    waiver."""
    sm_path = REPO_ROOT / "scripts" / "operator" / "surface-map.py"
    result = subprocess.run(
        ["python3", str(sm_path), "coverage", "--module",
         "trinity", "--json"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, (
        f"surface-map coverage trinity failed: {result.stderr[:300]}"
    )
    data = json.loads(result.stdout)
    entries = data.get("coverage", [data])
    entry = entries[0] if entries else {}
    surface_count = entry.get("surface_count", 0)
    assert surface_count >= 5, (
        f"trinity must be at >=5 surfaces post-R494; got {surface_count}"
    )
    matrix = entry.get("matrix", [])
    dashboard_row = next(
        (r for r in matrix if r.get("surface") == "dashboard"), None
    )
    assert dashboard_row is not None, (
        "trinity coverage matrix missing 'dashboard' row"
    )
    assert dashboard_row.get("state") == "shipped", (
        f"trinity dashboard surface must be shipped (not waived); "
        f"got {dashboard_row}"
    )
