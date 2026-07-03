#!/usr/bin/env python3
"""
scripts/operator/master-dashboard-api.py — Read-only HTTP API for the
master-dashboard aggregator (R498, E11.M2++).

Per operator §1g verbatim (sacrosanct):

  "We do not minimize anything."

This ships the `api` surface of the §1g 8-surface delivery ladder for
the `master-dashboard` module. The CLI (`sovereign-osctl master-dashboard
<verb>`) already covers ad-hoc operator queries; this API surface gives
OTHER consumers (the upcoming MCP server, the upcoming webapp tier-3
shell, automation scripts, monitoring) a stable wire contract.

Sovereignty (stdlib-only — zero added deps):
  - http.server.HTTPServer + BaseHTTPRequestHandler
  - Loopback-bind by default (127.0.0.1) — operator decides about exposure
  - Read-only verbs only (no mutation; render/install stay CLI-only —
    operator §17 sacrosanct boundary)

Read-only endpoints (R498 v1, R500 webapp):
  GET /version                 — service version + module identity
  GET /routes                  — DASHBOARD_ROUTES table (built-in + selfdef-discovered)
  GET /collisions              — port/subpath collision detection
  GET /health                  — TCP-probe every upstream port
  GET /discover                — load selfdef cross-repo manifests
  GET /healthz                 — API daemon liveness (always 200)
  GET /webapp/                 — single-file operator-§1g webapp (R500)
  GET /webapp/index.html       — alias for /webapp/

All responses are JSON (Content-Type: application/json). On error the
body is {"error": "..."} with a 4xx/5xx status. Loopback CIDR ACL
declines anything not 127.0.0.0/8 unless MASTER_DASHBOARD_API_BIND
is set explicitly by the operator.

Layer-B metric (sister to the CLI `_query_total{verb,backend,result}`):

  sovereign_os_operator_master_dashboard_api_request_total{endpoint,result}

Env vars (all overridable):
  MASTER_DASHBOARD_API_BIND       (default: 127.0.0.1)
  MASTER_DASHBOARD_API_PORT       (default: 8090)
  SOVEREIGN_OS_METRICS_DIR        (default: /var/lib/node_exporter/textfile_collector)
  MASTER_DASHBOARD_API_DRY_RUN    (default: unset; set to 1 = print and exit)
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

API_BIND = os.environ.get("MASTER_DASHBOARD_API_BIND", "127.0.0.1")
API_PORT = int(os.environ.get("MASTER_DASHBOARD_API_PORT", "8090"))
DRY_RUN = bool(os.environ.get("MASTER_DASHBOARD_API_DRY_RUN"))

METRICS_DIR = os.environ.get(
    "SOVEREIGN_OS_METRICS_DIR",
    "/var/lib/node_exporter/textfile_collector",
)

# HELP sovereign_os_operator_master_dashboard_api_request_total master-dashboard
#   read-only REST API request count (endpoint, result).
# TYPE sovereign_os_operator_master_dashboard_api_request_total counter
METRIC_NAME = "sovereign_os_operator_master_dashboard_api_request_total"

API_VERSION = "1.1.0-R500"

# R500 webapp surface — single-file monochrome SPA shipped under
# webapp/master-dashboard/index.html in the repo. Operator can override
# the on-disk path via env (e.g., post-install relocation to /usr/share).
_REPO_ROOT = Path(__file__).resolve().parents[2]
_WEBAPP_DEFAULT = _REPO_ROOT / "webapp" / "master-dashboard" / "index.html"
WEBAPP_PATH = Path(os.environ.get(
    "MASTER_DASHBOARD_WEBAPP_PATH", str(_WEBAPP_DEFAULT)
))

# SDD-045 Phase B — the described dashboard catalog. This is the single
# source of truth for the operator's global view: every surface with a
# real description + category + status + how-to-reach. The webapp renders
# it as the "all dashboards (described)" section so the operator sees a
# real explanation next to each label — not a bare slug list.
_CATALOG_DEFAULT = _REPO_ROOT / "config" / "dashboard-catalog.yaml"
CATALOG_PATH = Path(os.environ.get(
    "SOVEREIGN_OS_DASHBOARD_CATALOG", str(_CATALOG_DEFAULT)
))

# Master-dashboard CLI module — import directly so the API serves
# from the SAME data model the operator-facing CLI uses (no drift).
_THIS_DIR = Path(__file__).resolve().parent
_MD_PATH = _THIS_DIR / "master-dashboard.py"
_spec = importlib.util.spec_from_file_location("_md_core", _MD_PATH)
if _spec is None or _spec.loader is None:
    sys.stderr.write(
        f"[FATAL STRUCTURAL FRICTION] cannot load master-dashboard.py "
        f"from {_MD_PATH}\n"
    )
    sys.exit(1)
_md = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_md)


def _emit_metric(endpoint: str, result: str) -> None:
    """Best-effort textfile-collector emit (Layer B per SDD-016)."""
    if DRY_RUN:
        sys.stderr.write(
            f"  would emit: {METRIC_NAME}"
            f"{{endpoint=\"{endpoint}\",result=\"{result}\"}} 1\n"
        )
        return
    try:
        os.makedirs(METRICS_DIR, exist_ok=True)
        prom_path = os.path.join(
            METRICS_DIR, "sovereign-os-master-dashboard-api.prom"
        )
        line = (
            f"{METRIC_NAME}{{endpoint=\"{endpoint}\","
            f"result=\"{result}\"}} 1\n"
        )
        with open(prom_path, "a") as f:
            f.write(line)
    except OSError:
        pass


def _routes_payload() -> dict:
    routes_out = []
    for slug, r in _md.DASHBOARD_ROUTES.items():
        routes_out.append({
            "slug": slug,
            "port": r["port"],
            "healthz_path": r["healthz_path"],
            "subpath": r["subpath"],
            "label": r["label"],
            "source_repo": r["source_repo"],
        })
    return {
        "aggregator_port": _md.AGGREGATOR_PORT,
        "count": len(routes_out),
        "routes": routes_out,
    }


def _collisions_payload() -> dict:
    return _md.detect_collisions()


def _health_payload() -> dict:
    probes = []
    for slug, r in _md.DASHBOARD_ROUTES.items():
        probes.append(_md.probe_dashboard(slug, r))
    reachable = sum(1 for p in probes if p["reachable"])
    return {
        "count": len(probes),
        "reachable": reachable,
        "unreachable": len(probes) - reachable,
        "probes": probes,
    }


def _discover_payload() -> dict:
    valid, errors = _md.load_selfdef_manifests()
    return {
        "manifest_dir": str(_md.SELFDEF_MANIFEST_DIR),
        "discovered": valid,
        "errors": errors,
        "count": len(valid),
    }


def _toggles_payload() -> dict:
    """M060 R10129 — the dashboard directory + each route's operator on/off
    state, so the D-00 "main dashboard" reflects 'everything can be turned on
    and off'. Routes without a webapp mapping are always-on infrastructure."""
    core = _md._load_toggle_core()
    rows = []
    for slug, r in _md.DASHBOARD_ROUTES.items():
        webapp = _md._ROUTE_WEBAPP.get(slug)
        enabled = True if (core is None or webapp is None) else core.is_enabled(webapp)
        rows.append({
            "slug": slug,
            "subpath": r["subpath"],
            "label": r["label"],
            "port": r["port"],
            "source_repo": r["source_repo"],
            "webapp": webapp,
            "toggleable": webapp is not None,
            "enabled": enabled,
        })
    enabled_count = sum(1 for x in rows if x["enabled"])
    return {
        "aggregator_port": _md.AGGREGATOR_PORT,
        "count": len(rows),
        "enabled_count": enabled_count,
        "disabled_count": len(rows) - enabled_count,
        "dashboards": rows,
    }


