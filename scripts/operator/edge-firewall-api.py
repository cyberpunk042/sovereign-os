#!/usr/bin/env python3
"""
scripts/operator/edge-firewall-api.py — Read-only HTTP API for the
edge-firewall workstation-side enforcement-candidate registry
(R504, E11.M9++).

Per operator §1g verbatim (sacrosanct):

  "We do not minimize anything."

Per operator §1g 8-surface delivery contract (verbatim):

  "everything is not just core, not just cli, not just TUI, not just
  API, not just tool and MCP but also Dashboards and Web Apps and
  Services"

This ships the `api` surface of the §1g 8-surface delivery ladder for
the `edge-firewall` module. The CLI (`sovereign-osctl edge-firewall
<verb>`) already covers ad-hoc operator queries; this API surface gives
OTHER consumers (the upcoming MCP server, the upcoming webapp tier-3
shell, automation scripts, monitoring) a stable wire contract.

Sovereignty (stdlib-only — zero added deps):
  - http.server.HTTPServer + BaseHTTPRequestHandler
  - Loopback-bind by default (127.0.0.1)
  - Read-only verbs only (mutation `install` + interactive `wizard`
    stay CLI-only — operator §17 sacrosanct sovereignty boundary)

Read-only endpoints (R504 v1, R506 webapp):
  GET /version                     — service version + module identity
  GET /state                       — local + upstream firewall state
  GET /candidates                  — CANDIDATES registry (5 options)
  GET /recommend                   — recommendations for current state
  GET /install-plan?candidate=<id> — install plan for a named candidate
  GET /healthz                     — API daemon liveness (always 200)
  GET /webapp/                     — single-file operator-§1g webapp (R506)
  GET /webapp/index.html           — alias for /webapp/

Layer-B metric (sister to the CLI's `_query_total{verb,candidate,result}`):

  sovereign_os_operator_edge_firewall_api_request_total{endpoint,result}

Env vars (all overridable):
  EDGE_FIREWALL_API_BIND          (default: 127.0.0.1)
  EDGE_FIREWALL_API_PORT          (default: 8092)
  SOVEREIGN_OS_METRICS_DIR        (default: /var/lib/node_exporter/textfile_collector)
  EDGE_FIREWALL_API_DRY_RUN       (default: unset; set to 1 = print and exit)
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

# The HTTP plumbing (json / http.server / urllib) lives in _api_daemon.py now
# (F-2026-070) — imported below once the module dir is on sys.path.

API_BIND = os.environ.get("EDGE_FIREWALL_API_BIND", "127.0.0.1")
API_PORT = int(os.environ.get("EDGE_FIREWALL_API_PORT", "8092"))
DRY_RUN = bool(os.environ.get("EDGE_FIREWALL_API_DRY_RUN"))

METRICS_DIR = os.environ.get(
    "SOVEREIGN_OS_METRICS_DIR",
    "/var/lib/node_exporter/textfile_collector",
)

# HELP sovereign_os_operator_edge_firewall_api_request_total edge-firewall
#   read-only REST API request count (endpoint, result).
# TYPE sovereign_os_operator_edge_firewall_api_request_total counter
METRIC_NAME = "sovereign_os_operator_edge_firewall_api_request_total"

API_VERSION = "1.1.0-R506"

# R506 webapp surface — single-file monochrome SPA shipped under
# webapp/edge-firewall/index.html in the repo. Operator can override
# the on-disk path via env (e.g., post-install relocation to
# /usr/share).
_REPO_ROOT = Path(__file__).resolve().parents[2]
_WEBAPP_DEFAULT = _REPO_ROOT / "webapp" / "edge-firewall" / "index.html"
WEBAPP_PATH = Path(os.environ.get(
    "EDGE_FIREWALL_WEBAPP_PATH", str(_WEBAPP_DEFAULT)
))

# edge-firewall CLI module — import directly so the API serves from
# the SAME data model the operator-facing CLI uses (no drift).
_THIS_DIR = Path(__file__).resolve().parent
_EF_PATH = _THIS_DIR / "edge-firewall.py"
_spec = importlib.util.spec_from_file_location("_ef_core", _EF_PATH)
if _spec is None or _spec.loader is None:
    sys.stderr.write(
        f"[FATAL STRUCTURAL FRICTION] cannot load edge-firewall.py "
        f"from {_EF_PATH}\n"
    )
    sys.exit(1)
_ef = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ef)

# Shared read-only daemon scaffold (F-2026-070) — the HTTP plumbing every
# sovereign-*-api carried verbatim now lives in _api_daemon.py. This module keeps
# its own identity, port, routes, and 405 message.
sys.path.insert(0, str(_THIS_DIR))
import _api_daemon  # noqa: E402


def _state_payload() -> dict:
    return {
        "local": _ef.detect_local_state(),
        "upstream": _ef.detect_upstream_state(),
    }


def _candidates_payload() -> dict:
    return {
        "count": len(_ef.CANDIDATES),
        "candidates": _ef.CANDIDATES,
        "known_candidate_ids": _ef.KNOWN_CANDIDATE_IDS,
    }


def _recommend_payload() -> dict:
    local = _ef.detect_local_state()
    upstream = _ef.detect_upstream_state()
    recs = _ef.recommend_for_state(local, upstream)
    return {
        "upstream_tier": upstream.get("tier", "unknown"),
        "count": len(recs),
        "recommendations": recs,
    }


def _install_plan_payload(candidate_id: str) -> tuple[int, dict]:
    if not candidate_id:
        return 400, {
            "error": "missing required query param: candidate",
            "known": _ef.KNOWN_CANDIDATE_IDS,
        }
    cand = _ef._candidate(candidate_id)
    if cand is None:
        return 404, {
            "error": f"unknown candidate: {candidate_id!r}",
            "known": _ef.KNOWN_CANDIDATE_IDS,
        }
    plan = {
        "candidate": cand["id"],
        "label": cand["label"],
        "perf_cost_disclosed": cand["perf_cost"],
        "apt_packages": cand["apt_packages"],
        "systemd_units": cand["systemd_units"],
        "config_paths_touched": cand["config_paths"],
        "install_steps": [
            "apt-get update",
            f"apt-get install -y {' '.join(cand['apt_packages'])}",
            *[f"systemctl enable {u}" for u in cand["systemd_units"]],
            *[f"systemctl start {u}" for u in cand["systemd_units"]],
        ],
        "rollback_steps": [
            *[f"systemctl stop {u}" for u in cand["systemd_units"]],
            *[f"systemctl disable {u}" for u in cand["systemd_units"]],
            f"apt-get remove -y {' '.join(cand['apt_packages'])}",
        ],
        "next_action": (
            f"Run via CLI: sovereign-osctl edge-firewall install "
            f"{cand['id']} --apply --confirm-install"
        ),
        "wire_contract": (
            "This is a PLAN — read-only. Actual mutation requires "
            "the CLI `install` verb with --apply --confirm-install "
            "(operator §17 sovereignty boundary)."
        ),
    }
    return 200, plan


def _version_payload() -> dict:
    return {
        "module": "edge-firewall-api",
        "version": API_VERSION,
        "shipped_in": "R504 (E11.M9++) + R505 (E11.M9++ MCP surface) + R506 (E11.M9++ webapp surface)",
        "source": "scripts/operator/edge-firewall-api.py",
        "data_source": str(_EF_PATH),
        "webapp_path": str(WEBAPP_PATH),
        "surfaces": ["core", "cli", "tui", "dashboard", "api", "service",
                     "mcp", "webapp"],
        "standing_rule": "We do not minimize anything.",
    }


def _spec_for() -> "_api_daemon.DaemonSpec":
    """Build this daemon's DaemonSpec. Every endpoint (including /install-plan's
    query-param 400/404 semantics), status code, header, and metric label is
    preserved from the prior hand-written handler; only the shared HTTP plumbing
    moved to _api_daemon."""
    return _api_daemon.DaemonSpec(
        module="edge-firewall-api",
        webapp_module="edge-firewall-webapp",
        version=API_VERSION,
        metric_name=METRIC_NAME,
        prom_basename="sovereign-os-edge-firewall-api.prom",
        metrics_dir=METRICS_DIR,
        webapp_path=WEBAPP_PATH,
        data_source=str(_EF_PATH),
        endpoints_line=("/version /state /candidates /recommend "
                        "/install-plan + /healthz"),
        reject_error=(
            "read-only surface — mutation verbs `install` and interactive "
            "`wizard` stay CLI-only (operator §17 sovereignty boundary). Use "
            "sovereign-osctl edge-firewall install/wizard."),
        available=["/version", "/state", "/candidates", "/recommend",
                   "/install-plan", "/healthz", "/webapp/"],
        routes={
            "/version": ("version", lambda q: (200, _version_payload())),
            "/state": ("state", lambda q: (200, _state_payload())),
            "/candidates": ("candidates", lambda q: (200, _candidates_payload())),
            "/recommend": ("recommend", lambda q: (200, _recommend_payload())),
            # /install-plan preserves the query-param + 400/404 contract: the
            # handler returns (status, payload) straight from _install_plan_payload.
            "/install-plan": ("install_plan",
                              lambda q: _install_plan_payload(
                                  (q.get("candidate") or [""])[0])),
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
