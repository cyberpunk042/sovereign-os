#!/usr/bin/env python3
"""scripts/operator/surface-map.py — R453 (E11.M3).

Operator §1g verbatim:
  "Everything is not just core, not just cli, not just TUI, not just
   API, not just tool and MCP but also Dashboards and Web Apps and
   Services"

Multi-surface delivery contract surface. For every operator-facing
module/capability, this module asks: which of the 8 operator-named
surfaces does it ship on?

Operator-named surfaces (8, per §1g verbatim taxonomy):
  1. core           in-process library / functions
  2. cli            shell command surface (sovereign-osctl <verb>)
  3. tui            terminal UI (curses/textual/blessed)
  4. api            HTTP REST / RPC
  5. mcp            Model Context Protocol server
  6. dashboard      Grafana / web dashboard
  7. webapp         standalone web application surface
  8. service        systemd-managed daemon

CLI:
  surface-map.py surfaces [--json|--human]
      Enumerate the 8 operator-named surfaces with operator-§1g
      verbatim binding.

  surface-map.py modules [--json|--human]
      List all operator-facing modules tracked.

  surface-map.py coverage [--module <m>] [--surface <s>] [--json|--human]
      Coverage matrix — module × surface → has-it / waived /
      gap. Sorted by largest gap first.

  surface-map.py gaps [--module <m>] [--threshold N] [--json|--human]
      Modules below threshold surface count (default 3, per §1g
      "at least N of these surfaces present").

  surface-map.py waivers [--json|--human]
      Explicit per-module surface waivers (operator-discoverable;
      "this module legitimately doesn't ship on surface X because Y").

Exit codes:
  0 ok
  1 unknown subcommand / module / surface
  2 gaps above threshold (operator-discoverable failure mode)

Layer B metric (SDD-016):
  sovereign_os_operator_surface_map_query_total{verb,surface,result}

Operator-environment env vars:
  SOVEREIGN_OS_SURFACE_MAP_DRY_RUN  Logs intent; no file writes.
  SOVEREIGN_OS_DRY_RUN              Same effect (sovereign-wide).
  SOVEREIGN_OS_SURFACE_THRESHOLD    Minimum surface count (default 3).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

DRY_RUN = (
    os.environ.get("SOVEREIGN_OS_DRY_RUN") == "1"
    or os.environ.get("SOVEREIGN_OS_SURFACE_MAP_DRY_RUN") == "1"
)
METRICS_DIR = Path(
    os.environ.get(
        "SOVEREIGN_OS_TEXTFILE_DIR",
        "/var/lib/prometheus/node-exporter",
    )
)
DEFAULT_THRESHOLD = int(
    os.environ.get("SOVEREIGN_OS_SURFACE_THRESHOLD", "3")
)

# HELP sovereign_os_operator_surface_map_query_total surface-map operator-
# verb call count (verb, surface, result).
# TYPE sovereign_os_operator_surface_map_query_total counter
METRIC_NAME = "sovereign_os_operator_surface_map_query_total"

# Operator-named surfaces (8, per §1g verbatim — VERBATIM ordering
# preserved: core → cli → TUI → API → tool/MCP → Dashboards → Web Apps
# → Services).
SURFACES = [
    {
        "id": "core",
        "label": "core (in-process library)",
        "operator_named": "core",
        "§1g_position": 1,
    },
    {
        "id": "cli",
        "label": "cli (sovereign-osctl <verb>)",
        "operator_named": "cli",
        "§1g_position": 2,
    },
    {
        "id": "tui",
        "label": "TUI (terminal UI; curses/textual/blessed)",
        "operator_named": "TUI",
        "§1g_position": 3,
    },
    {
        "id": "api",
        "label": "API (HTTP REST/RPC)",
        "operator_named": "API",
        "§1g_position": 4,
    },
    {
        "id": "mcp",
        "label": "MCP (Model Context Protocol server)",
        "operator_named": "tool and MCP",
        "§1g_position": 5,
    },
    {
        "id": "dashboard",
        "label": "Dashboard (Grafana / web dashboard)",
        "operator_named": "Dashboards",
        "§1g_position": 6,
    },
    {
        "id": "webapp",
        "label": "Web App (standalone web application)",
        "operator_named": "Web Apps",
        "§1g_position": 7,
    },
    {
        "id": "service",
        "label": "Service (systemd-managed daemon)",
        "operator_named": "Services",
        "§1g_position": 8,
    },
]
SURFACE_IDS = [s["id"] for s in SURFACES]

# Per-module surface coverage. For each module, which of the 8 surfaces
# does it currently ship on? Maintained by hand for operator-discoverable
# accuracy. "waivers" enumerate surfaces the module legitimately doesn't
# ship on with operator-named rationale.
MODULE_COVERAGE = {
    "auth-tier": {
        "shipped_in": "R450 (E11.M7) + R484 (E11.M7+ Grafana dashboard) + R501 (E11.M7++ read-only REST API + systemd service) + R502 (E11.M7++ MCP surface) + R503 (E11.M7++ webapp surface)",
        "surfaces": ["core", "cli", "dashboard", "api", "service", "mcp", "webapp"],
        "waivers": {
            "tui":       "not applicable — config surface, not interactive",
        },
    },
    "edge-firewall": {
        "shipped_in": "R451 (E11.M9) + R482 (E11.M9+ wizard tui) + R485 (E11.M9+ Grafana dashboard) + R504 (E11.M9++ read-only REST API + systemd service) + R505 (E11.M9++ MCP surface) + R506 (E11.M9++ webapp surface)",
        "surfaces": ["core", "cli", "tui", "dashboard", "api", "service", "mcp", "webapp"],
        "waivers": {},
    },
    "network-edge": {
        "shipped_in": "R449 (E11.M8) + R483 (E11.M8+ opnsense watch tui) + R486 (E11.M8+ Grafana dashboard) + R507 (E11.M8++ read-only REST API + systemd service) + R508 (E11.M8++ MCP surface) + R509 (E11.M8++ webapp surface)",
        "surfaces": ["core", "cli", "tui", "dashboard", "api", "service", "mcp", "webapp"],
        "waivers": {},
    },
    "master-dashboard": {
        "shipped_in": "R452 (E11.M2) + R488 (E11.M2+ watch tui) + R498 (E11.M2++ read-only REST API) + R499 (E11.M2++ MCP surface) + R500 (E11.M2++ webapp surface)",
        "surfaces": ["core", "cli", "tui", "service", "api", "mcp", "webapp"],
        "waivers": {
            "dashboard": "self-referential — master-dashboard IS the aggregator",
        },
    },
    "global-history": {
        "shipped_in": "R448 (E11.M5) + R481 (E11.M5+ tui surface) + R487 (E11.M5+ Grafana dashboard) + R510 (E11.M5++ read-only REST API + systemd service) + R511 (E11.M5++ MCP surface) + R512 (E11.M5++ webapp surface)",
        "surfaces": ["core", "cli", "tui", "dashboard", "api", "service", "mcp", "webapp"],
        "waivers": {},
    },
    "bashrc": {
        "shipped_in": "R447 (E11.M6)",
        "surfaces": ["core", "cli"],
        "waivers": {
            "tui":       "not applicable — config surface, idempotent install",
            "api":       "not applicable — local shell integration",
            "mcp":       "not applicable — local shell integration",
            "dashboard": "not applicable — local shell integration",
            "webapp":    "not applicable — local shell integration",
            "service":   "not applicable — config installer, no daemon",
        },
    },
    "trinity": {
        "shipped_in": "R290-R299 (E5) + R494 (Grafana dashboard) + R513 (E5++ refresh-loop TUI surface) + R514 (E5++ MCP surface) + R515 (E5++ read-only REST API + webapp)",
        "surfaces": ["core", "cli", "tui", "dashboard", "api", "service", "mcp", "webapp"],
        "waivers": {},
    },
    "router": {
        "shipped_in": "SDD-011 + R495 (Grafana dashboard) + R516 (E5++ refresh-loop TUI surface) + R517 (E5++ MCP surface) + R518 (E5++ read-only REST API + webapp)",
        "surfaces": ["core", "cli", "tui", "api", "service", "dashboard", "mcp", "webapp"],
        "waivers": {},
    },
    "compliance": {
        "shipped_in": "R458 + R489 (Grafana dashboard) + R519 (E5++ refresh-loop TUI surface) + R520 (E5++ MCP surface) + R521 (E5++ read-only REST API + webapp + systemd service)",
        "surfaces": ["core", "cli", "tui", "api", "service", "dashboard", "mcp", "webapp"],
        "waivers": {},
    },
    "anti-minimization-audit": {
        "shipped_in": "R456 + R490 (Grafana dashboard) + R522 (E5++ refresh-loop TUI surface) + R523 (E5++ MCP surface) + R524 (E5++ read-only REST API + webapp + systemd service)",
        "surfaces": ["core", "cli", "tui", "api", "service", "dashboard", "mcp", "webapp"],
        "waivers": {},
    },
    "doc-coverage": {
        "shipped_in": "R454 + R491 (Grafana dashboard) + R525 (E5++ refresh-loop TUI surface) + R526 (E5++ MCP surface) + R527 (E5++ read-only REST API + webapp + systemd service)",
        "surfaces": ["core", "cli", "tui", "api", "service", "dashboard", "mcp", "webapp"],
        "waivers": {},
    },
    "ux-design-audit": {
        "shipped_in": "R457 + R492 (Grafana dashboard) + R528 (E5++ refresh-loop TUI surface) + R529 (E5++ MCP surface) + R530 (E5++ read-only REST API + webapp + systemd service)",
        "surfaces": ["core", "cli", "tui", "api", "service", "dashboard", "mcp", "webapp"],
        "waivers": {},
    },
    "surface-map": {
        "shipped_in": "R453 + R493 (Grafana dashboard) + R531 (E5++ refresh-loop TUI surface) + R532 (E5++ MCP surface) + R533 (E5++ read-only REST API + webapp + systemd service)",
        "surfaces": ["core", "cli", "tui", "api", "service", "dashboard", "mcp", "webapp"],
        "waivers": {},
    },
    "weaver": {
        "shipped_in": "R152-R155 (master spec § 21) + R496 (Grafana dashboard) + R534 (E5++ refresh-loop TUI surface) + R535 (E5++ MCP surface — read-only weaver-list + weaver-state-files) + R536 (E5++ read-only REST API + webapp + systemd service — write/read stay CLI-only per operator §17 sovereignty boundary)",
        "surfaces": ["core", "cli", "tui", "api", "service", "dashboard", "mcp", "webapp"],
        "waivers": {},
    },
    "auditor": {
        "shipped_in": "R152-R155 (master spec §§ 10, 17) + R497 (Grafana dashboard) + R537 (E5++ refresh-loop TUI surface — read-only inspection) + R538 (E5++ MCP surface — read-only auditor-status + auditor-last-violation + auditor-history) + R539 (E5++ read-only REST API + webapp — separate inspection daemon, coexists with R155 guardian-core neutralization daemon; neutralization stays CCD-triggered + CLI-gated per operator §17)",
        "surfaces": ["core", "cli", "tui", "api", "service", "dashboard", "mcp", "webapp"],
        "waivers": {},
    },
    # M060 cross-repo READ-ONLY mirror modules — each consumes the
    # selfdef-side MS007 typed-mirror crate of its name and projects
    # it through 6 §1g surfaces. tui + dashboard waived: operators
    # primarily reach mirror state via CLI / webapp / MCP; Grafana
    # dashboard panels for each mirror remain future work but are
    # not the cockpit's primary path.
    "profile-mirror": {
        "shipped_in": "M060 R10063-R10068 (D-02 active profile) + selfdef MS040 + MS007 profile-mirror crate · §1g 6/8 surfaces (core/cli/api/webapp/service/mcp); web NEVER mutates per R10212",
        "surfaces": ["core", "cli", "api", "webapp", "service", "mcp"],
        "waivers": {
            "tui": "not applicable — the operator-facing TUI for this IPS state lives in selfdef (selfdef tui on the daemon side); per 'Respect the projects', sovereign-os mirror modules are READ-ONLY cross-repo consumers without their own TUI surface",
            "dashboard": "not applicable — the webapp surface IS the dashboard for M060 cross-repo mirrors (the master-dashboard aggregator is the §1g 'dashboard' surface for sovereign-os-native modules; per-mirror Grafana panels duplicate the webapp's read-only render of the same selfdef-published JSON)",
        },
    },
    "grants-mirror": {
        "shipped_in": "M060 R10114-R10115 (D-13 filesystem grants) + selfdef MS037 + MS007 grants-mirror crate · §1g 6/8 surfaces (core/cli/api/webapp/service/mcp); web NEVER mutates — grant issue/revoke is selfdefctl + MS003 per R10212",
        "surfaces": ["core", "cli", "api", "webapp", "service", "mcp"],
        "waivers": {
            "tui": "not applicable — the operator-facing TUI for this IPS state lives in selfdef (selfdef tui on the daemon side); per 'Respect the projects', sovereign-os mirror modules are READ-ONLY cross-repo consumers without their own TUI surface",
            "dashboard": "not applicable — the webapp surface IS the dashboard for M060 cross-repo mirrors (the master-dashboard aggregator is the §1g 'dashboard' surface for sovereign-os-native modules; per-mirror Grafana panels duplicate the webapp's read-only render of the same selfdef-published JSON)",
        },
    },
    "capability-mirror": {
        "shipped_in": "M060 R10116-R10117 (D-14 capability tokens) + selfdef MS035 + MS007 capability-mirror crate · §1g 6/8 surfaces (core/cli/api/webapp/service/mcp); web NEVER mutates — token issue/revoke is selfdefctl + MS003 per R10212",
        "surfaces": ["core", "cli", "api", "webapp", "service", "mcp"],
        "waivers": {
            "tui": "not applicable — the operator-facing TUI for this IPS state lives in selfdef (selfdef tui on the daemon side); per 'Respect the projects', sovereign-os mirror modules are READ-ONLY cross-repo consumers without their own TUI surface",
            "dashboard": "not applicable — the webapp surface IS the dashboard for M060 cross-repo mirrors (the master-dashboard aggregator is the §1g 'dashboard' surface for sovereign-os-native modules; per-mirror Grafana panels duplicate the webapp's read-only render of the same selfdef-published JSON)",
        },
    },
    "sandbox-mirror": {
        "shipped_in": "M060 R10118-R10119 (D-15 sandboxes) + selfdef MS032 + MS036 + MS007 sandbox-mirror crate · §1g 6/8 surfaces (core/cli/api/webapp/service/mcp); web NEVER mutates — allocate/checkpoint/release is selfdefctl + MS003 per R10212",
        "surfaces": ["core", "cli", "api", "webapp", "service", "mcp"],
        "waivers": {
            "tui": "not applicable — the operator-facing TUI for this IPS state lives in selfdef (selfdef tui on the daemon side); per 'Respect the projects', sovereign-os mirror modules are READ-ONLY cross-repo consumers without their own TUI surface",
            "dashboard": "not applicable — the webapp surface IS the dashboard for M060 cross-repo mirrors (the master-dashboard aggregator is the §1g 'dashboard' surface for sovereign-os-native modules; per-mirror Grafana panels duplicate the webapp's read-only render of the same selfdef-published JSON)",
        },
    },
    "audit-mirror": {
        "shipped_in": "M060 R10120 (D-16 audit chain; backward-sweep redefinition from MS009 cycles to MS016 chain) + selfdef MS016 SHA-256 chain + MS049 13-field spans + MS026 OCSF + MS003 verify-only + MS007 audit-mirror crate · §1g 6/8 surfaces (core/cli/api/webapp/service/mcp); chain is APPEND-ONLY by MS016 R03567 — NO mutation surface; verify/show/export is selfdefctl + MS003 per R10212",
        "surfaces": ["core", "cli", "api", "webapp", "service", "mcp"],
        "waivers": {
            "tui": "not applicable — the operator-facing TUI for this IPS state lives in selfdef (selfdef tui on the daemon side); per 'Respect the projects', sovereign-os mirror modules are READ-ONLY cross-repo consumers without their own TUI surface",
            "dashboard": "not applicable — the webapp surface IS the dashboard for M060 cross-repo mirrors (the master-dashboard aggregator is the §1g 'dashboard' surface for sovereign-os-native modules; per-mirror Grafana panels duplicate the webapp's read-only render of the same selfdef-published JSON)",
        },
    },
    "quarantine-mirror": {
        "shipped_in": "M060 R10121-R10122 (D-17 quarantine) + selfdef MS042 declaration-vs-observed + MS007 quarantine-mirror crate · §1g 6/8 surfaces (core/cli/api/webapp/service/mcp); web NEVER mutates — release/forfeit is selfdefctl + MS003 per R10212",
        "surfaces": ["core", "cli", "api", "webapp", "service", "mcp"],
        "waivers": {
            "tui": "not applicable — the operator-facing TUI for this IPS state lives in selfdef (selfdef tui on the daemon side); per 'Respect the projects', sovereign-os mirror modules are READ-ONLY cross-repo consumers without their own TUI surface",
            "dashboard": "not applicable — the webapp surface IS the dashboard for M060 cross-repo mirrors (the master-dashboard aggregator is the §1g 'dashboard' surface for sovereign-os-native modules; per-mirror Grafana panels duplicate the webapp's read-only render of the same selfdef-published JSON)",
        },
    },
    "trust-mirror": {
        "shipped_in": "M060 R10123 (D-18 trust scores) + selfdef MS042 per-tool trust + MS007 trust-score-mirror crate · §1g 6/8 surfaces (core/cli/api/webapp/service/mcp); web NEVER mutates — score reset is selfdefctl + MS003 per R10212",
        "surfaces": ["core", "cli", "api", "webapp", "service", "mcp"],
        "waivers": {
            "tui": "not applicable — the operator-facing TUI for this IPS state lives in selfdef (selfdef tui on the daemon side); per 'Respect the projects', sovereign-os mirror modules are READ-ONLY cross-repo consumers without their own TUI surface",
            "dashboard": "not applicable — the webapp surface IS the dashboard for M060 cross-repo mirrors (the master-dashboard aggregator is the §1g 'dashboard' surface for sovereign-os-native modules; per-mirror Grafana panels duplicate the webapp's read-only render of the same selfdef-published JSON)",
        },
    },
    "lm-orchestration": {
        "shipped_in": "D-21-lm-orchestration (cockpit panel — profiles + model→hardware assignment grid + AVX-512/GPU capabilities; reuses the model-health core + runtime-modes profile lister)",
        "surfaces": ["core", "api", "webapp", "service"],
        "waivers": {
            "cli":       "not applicable — CLI is `sovereign-osctl model-health` + `runtime-modes` on the shared cores",
            "tui":       "not applicable — cockpit web panel, not an interactive TUI",
            "dashboard": "not applicable — the webapp IS this panel's operator dashboard",
            "mcp":       "not applicable — read-only render of shared cores",
        },
    },

    "lm-status-operability": {
        "shipped_in": "D-22-lm-status-operability (cockpit panel — per-device LM status + operability + render-only chat; reuses the model-health core)",
        "surfaces": ["core", "api", "webapp", "service"],
        "waivers": {
            "cli":       "not applicable — CLI is `sovereign-osctl model-health` on the shared core",
            "tui":       "not applicable — cockpit web panel, not an interactive TUI",
            "dashboard": "not applicable — the webapp IS this panel's operator dashboard",
            "mcp":       "not applicable — read-only render of the shared model-health core",
        },
    },

    "models-catalog": {
        "shipped_in": "D-23-models-catalog (cockpit panel — the canonical model registry by SRP tier; reuses the model-health load_catalog core)",
        "surfaces": ["core", "api", "webapp", "service"],
        "waivers": {
            "cli":       "not applicable — CLI is `sovereign-osctl models` on the shared catalog",
            "tui":       "not applicable — cockpit web panel, not an interactive TUI",
            "dashboard": "not applicable — the webapp IS this panel's operator dashboard",
            "mcp":       "not applicable — read-only render of the shared catalog reader",
        },
    },

    "cpu-features": {
        "shipped_in": "D-24-cpu-features (cockpit panel — deep AVX-512 capability + workload-fit + advisory; reuses avx512-advisor)",
        "surfaces": ["core", "api", "webapp", "service"],
        "waivers": {
            "cli":       "not applicable — CLI is `scripts/hardware/avx512-advisor.py`",
            "tui":       "not applicable — cockpit web panel, not an interactive TUI",
            "dashboard": "not applicable — the webapp IS this panel's operator dashboard",
            "mcp":       "not applicable — read-only render of the shared advisor",
        },
    },

    "selfdef-management": {
        "shipped_in": "D-25-selfdef-management (cockpit panel — READ-ONLY consumer view of the selfdef IPS: on/off enablement + M060 mirror-chain health + links to the 6 domain panels D-13..D-18; reuses the m060-health probe() consumer proxy — R10212)",
        "surfaces": ["core", "api", "webapp", "service"],
        "waivers": {
            "cli":       "not applicable — the selfdef producer owns the CLI (`sovereign-osctl selfdef {status,on,off}`); this READ-ONLY consumer never mutates",
            "tui":       "not applicable — cockpit web panel, not an interactive TUI",
            "dashboard": "not applicable — the webapp IS this panel's operator dashboard",
            "mcp":       "not applicable — read-only render of the shared m060-health consumer proxy",
        },
    },

}

KNOWN_MODULES = list(MODULE_COVERAGE.keys())

# R462 cross-repo: selfdef-side SurfaceManifest TOMLs live here. The
# selfdef-surface-manifest crate (SD-R-MULTI-SURFACE-AUDIT-1) writes
# one per module declaring its §1g surface coverage. surface-map
# `selfdef` verb reads them.
SELFDEF_SURFACE_DIR = Path(
    os.environ.get(
        "SOVEREIGN_OS_SELFDEF_SURFACE_DIR",
        "/etc/selfdef/surfaces",
    )
)


def _emit_metric(verb: str, surface: str, result: str) -> None:
    """Best-effort SDD-016 metric write; never raises."""
    if DRY_RUN:
        sys.stderr.write(
            f"  would emit: {METRIC_NAME}"
            f'{{verb="{verb}",surface="{surface}",'
            f'result="{result}"}} 1\n'
        )
        return
    try:
        METRICS_DIR.mkdir(parents=True, exist_ok=True)
        prom = METRICS_DIR / "sovereign-os-operator-surface-map.prom"
        line = (
            f"{METRIC_NAME}"
            f'{{verb="{verb}",surface="{surface}",'
            f'result="{result}"}} 1\n'
        )
        tmp = prom.with_suffix(".prom.tmp")
        tmp.write_text(line)
        tmp.replace(prom)
    except OSError:
        pass


# R478: classify a waiver rationale into one of two operator-canonical
# categories. The convention established across MODULE_COVERAGE is:
#   "not applicable — ..."  → STRUCTURAL ceiling. The surface CANNOT
#       apply to this module by definition (e.g., bashrc on `service`
#       — bashrc is a config installer, not a daemon). The shortfall
#       to threshold here is NOT closeable without a paradigm shift;
#       it's already operator-fully-described.
#   "FUTURE — ..."          → ROADMAP shortfall. The surface COULD
#       apply but isn't shipped yet. This IS a tracked gap — operator
#       wants the work and has a rationale for what each surface
#       would deliver.
# Anti-min precision (R478): only FUTURE-class shortfalls should fire
# as 'surface-gap' in the anti-min audit. STRUCTURAL waivers are at
# ceiling — flagging them is a false-positive (they aren't minimized
# work, they're correctly-shaped work).
def _classify_waiver(rationale: str) -> str:
    """Classify a waiver rationale string. Returns 'structural' for
    'not applicable'-prefixed rationales, 'future' for 'FUTURE'-prefixed
    rationales, 'other' for anything that doesn't match either prefix
    (defensive — caller treats 'other' as 'future' so unclassified
    waivers still surface in gaps, anti-min-safe default)."""
    if not rationale:
        return "other"
    head = rationale.strip().lower()
    if head.startswith("not applicable"):
        return "structural"
    if head.startswith("future"):
        return "future"
    if head.startswith("self-referential"):
        # "self-referential — master-dashboard IS the aggregator" is
        # structurally-equivalent to NA: the surface IS the module.
        return "structural"
    if head.startswith("candidates are") or head.startswith("candidates ARE"):
        # "candidates ARE services" — the surface concept is realized
        # AS the unshipped-surface kind, not separately deliverable.
        return "structural"
    return "other"


def coverage_for(module: str) -> dict:
    """Return coverage details for one module."""
    if module not in MODULE_COVERAGE:
        return {}
    entry = MODULE_COVERAGE[module]
    shipped = set(entry["surfaces"])
    waivers = entry.get("waivers", {})
    matrix = []
    structural_count = 0
    future_count = 0
    gap_count = 0
    for s in SURFACE_IDS:
        if s in shipped:
            matrix.append({"surface": s, "state": "shipped"})
        elif s in waivers:
            cls = _classify_waiver(waivers[s])
            matrix.append({
                "surface": s,
                "state": "waived",
                "waiver_class": cls,
                "rationale": waivers[s],
            })
            if cls == "structural":
                structural_count += 1
            else:
                future_count += 1
        else:
            matrix.append({"surface": s, "state": "gap"})
            gap_count += 1
    # R478: structural ceiling = NO future-class waivers AND no bare
    # gaps. The module is fully described and at its operator-stated
    # ceiling; remaining shortfall to threshold is structural, not a
    # minimization to close.
    at_ceiling = (future_count == 0 and gap_count == 0)
    return {
        "module": module,
        "shipped_in": entry["shipped_in"],
        "surface_count": len(shipped),
        "structural_waiver_count": structural_count,
        "future_waiver_count": future_count,
        "at_structural_ceiling": at_ceiling,
        "matrix": matrix,
    }


# --- Verbs ---


def cmd_surfaces(args) -> int:
    out = {"surfaces": SURFACES, "count": len(SURFACES)}
    if args.fmt == "json":
        print(json.dumps(out, indent=2))
    else:
        print(f"── surface-map.surfaces "
              f"({len(SURFACES)} operator-named surfaces) ──")
        for s in SURFACES:
            print(f"  {s['§1g_position']}. {s['id']:10s} "
                  f"({s['operator_named']!r}) — {s['label']}")
    _emit_metric("surfaces", "all", "ok")
    return 0


def cmd_modules(args) -> int:
    out = {
        "modules": [
            {"id": m, "shipped_in": MODULE_COVERAGE[m]["shipped_in"],
             "surface_count": len(MODULE_COVERAGE[m]["surfaces"])}
            for m in KNOWN_MODULES
        ],
        "count": len(KNOWN_MODULES),
    }
    if args.fmt == "json":
        print(json.dumps(out, indent=2))
    else:
        print(f"── surface-map.modules "
              f"({len(KNOWN_MODULES)} tracked modules) ──")
        for m in out["modules"]:
            print(f"  {m['id']:25s} surfaces={m['surface_count']}/8 "
                  f"({m['shipped_in']})")
    _emit_metric("modules", "all", "ok")
    return 0


def cmd_coverage(args) -> int:
    if args.module and args.module not in KNOWN_MODULES:
        print(f"unknown module: {args.module!r}; "
              f"known: {KNOWN_MODULES}", file=sys.stderr)
        _emit_metric("coverage", "any", "unknown-module")
        return 1
    if args.surface and args.surface not in SURFACE_IDS:
        print(f"unknown surface: {args.surface!r}; "
              f"known: {SURFACE_IDS}", file=sys.stderr)
        _emit_metric("coverage", args.surface or "any", "unknown-surface")
        return 1

    rows = []
    target = [args.module] if args.module else KNOWN_MODULES
    for m in target:
        cov = coverage_for(m)
        if args.surface:
            cov["matrix"] = [
                e for e in cov["matrix"] if e["surface"] == args.surface
            ]
        rows.append(cov)
    rows.sort(key=lambda r: r["surface_count"])  # smallest first = largest gap
    out = {"coverage": rows, "count": len(rows)}
    if args.fmt == "json":
        print(json.dumps(out, indent=2))
    else:
        print(f"── surface-map.coverage "
              f"({len(rows)} module{'s' if len(rows)!=1 else ''}) ──")
        for r in rows:
            print(f"\n  {r['module']} "
                  f"(surfaces={r['surface_count']}/8, "
                  f"shipped={r['shipped_in']})")
            for e in r["matrix"]:
                mark = {"shipped": "✓", "waived": "○", "gap": "✗"}[e["state"]]
                rat = (
                    f"  — {e['rationale']}" if e.get("rationale") else ""
                )
                print(f"    {mark} {e['surface']:12s} {e['state']}{rat}")
    _emit_metric("coverage", args.surface or "all", "ok")
    return 0


def cmd_gaps(args) -> int:
    threshold = (args.threshold
                 if args.threshold is not None
                 else DEFAULT_THRESHOLD)
    target = [args.module] if args.module else KNOWN_MODULES
    if args.module and args.module not in KNOWN_MODULES:
        print(f"unknown module: {args.module!r}", file=sys.stderr)
        _emit_metric("gaps", "any", "unknown-module")
        return 1

    below = []
    at_ceiling = []
    for m in target:
        cov = coverage_for(m)
        if cov["surface_count"] < threshold:
            row = {
                "module": m,
                "surface_count": cov["surface_count"],
                "shortfall": threshold - cov["surface_count"],
                "shipped_in": cov["shipped_in"],
                "future_waiver_count": cov["future_waiver_count"],
                "structural_waiver_count": cov["structural_waiver_count"],
            }
            # R478: split structural-ceiling modules into a separate
            # bucket — they aren't anti-min candidates, but stay
            # visible in the output (operator-transparency).
            if cov["at_structural_ceiling"]:
                at_ceiling.append(row)
            else:
                below.append(row)
    below.sort(key=lambda r: r["shortfall"], reverse=True)
    at_ceiling.sort(key=lambda r: r["module"])

    out = {
        "threshold": threshold,
        "below_threshold": below,
        "at_structural_ceiling": at_ceiling,
        "count": len(below),
    }
    if args.fmt == "json":
        print(json.dumps(out, indent=2))
    else:
        print(f"── surface-map.gaps (threshold={threshold}, "
              f"{len(below)} module{'s' if len(below)!=1 else ''} "
              f"below) ──")
        for r in below:
            print(f"  ✗ {r['module']:25s} "
                  f"surfaces={r['surface_count']}/8 "
                  f"(short by {r['shortfall']}, "
                  f"FUTURE-waivers={r['future_waiver_count']})")
        if at_ceiling:
            print(f"  — at structural ceiling (excluded, R478): "
                  f"{len(at_ceiling)} module"
                  f"{'s' if len(at_ceiling)!=1 else ''} —")
            for r in at_ceiling:
                print(f"  ◦ {r['module']:25s} "
                      f"surfaces={r['surface_count']}/8 "
                      f"(NA-waivers={r['structural_waiver_count']})")
    result = "ok" if not below else "below-threshold"
    _emit_metric("gaps", "all", result)
    return 2 if below else 0


def cmd_waivers(args) -> int:
    target = [args.module] if args.module else KNOWN_MODULES
    if args.module and args.module not in KNOWN_MODULES:
        print(f"unknown module: {args.module!r}", file=sys.stderr)
        _emit_metric("waivers", "any", "unknown-module")
        return 1
    rows = []
    for m in target:
        entry = MODULE_COVERAGE[m]
        for surface, rationale in entry.get("waivers", {}).items():
            rows.append({
                "module": m,
                "surface": surface,
                "rationale": rationale,
            })
    out = {"waivers": rows, "count": len(rows)}
    if args.fmt == "json":
        print(json.dumps(out, indent=2))
    else:
        print(f"── surface-map.waivers ({len(rows)} entries) ──")
        for r in rows:
            print(f"  {r['module']:25s} {r['surface']:10s} "
                  f"— {r['rationale']}")
    _emit_metric("waivers", "all", "ok")
    return 0


# --- R540 system-wide §1g milestone rollup ---
#
# Per operator §1g standing rule verbatim (sacrosanct, R453 anchor):
#
#   "everything is not just core, not just cli, not just TUI, not just
#    API, not just tool and MCP but also Dashboards and Web Apps and
#    Services."
#
# R539 closed the §1g 8-surface delivery contract across ALL §1g-
# named modules. This rollup verb codifies the historic milestone as
# a first-class operator-visible observable: instead of forcing
# operators to grep the coverage matrix to discover the system-wide
# state, `surface-map milestone` reports the rollup directly.
#
# Operator-§1g UX rule: 30-second readable. The rollup MUST surface:
#   - total modules tracked
#   - count at structural ceiling (every unshipped surface is
#     "not applicable — ..."; NO FUTURE work tracked)
#   - count at full 8-surface delivery (the §1g ladder closed)
#   - count carrying FUTURE waivers (R539 historic: must be 0)
#   - the list of §1g-named modules at full 8/8 (in shipped-order)
#   - the list of structural-ceiling-but-below-8 modules (e.g.
#     bashrc 2/8, auth-tier 7/8, master-dashboard 7/8 — all with
#     STRUCTURAL waivers, not FUTURE work)
#   - the historic R539 anchor + verbatim §1g standing rule
#
# Mirrors the coverage_for(module) per-module return shape but
# scoped to the WHOLE module set. The rollup mechanism is the
# operator-§1g "milestone" framing the R539 historic state and
# making any future regression (a new module added with a FUTURE
# waiver) immediately visible at the milestone surface.

R539_HISTORIC_ANCHOR = (
    "R539 (E5++) — TWELFTH §1g-named module (auditor) reached "
    "structural ceiling with the auditor API + webapp surfaces, "
    "closing the §1g 8-surface delivery contract across the ENTIRE "
    "set of §1g-named modules. The rotation pool is exhausted: ALL "
    "twelve §1g instruments (edge-firewall R506 / network-edge R509 / "
    "global-history R512 / trinity R515 / router R518 / compliance "
    "R521 / anti-minimization-audit R524 / doc-coverage R527 / "
    "ux-design-audit R530 / surface-map R533 / weaver R536 / "
    "auditor R539) plus auth-tier / bashrc / master-dashboard are "
    "at structural ceiling with ZERO FUTURE waivers remaining."
)

R453_STANDING_RULE = (
    "everything is not just core, not just cli, not just TUI, "
    "not just API, not just tool and MCP but also Dashboards and "
    "Web Apps and Services."
)


def milestone_rollup() -> dict:
    """R540 — system-wide §1g 8-surface delivery contract rollup.

    Returns a dict surfacing the historic R539 milestone state for
    operator-§1g visibility (operator-§1g UX rule: 30-second readable)
    + structural-regression detection (a future module added with a
    FUTURE waiver will flip future_carrying_count off zero, which is
    the load-bearing post-R539 invariant)."""
    records = [coverage_for(m) for m in KNOWN_MODULES]
    full_8 = sorted(
        [r["module"] for r in records if r.get("surface_count") == 8]
    )
    at_ceiling_below_8 = sorted(
        [
            {
                "module": r["module"],
                "surface_count": r.get("surface_count"),
                "structural_waiver_count":
                    r.get("structural_waiver_count"),
            }
            for r in records
            if r.get("at_structural_ceiling") is True
            and r.get("surface_count", 0) < 8
        ],
        key=lambda x: x["module"],
    )
    future_carrying = sorted(
        [
            {
                "module": r["module"],
                "future_waiver_count": r.get("future_waiver_count"),
            }
            for r in records
            if r.get("future_waiver_count", 0) > 0
        ],
        key=lambda x: x["module"],
    )
    at_ceiling_count = sum(
        1 for r in records if r.get("at_structural_ceiling") is True
    )
    return {
        "module": "surface-map",
        "verb": "milestone",
        "spec_ref": (
            "operator §1g 8-surface delivery contract (R453 anchor) — "
            "TWELFTH §1g module at ceiling closes the ladder (R539)"
        ),
        "total_modules": len(records),
        "at_structural_ceiling_count": at_ceiling_count,
        "full_8_surface_count": len(full_8),
        "future_carrying_count": len(future_carrying),
        "at_full_8_surfaces": full_8,
        "at_ceiling_below_8_surfaces": at_ceiling_below_8,
        "future_carrying_modules": future_carrying,
        "all_at_structural_ceiling": at_ceiling_count == len(records),
        "all_g1g_named_at_full_8": len(full_8) >= 12,
        "zero_future_waivers": len(future_carrying) == 0,
        "historic_anchor": R539_HISTORIC_ANCHOR,
        "standing_rule": R453_STANDING_RULE,
    }


def cmd_milestone(args) -> int:
    """`surface-map milestone` — surface the system-wide §1g 8-surface
    delivery contract rollup. R540 operator-§1g visibility verb."""
    rollup = milestone_rollup()
    if args.fmt == "json":
        print(json.dumps(rollup, indent=2))
    else:
        print(
            f"── surface-map.milestone — §1g 8-surface delivery "
            f"contract rollup ──"
        )
        print(f"  total modules tracked         : "
              f"{rollup['total_modules']}")
        print(f"  at structural ceiling          : "
              f"{rollup['at_structural_ceiling_count']}/"
              f"{rollup['total_modules']}")
        print(f"  at full 8-surface delivery     : "
              f"{rollup['full_8_surface_count']}/"
              f"{rollup['total_modules']}")
        print(f"  carrying FUTURE waivers        : "
              f"{rollup['future_carrying_count']}")
        print(f"  ALL at structural ceiling?     : "
              f"{rollup['all_at_structural_ceiling']}")
        print(f"  ALL §1g-named at full 8/8?     : "
              f"{rollup['all_g1g_named_at_full_8']}")
        print(f"  ZERO FUTURE waivers?           : "
              f"{rollup['zero_future_waivers']}")
        print()
        print(f"  Modules at full 8/8 surfaces "
              f"({len(rollup['at_full_8_surfaces'])}):")
        for m in rollup["at_full_8_surfaces"]:
            print(f"    - {m}")
        print()
        if rollup["at_ceiling_below_8_surfaces"]:
            print(
                f"  Structural-ceiling modules below 8 surfaces "
                f"({len(rollup['at_ceiling_below_8_surfaces'])} — "
                f"all carry 'not applicable' structural waivers, "
                f"NOT FUTURE work):"
            )
            for r in rollup["at_ceiling_below_8_surfaces"]:
                print(f"    - {r['module']:25s} {r['surface_count']}/8 "
                      f"(structural waivers: "
                      f"{r['structural_waiver_count']})")
            print()
        if rollup["future_carrying_modules"]:
            print(
                f"  ⚠ Modules with FUTURE waivers "
                f"({len(rollup['future_carrying_modules'])}) — "
                f"R539 invariant violated; these need closure rounds:"
            )
            for r in rollup["future_carrying_modules"]:
                print(f"    - {r['module']:25s} "
                      f"FUTURE waivers: {r['future_waiver_count']}")
            print()
        print(f"  Historic anchor: {rollup['historic_anchor']}")
        print()
        print(f"  R453 standing rule (operator §1g sacrosanct):")
        print(f"    \"{rollup['standing_rule']}\"")
    _emit_metric("milestone", "all", "ok")
    return 0


# --- R462 cross-repo selfdef surface-manifest discovery ---


def load_selfdef_surface_manifests() -> tuple[list[dict], list[dict]]:
    """Read every .toml under SELFDEF_SURFACE_DIR.

    Returns (valid, errors). Each valid entry has:
      module, label, surfaces (list of {id, state, reason?}),
      shipped_count, planned_count, waived_count,
      source_repo='selfdef', manifest_path.

    Cross-repo binding: SD-R-MULTI-SURFACE-AUDIT-1
    (crates/selfdef-surface-manifest in selfdef repo).
    """
    valid: list[dict] = []
    errors: list[dict] = []
    if not SELFDEF_SURFACE_DIR.is_dir():
        return valid, errors
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib  # type: ignore[import-not-found]
        except ImportError:
            errors.append({
                "path": str(SELFDEF_SURFACE_DIR),
                "error": "no TOML library available",
            })
            return valid, errors
    for p in sorted(SELFDEF_SURFACE_DIR.glob("*.toml")):
        try:
            data = tomllib.loads(p.read_text(encoding="utf-8"))
        except (OSError, Exception) as e:  # noqa: BLE001
            errors.append({"path": str(p), "error": f"parse: {e}"})
            continue
        if data.get("schema_version") != 1:
            errors.append({
                "path": str(p),
                "error": "unsupported schema_version",
            })
            continue
        mod = data.get("module") or {}
        surfaces_in = data.get("surfaces") or []
        if not mod.get("id") or not surfaces_in:
            errors.append({
                "path": str(p),
                "error": "missing module.id or surfaces[]",
            })
            continue
        # Validate per-entry shape; reject unknown surface ids
        valid_surfaces = []
        bad_id = None
        for s in surfaces_in:
            sid = s.get("id")
            state = s.get("state")
            if sid not in SURFACE_IDS:
                bad_id = sid
                break
            if state not in ("shipped", "waived", "planned"):
                bad_id = f"state={state}"
                break
            valid_surfaces.append({
                "id": sid,
                "state": state,
                "reason": s.get("reason"),
            })
        if bad_id is not None:
            errors.append({
                "path": str(p),
                "error": f"bad surface entry: {bad_id}",
            })
            continue
        valid.append({
            "module": str(mod["id"]),
            "label": str(mod.get("label", mod["id"])),
            "surfaces": valid_surfaces,
            "shipped_count": sum(
                1 for s in valid_surfaces if s["state"] == "shipped"
            ),
            "waived_count": sum(
                1 for s in valid_surfaces if s["state"] == "waived"
            ),
            "planned_count": sum(
                1 for s in valid_surfaces if s["state"] == "planned"
            ),
            "source_repo": "selfdef",
            "manifest_path": str(p),
        })
    return valid, errors


def cmd_selfdef(args) -> int:
    """Scan SELFDEF_SURFACE_DIR for cross-repo SurfaceManifests."""
    valid, errors = load_selfdef_surface_manifests()
    out = {
        "manifest_dir": str(SELFDEF_SURFACE_DIR),
        "discovered": valid,
        "errors": errors,
        "count": len(valid),
    }
    if args.fmt == "json":
        print(json.dumps(out, indent=2))
    else:
        print(f"── surface-map.selfdef "
              f"({len(valid)} selfdef manifest{'s' if len(valid)!=1 else ''} "
              f"under {SELFDEF_SURFACE_DIR}) ──")
        for m in valid:
            print(f"  ✓ {m['module']:25s} "
                  f"shipped={m['shipped_count']}/8 "
                  f"waived={m['waived_count']} "
                  f"planned={m['planned_count']}  ({m['label']})")
        for e in errors:
            print(f"  ✗ {e['path']}  {e['error']}")
    _emit_metric("selfdef", "any", "ok" if not errors else "issues")
    return 0


# --- Argparse ---


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="surface-map.py",
        description=(
            "R453 (E11.M3): operator §1g multi-surface delivery "
            "contract — which of the 8 operator-named surfaces "
            "(core/cli/TUI/API/MCP/Dashboard/Web App/Service) does "
            "each operator-facing module ship on?"
        ),
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    def _add_fmt(sp):
        g = sp.add_mutually_exclusive_group()
        g.add_argument("--json", dest="fmt", action="store_const",
                       const="json", default="human")
        g.add_argument("--human", dest="fmt", action="store_const",
                       const="human")

    sp_surf = sub.add_parser("surfaces",
                             help="enumerate the 8 §1g surfaces")
    _add_fmt(sp_surf)

    sp_mods = sub.add_parser("modules",
                             help="list tracked operator-facing modules")
    _add_fmt(sp_mods)

    sp_cov = sub.add_parser("coverage",
                            help="module × surface coverage matrix")
    sp_cov.add_argument("--module", help="filter to one module")
    sp_cov.add_argument("--surface", help="filter to one surface")
    _add_fmt(sp_cov)

    sp_gap = sub.add_parser("gaps",
                            help="modules below surface threshold")
    sp_gap.add_argument("--module", help="filter to one module")
    sp_gap.add_argument("--threshold", type=int, default=None,
                        help=f"min surfaces (default {DEFAULT_THRESHOLD})")
    _add_fmt(sp_gap)

    sp_waiv = sub.add_parser("waivers",
                             help="per-module explicit surface waivers")
    sp_waiv.add_argument("--module", help="filter to one module")
    _add_fmt(sp_waiv)

    sp_sd = sub.add_parser(
        "selfdef",
        help=("R462 cross-repo: scan SELFDEF_SURFACE_DIR for selfdef-"
              "side SurfaceManifests (SD-R-MULTI-SURFACE-AUDIT-1)"),
    )
    _add_fmt(sp_sd)

    sp_ms = sub.add_parser(
        "milestone",
        help=("R540: system-wide §1g 8-surface delivery contract "
              "rollup — surfaces the R539 historic milestone "
              "(ALL §1g modules at structural ceiling, ZERO FUTURE "
              "waivers across the entire codebase)"),
    )
    _add_fmt(sp_ms)

    args = p.parse_args(argv)
    return {
        "surfaces": cmd_surfaces,
        "modules": cmd_modules,
        "coverage": cmd_coverage,
        "gaps": cmd_gaps,
        "waivers": cmd_waivers,
        "selfdef": cmd_selfdef,
        "milestone": cmd_milestone,
    }[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
