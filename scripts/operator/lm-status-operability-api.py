#!/usr/bin/env python3
"""scripts/operator/lm-status-operability-api.py — read-only HTTP API +
webapp host for the D-22 "Language Model Status & Operability" cockpit
dashboard.

The `api` + `service` + `webapp` surfaces for the lm-status-operability
panel. It imports the SAME core the D-03 model-health CLI/webapp use
(scripts/inference/model-health.py) so the two cockpit panels and
`sovereign-osctl model-health` never drift — Panel D-22 is a different
*rendering* (per-device Model 0/1/2 tabs + History|Selected + operability
Actions/Tests + a render-only Chat) of the same joined data model, not a
new data source.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."

Sovereignty (stdlib-only, zero deps):
  - http.server + BaseHTTPRequestHandler; loopback-bind by default
  - READ-ONLY (all model/agent mutation are MS003-signed CLI verbs, never
    web mutations — R10212 / MASTER-PLAN.md:196-199). do_POST/PUT/DELETE
    fail-closed with 405.
  - same-origin webapp (no CDN, no cross-origin script per §1g UX rule)

Device mapping (M075 SRP topology): CPU0 = Conductor (Pulse, bitnet.cpp),
GPU0 = Logic Engine, GPU1 = Oracle Core (Blackwell). Model 0/1/2 = the
per-role candidate/loaded models from the model-health snapshot.

Endpoints (the exact contract webapp/d-22-lm-status-operability/index.html
fetches):
  GET /api/lm-status/health   full model-health snapshot (shared core)
  GET /api/lm-status/devices  per-device (CPU0/GPU0/GPU1) Model 0/1/2 +
                              history/selected view derived from the snapshot
  GET /api/lm-status/stream   Server-Sent Events (model-state-change events)
  GET /webapp/ | /webapp/index.html   the D-22 single-file dashboard
  GET /version | /healthz | /

Env (all overridable):
  LM_STATUS_API_BIND      (default 127.0.0.1)
  LM_STATUS_API_PORT      (default 8122)
  LM_STATUS_API_DRY_RUN   (set=1 → print config + exit)
  LM_STATUS_WEBAPP_PATH   (override the on-disk webapp asset)
  LM_STATUS_STREAM_INTERVAL (SSE push seconds, default 3.0)
  SOVEREIGN_OS_METRICS_DIR  (node_exporter textfile collector dir)
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

API_BIND = os.environ.get("LM_STATUS_API_BIND", "127.0.0.1")
API_PORT = int(os.environ.get("LM_STATUS_API_PORT", "8122"))
DRY_RUN = bool(os.environ.get("LM_STATUS_API_DRY_RUN"))
STREAM_INTERVAL = float(os.environ.get("LM_STATUS_STREAM_INTERVAL", "3.0"))
API_VERSION = "1.0.0"
SHIPPED_IN = "D-22-lm-status-operability"

METRICS_DIR = os.environ.get(
    "SOVEREIGN_OS_METRICS_DIR", "/var/lib/node_exporter/textfile_collector",
)
METRIC_NAME = "sovereign_os_operator_lm_status_api_request_total"

_REPO_ROOT = Path(__file__).resolve().parents[2]
WEBAPP_PATH = Path(os.environ.get(
    "LM_STATUS_WEBAPP_PATH",
    str(_REPO_ROOT / "webapp" / "d-22-lm-status-operability" / "index.html"),
))

# Import the SAME model-health core the D-03 panel + CLI use (hyphenated
# filename → importlib) so the two cockpit panels never drift.
_CORE_PATH = _REPO_ROOT / "scripts" / "inference" / "model-health.py"
_spec = importlib.util.spec_from_file_location("_modelhealth_core", _CORE_PATH)
if _spec is None or _spec.loader is None:
    sys.stderr.write(
        f"[FATAL STRUCTURAL FRICTION] cannot load model-health.py "
        f"from {_CORE_PATH}\n"
    )
    sys.exit(1)
_core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_core)

# Import the SDD-062 single-prompt inference engine (the SAME engine the
# `inference prompt` CLI verb uses) so the web chat and the CLI never drift.
_PROMPT_PATH = _REPO_ROOT / "scripts" / "inference" / "prompt.py"
_pspec = importlib.util.spec_from_file_location("_inference_prompt_engine", _PROMPT_PATH)
_prompt = None
if _pspec is not None and _pspec.loader is not None:
    _prompt = importlib.util.module_from_spec(_pspec)
    try:
        _pspec.loader.exec_module(_prompt)
    except Exception as _e:  # noqa: BLE001 — chat degrades to 503, never fails the daemon
        sys.stderr.write(f"[warn] prompt engine unavailable ({_e}); chat → 503\n")
        _prompt = None

# Device slot → SRP role (M075). The panel's three device columns.
DEVICES = [
    {"slot": "CPU0", "role": "conductor", "label": "Ryzen 9 9900X AM5 AVX-512"},
    {"slot": "GPU0", "role": "logic", "label": "Logic Engine"},
    {"slot": "GPU1", "role": "oracle", "label": "Oracle Core (Blackwell)"},
]


def _emit_metric(endpoint: str, result: str) -> None:
    if DRY_RUN:
        return
    try:
        os.makedirs(METRICS_DIR, exist_ok=True)
        prom = os.path.join(METRICS_DIR, "sovereign-os-lm-status-api.prom")
        with open(prom, "a") as f:
            f.write(f'{METRIC_NAME}{{endpoint="{endpoint}",result="{result}"}} 1\n')
    except OSError:
        pass


def devices_view() -> dict[str, Any]:
    """Reshape the shared model-health snapshot into the per-device panel
    model: one entry per CPU0/GPU0/GPU1 device with its Model 0/1/2 slots,
    a live/label for the device, and the per-model latency history joined
    from the snapshot's `models` list. Degrades to empty slots / `—` when a
    device or runtime state is absent (honest idle state), never raises."""
    snap = _core.snapshot()
    roles = snap.get("roles", {})
    lat_by_id = {m.get("id"): m for m in (snap.get("models") or [])}
    devices: list[dict[str, Any]] = []
    for dev in DEVICES:
        role = dev["role"]
        r = roles.get(role, {})
        models = r.get("models") or []
        slots = []
        for idx in range(3):  # Model 0 / Model 1 / Model 2
            if idx < len(models):
                m = models[idx]
                mid = m.get("id")
                lat = lat_by_id.get(mid, {})
                slots.append({
                    "slot": idx,
                    "id": mid,
                    "precision": m.get("precision"),
                    "status": m.get("status"),
                    "context_window_tokens": m.get("context_window_tokens"),
                    "p50_ms": lat.get("p50_ms"),
                    "p95_ms": lat.get("p95_ms"),
                    "p99_ms": lat.get("p99_ms"),
                    "req_per_min": lat.get("req_per_min"),
                })
            else:
                slots.append({"slot": idx, "id": None})
        devices.append({
            "slot": dev["slot"],
            "role": role,
            "label": r.get("gpu_name") or dev["label"],
            "util_pct": r.get("util_pct"),
            "vram_used_gb": r.get("vram_used_gb"),
            "vram_total_gb": r.get("vram_total_gb"),
            "tokens_per_sec": r.get("tokens_per_sec"),
            "model_source": r.get("model_source"),
            "loaded_count": r.get("loaded_count"),
            "models": slots,
        })
    return {
        "schema_version": snap.get("schema_version"),
        "summary": snap.get("summary", {}),
        "devices": devices,
        "kvcache": snap.get("kvcache", []),
    }


def _version_payload() -> dict:
    return {
        "service": "lm-status-operability-api",
        "version": API_VERSION,
        "module": "d-22-lm-status-operability",
        "shipped_in": SHIPPED_IN,
        "catalog_source": "reuses scripts/inference/model-health.py (M060 D-03) "
                          "+ M075 SRP topology",
        "core": str(_CORE_PATH),
        "webapp_path": str(WEBAPP_PATH),
        "surfaces": ["core", "api", "webapp", "service"],
        "standing_rule": "We do not minimize anything.",
    }


_CONTROL_SYSTEMS_FILE = _REPO_ROOT / "config" / "control-systems.yaml"


def _load_control_systems():
    """SDD-045 control-surface registry (config/control-systems.yaml) served
    at GET /control-systems for the inlined control surface. yaml is an
    optional dependency — degrade to empty (never raise) when absent so the
    daemon stays functional on a stdlib-only host."""
    try:
        import yaml  # optional
    except ImportError:
        return None
    try:
        return yaml.safe_load(_CONTROL_SYSTEMS_FILE.read_text())
    except OSError:
        return None


class LmStatusAPIHandler(BaseHTTPRequestHandler):
    server_version = f"sovereign-os-lm-status-api/{API_VERSION}"
    sys_version = ""

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write(f"[api] {self.address_string()} {fmt % args}\n")

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Sovereign-Module", "lm-status-operability-api")
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
        self.send_header("X-Sovereign-Module", "d-22-lm-status-operability-webapp")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(body)
        _emit_metric("webapp", "ok")

    def _send_stream(self) -> None:
        """SSE: push a fresh per-device view every STREAM_INTERVAL seconds as
        a `model-state-change` event (the name the D-22 webapp listens for)
        until the client disconnects. Read-only, same-origin."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Sovereign-Module", "lm-status-operability-api")
        self.end_headers()
        _emit_metric("stream", "open")
        try:
            while True:
                payload = json.dumps(devices_view())
                self.wfile.write(
                    f"event: model-state-change\ndata: {payload}\n\n".encode("utf-8")
                )
                self.wfile.flush()
                time.sleep(STREAM_INTERVAL)
        except (BrokenPipeError, ConnectionResetError, OSError):
            return  # client went away — normal SSE lifecycle

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
        if path == "/api/lm-status/stream":
            self._send_stream()
            return
        try:
            if path == "/version":
                self._send_json(200, _version_payload())
                _emit_metric("version", "ok")
                return
            if path == "/api/lm-status/health":
                self._send_json(200, _core.snapshot())
                _emit_metric("health", "ok")
                return
            if path == "/api/lm-status/devices":
                self._send_json(200, devices_view())
                _emit_metric("devices", "ok")
                return
        except Exception as e:  # noqa: BLE001
            self._send_json(500, {"error": str(e)})
            _emit_metric(path.lstrip("/") or "unknown", "500")
            return
        self._send_json(404, {
            "error": f"unknown endpoint: {path!r}",
            "available": ["/api/lm-status/health", "/api/lm-status/devices",
                          "/api/lm-status/stream", "/version", "/healthz",
                          "/webapp/"],
        })
        _emit_metric(path.lstrip("/") or "unknown", "404")

    def do_HEAD(self) -> None:  # noqa: N802
        self._send_json(200, {"status": "ok"})

    def _send_chat(self) -> None:
        """SDD-062 — the ONE sanctioned POST: a bounded, loopback-only inference-
        query proxy. A chat completion is a NON-MUTATING read-compute to a local
        model (no host/state mutation, no shell, no new process) — it streams token
        deltas back as SSE. All actual state mutations stay 405 (below) + exec-rail-
        only. SB-077: an unreachable backend streams an honest `error` event."""
        if _prompt is None:
            self._send_json(503, {"error": "inference prompt engine unavailable"})
            _emit_metric("chat", "503")
            return
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > 64_000:  # bounded request body
            self._send_json(400, {"error": "missing or oversize JSON body {prompt}"})
            _emit_metric("chat", "400")
            return
        try:
            req = json.loads(self.rfile.read(length).decode("utf-8"))
            text = str(req.get("prompt", ""))
        except (json.JSONDecodeError, ValueError, UnicodeDecodeError):
            self._send_json(400, {"error": "body must be JSON {prompt: <text>}"})
            _emit_metric("chat", "400")
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Sovereign-Module", "lm-status-operability-api")
        self.end_headers()
        _emit_metric("chat", "open")
        done = None
        try:
            for ev in _prompt.run(text):
                self.wfile.write(
                    f"event: {ev['type']}\ndata: {json.dumps(ev)}\n\n".encode("utf-8"))
                self.wfile.flush()
                if ev["type"] == "done":
                    done = ev
        except (BrokenPipeError, ConnectionResetError, OSError):
            return  # client went away mid-stream
        # publish the REAL measured telemetry (only on a real completion).
        if done and done.get("tokens"):
            latency = done["elapsed_s"] * 1000.0 / done["tokens"]
            try:
                _prompt.publish_telemetry(done["tier"], done["tokens_per_sec"], latency)
            except Exception:  # noqa: BLE001 — telemetry is best-effort
                pass

    def _reject(self) -> None:
        self._send_json(405, {
            "error": "read-only surface — model/agent actions are MS003-signed "
                     "CLI verbs, never web mutations (R10212). The single exception "
                     "is POST /api/lm-status/chat (a non-mutating inference read-"
                     "compute to the loopback router, SDD-062).",
            "allowed": ["GET", "HEAD", "POST /api/lm-status/chat"],
        })
        _emit_metric(self.command.lower(), "405")

    def do_POST(self):  # noqa: N802
        path = urllib.parse.urlsplit(self.path).path.rstrip("/") or "/"
        if path == "/api/lm-status/chat":
            self._send_chat()
            return
        self._reject()  # every other mutation stays 405 + exec-rail-only

    def do_PUT(self):     self._reject()  # noqa: E704 N802
    def do_DELETE(self):  self._reject()  # noqa: E704 N802


def serve(bind: str = API_BIND, port: int = API_PORT) -> int:
    print(f"[*] lm-status-operability-api {API_VERSION} on http://{bind}:{port}/",
          flush=True)
    httpd = ThreadingHTTPServer((bind, port), LmStatusAPIHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] shutting down", flush=True)
    finally:
        httpd.server_close()
    return 0


def main(argv: list[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser(
        description="lm-status-operability read-only API + webapp host")
    p.add_argument("--bind", default=API_BIND)
    p.add_argument("--port", type=int, default=API_PORT)
    p.add_argument("--self-check", action="store_true",
                   help="build one devices view, print it, and exit 0 (CI smoke)")
    args = p.parse_args(argv)
    if args.self_check or DRY_RUN:
        print(json.dumps({"config": _version_payload(),
                          "sample_devices": devices_view()}, indent=2))
        return 0
    return serve(args.bind, args.port)


if __name__ == "__main__":
    sys.exit(main())
