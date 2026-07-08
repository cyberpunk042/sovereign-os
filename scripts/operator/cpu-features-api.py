#!/usr/bin/env python3
"""scripts/operator/cpu-features-api.py — read-only HTTP API + webapp host
for the D-24 "CPU Features" cockpit dashboard.

Flips the dashboard-catalog `cpu-features` planned surface to live. The deep
AVX-512 capability view: the raw extension map, the per-AI-workload fit
verdict, and the actionable advisory — reusing the shipped
scripts/hardware/avx512-advisor.py (probe / workloads / advisory) so the
panel and the CLI advisor never drift. Distinct from D-21's Features-CPU
summary (this is the full capability + workload-fit + advisory drill-down).

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."

Sovereignty (stdlib-only, zero deps): loopback-bind, READ-ONLY (pure
capability observation; there is nothing to mutate). do_POST/PUT/DELETE
fail-closed 405.

Endpoints (the exact contract webapp/d-24-cpu-features/index.html fetches):
  GET /api/cpu-features/probe      raw AVX-512 extension map + cpu model
  GET /api/cpu-features/workloads  per-AI-workload fit verdict
  GET /api/cpu-features/advisory   actionable hints for missing extensions
  GET /api/cpu-features/stream     Server-Sent Events (features-change)
  GET /webapp/ | /webapp/index.html   the D-24 single-file dashboard
  GET /version | /healthz | /

Env (all overridable):
  CPU_FEATURES_API_BIND / _PORT (default 127.0.0.1 / 8124)
  CPU_FEATURES_API_DRY_RUN      (set=1 → print config + exit)
  CPU_FEATURES_WEBAPP_PATH      (override the on-disk webapp asset)
  CPU_FEATURES_STREAM_INTERVAL  (SSE push seconds, default 30.0)
  SOVEREIGN_OS_METRICS_DIR      (node_exporter textfile collector dir)
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

API_BIND = os.environ.get("CPU_FEATURES_API_BIND", "127.0.0.1")
API_PORT = int(os.environ.get("CPU_FEATURES_API_PORT", "8124"))
DRY_RUN = bool(os.environ.get("CPU_FEATURES_API_DRY_RUN"))
STREAM_INTERVAL = float(os.environ.get("CPU_FEATURES_STREAM_INTERVAL", "30.0"))
API_VERSION = "1.0.0"
SHIPPED_IN = "D-24-cpu-features"

METRICS_DIR = os.environ.get(
    "SOVEREIGN_OS_METRICS_DIR", "/var/lib/node_exporter/textfile_collector",
)
METRIC_NAME = "sovereign_os_operator_cpu_features_api_request_total"

_REPO_ROOT = Path(__file__).resolve().parents[2]
WEBAPP_PATH = Path(os.environ.get(
    "CPU_FEATURES_WEBAPP_PATH",
    str(_REPO_ROOT / "webapp" / "d-24-cpu-features" / "index.html"),
))
_ADVISOR = _REPO_ROOT / "scripts" / "hardware" / "avx512-advisor.py"
_CONTROL_SYSTEMS_FILE = _REPO_ROOT / "config" / "control-systems.yaml"


def _advisor(verb: str) -> dict[str, Any]:
    """Reuse the shipped avx512-advisor.py <verb> --json. Degrades to an
    honest {'error': …, 'avx512_supported': None} envelope (never raises)
    when the advisor or python is unavailable."""
    if shutil.which("python3") is None or not _ADVISOR.is_file():
        return {"error": "avx512-advisor unavailable", "avx512_supported": None}
    try:
        r = subprocess.run(
            ["python3", str(_ADVISOR), verb, "--json"],
            capture_output=True, text=True, timeout=6, check=False,
        )
    except (OSError, subprocess.SubprocessError) as e:
        return {"error": str(e), "avx512_supported": None}
    if r.returncode != 0:
        return {"error": r.stderr.strip()[:200] or f"advisor {verb} exit {r.returncode}",
                "avx512_supported": None}
    try:
        return json.loads(r.stdout)
    except (ValueError, json.JSONDecodeError) as e:
        return {"error": f"advisor {verb} bad json: {e}", "avx512_supported": None}


def _load_control_systems():
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
        prom = os.path.join(METRICS_DIR, "sovereign-os-cpu-features-api.prom")
        with open(prom, "a") as f:
            f.write(f'{METRIC_NAME}{{endpoint="{endpoint}",result="{result}"}} 1\n')
    except OSError:
        pass


def _version_payload() -> dict:
    return {
        "service": "cpu-features-api",
        "version": API_VERSION,
        "module": "d-24-cpu-features",
        "shipped_in": SHIPPED_IN,
        "catalog_source": "reuses scripts/hardware/avx512-advisor.py (probe/workloads/advisory)",
        "advisor": str(_ADVISOR),
        "webapp_path": str(WEBAPP_PATH),
        "surfaces": ["core", "api", "webapp", "service"],
        "standing_rule": "We do not minimize anything.",
    }


class CpuFeaturesAPIHandler(BaseHTTPRequestHandler):
    server_version = f"sovereign-os-cpu-features-api/{API_VERSION}"
    sys_version = ""

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write(f"[api] {self.address_string()} {fmt % args}\n")

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Sovereign-Module", "cpu-features-api")
        self.send_header("X-Sovereign-Version", API_VERSION)
        self.end_headers()
        self.wfile.write(body)

    def _send_webapp(self) -> None:
        try:
            body = WEBAPP_PATH.read_bytes()
        except OSError as e:
            self._send_json(500, {"error": f"webapp asset unreadable: {e}"})
            _emit_metric("webapp", "500")
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Sovereign-Module", "d-24-cpu-features-webapp")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(body)
        _emit_metric("webapp", "ok")

    def _send_stream(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Sovereign-Module", "cpu-features-api")
        self.end_headers()
        _emit_metric("stream", "open")
        try:
            while True:
                payload = json.dumps({"probe": _advisor("probe"),
                                      "workloads": _advisor("workloads"),
                                      "advisory": _advisor("advisory")})
                self.wfile.write(f"event: features-change\ndata: {payload}\n\n".encode("utf-8"))
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
        if path == "/api/cpu-features/stream":
            self._send_stream()
            return
        try:
            if path == "/version":
                self._send_json(200, _version_payload()); _emit_metric("version", "ok"); return
            if path == "/api/cpu-features/probe":
                self._send_json(200, _advisor("probe")); _emit_metric("probe", "ok"); return
            if path == "/api/cpu-features/workloads":
                self._send_json(200, _advisor("workloads")); _emit_metric("workloads", "ok"); return
            if path == "/api/cpu-features/advisory":
                self._send_json(200, _advisor("advisory")); _emit_metric("advisory", "ok"); return
        except Exception as e:  # noqa: BLE001
            self._send_json(500, {"error": str(e)})
            _emit_metric(path.lstrip("/") or "unknown", "500")
            return
        self._send_json(404, {
            "error": f"unknown endpoint: {path!r}",
            "available": ["/api/cpu-features/probe", "/api/cpu-features/workloads",
                          "/api/cpu-features/advisory", "/api/cpu-features/stream",
                          "/control-systems", "/version", "/healthz", "/webapp/"],
        })
        _emit_metric(path.lstrip("/") or "unknown", "404")

    def do_HEAD(self) -> None:  # noqa: N802
        self._send_json(200, {"status": "ok"})

    def _reject(self) -> None:
        self._send_json(405, {"error": "read-only surface — capability observation only (R10212)",
                              "allowed": ["GET", "HEAD"]})
        _emit_metric(self.command.lower(), "405")

    def do_POST(self):    self._reject()  # noqa: E704 N802
    def do_PUT(self):     self._reject()  # noqa: E704 N802
    def do_DELETE(self):  self._reject()  # noqa: E704 N802


def serve(bind: str = API_BIND, port: int = API_PORT) -> int:
    print(f"[*] cpu-features-api {API_VERSION} on http://{bind}:{port}/", flush=True)
    httpd = ThreadingHTTPServer((bind, port), CpuFeaturesAPIHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] shutting down", flush=True)
    finally:
        httpd.server_close()
    return 0


def main(argv: list[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser(description="cpu-features read-only API + webapp host")
    p.add_argument("--bind", default=API_BIND)
    p.add_argument("--port", type=int, default=API_PORT)
    p.add_argument("--self-check", action="store_true",
                   help="build one probe/workloads/advisory view + exit 0 (CI smoke)")
    args = p.parse_args(argv)
    if args.self_check or DRY_RUN:
        print(json.dumps({"config": _version_payload(),
                          "probe": _advisor("probe"),
                          "workloads": _advisor("workloads"),
                          "advisory": _advisor("advisory")}, indent=2))
        return 0
    return serve(args.bind, args.port)


if __name__ == "__main__":
    sys.exit(main())
