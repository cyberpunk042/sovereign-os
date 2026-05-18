"""R453 (E11.M3) — multi-surface delivery contract lint.

Per operator §1g verbatim:
  "Everything is not just core, not just cli, not just TUI, not just
   API, not just tool and MCP but also Dashboards and Web Apps and
   Services"

8th substantive feature of §1g/§1h Epic E11 arc:
  R446 — E11.M4 Nemotron 3 (partial)
  R447 — E11.M6 bashrc opt-in
  R448 — E11.M5 global-history
  R449 — E11.M8 network-edge
  R450 — E11.M7 auth-tier ladder
  R451 — E11.M9 edge-firewall alternative
  R452 — E11.M2 master-dashboard aggregator
  R453 — E11.M3 multi-surface delivery contract
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SM_PY = REPO_ROOT / "scripts" / "operator" / "surface-map.py"
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"

# §1g verbatim 8-surface taxonomy (ORDER preserved)
EXPECTED_SURFACES = [
    "core",
    "cli",
    "tui",
    "api",
    "mcp",
    "dashboard",
    "webapp",
    "service",
]


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# --- Structural ---


def test_surface_map_script_exists():
    assert SM_PY.is_file(), f"missing {SM_PY}"


def test_surface_map_executable():
    assert os.access(SM_PY, os.X_OK), f"{SM_PY} not executable"


def test_python3_shebang():
    body = _read(SM_PY)
    assert body.startswith("#!/usr/bin/env python3")


def test_documents_e11_m3_origin():
    body = _read(SM_PY)
    assert "E11.M3" in body and "§1g" in body


def test_quotes_operator_verbatim_1g_phrase():
    """§1g verbatim 8-surface taxonomy phrases MUST appear."""
    body = _read(SM_PY)
    flat = re.sub(r"\s+", " ", body)
    for phrase in (
        "not just core",
        "not just cli",
        "not just TUI",
        "not just API",
        "not just tool and MCP",
        "Dashboards and Web Apps and Services",
    ):
        assert phrase in flat, (
            f"missing operator §1g verbatim phrase {phrase!r}"
        )


# --- 8-surface taxonomy ---


def test_surfaces_catalog_defined():
    body = _read(SM_PY)
    assert "SURFACES" in body, "missing SURFACES catalog"
    for s in EXPECTED_SURFACES:
        assert f'"{s}"' in body, f"SURFACES missing {s!r}"


def test_each_surface_has_operator_named_field():
    body = _read(SM_PY)
    n = body.count('"operator_named":')
    assert n >= 8, (
        f"only {n} 'operator_named' fields (expected ≥8, one per surface)"
    )


def test_each_surface_has_position_field():
    body = _read(SM_PY)
    # §1g_position field marks the order in the operator §1g sentence
    n = body.count("§1g_position")
    assert n >= 9, (  # 1 in docstring + 8 in entries
        f"only {n} '§1g_position' references (expected ≥9)"
    )


# --- Module coverage table ---


def test_module_coverage_table_defined():
    body = _read(SM_PY)
    assert "MODULE_COVERAGE" in body, "missing MODULE_COVERAGE table"


def test_coverage_includes_recent_e11_modules():
    """Recent E11.Mx modules MUST be tracked."""
    body = _read(SM_PY)
    for m in ("auth-tier", "edge-firewall", "network-edge",
              "master-dashboard", "global-history", "bashrc"):
        assert f'"{m}":' in body, (
            f"MODULE_COVERAGE missing E11 module {m!r}"
        )


def test_each_module_has_shipped_in_field():
    body = _read(SM_PY)
    n = body.count('"shipped_in":')
    assert n >= 8, f"only {n} 'shipped_in' fields (expected ≥8 modules)"


def test_each_module_has_waivers_field():
    body = _read(SM_PY)
    n = body.count('"waivers":')
    assert n >= 8, f"only {n} 'waivers' fields (expected ≥8 modules)"


# --- CLI surface (5 verbs) ---


def test_supports_surfaces_verb():
    body = _read(SM_PY)
    assert '"surfaces"' in body


def test_supports_modules_verb():
    body = _read(SM_PY)
    assert '"modules"' in body


def test_supports_coverage_verb():
    body = _read(SM_PY)
    assert '"coverage"' in body


def test_supports_gaps_verb():
    body = _read(SM_PY)
    assert '"gaps"' in body


def test_supports_waivers_verb():
    body = _read(SM_PY)
    assert '"waivers"' in body


def test_json_and_human_format_flags():
    body = _read(SM_PY)
    assert "--json" in body and "--human" in body


def test_threshold_env_overridable():
    body = _read(SM_PY)
    assert "SOVEREIGN_OS_SURFACE_THRESHOLD" in body


# --- DRY-RUN + env overlay ---


def test_supports_dry_run():
    body = _read(SM_PY)
    assert "SOVEREIGN_OS_DRY_RUN" in body


def test_supports_dedicated_dry_run_env():
    body = _read(SM_PY)
    assert "SOVEREIGN_OS_SURFACE_MAP_DRY_RUN" in body


# --- Metric ---


def test_emits_layer_b_metric():
    body = _read(SM_PY)
    assert "sovereign_os_operator_surface_map_query_total" in body


# --- osctl integration ---


def test_osctl_dispatches_surface_map():
    body = _read(OSCTL)
    assert "surface-map)" in body, (
        "osctl missing surface-map) dispatcher"
    )
    assert "surface-map.py" in body, (
        "osctl dispatcher doesn't reference surface-map.py"
    )


def test_osctl_help_documents_surface_map_verbs():
    body = _read(OSCTL)
    for sub in (
        "surface-map surfaces",
        "surface-map modules",
        "surface-map coverage",
        "surface-map gaps",
        "surface-map waivers",
    ):
        assert sub in body, f"osctl help missing {sub!r}"


def test_osctl_help_references_e11_m3():
    body = _read(OSCTL)
    assert "E11.M3" in body


# --- Smoke tests ---


def test_surfaces_verb_returns_eight():
    """surfaces --json MUST return exactly 8 operator-named surfaces
    in §1g verbatim order."""
    result = subprocess.run(
        ["python3", str(SM_PY), "surfaces", "--json"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, (
        f"surfaces failed: stderr={result.stderr[:200]}"
    )
    data = json.loads(result.stdout)
    assert data["count"] == 8, f"expected 8 surfaces, got {data['count']}"
    ids = [s["id"] for s in data["surfaces"]]
    assert ids == EXPECTED_SURFACES, (
        f"surface order drift: {ids} vs {EXPECTED_SURFACES}"
    )


def test_modules_verb_runs():
    result = subprocess.run(
        ["python3", str(SM_PY), "modules", "--json"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["count"] >= 6


def test_coverage_verb_full_matrix():
    """coverage on a known module MUST return an 8-row matrix."""
    result = subprocess.run(
        ["python3", str(SM_PY), "coverage", "--module", "auth-tier",
         "--json"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    rows = data["coverage"]
    assert len(rows) == 1
    matrix = rows[0]["matrix"]
    assert len(matrix) == 8, f"expected 8-row matrix, got {len(matrix)}"
    states = {e["state"] for e in matrix}
    assert states <= {"shipped", "waived", "gap"}, (
        f"unexpected states: {states}"
    )


def test_gaps_verb_with_threshold():
    result = subprocess.run(
        ["python3", str(SM_PY), "gaps", "--threshold", "1", "--json"],
        capture_output=True, text=True, timeout=10,
    )
    # threshold=1 means no gaps (every tracked module ships ≥1)
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["count"] == 0


def test_gaps_verb_exits_nonzero_when_below():
    """gaps with high threshold MUST exit 2 (operator-discoverable
    failure mode)."""
    result = subprocess.run(
        ["python3", str(SM_PY), "gaps", "--threshold", "8", "--json"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 2


def test_coverage_unknown_module_fails():
    result = subprocess.run(
        ["python3", str(SM_PY), "coverage", "--module", "bogus"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode != 0


def test_waivers_verb_runs():
    result = subprocess.run(
        ["python3", str(SM_PY), "waivers", "--json"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert "waivers" in data
    assert data["count"] >= 10  # many waivers across modules
