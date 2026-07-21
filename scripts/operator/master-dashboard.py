#!/usr/bin/env python3
"""scripts/operator/master-dashboard.py — R452 (E11.M2).

Operator §1g verbatim:
  "Maybe there can even be an option to add a reverse proxy nginx or
   such to do a master dashboard which regroup all those of different
   port under a single port and super-dashboard"

Workstation-side master-dashboard / reverse-proxy aggregator. Renders
nginx (or alternative) config that consolidates per-port dashboards
under a single super-dashboard port at operator-named subpaths.

Sister surface to R450 auth-tier (which owns the dashboard REGISTRY).
This module owns the ROUTING SURFACE — it reads the same registry and
emits a reverse-proxy config that fronts every registered dashboard.

Operator-named aggregator modes (3 options, per operator §1g):
  1. per-port-direct        Operator hits each dashboard on its own
                            port directly (no aggregator). Default.
                            Lowest complexity; LAN-only.
  2. reverse-proxied        nginx (or caddy/traefik) fronts all
                            dashboards under a single super-port.
                            Operator §1g "reverse proxy nginx or such".
  3. alternative-aggregator caddy / traefik / haproxy — operator-
                            named alternatives to nginx for the same
                            aggregation role.

CLI:
  master-dashboard.py list [--json|--human]
      Enumerate dashboards eligible for aggregation (read from
      auth-tier registry).

  master-dashboard.py routes [--mode <mode>] [--json|--human]
      Show the route table the aggregator would emit
      (slug → upstream port → subpath).

  master-dashboard.py collisions [--json|--human]
      Detect slug/port/subpath collisions BEFORE rendering. Operator-
      discoverable; prevents broken aggregator from ever shipping.

  master-dashboard.py render --backend <nginx|caddy|traefik>
                             [--apply --confirm-render]
                             [--json|--human]
      Render the reverse-proxy config to /etc/sovereign-os/master-
      dashboard/{backend}.conf. Triple-gated (--apply +
      --confirm-render). Without gates → preview-only.

  master-dashboard.py health [--json|--human]
      Probe each upstream dashboard's :PORT/healthz (or :PORT/) and
      report aggregator-reachability per dashboard.

Exit codes:
  0 ok
  1 unknown subcommand / unknown backend / unknown mode
  2 render blocked (gates missing) or collision detected
  3 render preview only (no --apply)

Layer B metric (SDD-016):
  sovereign_os_operator_master_dashboard_query_total{verb,backend,result}

Operator-environment env vars:
  SOVEREIGN_OS_MASTER_DASHBOARD_DRY_RUN  Logs intent; no file writes.
  SOVEREIGN_OS_DRY_RUN                   Same effect (sovereign-wide).
  SOVEREIGN_OS_MASTER_DASHBOARD_PORT     Aggregator listen port
                                          (default: 8000).
  SOVEREIGN_OS_MASTER_DASHBOARD_OUT      Override render output dir
                                          (default:
                                           /etc/sovereign-os/master-dashboard).
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

DRY_RUN = (
    os.environ.get("SOVEREIGN_OS_DRY_RUN") == "1"
    or os.environ.get("SOVEREIGN_OS_MASTER_DASHBOARD_DRY_RUN") == "1"
)
METRICS_DIR = Path(
    os.environ.get(
        "SOVEREIGN_OS_TEXTFILE_DIR",
        "/var/lib/prometheus/node-exporter",
    )
)
AGGREGATOR_PORT = int(
    os.environ.get("SOVEREIGN_OS_MASTER_DASHBOARD_PORT", "8000")
)
OUTPUT_DIR = Path(
    os.environ.get(
        "SOVEREIGN_OS_MASTER_DASHBOARD_OUT",
        "/etc/sovereign-os/master-dashboard",
    )
)

# Operator-named modes (§1g verbatim — 3 options)
OPERATOR_NAMED_MODES = [
    "per-port-direct",
    "reverse-proxied",
    "alternative-aggregator",
]

# Operator-named backends — "reverse proxy nginx or such" → such = caddy/traefik
SUPPORTED_BACKENDS = ["nginx", "caddy", "traefik"]

# Per-dashboard routing table (sister to auth-tier DEFAULT_REGISTRY).
# slug → {port, healthz_path, subpath, label, source_repo}
#
# F-2026-072: this table used to be a 26-entry hand-maintained dict that went
# stale against the 55-panel reality. It is now GENERATED into
# config/dashboard-routes.yaml by scripts/operator/gen-dashboard-routes.py
# (joining config/dashboard-catalog.yaml with each panel API's own listen port)
# and CI-locked by tests/lint/test_dashboard_routes.py. We load it here with a
# dependency-free parser (the generated flow-map is a fixed single-line shape),
# so the aggregator never fails to route because PyYAML is absent.
ROUTES_FILE = Path(__file__).resolve().parent.parent.parent / "config" / "dashboard-routes.yaml"


def _load_routes() -> dict:
    """Parse config/dashboard-routes.yaml → {slug: {port, healthz_path,
    subpath, label, source_repo}}. Regex-based (no PyYAML dependency): the file
    is generator-emitted with a fixed `- {slug: …, port: …, …}` shape per line,
    under the `routes:` key (the `static_only:`/`skipped:` blocks are operator-
    visibility metadata, not proxied, and are ignored here)."""
    import re
    routes: dict[str, dict] = {}
    try:
        text = ROUTES_FILE.read_text(encoding="utf-8")
    except OSError:
        return routes
    # Only the `routes:` section (stop at the next top-level `static_only:` key).
    start = text.find("\nroutes:")
    if start == -1:
        return routes
    section = text[start:]
    end = section.find("\nstatic_only:")
    if end != -1:
        section = section[:end]
    line_re = re.compile(
        r'- \{slug: (?P<slug>[^,]+), port: (?P<port>\d+), '
        r'healthz_path: "(?P<healthz>[^"]*)", subpath: "(?P<subpath>[^"]*)", '
        r'source_repo: (?P<repo>[^,]+), label: "(?P<label>[^"]*)"\}'
    )
    for m in line_re.finditer(section):
        routes[m.group("slug")] = {
            "port": int(m.group("port")),
            "healthz_path": m.group("healthz"),
            "subpath": m.group("subpath"),
            "label": m.group("label"),
            "source_repo": m.group("repo"),
        }
    return routes


# Fallback infra set — the always-on non-panel upstreams. If the generated table
# is unreadable (deleted / corrupt), the aggregator still fronts the core
# services rather than serving an empty route table. The Trinity tiers + router
# daemon are the contract-required minimum (test_master_dashboard_contract.py).
_FALLBACK_ROUTES = {
    "trinity-pulse": {"port": 8081, "healthz_path": "/v1/models",
                      "subpath": "/pulse/", "label": "Trinity Pulse (bitnet.cpp HTTP)",
                      "source_repo": "sovereign-os"},
    "trinity-logic-engine": {"port": 8082, "healthz_path": "/v1/models",
                             "subpath": "/logic/", "label": "Trinity Logic Engine (vLLM)",
                             "source_repo": "sovereign-os"},
    "trinity-oracle-core": {"port": 8083, "healthz_path": "/v1/models",
                            "subpath": "/oracle/", "label": "Trinity Oracle Core (vLLM Blackwell)",
                            "source_repo": "sovereign-os"},
    "router-engine": {"port": 8080, "healthz_path": "/healthz",
                      "subpath": "/router-engine/", "label": "SDD-011 Deterministic Router daemon",
                      "source_repo": "sovereign-os"},
}

DASHBOARD_ROUTES = _load_routes() or dict(_FALLBACK_ROUTES)

KNOWN_SLUGS = list(DASHBOARD_ROUTES.keys())

# R460 (selfdef-cross-repo): per the selfdef-side
# SD-R-DASHBOARD-MANIFEST-1 crate, every selfdef module exposing a
# dashboard ships a TOML manifest at /etc/selfdef/dashboards/<m>.toml.
# This dir is the operator-overridable directory the discover verb
# scans to fold cross-repo dashboards into the aggregator route table.
SELFDEF_MANIFEST_DIR = Path(
    os.environ.get(
        "SOVEREIGN_OS_SELFDEF_MANIFEST_DIR",
        "/etc/selfdef/dashboards",
    )
)


# HELP sovereign_os_operator_master_dashboard_query_total master-dashboard
# operator-verb call count (verb, backend, result).
# TYPE sovereign_os_operator_master_dashboard_query_total counter
METRIC_NAME = "sovereign_os_operator_master_dashboard_query_total"


def _emit_metric(verb: str, backend: str, result: str) -> None:
    """Best-effort SDD-016 metric write; never raises.

    Literal metric name in HELP/TYPE comments above (R443 metric-
    inventory-lockstep contract)."""
    if DRY_RUN:
        sys.stderr.write(
            f"  would emit: {METRIC_NAME}"
            f'{{verb="{verb}",backend="{backend}",result="{result}"}} 1\n'
        )
        return
    try:
        METRICS_DIR.mkdir(parents=True, exist_ok=True)
        prom = METRICS_DIR / "sovereign-os-operator-master-dashboard.prom"
        line = (
            f"{METRIC_NAME}"
            f'{{verb="{verb}",backend="{backend}",result="{result}"}} 1\n'
        )
        tmp = prom.with_suffix(".prom.tmp")
        tmp.write_text(line)
        tmp.replace(prom)
    except OSError:
        pass


# --- Collision detection ---


# F-2026-070: the unified sovereign-networking-api intentionally fronts three
# concern-distinct panels (each its own subpath) from ONE upstream port — a
# reverse-proxy fan-in (many subpaths → one backend), not a real collision.
# A shared port among ONLY these slugs is allowed; any other shared port, or a
# shared subpath, is still a genuine collision. Mirrors the exemption in
# tests/lint/test_dashboard_routes.py::test_routes_are_collision_free.
# Design is documented (not a surprise) in docs/src/ops/cockpit.md
# § "Routing — how panels reach their backends (and why some share a port)".
# Adding a new unified group is a DELIBERATE edit here (never a silent relax).
_UNIFIED_SHARED_PORT_SLUGS = frozenset({"network-edge", "edge-firewall", "d-12-networking"})


def detect_collisions() -> dict:
    """Detect port/subpath/slug collisions in DASHBOARD_ROUTES.

    Operator-discoverable: aggregator fails IF two dashboards collide.
    Surfacing this BEFORE render is the §1g UX bar.
    """
    port_to_slugs: dict[int, list[str]] = {}
    subpath_to_slugs: dict[str, list[str]] = {}
    for slug, route in DASHBOARD_ROUTES.items():
        port_to_slugs.setdefault(route["port"], []).append(slug)
        subpath_to_slugs.setdefault(route["subpath"], []).append(slug)
    port_collisions = {
        p: slugs for p, slugs in port_to_slugs.items()
        if len(slugs) > 1 and not set(slugs).issubset(_UNIFIED_SHARED_PORT_SLUGS)
    }
    subpath_collisions = {
        s: slugs for s, slugs in subpath_to_slugs.items() if len(slugs) > 1
    }
    # Intentional shared-port fan-in (declared unified group) — surfaced, not
    # hidden, so an operator running `collisions` SEES the shared port is by
    # design (see docs/src/ops/cockpit.md § Routing). Distinct from a collision.
    intentional_shared_ports = {
        p: slugs for p, slugs in port_to_slugs.items()
        if len(slugs) > 1 and set(slugs).issubset(_UNIFIED_SHARED_PORT_SLUGS)
    }
    return {
        "port_collisions": port_collisions,
        "subpath_collisions": subpath_collisions,
        "intentional_shared_ports": intentional_shared_ports,
        "has_collisions": bool(port_collisions or subpath_collisions),
    }


# --- Health probing ---


def probe_dashboard(slug: str, route: dict, timeout: float = 1.0) -> dict:
    """TCP-connect probe to dashboard upstream port. Never raises."""
    host = "127.0.0.1"
    port = route["port"]
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect((host, port))
            return {
                "slug": slug,
                "port": port,
                "reachable": True,
                "tier": "tcp-open",
            }
    except (socket.timeout, ConnectionRefusedError, OSError):
        return {
            "slug": slug,
            "port": port,
            "reachable": False,
            "tier": "tcp-closed",
        }


# --- Config rendering (per backend) ---


def render_nginx(routes: dict) -> str:
    """Render an nginx reverse-proxy config consolidating routes."""
    lines = [
        "# Generated by sovereign-osctl master-dashboard render",
        "# R452 (E11.M2): operator §1g reverse-proxy aggregator",
        "# DO NOT EDIT — re-run `sovereign-osctl master-dashboard render`",
        "",
        "server {",
        f"    listen {AGGREGATOR_PORT};",
        "    server_name _;",
        "",
        "    # Operator §1g: 'master dashboard which regroup all those of",
        "    # different port under a single port and super-dashboard'",
        "",
    ]
    for slug, route in routes.items():
        subpath = route["subpath"]
        port = route["port"]
        label = route["label"]
        lines.extend([
            f"    # {label} ({slug})",
            f"    location {subpath} {{",
            f"        proxy_pass http://127.0.0.1:{port}/;",
            "        proxy_set_header Host $host;",
            "        proxy_set_header X-Real-IP $remote_addr;",
            "        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;",
            "        proxy_set_header X-Forwarded-Proto $scheme;",
            "    }",
            "",
        ])
    lines.extend([
        "    # Root: index page — count only (each dashboard has its own",
        "    # location block above; enumerating 50+ subpaths here is noise).",
        "    location = / {",
        f"        return 200 'sovereign-os master-dashboard — {len(routes)} dashboards aggregated under :{AGGREGATOR_PORT}';",
        "        add_header Content-Type text/plain;",
        "    }",
        "}",
        "",
    ])
    return "\n".join(lines)


def render_caddy(routes: dict) -> str:
    """Render a Caddy reverse-proxy config."""
    lines = [
        "# Generated by sovereign-osctl master-dashboard render",
        "# R452 (E11.M2): operator §1g reverse-proxy aggregator (Caddy)",
        "",
        f":{AGGREGATOR_PORT} {{",
    ]
    for slug, route in routes.items():
        subpath = route["subpath"].rstrip("/")
        port = route["port"]
        label = route["label"]
        lines.append(f"    # {label} ({slug})")
        lines.append(f"    reverse_proxy {subpath}/* 127.0.0.1:{port}")
    lines.append("    respond / \"sovereign-os master-dashboard\" 200")
    lines.append("}")
    lines.append("")
    return "\n".join(lines)


def render_traefik(routes: dict) -> str:
    """Render a Traefik dynamic config (YAML)."""
    lines = [
        "# Generated by sovereign-osctl master-dashboard render",
        "# R452 (E11.M2): operator §1g reverse-proxy aggregator (Traefik)",
        "",
        "http:",
        "  routers:",
    ]
    for slug, route in routes.items():
        subpath = route["subpath"].rstrip("/")
        lines.extend([
            f"    {slug}:",
            f"      rule: \"PathPrefix(`{subpath}`)\"",
            f"      service: {slug}",
            "      entryPoints:",
            "        - master-dashboard",
        ])
    lines.append("  services:")
    for slug, route in routes.items():
        port = route["port"]
        lines.extend([
            f"    {slug}:",
            "      loadBalancer:",
            "        servers:",
            f"          - url: \"http://127.0.0.1:{port}/\"",
        ])
    lines.append("")
    return "\n".join(lines)


BACKEND_RENDERERS = {
    "nginx": render_nginx,
    "caddy": render_caddy,
    "traefik": render_traefik,
}


# --- Verbs ---


def cmd_list(args) -> int:
    out = {
        "dashboards": [
            {"slug": s, **r} for s, r in DASHBOARD_ROUTES.items()
        ],
        "count": len(DASHBOARD_ROUTES),
        "aggregator_port": AGGREGATOR_PORT,
    }
    if args.fmt == "json":
        print(json.dumps(out, indent=2))
    else:
        print(f"── master-dashboard.list "
              f"({len(DASHBOARD_ROUTES)} dashboards, "
              f"aggregator-port={AGGREGATOR_PORT}) ──")
        for slug, r in DASHBOARD_ROUTES.items():
            print(f"  {slug:30s} :{r['port']:<5d} → {r['subpath']:12s} "
                  f"({r['label']})")
    _emit_metric("list", "any", "ok")
    return 0


# --- M060 R10129-R10132 dashboard on/off toggles ---

def _load_toggle_core():
    """Import the dashboard-toggles core (hyphenated filename → importlib)."""
    import importlib.util
    core_path = Path(__file__).resolve().parent.parent / "manifest" / "dashboard-toggles.py"
    spec = importlib.util.spec_from_file_location("_dash_toggles", core_path)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# M060 R10129 / SDD-040 D-040.5 — since F-2026-072 the aggregator route slug IS
# the webapp dashboard slug (both derive from config/dashboard-catalog.yaml), so
# the route slug is the toggle-catalog key directly — no indirection map. Infra
# upstreams (trinity engines, router-engine, grafana, node_exporter) are not in
# the toggle catalog, and is_enabled() fail-opens on an absent slug (→ True), so
# they are always kept.


def _enabled_routes(routes: dict) -> tuple[dict, list[str]]:
    """Filter routes to operator-enabled ones (M060 R10129). Returns
    (enabled_routes, disabled_slugs). A route slug absent from the toggle catalog
    (infra) fail-opens to enabled. Toggle core unavailable → everything kept
    (the aggregator never hides a dashboard because the toggle file is missing)."""
    core = _load_toggle_core()
    if core is None:
        return routes, []
    enabled, disabled = {}, []
    for slug, r in routes.items():
        if not core.is_enabled(slug):
            disabled.append(slug)
            continue
        enabled[slug] = r
    return enabled, disabled


def cmd_toggles(args) -> int:
    """Surface the operator dashboard on/off state (M060 R10129) — every
    cockpit dashboard + its enabled bit, from /etc/sovereign-os/dashboards.toml.
    Read-only; toggle via `sovereign-osctl dashboards {enable,disable}`."""
    core = _load_toggle_core()
    if core is None:
        print("dashboard-toggles core unavailable", file=sys.stderr)
        return 1
    state = core.toggles()
    if args.fmt == "json":
        print(json.dumps(state, indent=2))
    else:
        print(f"── master-dashboard.toggles "
              f"({state['enabled_count']}/{state['total']} enabled · "
              f"toml={'present' if state['toml_present'] else 'absent (all on)'}) ──")
        for r in state["dashboards"]:
            mark = "on " if r["enabled"] else "OFF"
            disk = "" if r["on_disk"] else "  (pre-staged, not on disk)"
            print(f"  [{mark}] {r['slug']}{disk}")
    _emit_metric("toggles", "any", "ok")
    return 0


# --- R460 selfdef cross-repo manifest discovery ---


def load_selfdef_manifests() -> tuple[list[dict], list[dict]]:
    """Read every .toml manifest under SELFDEF_MANIFEST_DIR.

    Returns (valid_manifests, errors). Each valid entry mirrors the
    selfdef-side DashboardSpec — module/port/healthz_path/subpath/
    label/auth_tier/surfaces — augmented with `source_repo="selfdef"`
    and `manifest_path`. Errors collect file-level failures so the
    operator can see WHY a manifest didn't load.

    Cross-repo binding: SD-R-DASHBOARD-MANIFEST-1
    (crates/selfdef-dashboard-manifest in selfdef repo).
    """
    valid: list[dict] = []
    errors: list[dict] = []
    if not SELFDEF_MANIFEST_DIR.is_dir():
        return valid, errors
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib  # type: ignore[import-not-found]
        except ImportError:
            errors.append({
                "path": str(SELFDEF_MANIFEST_DIR),
                "error": "no TOML library available (need tomllib py3.11+ "
                         "or tomli py3.10)",
            })
            return valid, errors
    for p in sorted(SELFDEF_MANIFEST_DIR.glob("*.toml")):
        try:
            data = tomllib.loads(p.read_text(encoding="utf-8"))
        except (OSError, Exception) as e:  # noqa: BLE001
            errors.append({"path": str(p), "error": f"parse: {e}"})
            continue
        schema_v = data.get("schema_version")
        if schema_v != 1:
            errors.append({
                "path": str(p),
                "error": f"unsupported schema_version={schema_v!r}",
            })
            continue
        d = data.get("dashboard") or {}
        try:
            entry = {
                "slug": str(d["module"]),
                "port": int(d["port"]),
                "healthz_path": str(d["healthz_path"]),
                "subpath": str(d["subpath"]),
                "label": str(d["label"]),
                "auth_tier": str(d["auth_tier"]),
                "surfaces": list(d.get("surfaces", [])),
                "source_repo": "selfdef",
                "manifest_path": str(p),
            }
        except (KeyError, TypeError, ValueError) as e:
            errors.append({"path": str(p), "error": f"shape: {e}"})
            continue
        valid.append(entry)
    return valid, errors


def cmd_discover(args) -> int:
    """Scan SELFDEF_MANIFEST_DIR for cross-repo dashboard manifests."""
    valid, errors = load_selfdef_manifests()
    # Detect collisions vs the built-in DASHBOARD_ROUTES
    builtin_ports = {r["port"] for r in DASHBOARD_ROUTES.values()}
    builtin_subpaths = {r["subpath"] for r in DASHBOARD_ROUTES.values()}
    builtin_slugs = set(DASHBOARD_ROUTES.keys())
    # ...AND among the selfdef manifests themselves. Two cross-repo manifests
    # claiming the same slug/port/subpath collide just as surely as one
    # colliding with a built-in route — both would silently route to the same
    # place. Checking each manifest only against the built-ins (as before)
    # missed this entirely, so a pair of conflicting selfdef manifests passed
    # discovery clean. Count occurrences across `valid` and flag any > 1.
    sd_slug_counts: dict[str, int] = {}
    sd_port_counts: dict[int, int] = {}
    sd_subpath_counts: dict[str, int] = {}
    for m in valid:
        sd_slug_counts[m["slug"]] = sd_slug_counts.get(m["slug"], 0) + 1
        sd_port_counts[m["port"]] = sd_port_counts.get(m["port"], 0) + 1
        sd_subpath_counts[m["subpath"]] = sd_subpath_counts.get(m["subpath"], 0) + 1
    collisions = []
    for m in valid:
        c = []
        if m["slug"] in builtin_slugs:
            c.append(f"slug collides with built-in {m['slug']!r}")
        if m["port"] in builtin_ports:
            c.append(f"port {m['port']} collides with built-in")
        if m["subpath"] in builtin_subpaths:
            c.append(
                f"subpath {m['subpath']!r} collides with built-in"
            )
        if sd_slug_counts[m["slug"]] > 1:
            c.append(
                f"slug {m['slug']!r} shared by "
                f"{sd_slug_counts[m['slug']]} selfdef manifests"
            )
        if sd_port_counts[m["port"]] > 1:
            c.append(
                f"port {m['port']} shared by "
                f"{sd_port_counts[m['port']]} selfdef manifests"
            )
        if sd_subpath_counts[m["subpath"]] > 1:
            c.append(
                f"subpath {m['subpath']!r} shared by "
                f"{sd_subpath_counts[m['subpath']]} selfdef manifests"
            )
        if c:
            collisions.append({"slug": m["slug"], "issues": c})
    out = {
        "manifest_dir": str(SELFDEF_MANIFEST_DIR),
        "discovered": valid,
        "errors": errors,
        "collisions": collisions,
        "count": len(valid),
    }
    if args.fmt == "json":
        print(json.dumps(out, indent=2))
    else:
        print(f"── master-dashboard.discover "
              f"({len(valid)} selfdef manifest{'s' if len(valid)!=1 else ''} "
              f"under {SELFDEF_MANIFEST_DIR}) ──")
        for m in valid:
            print(f"  ✓ {m['slug']:25s} :{m['port']:<5d} → {m['subpath']:15s} "
                  f"(auth={m['auth_tier']}, repo={m['source_repo']})")
        for e in errors:
            print(f"  ✗ {e['path']}  {e['error']}")
        for c in collisions:
            print(f"  ⚠ {c['slug']}: {'; '.join(c['issues'])}")
    _emit_metric("discover", "any",
                 "ok" if not errors and not collisions else "issues")
    return 0


def cmd_routes(args) -> int:
    mode = args.mode or "reverse-proxied"
    if mode not in OPERATOR_NAMED_MODES:
        print(f"unknown mode: {mode!r}; known: {OPERATOR_NAMED_MODES}",
              file=sys.stderr)
        _emit_metric("routes", mode, "unknown-mode")
        return 1
    routes_out = []
    for slug, r in DASHBOARD_ROUTES.items():
        routes_out.append({
            "slug": slug,
            "upstream": f"http://127.0.0.1:{r['port']}/",
            "subpath": r["subpath"],
            "label": r["label"],
        })
    out = {
        "mode": mode,
        "aggregator_port": AGGREGATOR_PORT,
        "routes": routes_out,
    }
    if args.fmt == "json":
        print(json.dumps(out, indent=2))
    else:
        print(f"── master-dashboard.routes (mode={mode}, "
              f"aggregator-port={AGGREGATOR_PORT}) ──")
        for r in routes_out:
            print(f"  :{AGGREGATOR_PORT}{r['subpath']} → {r['upstream']}  "
                  f"({r['slug']})")
    _emit_metric("routes", mode, "ok")
    return 0


def cmd_collisions(args) -> int:
    coll = detect_collisions()
    if args.fmt == "json":
        print(json.dumps(coll, indent=2))
    else:
        print("── master-dashboard.collisions ──")
        if not coll["has_collisions"]:
            print("  ✓ no collisions — aggregator-safe to render")
        else:
            print("  ✗ COLLISIONS DETECTED:")
            for p, slugs in coll["port_collisions"].items():
                print(f"    port {p} claimed by: {slugs}")
            for s, slugs in coll["subpath_collisions"].items():
                print(f"    subpath {s!r} claimed by: {slugs}")
        # Always surface the by-design shared-port fan-in (distinct subpaths →
        # one unified daemon) so it never reads as a hidden exception.
        for p, slugs in coll.get("intentional_shared_ports", {}).items():
            print(f"  · intentional shared port {p} (one unified daemon, distinct "
                  f"subpaths): {', '.join(slugs)}")
    result = "collisions" if coll["has_collisions"] else "clean"
    _emit_metric("collisions", "any", result)
    return 2 if coll["has_collisions"] else 0


def cmd_render(args) -> int:
    backend = args.backend
    if backend not in SUPPORTED_BACKENDS:
        print(f"unknown backend: {backend!r}; "
              f"known: {SUPPORTED_BACKENDS}", file=sys.stderr)
        _emit_metric("render", backend, "unknown-backend")
        return 1

    coll = detect_collisions()
    if coll["has_collisions"]:
        print(f"COLLISIONS DETECTED — refusing to render. "
              f"Run `sovereign-osctl master-dashboard collisions` for "
              f"details.", file=sys.stderr)
        _emit_metric("render", backend, "blocked-collisions")
        return 2

    # M060 R10129 / D-040.5 — render ONLY operator-enabled dashboards; a
    # disabled dashboard is omitted from the reverse-proxy config (the operator
    # turned it off via `sovereign-osctl dashboards disable <slug>`).
    enabled_routes, disabled_slugs = _enabled_routes(DASHBOARD_ROUTES)
    renderer = BACKEND_RENDERERS[backend]
    config_text = renderer(enabled_routes)
    extensions = {"nginx": "conf", "caddy": "Caddyfile", "traefik": "yaml"}
    out_path = OUTPUT_DIR / f"{backend}.{extensions[backend]}"

    out = {
        "backend": backend,
        "out_path": str(out_path),
        "byte_count": len(config_text.encode("utf-8")),
        "dashboards_aggregated": len(enabled_routes),
        "dashboards_disabled": disabled_slugs,
        "aggregator_port": AGGREGATOR_PORT,
    }

    # Triple-gate: --apply + --confirm-render
    if not (args.apply and args.confirm_render):
        out["preview"] = True
        out["config_preview"] = config_text
        out["next_action"] = (
            f"Run: sovereign-osctl master-dashboard render "
            f"--backend {backend} --apply --confirm-render"
        )
        if args.fmt == "json":
            print(json.dumps(out, indent=2))
        else:
            print(f"── master-dashboard.render PREVIEW ({backend}) ──")
            print(f"  out_path:           {out_path}")
            print(f"  dashboards:         {len(enabled_routes)} enabled"
                  + (f" · {len(disabled_slugs)} disabled ({', '.join(disabled_slugs)})"
                     if disabled_slugs else ""))
            print(f"  aggregator-port:    {AGGREGATOR_PORT}")
            print(f"  byte-count:         {len(config_text.encode('utf-8'))}")
            print(f"  next: --apply --confirm-render to commit")
        _emit_metric("render", backend, "preview")
        return 0

    # Triple-gate satisfied; --apply mode
    if DRY_RUN:
        if args.fmt == "json":
            out["dry_run"] = True
            print(json.dumps(out, indent=2))
        else:
            print(f"── master-dashboard.render DRY-RUN ({backend}) ──")
            print(f"  would write {len(config_text.encode('utf-8'))} bytes "
                  f"to {out_path}")
        _emit_metric("render", backend, "dry-run")
        return 0

    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        tmp = out_path.with_suffix(out_path.suffix + ".tmp")
        tmp.write_text(config_text)
        tmp.replace(out_path)
    except OSError as e:
        print(f"render failed: {e}", file=sys.stderr)
        _emit_metric("render", backend, "write-failed")
        return 2

    out["applied"] = True
    if args.fmt == "json":
        print(json.dumps(out, indent=2))
    else:
        print(f"── master-dashboard.render APPLIED ({backend}) ──")
        print(f"  wrote: {out_path}")
        print(f"  next:  reload {backend} (e.g. "
              f"`systemctl reload {backend}`)")
    _emit_metric("render", backend, "applied")
    return 0


def cmd_health(args) -> int:
    probes = [
        probe_dashboard(s, r) for s, r in DASHBOARD_ROUTES.items()
    ]
    reachable = sum(1 for p in probes if p["reachable"])
    out = {
        "probes": probes,
        "reachable_count": reachable,
        "total_count": len(probes),
    }
    if args.fmt == "json":
        print(json.dumps(out, indent=2))
    else:
        print(f"── master-dashboard.health "
              f"({reachable}/{len(probes)} reachable) ──")
        for p in probes:
            mark = "✓" if p["reachable"] else "✗"
            print(f"  {mark} {p['slug']:30s} :{p['port']:<5d} "
                  f"({p['tier']})")
    _emit_metric("health", "any", "ok")
    return 0


def cmd_watch(args) -> int:
    """R488 (E11.M2+) — refresh-loop TUI for master-dashboard.

    Operator-§1g surface: an interactive ANSI-clear refresh-loop view
    that combines the health probes + collision-state + per-route
    reachability into one continuously-updating panel. Same shape as
    R483 (network-edge opnsense watch) and R481 (global-history tail).

    Operator-named guarantees:
      - Minimum refresh interval = 1s (max(1, ...) floor) so the
        operator can't accidentally hammer the upstreams.
      - SOVEREIGN_OS_DRY_RUN=1 forces single-render exit (CI-safe).
      - Bounded by --iterations (0 = unbounded).
      - Layer B metric emitted per-tick with verb='watch'.
    """
    refresh = max(1, int(args.refresh))
    iterations = int(args.iterations)
    dry_run = os.environ.get("SOVEREIGN_OS_DRY_RUN", "") == "1"
    if dry_run and iterations == 0:
        iterations = 1

    frame = 0
    while True:
        frame += 1
        sys.stdout.write("\x1b[2J\x1b[H")
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        probes = [probe_dashboard(s, r) for s, r in DASHBOARD_ROUTES.items()]
        reachable = sum(1 for p in probes if p["reachable"])
        total = len(probes)
        coll = detect_collisions()
        collisions = coll["has_collisions"]
        result_state = "collisions" if collisions else (
            "all-reachable" if reachable == total else "partial"
        )

        print(f"── master-dashboard.watch (frame {frame}, "
              f"refresh={refresh}s, {now}) ──")
        print(f"  reachable : {reachable}/{total}")
        print(f"  collisions: {'YES' if collisions else 'no'}")
        if collisions:
            for p, slugs in coll["port_collisions"].items():
                print(f"    port {p} claimed by: {slugs}")
            for s, slugs in coll["subpath_collisions"].items():
                print(f"    subpath {s!r} claimed by: {slugs}")
        print()
        print("  per-route reachability:")
        for p in probes:
            mark = "✓" if p["reachable"] else "✗"
            print(f"    {mark} {p['slug']:30s} :{p['port']:<5d} "
                  f"({p['tier']})")
        print()
        if iterations > 0 and frame >= iterations:
            print(f"  (reached --iterations={iterations}; exit)")
        else:
            print(f"  (Ctrl-C to exit; refresh in {refresh}s)")
        sys.stdout.flush()

        _emit_metric("watch", "any", result_state)

        if iterations > 0 and frame >= iterations:
            break
        try:
            time.sleep(refresh)
        except KeyboardInterrupt:
            print("\n  ── master-dashboard.watch interrupted ──")
            break
    return 0


# --- Argparse ---


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="master-dashboard.py",
        description=(
            "R452 (E11.M2): operator §1g reverse-proxy aggregator — "
            "master-dashboard regrouping per-port dashboards under "
            "a single super-dashboard port."
        ),
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    def _add_fmt(sp):
        g = sp.add_mutually_exclusive_group()
        g.add_argument("--json", dest="fmt", action="store_const",
                       const="json", default="human")
        g.add_argument("--human", dest="fmt", action="store_const",
                       const="human")

    sp_list = sub.add_parser("list",
                             help="list aggregatable dashboards")
    _add_fmt(sp_list)

    sp_routes = sub.add_parser("routes",
                               help="show route table for a mode")
    sp_routes.add_argument("--mode", default="reverse-proxied",
                           choices=OPERATOR_NAMED_MODES)
    _add_fmt(sp_routes)

    sp_coll = sub.add_parser("collisions",
                             help="detect port/subpath collisions")
    _add_fmt(sp_coll)

    sp_render = sub.add_parser("render",
                               help="render reverse-proxy config")
    sp_render.add_argument("--backend", required=True,
                           choices=SUPPORTED_BACKENDS)
    sp_render.add_argument("--apply", action="store_true")
    sp_render.add_argument("--confirm-render", action="store_true")
    _add_fmt(sp_render)

    sp_health = sub.add_parser("health",
                               help="probe upstream dashboard reachability")
    _add_fmt(sp_health)

    sp_toggles = sub.add_parser(
        "toggles",
        help="M060 R10129 — show every dashboard's operator on/off state")
    _add_fmt(sp_toggles)

    sp_disc = sub.add_parser(
        "discover",
        help=("scan SELFDEF_MANIFEST_DIR for selfdef-side dashboard "
              "manifests (cross-repo binding "
              "SD-R-DASHBOARD-MANIFEST-1)"),
    )
    _add_fmt(sp_disc)

    sp_watch = sub.add_parser(
        "watch",
        help=("R488 (E11.M2+): refresh-loop TUI showing health + "
              "collisions + per-route reachability; ANSI-clear-redraw"),
    )
    sp_watch.add_argument("--refresh", type=int, default=5,
                          help="refresh interval in seconds "
                               "(floor=1s; default=5)")
    sp_watch.add_argument("--iterations", type=int, default=0,
                          help="max iterations before exit "
                               "(0=unbounded; default=0)")
    _add_fmt(sp_watch)

    args = p.parse_args(argv)
    return {
        "list": cmd_list,
        "routes": cmd_routes,
        "collisions": cmd_collisions,
        "render": cmd_render,
        "health": cmd_health,
        "discover": cmd_discover,
        "watch": cmd_watch,
        "toggles": cmd_toggles,
    }[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
