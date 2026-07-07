#!/usr/bin/env python3
"""scripts/operator/models-catalog-api.py — read-only HTTP API + webapp host
for the D-23 "Model Catalog" cockpit dashboard.

Flips the dashboard-catalog `models-catalog` planned surface to live. Shows
the full canonical model registry (models/catalog.yaml) — all models with
their tier / class / engine / quantization / params / context / license /
purpose — the browse-the-portfolio view (distinct from D-03 which shows the
LIVE serving health of the currently-bound models).

Reuses the SAME catalog reader the D-03 model-health core + CLI use
(scripts/inference/model-health.py `load_catalog`), so the catalog view and
`sovereign-osctl models` never drift.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."

Sovereignty (stdlib-only, zero deps): loopback-bind, READ-ONLY (model
lifecycle is signed `sovereign-osctl models …` CLI verbs, never web
mutations — R10212). do_POST/PUT/DELETE fail-closed 405.

Endpoints (the exact contract webapp/d-23-models-catalog/index.html fetches):
  GET /api/models-catalog/catalog     all models grouped by tier
  GET /api/models-catalog/stream      Server-Sent Events (catalog-change)
  GET /webapp/ | /webapp/index.html   the D-23 single-file dashboard
  GET /version | /healthz | /

Env (all overridable):
  MODELS_CATALOG_API_BIND      (default 127.0.0.1)
  MODELS_CATALOG_API_PORT      (default 8123)
  MODELS_CATALOG_API_DRY_RUN   (set=1 → print config + exit)
  MODELS_CATALOG_WEBAPP_PATH   (override the on-disk webapp asset)
  MODELS_CATALOG_STREAM_INTERVAL (SSE push seconds, default 10.0)
  SOVEREIGN_OS_METRICS_DIR     (node_exporter textfile collector dir)
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

API_BIND = os.environ.get("MODELS_CATALOG_API_BIND", "127.0.0.1")
API_PORT = int(os.environ.get("MODELS_CATALOG_API_PORT", "8123"))
DRY_RUN = bool(os.environ.get("MODELS_CATALOG_API_DRY_RUN"))
STREAM_INTERVAL = float(os.environ.get("MODELS_CATALOG_STREAM_INTERVAL", "10.0"))
CPUINFO = None  # unused; kept parallel to sibling daemons
API_VERSION = "1.0.0"
SHIPPED_IN = "D-23-models-catalog"

METRICS_DIR = os.environ.get(
    "SOVEREIGN_OS_METRICS_DIR", "/var/lib/node_exporter/textfile_collector",
)
METRIC_NAME = "sovereign_os_operator_models_catalog_api_request_total"

_REPO_ROOT = Path(__file__).resolve().parents[2]
WEBAPP_PATH = Path(os.environ.get(
    "MODELS_CATALOG_WEBAPP_PATH",
    str(_REPO_ROOT / "webapp" / "d-23-models-catalog" / "index.html"),
))

# Reuse the SAME catalog reader as D-03 + the CLI (no drift).
_CORE_PATH = _REPO_ROOT / "scripts" / "inference" / "model-health.py"
_spec = importlib.util.spec_from_file_location("_modelhealth_core", _CORE_PATH)
if _spec is None or _spec.loader is None:
    sys.stderr.write(f"[FATAL STRUCTURAL FRICTION] cannot load {_CORE_PATH}\n")
    sys.exit(1)
_core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_core)

_CONTROL_SYSTEMS_FILE = _REPO_ROOT / "config" / "control-systems.yaml"

TIER_ORDER = ["pulse", "logic", "oracle", "router"]
TIER_LABEL = {
    "pulse": "Pulse — Conductor (CPU / bitnet.cpp ternary)",
    "logic": "Logic — Logic Engine (GPU 0)",
    "oracle": "Oracle — Oracle Core (GPU 1, Blackwell)",
    "router": "Router — RAG / draft / rerank helpers",
}


def _load_control_systems():
    """SDD-045 control-surface registry served at GET /control-systems. yaml
    is an optional dependency — degrade to empty (never raise) when absent."""
    try:
        import yaml  # optional
    except ImportError:
        return None
    try:
        return yaml.safe_load(_CONTROL_SYSTEMS_FILE.read_text())
    except OSError:
        return None


def _emit_metric(endpoint: str, result: str) -> None:
    if DRY_RUN:
        return
    try:
        os.makedirs(METRICS_DIR, exist_ok=True)
        prom = os.path.join(METRICS_DIR, "sovereign-os-models-catalog-api.prom")
        with open(prom, "a") as f:
            f.write(f'{METRIC_NAME}{{endpoint="{endpoint}",result="{result}"}} 1\n')
    except OSError:
        pass


def catalog_view() -> dict[str, Any]:
    """The full model registry grouped by SRP tier, each row reduced to the
    dashboard's display shape. Reuses model-health.load_catalog (no drift).
    Absent/unreadable catalog → empty groups (never raises)."""
    models = _core.load_catalog()
    groups: dict[str, list[dict[str, Any]]] = {t: [] for t in TIER_ORDER}
    for m in models:
        tier = str(m.get("tier", "")).lower()
        if tier not in groups:
            groups.setdefault("other", [])
            tier = "other"
        params = m.get("parameters_millions")
        groups[tier].append({
            "id": m.get("id", "?"),
            "class": m.get("class"),
            "engine": m.get("engine"),
            "precision": _core._precision(m),
            "quantization": m.get("quantization"),
            "params_b": round(params / 1000, 1) if isinstance(params, (int, float)) else None,
            "context_window_tokens": m.get("context_window_tokens"),
            "size_class": m.get("size_class"),
            "license": m.get("license"),
            "purpose": m.get("purpose"),
            "hf_repo_id": m.get("hf_repo_id"),
            "status": m.get("status"),
        })
    ordered = [
        {"tier": t, "label": TIER_LABEL.get(t, t), "models": groups[t]}
        for t in TIER_ORDER if groups.get(t)
    ]
    if groups.get("other"):
        ordered.append({"tier": "other", "label": "Other", "models": groups["other"]})
    return {"total": len(models), "tiers": ordered,
            "catalog_path": str(_core.CATALOG_PATH)}


def _version_payload() -> dict:
    return {
        "service": "models-catalog-api",
        "version": API_VERSION,
        "module": "d-23-models-catalog",
        "shipped_in": SHIPPED_IN,
        "catalog_source": "reuses scripts/inference/model-health.py load_catalog "
                          "(models/catalog.yaml)",
        "core": str(_CORE_PATH),
        "webapp_path": str(WEBAPP_PATH),
        "surfaces": ["core", "api", "webapp", "service"],
        "standing_rule": "We do not minimize anything.",
    }


class ModelsCatalogAPIHandler(BaseHTTPRequestHandler):
    server_version = f"sovereign-os-models-catalog-api/{API_VERSION}"
    sys_version = ""

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write(f"[api] {self.address_string()} {fmt % args}\n")

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Sovereign-Module", "models-catalog-api")
        self.send_header("X-Sovereign-Version", API_VERSION)
        self.end_headers()
        self.wfile.write(body)

    def _send_webapp(self) -> None:
        try:
            body = WEBAPP_PATH.read_bytes()
        except OSError as e:
            self._send_json(500, {"error": f"webapp asset unreadable: {e}",
                                  "expected_path": str(WEBAPP_PATH)})
            _emit_metric("webapp", "500")
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Sovereign-Module", "d-23-models-catalog-webapp")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(body)
        _emit_metric("webapp", "ok")

    def _send_stream(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Sovereign-Module", "models-catalog-api")
        self.end_headers()
        _emit_metric("stream", "open")
        try:
            while True:
                payload = json.dumps(catalog_view())
                self.wfile.write(
                    f"event: catalog-change\ndata: {payload}\n\n".encode("utf-8")
                )
                self.wfile.flush()
                time.sleep(STREAM_INTERVAL)
        except (BrokenPipeError, ConnectionResetError, OSError):
            return

    def do_GET(self) -> None:  # noqa: N802
        path = urllib.parse.urlsplit(self.path).path.rstrip("/") or "/"
        if path in ("/", "/healthz"):
            self._send_json(200, {"status": "ok", "version": API_VERSION})
            _emit_metric("healthz" if path == "/healthz" else "root", "ok")
            return
        if path in ("/control-systems", "/control-systems.json"):
            cs = _load_control_systems()
            self._send_json(200, cs if cs is not None else {"systems": []})
            _emit_metric("control-systems", "ok")
            return
        if path in ("/webapp", "/webapp/index.html"):
            self._send_webapp()
            return
        if path == "/api/models-catalog/stream":
            self._send_stream()
            return
        try:
            if path == "/version":
                self._send_json(200, _version_payload())
                _emit_metric("version", "ok")
                return
            if path == "/api/models-catalog/catalog":
                self._send_json(200, catalog_view())
                _emit_metric("catalog", "ok")
                return
        except Exception as e:  # noqa: BLE001
            self._send_json(500, {"error": str(e)})
            _emit_metric(path.lstrip("/") or "unknown", "500")
            return
        self._send_json(404, {
            "error": f"unknown endpoint: {path!r}",
            "available": ["/api/models-catalog/catalog",
                          "/api/models-catalog/stream", "/control-systems",
                          "/version", "/healthz", "/webapp/"],
        })
        _emit_metric(path.lstrip("/") or "unknown", "404")

    def do_HEAD(self) -> None:  # noqa: N802
        self._send_json(200, {"status": "ok"})

    def _reject(self) -> None:
        self._send_json(405, {
            "error": "read-only surface — model lifecycle is signed "
                     "`sovereign-osctl models …` CLI verbs, never web mutations (R10212)",
            "allowed": ["GET", "HEAD"],
        })
        _emit_metric(self.command.lower(), "405")

    def do_POST(self):    self._reject()  # noqa: E704 N802
    def do_PUT(self):     self._reject()  # noqa: E704 N802
    def do_DELETE(self):  self._reject()  # noqa: E704 N802


def serve(bind: str = API_BIND, port: int = API_PORT) -> int:
    print(f"[*] models-catalog-api {API_VERSION} on http://{bind}:{port}/", flush=True)
    httpd = ThreadingHTTPServer((bind, port), ModelsCatalogAPIHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] shutting down", flush=True)
    finally:
        httpd.server_close()
    return 0


def main(argv: list[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser(description="models-catalog read-only API + webapp host")
    p.add_argument("--bind", default=API_BIND)
    p.add_argument("--port", type=int, default=API_PORT)
    p.add_argument("--self-check", action="store_true",
                   help="build one catalog view + exit 0 (CI smoke)")
    args = p.parse_args(argv)
    if args.self_check or DRY_RUN:
        print(json.dumps({"config": _version_payload(),
                          "sample_catalog": catalog_view()}, indent=2))
        return 0
    return serve(args.bind, args.port)


if __name__ == "__main__":
    sys.exit(main())