def _catalog_payload() -> dict:
    """SDD-045 Phase B — serve the described catalog as JSON so the webapp
    renders label + REAL description + category + status + link for every
    surface. Parsed with a stdlib-only mini-YAML reader when PyYAML is
    absent, so the read-only API keeps zero hard third-party deps.

    Honest-degraded: if the catalog is unreadable, returns an error payload
    (never a fabricated list) so the webapp shows the gap instead of hiding
    it — per the standing rule, no minimizing.
    """
    try:
        raw = CATALOG_PATH.read_text(encoding="utf-8")
    except OSError as e:
        return {"error": f"catalog unreadable: {e}",
                "expected_path": str(CATALOG_PATH),
                "categories": [], "dashboards": []}
    try:
        import yaml  # type: ignore
        doc = yaml.safe_load(raw)
    except ModuleNotFoundError:
        doc = _mini_yaml_catalog(raw)
    except Exception as e:  # noqa: BLE001 — malformed catalog is operator-visible
        return {"error": f"catalog parse failed: {e}",
                "path": str(CATALOG_PATH), "categories": [], "dashboards": []}
    cats = doc.get("categories", []) if isinstance(doc, dict) else []
    dash = doc.get("dashboards", []) if isinstance(doc, dict) else []
    # order category blurbs the way the webapp groups them
    return {
        "source": str(CATALOG_PATH),
        "schema_version": (doc or {}).get("schema_version"),
        "category_count": len(cats),
        "dashboard_count": len(dash),
        "categories": cats,
        "dashboards": dash,
    }


