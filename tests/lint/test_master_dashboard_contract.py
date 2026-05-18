"""R452 (E11.M2) — master-dashboard / reverse-proxy aggregator
contract lint.

Per operator §1g verbatim:
  "Maybe there can even be an option to add a reverse proxy nginx or
   such to do a master dashboard which regroup all those of different
   port under a single port and super-dashboard"

7th substantive feature of §1g/§1h Epic E11 arc:
  R446 — E11.M4 Nemotron 3 (partial)
  R447 — E11.M6 bashrc opt-in
  R448 — E11.M5 global-history
  R449 — E11.M8 network-edge
  R450 — E11.M7 auth-tier ladder
  R451 — E11.M9 edge-firewall alternative
  R452 — E11.M2 master-dashboard aggregator
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MD_PY = REPO_ROOT / "scripts" / "operator" / "master-dashboard.py"
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"

EXPECTED_MODES = [
    "per-port-direct",
    "reverse-proxied",
    "alternative-aggregator",
]
EXPECTED_BACKENDS = ["nginx", "caddy", "traefik"]


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# --- Structural ---


def test_master_dashboard_script_exists():
    assert MD_PY.is_file(), f"missing {MD_PY}"


def test_master_dashboard_executable():
    assert os.access(MD_PY, os.X_OK), f"{MD_PY} not executable"


def test_python3_shebang():
    body = _read(MD_PY)
    assert body.startswith("#!/usr/bin/env python3")


def test_documents_e11_m2_origin():
    body = _read(MD_PY)
    assert "E11.M2" in body and "§1g" in body


def test_quotes_operator_verbatim_1g_phrase():
    """§1g verbatim reverse-proxy phrase MUST appear."""
    body = _read(MD_PY)
    flat = re.sub(r"\s+", " ", body)
    for phrase in (
        "reverse proxy nginx",
        "master dashboard",
        "single port",
        "super-dashboard",
    ):
        assert phrase in flat, (
            f"missing operator §1g verbatim phrase {phrase!r}"
        )


# --- Operator-named modes (3) ---


def test_operator_named_modes_present():
    body = _read(MD_PY)
    assert "OPERATOR_NAMED_MODES" in body
    for m in EXPECTED_MODES:
        assert f'"{m}"' in body, f"missing operator-named mode {m!r}"


# --- Supported backends (3) ---


def test_supported_backends_present():
    body = _read(MD_PY)
    assert "SUPPORTED_BACKENDS" in body
    for b in EXPECTED_BACKENDS:
        assert f'"{b}"' in body, f"missing backend {b!r}"


def test_renderer_per_backend():
    """Every backend MUST have a dedicated render_<backend> function."""
    body = _read(MD_PY)
    for b in EXPECTED_BACKENDS:
        assert f"def render_{b}(" in body, (
            f"missing render_{b}() function"
        )


# --- Dashboard routes table ---


def test_dashboard_routes_table_defined():
    body = _read(MD_PY)
    assert "DASHBOARD_ROUTES" in body, "missing DASHBOARD_ROUTES table"


def test_routes_include_trinity_tiers():
    body = _read(MD_PY)
    for name in ("trinity-pulse", "trinity-logic-engine",
                 "trinity-oracle-core"):
        assert f'"{name}"' in body, (
            f"DASHBOARD_ROUTES missing Trinity tier {name!r}"
        )


def test_routes_include_router():
    body = _read(MD_PY)
    assert '"router"' in body, "DASHBOARD_ROUTES missing router"


def test_each_route_has_port():
    body = _read(MD_PY)
    n = body.count('"port":')
    assert n >= 6, f"only {n} 'port' fields (expected ≥6 dashboards)"


def test_each_route_has_subpath():
    body = _read(MD_PY)
    n = body.count('"subpath":')
    assert n >= 6, f"only {n} 'subpath' fields (expected ≥6)"


def test_each_route_has_label():
    body = _read(MD_PY)
    n = body.count('"label":')
    assert n >= 6, f"only {n} 'label' fields (expected ≥6)"


# --- CLI surface (5 verbs) ---


def test_supports_list_verb():
    body = _read(MD_PY)
    assert '"list"' in body


def test_supports_routes_verb():
    body = _read(MD_PY)
    assert '"routes"' in body


def test_supports_collisions_verb():
    body = _read(MD_PY)
    assert '"collisions"' in body


def test_supports_render_verb():
    body = _read(MD_PY)
    assert '"render"' in body


def test_supports_health_verb():
    body = _read(MD_PY)
    assert '"health"' in body


def test_render_has_triple_gate():
    """`render` MUST require --apply + --confirm-render."""
    body = _read(MD_PY)
    assert "--apply" in body, "render missing --apply gate"
    assert "--confirm-render" in body, (
        "render missing --confirm-render gate"
    )


def test_render_blocks_on_collisions():
    """render MUST refuse when collisions detected."""
    body = _read(MD_PY)
    assert "blocked-collisions" in body, (
        "render doesn't block on collisions"
    )


def test_json_and_human_format_flags():
    body = _read(MD_PY)
    assert "--json" in body and "--human" in body


# --- DRY-RUN + env overlay ---


def test_supports_dry_run():
    body = _read(MD_PY)
    assert "SOVEREIGN_OS_DRY_RUN" in body


def test_supports_dedicated_dry_run_env():
    body = _read(MD_PY)
    assert "SOVEREIGN_OS_MASTER_DASHBOARD_DRY_RUN" in body


def test_aggregator_port_overridable():
    body = _read(MD_PY)
    assert "SOVEREIGN_OS_MASTER_DASHBOARD_PORT" in body


def test_output_dir_overridable():
    body = _read(MD_PY)
    assert "SOVEREIGN_OS_MASTER_DASHBOARD_OUT" in body


# --- Metric ---


def test_emits_layer_b_metric():
    body = _read(MD_PY)
    assert "sovereign_os_operator_master_dashboard_query_total" in body


# --- osctl integration ---


def test_osctl_dispatches_master_dashboard():
    body = _read(OSCTL)
    assert "master-dashboard)" in body, (
        "osctl missing master-dashboard) dispatcher"
    )
    assert "master-dashboard.py" in body, (
        "osctl dispatcher doesn't reference master-dashboard.py"
    )


def test_osctl_help_documents_master_dashboard_verbs():
    body = _read(OSCTL)
    for sub in (
        "master-dashboard list",
        "master-dashboard routes",
        "master-dashboard collisions",
        "master-dashboard render",
        "master-dashboard health",
    ):
        assert sub in body, f"osctl help missing {sub!r}"


def test_osctl_help_references_e11_m2():
    body = _read(OSCTL)
    assert "E11.M2" in body


# --- Smoke tests ---


def test_list_verb_runs():
    result = subprocess.run(
        ["python3", str(MD_PY), "list", "--json"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, (
        f"list --json failed: stderr={result.stderr[:200]}"
    )
    data = json.loads(result.stdout)
    assert "dashboards" in data
    assert data["count"] >= 6, (
        f"expected ≥6 dashboards, got {data['count']}"
    )


def test_routes_verb_runs():
    result = subprocess.run(
        ["python3", str(MD_PY), "routes", "--json"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, (
        f"routes --json failed: stderr={result.stderr[:200]}"
    )
    data = json.loads(result.stdout)
    assert "routes" in data
    assert data["mode"] in EXPECTED_MODES


def test_collisions_verb_runs_clean():
    """Default DASHBOARD_ROUTES MUST be collision-free."""
    result = subprocess.run(
        ["python3", str(MD_PY), "collisions", "--json"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, (
        f"collisions failed: stderr={result.stderr[:200]}"
    )
    data = json.loads(result.stdout)
    assert data["has_collisions"] is False, (
        f"default routes have collisions: {data}"
    )


def test_render_nginx_preview_runs():
    """render without --apply MUST preview, NOT write."""
    result = subprocess.run(
        ["python3", str(MD_PY), "render", "--backend", "nginx",
         "--json"],
        capture_output=True, text=True, timeout=10,
        env={**os.environ, "SOVEREIGN_OS_MASTER_DASHBOARD_OUT":
             "/tmp/md-test-noexist"},
    )
    assert result.returncode == 0, (
        f"render preview failed: stderr={result.stderr[:200]}"
    )
    data = json.loads(result.stdout)
    assert data.get("preview") is True
    assert "config_preview" in data
    assert not Path("/tmp/md-test-noexist").exists(), (
        "render preview wrote the output dir (should not)"
    )


def test_render_unknown_backend_fails():
    result = subprocess.run(
        ["python3", str(MD_PY), "render", "--backend", "bogus"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode != 0, (
        "render with unknown backend should fail"
    )


def test_health_verb_runs():
    result = subprocess.run(
        ["python3", str(MD_PY), "health", "--json"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, (
        f"health failed: stderr={result.stderr[:200]}"
    )
    data = json.loads(result.stdout)
    assert "probes" in data
    assert data["total_count"] >= 6
