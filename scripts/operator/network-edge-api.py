#!/usr/bin/env python3
"""
scripts/operator/network-edge-api.py — Read-only HTTP API for the
network-edge / OPNsense detection surface (R507, E11.M8++).

Per operator §1g verbatim (sacrosanct):

  "We do not minimize anything."

Per operator §1g 8-surface delivery contract (verbatim):

  "everything is not just core, not just cli, not just TUI, not just
  API, not just tool and MCP but also Dashboards and Web Apps and
  Services"

This ships the `api` surface of the §1g 8-surface delivery ladder for
the `network-edge` module. The CLI (`sovereign-osctl network-edge
<verb>`) already covers ad-hoc operator queries; this API surface
gives OTHER consumers (the upcoming MCP server, the upcoming webapp
tier-3 shell, automation scripts, monitoring) a stable wire contract.

Sovereignty (stdlib-only — zero added deps):
  - http.server.HTTPServer + BaseHTTPRequestHandler
  - Loopback-bind by default (127.0.0.1)
  - Read-only verbs only (network-edge has no mutation verbs — the
    upstream OPNsense is queried, never modified by this surface;
    actual OPNsense config changes are operator-driven via the
    OPNsense UI / API directly, outside the sovereign-os boundary)

Read-only endpoints (R507 v1, R509 webapp v2):
  GET /version                     — service version + module identity
  GET /detect                      — full network-edge detection bundle
                                     (interfaces + gateway + nat-chain +
                                     vpn + opnsense + capabilities)
  GET /interfaces                  — per-interface state
  GET /nat-chain                   — NAT-layer visibility from
                                     workstation
  GET /opnsense/status             — OPNsense reachability + tier
  GET /opnsense/capabilities       — capability ladder for the
                                     current OPNsense tier
  GET /webapp/                     — R509 single-file monochrome SPA
                                     mirroring the read-only verbs
                                     (operator-§1g: zero external deps)
  GET /healthz                     — API daemon liveness (always 200)

Layer-B metric (sister to the CLI's `_query_total{verb,result}`):

  sovereign_os_operator_network_edge_api_request_total{endpoint,result}

Env vars (all overridable):
  NETWORK_EDGE_API_BIND          (default: 127.0.0.1)
  NETWORK_EDGE_API_PORT          (default: 8093)
  NETWORK_EDGE_WEBAPP_PATH       (default: <repo>/webapp/network-edge/index.html)
  SOVEREIGN_OS_METRICS_DIR       (default: /var/lib/node_exporter/textfile_collector)
  NETWORK_EDGE_API_DRY_RUN       (default: unset; set to 1 = print and exit)
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

# The HTTP plumbing (json / http.server / urllib) lives in _api_daemon.py now
# (F-2026-070) — imported below once the module dir is on sys.path.

API_BIND = os.environ.get("NETWORK_EDGE_API_BIND", "127.0.0.1")
API_PORT = int(os.environ.get("NETWORK_EDGE_API_PORT", "8093"))
DRY_RUN = bool(os.environ.get("NETWORK_EDGE_API_DRY_RUN"))

METRICS_DIR = os.environ.get(
    "SOVEREIGN_OS_METRICS_DIR",
    "/var/lib/node_exporter/textfile_collector",
)

# HELP sovereign_os_operator_network_edge_api_request_total network-edge
#   read-only REST API request count (endpoint, result).
# TYPE sovereign_os_operator_network_edge_api_request_total counter
METRIC_NAME = "sovereign_os_operator_network_edge_api_request_total"

API_VERSION = "1.1.0-R509"

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WEBAPP_DEFAULT = _REPO_ROOT / "webapp" / "network-edge" / "index.html"
WEBAPP_PATH = Path(os.environ.get(
    "NETWORK_EDGE_WEBAPP_PATH", str(_WEBAPP_DEFAULT)
))

# network-edge CLI module — import directly so the API serves from the
# SAME data model the operator-facing CLI uses (no drift). The CLI
# dispatches `network-edge` to `network-topology.py` (R449 lineage).
_THIS_DIR = Path(__file__).resolve().parent
_NE_PATH = _THIS_DIR / "network-topology.py"
_spec = importlib.util.spec_from_file_location("_ne_core", _NE_PATH)
if _spec is None or _spec.loader is None:
    sys.stderr.write(
        f"[FATAL STRUCTURAL FRICTION] cannot load network-topology.py "
        f"from {_NE_PATH}\n"
    )
    sys.exit(1)
_ne = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ne)

# Shared read-only daemon scaffold (F-2026-070) — the HTTP plumbing every
# sovereign-*-api carried verbatim now lives in _api_daemon.py. This module keeps
# its own identity, port, routes, and 405 message.
sys.path.insert(0, str(_THIS_DIR))
import _api_daemon  # noqa: E402


def _detect_payload() -> dict:
    interfaces = _ne.detect_interfaces()
    return {
        "interfaces_count": len(interfaces),
        "interfaces": interfaces,
        "default_gateway": _ne.detect_default_gateway(),
        "nat_chain": _ne.detect_nat_chain(),
        "vpn_bridge": _ne.detect_vpn_bridge(),
        "opnsense": _ne.detect_opnsense_state(),
        "capabilities": _ne.detect_capabilities(),
        "operator_named_edge_hardware":
            _ne.OPERATOR_NAMED_EDGE_HARDWARE,
    }


def _interfaces_payload() -> dict:
    interfaces = _ne.detect_interfaces()
    return {"count": len(interfaces), "interfaces": interfaces}


def _nat_chain_payload() -> dict:
    return _ne.detect_nat_chain()


def _opnsense_status_payload() -> dict:
    return _ne.detect_opnsense_state()


def _opnsense_capabilities_payload() -> dict:
    return _ne.detect_capabilities()


def _version_payload() -> dict:
    return {
        "module": "network-edge-api",
        "version": API_VERSION,
        "shipped_in": (
            "R507 (E11.M8++ read-only REST API + systemd service) + "
            "R508 (E11.M8++ MCP surface) + "
            "R509 (E11.M8++ webapp surface)"
        ),
        "source": "scripts/operator/network-edge-api.py",
        "data_source": str(_NE_PATH),
        "webapp_path": str(WEBAPP_PATH),
        "surfaces": [
            "core", "cli", "tui", "dashboard",
            "api", "service", "mcp", "webapp",
        ],
        "standing_rule": "We do not minimize anything.",
    }


def _spec_for(port_placeholder: None = None) -> "_api_daemon.DaemonSpec":
    """Build this daemon's DaemonSpec (identity + routes + 405 message). Every
    endpoint, status code, header, and metric label is preserved from the prior
    hand-written handler; only the shared HTTP plumbing moved to _api_daemon."""
    return _api_daemon.DaemonSpec(
        module="network-edge-api",
        webapp_module="network-edge-webapp",
        version=API_VERSION,
        metric_name=METRIC_NAME,
        prom_basename="sovereign-os-network-edge-api.prom",
        metrics_dir=METRICS_DIR,
        webapp_path=WEBAPP_PATH,
        data_source=str(_NE_PATH),
        endpoints_line=("/version /detect /interfaces /nat-chain "
                        "/opnsense/status /opnsense/capabilities /webapp/ "
                        "+ /healthz"),
        extra_banner=[f"  webapp:      {WEBAPP_PATH}"],
        reject_error=(
            "read-only surface — network-edge has no mutation verbs at any "
            "surface (operator §17 sovereignty boundary). OPNsense config "
            "changes are operator-driven via the OPNsense UI / API directly, "
            "outside the sovereign-os boundary."),
        available=["/version", "/detect", "/interfaces", "/nat-chain",
                   "/opnsense/status", "/opnsense/capabilities", "/webapp/",
                   "/healthz"],
        routes={
            "/version": ("version", lambda q: (200, _version_payload())),
            "/detect": ("detect", lambda q: (200, _detect_payload())),
            "/interfaces": ("interfaces", lambda q: (200, _interfaces_payload())),
            "/nat-chain": ("nat_chain", lambda q: (200, _nat_chain_payload())),
            "/opnsense/status":
                ("opnsense_status", lambda q: (200, _opnsense_status_payload())),
            "/opnsense/capabilities":
                ("opnsense_capabilities",
                 lambda q: (200, _opnsense_capabilities_payload())),
        },
        is_dry_run=lambda: DRY_RUN,
    )


def serve(bind: str = API_BIND, port: int = API_PORT) -> int:
    return _api_daemon.serve(_spec_for(), bind, port)


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "dry-run":
        global DRY_RUN  # noqa: PLW0603
        DRY_RUN = True
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        return 0
    return serve()


if __name__ == "__main__":
    sys.exit(main())