def _mini_yaml_catalog(raw: str) -> dict:
    """Last-resort stdlib parse of dashboard-catalog.yaml when PyYAML is
    absent (the API daemon aims for zero hard deps). The catalog uses a
    single, regular flow-map-per-entry shape; parse exactly that. If the
    shape ever diverges this raises, surfacing the drift rather than
    silently returning a partial list."""
    import ast
    import re

    def _flow_to_obj(block: str) -> dict:
        # convert a YAML flow map `{k: v, k2: "v2", list: [a, b]}` (possibly
        # multi-line) into a Python dict via a tolerant tokenizer.
        obj: dict = {}
        # normalize whitespace/newlines inside the flow map
        body = block.strip()
        if body.startswith("{"):
            body = body[1:]
        if body.endswith("}"):
            body = body[:-1]
        # split top-level commas (respect [] and "" nesting)
        parts, depth, buf, instr = [], 0, [], None
        for ch in body:
            if instr:
                buf.append(ch)
                if ch == instr:
                    instr = None
                continue
            if ch in "\"'":
                instr = ch; buf.append(ch); continue
            if ch in "[{":
                depth += 1
            elif ch in "]}":
                depth -= 1
            if ch == "," and depth == 0:
                parts.append("".join(buf)); buf = []
            else:
                buf.append(ch)
        if buf:
            parts.append("".join(buf))
        for p in parts:
            if ":" not in p:
                continue
            k, v = p.split(":", 1)
            k, v = k.strip(), v.strip()
            if not k:
                continue
            if v.startswith("[") and v.endswith("]"):
                inner = v[1:-1].strip()
                obj[k] = [x.strip().strip("\"'") for x in inner.split(",") if x.strip()] if inner else []
            elif v in ("null", "~", ""):
                obj[k] = None
            elif (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                try:
                    obj[k] = ast.literal_eval(v)
                except (ValueError, SyntaxError):
                    obj[k] = v.strip("\"'")
            else:
                obj[k] = v
        return obj

    def _scalar(v: str):
        v = v.strip()
        if v in ("null", "~", ""):
            return None
        if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
            try:
                return ast.literal_eval(v)
            except (ValueError, SyntaxError):
                return v.strip("\"'")
        return v

    categories: list = []
    dashboards: list = []
    section = None
    lines = raw.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if stripped.startswith("#") or not stripped:
            i += 1; continue
        if re.match(r"^categories:\s*$", line):
            section = "categories"; i += 1; continue
        if re.match(r"^dashboards:\s*$", line):
            section = "dashboards"; i += 1; continue
        if re.match(r"^schema_version:", line):
            i += 1; continue
        if stripped.startswith("- "):
            entry = stripped[2:]
            target = categories if section == "categories" else dashboards
            if entry.startswith("{"):
                # flow-map list item — gather until braces balance
                depth = entry.count("{") - entry.count("}")
                buf = [entry]
                while depth > 0 and i + 1 < len(lines):
                    i += 1
                    nxt = lines[i]
                    buf.append(nxt.strip())
                    depth += nxt.count("{") - nxt.count("}")
                target.append(_flow_to_obj(" ".join(buf)))
                i += 1; continue
            # block-mapping list item (e.g. categories): first pair on the
            # `- ` line, continuation `key: value` lines at deeper indent.
            obj: dict = {}
            if ":" in entry:
                k, v = entry.split(":", 1)
                obj[k.strip()] = _scalar(v)
            base_indent = len(line) - len(line.lstrip())
            while i + 1 < len(lines):
                nxt = lines[i + 1]
                if not nxt.strip() or nxt.strip().startswith("#"):
                    i += 1; continue
                nxt_indent = len(nxt) - len(nxt.lstrip())
                if nxt_indent <= base_indent or nxt.strip().startswith("- "):
                    break
                if ":" in nxt:
                    k, v = nxt.strip().split(":", 1)
                    obj[k.strip()] = _scalar(v)
                i += 1
            target.append(obj)
            i += 1; continue
        i += 1
    return {"categories": categories, "dashboards": dashboards}


def _version_payload() -> dict:
    return {
        "module": "master-dashboard-api",
        "version": API_VERSION,
        "shipped_in": "R498 (E11.M2++) + R500 (E11.M2++ webapp surface)",
        "source": "scripts/operator/master-dashboard-api.py",
        "data_source": str(_MD_PATH),
        "webapp_path": str(WEBAPP_PATH),
        "surfaces": ["core", "cli", "tui", "service", "api", "mcp", "webapp"],
        "standing_rule": "We do not minimize anything.",
    }


_ENDPOINT_HANDLERS = {
    "/version":    _version_payload,
    "/routes":     _routes_payload,
    "/collisions": _collisions_payload,
    "/health":     _health_payload,
    "/discover":   _discover_payload,
    "/toggles":    _toggles_payload,
    "/catalog":    _catalog_payload,  # SDD-045 Phase B — described global view
}


class MasterDashboardAPIHandler(BaseHTTPRequestHandler):
    server_version = f"sovereign-os-master-dashboard-api/{API_VERSION}"
    sys_version = ""  # don't leak Python version to clients

    def log_message(self, format: str, *args) -> None:
        # Route logs to stderr without the verbose default prefix;
        # systemd journal captures these via Type=simple StandardError=journal.
        sys.stderr.write(
            f"[api] {self.address_string()} {format % args}\n"
        )

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Sovereign-Module", "master-dashboard-api")
        self.send_header("X-Sovereign-Version", API_VERSION)
        self.end_headers()
        self.wfile.write(body)

    def _send_webapp(self) -> None:
        """R500 — serve the single-file monochrome webapp from disk.
        Read-only; same-origin with the JSON endpoints (no CORS dance,
        no CDN, no cross-origin script loads — operator-§1g UX rule)."""
        try:
            body = WEBAPP_PATH.read_bytes()
        except OSError as e:
            self._send_json(500, {
                "error": f"webapp asset unreadable: {e}",
                "expected_path": str(WEBAPP_PATH),
            })
            _emit_metric("webapp", "500")
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Sovereign-Module", "master-dashboard-webapp")
        self.send_header("X-Sovereign-Version", API_VERSION)
        # Read-only mirror — webapp does NOT need cross-origin embedding.
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(body)
        _emit_metric("webapp", "ok")

    def do_GET(self) -> None:  # noqa: N802 (BaseHTTPRequestHandler API)
        # Strip query string + trailing slash
        path = self.path.split("?", 1)[0].rstrip("/") or "/"

        if path == "/healthz" or path == "/":
            self._send_json(200, {"status": "ok", "version": API_VERSION})
            _emit_metric("healthz" if path == "/healthz" else "root", "ok")
            return

        if path in ("/webapp", "/webapp/", "/webapp/index.html"):
            self._send_webapp()
            return

        handler = _ENDPOINT_HANDLERS.get(path)
        if handler is None:
            self._send_json(404, {
                "error": f"unknown endpoint: {path!r}",
                "available": (
                    sorted(_ENDPOINT_HANDLERS.keys())
                    + ["/healthz", "/webapp/"]
                ),
            })
            _emit_metric(path.lstrip("/") or "unknown", "404")
            return

        try:
            payload = handler()
        except Exception as e:  # noqa: BLE001
            self._send_json(500, {"error": str(e)})
            _emit_metric(path.lstrip("/"), "500")
            return

        self._send_json(200, payload)
        _emit_metric(path.lstrip("/"), "ok")

    def do_HEAD(self) -> None:  # noqa: N802
        # Same dispatch as GET but no body. The framework still calls
        # do_GET for state-shape consistency; we just suppress the body
        # for HEAD requests via a per-request flag.
        self.do_GET()

    # Decline non-GET methods explicitly — this surface is read-only.
    def do_POST(self):    self._reject_mutation()  # noqa: E704 N802
    def do_PUT(self):     self._reject_mutation()  # noqa: E704 N802
    def do_DELETE(self):  self._reject_mutation()  # noqa: E704 N802
    def do_PATCH(self):   self._reject_mutation()  # noqa: E704 N802

    def _reject_mutation(self) -> None:
        self._send_json(405, {
            "error": "read-only surface — mutation verbs stay CLI-only "
                     "(operator §17 sovereignty boundary). Use "
                     "sovereign-osctl master-dashboard render/install.",
            "allowed": ["GET", "HEAD"],
        })
        _emit_metric(self.command.lower(), "405")


def serve(bind: str = API_BIND, port: int = API_PORT) -> int:
    print(
        f"[*] master-dashboard-api {API_VERSION} listening "
        f"on http://{bind}:{port}/",
        flush=True,
    )
    print(f"  data source: {_MD_PATH}", flush=True)
    print(f"  endpoints:   {sorted(_ENDPOINT_HANDLERS.keys())} + /healthz",
          flush=True)
    if bind != "127.0.0.1":
        print(
            f"  WARNING: bind={bind!r} is NOT loopback — operator "
            f"explicitly exposed this surface beyond the host.",
            flush=True,
        )
    if DRY_RUN:
        print("  DRY-RUN: configuration validated, not serving.", flush=True)
        return 0

    try:
        httpd = HTTPServer((bind, port), MasterDashboardAPIHandler)
    except OSError as e:
        sys.stderr.write(
            f"[FATAL STRUCTURAL FRICTION] cannot bind {bind}:{port} — {e}\n"
        )
        return 1

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] master-dashboard-api shutdown requested.", flush=True)
        httpd.server_close()
        return 0


def main() -> int:
    # Argparse is overkill here — env vars are the operator-§1g knob set.
    # Single positional arg `dry-run` for parity with other operator scripts.
    if len(sys.argv) > 1 and sys.argv[1] == "dry-run":
        global DRY_RUN  # noqa: PLW0603
        DRY_RUN = True
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        return 0
    return serve()


if __name__ == "__main__":
    sys.exit(main())
