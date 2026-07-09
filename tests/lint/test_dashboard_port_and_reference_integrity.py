"""Static referential-integrity guard for the operator dashboard surface.

Caught 2026-07-09: a merge landed several panels on ports already bound by other
panels (flash/ups vs lm-status/cpu-features, hardware-pressure vs compliance,
ux-design-audit vs the hub). The existing `test_panel_collision_guard.py` only
checks a RUNTIME workaround in panel.sh (don't start a data API on the hub port);
it can't catch two *data* APIs sharing a port, so panel.sh started conflicting
daemons and panels answered with the wrong data. This is the STATIC guard:

  1. No two systemd units bind the same Environment=*PORT=.
  2. DASHBOARD_ROUTES (the canonical registry) has unique ports + subpaths.
     (Its `port` is the UPSTREAM service the panel reflects — e.g. router→8080
     the live inference router, grafana→3000 — NOT the dashboard-api port, so it
     is intentionally not required to equal the sovereign-<slug>-api unit port.)
  3. Every dashboard-catalog path is unique + absolute; every `api:` resolves to
     a real systemd unit (so the master-dashboard registry never shows a panel as
     unreachable because its api name has no daemon).
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
UNITS_DIR = REPO / "systemd" / "system"
CATALOG = REPO / "config" / "dashboard-catalog.yaml"


def _unit_ports() -> dict[int, list[str]]:
    """port -> [unit stems] for every unit declaring Environment=*PORT=."""
    ports: dict[int, list[str]] = {}
    for f in sorted(UNITS_DIR.glob("*.service")):
        m = re.search(r"Environment=[A-Z_]*PORT=(\d+)", f.read_text(encoding="utf-8"))
        if m:
            ports.setdefault(int(m.group(1)), []).append(f.stem)
    return ports


def _unit_stems() -> set[str]:
    return {f.stem for f in UNITS_DIR.glob("*.service")}


def test_no_duplicate_ports_across_units():
    collisions = {p: u for p, u in _unit_ports().items() if len(u) > 1}
    assert not collisions, (
        "systemd units binding the SAME port (panel.sh will start conflicting "
        "daemons; one panel gets the wrong data API):\n"
        + "\n".join(f"  port {p} → {', '.join(sorted(u))}" for p, u in sorted(collisions.items()))
        + "\n\nGive each a unique Environment=*PORT= (free slots exist in 8126-8135)."
    )


def _dashboard_routes() -> dict:
    spec = importlib.util.spec_from_file_location(
        "md", REPO / "scripts" / "operator" / "master-dashboard.py"
    )
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)  # type: ignore
    return m.DASHBOARD_ROUTES


def test_dashboard_routes_internally_unique():
    """The canonical registry must not route two panels to the same upstream
    port or the same subpath (the /collisions endpoint proves this to operators;
    this locks it statically)."""
    routes = _dashboard_routes()
    ports: dict[int, list[str]] = {}
    subs: dict[str, list[str]] = {}
    for slug, r in routes.items():
        if r.get("port") is not None:
            ports.setdefault(r["port"], []).append(slug)
        if r.get("subpath"):
            subs.setdefault(r["subpath"], []).append(slug)
    port_coll = {p: s for p, s in ports.items() if len(s) > 1}
    sub_coll = {s: sl for s, sl in subs.items() if len(sl) > 1}
    assert not port_coll, f"DASHBOARD_ROUTES upstream-port collisions: {port_coll}"
    assert not sub_coll, f"DASHBOARD_ROUTES subpath collisions: {sub_coll}"


def test_catalog_paths_unique_and_apis_resolve():
    import yaml
    cat = yaml.safe_load(CATALOG.read_text(encoding="utf-8"))
    units = _unit_stems()
    paths: dict[str, list[str]] = {}
    bad_abs, bad_api = [], []
    for e in cat.get("dashboards", []):
        slug, path, api = e.get("slug"), e.get("path"), e.get("api")
        if path:
            if not path.startswith("/"):
                bad_abs.append(f"{slug}: path {path!r} is not absolute")
            paths.setdefault(path, []).append(slug)
        # `api:` (when present) must name a real systemd unit — else the
        # master-dashboard registry marks the panel unreachable. Sharing one
        # api across sibling slugs (e.g. the D-12 split) is allowed.
        if api and api not in units:
            bad_api.append(f"{slug}: api {api!r} has no systemd unit")
    path_coll = {p: s for p, s in paths.items() if len(s) > 1}
    assert not path_coll, f"catalog PATH collisions (two panels, same URL): {path_coll}"
    assert not bad_abs, "non-absolute catalog paths:\n  " + "\n  ".join(bad_abs)
    assert not bad_api, "catalog api names with no daemon:\n  " + "\n  ".join(bad_api)
