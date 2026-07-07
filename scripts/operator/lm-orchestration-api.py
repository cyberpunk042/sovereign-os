#!/usr/bin/env python3
"""scripts/operator/lm-orchestration-api.py — read-only HTTP API + webapp
host for the D-21 "Language Model Orchestration" cockpit dashboard.

The `api` + `service` + `webapp` surfaces for the lm-orchestration panel.
It composes THREE already-shipped data sources (no new data model, no
drift):

  - the model-health core (scripts/inference/model-health.py) — the live
    hardware/GPU/CPU + per-role model state, reshaped into the panel's
    GPU0/GPU1/Ext-GPU/CPU0 assignment grid (M075 SRP topology).
  - the runtime-modes profile lister (scripts/operator/runtime-modes-api.py
    `_list_profiles()`) — the M076 runtime load-balancing profiles the
    Profiles row renders. The panel is profile-agnostic: it lists whatever
    profiles/runtime/*.yaml the system ships (today the 3 verbatim-locked
    §18 profiles; a future orchestration-intent family renders here too).
  - /proc/cpuinfo flags — the CPU AVX-512 feature capabilities (Features
    CPU) + GPU capability flags from the model-health GPU probe (Features
    GPUs).

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."

Sovereignty (stdlib-only, zero deps): loopback-bind, READ-ONLY (all
model→hardware assignment is MS003-signed CLI verbs — `sovereign srp
override` / `sovereign model load --role …` — never web mutations, per
R10212). do_POST/PUT/DELETE fail-closed 405.

Endpoints (the exact contract webapp/d-21-lm-orchestration/index.html
fetches):
  GET /api/lm-orchestration/grid      GPU0/GPU1/Ext-GPU/CPU0 assignment grid
  GET /api/lm-orchestration/profiles  runtime profiles (M076) for the row
  GET /api/lm-orchestration/features  CPU (AVX-512) + GPU capability flags
  GET /api/lm-orchestration/stream    Server-Sent Events (state-change)
  GET /webapp/ | /webapp/index.html   the D-21 single-file dashboard
  GET /version | /healthz | /

Env (all overridable):
  LM_ORCH_API_BIND      (default 127.0.0.1)
  LM_ORCH_API_PORT      (default 8121)
  LM_ORCH_API_DRY_RUN   (set=1 → print config + exit)
  LM_ORCH_WEBAPP_PATH   (override the on-disk webapp asset)
  LM_ORCH_STREAM_INTERVAL (SSE push seconds, default 3.0)
  LM_ORCH_CPUINFO       (override /proc/cpuinfo path — test seam)
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

API_BIND = os.environ.get("LM_ORCH_API_BIND", "127.0.0.1")
API_PORT = int(os.environ.get("LM_ORCH_API_PORT", "8121"))
DRY_RUN = bool(os.environ.get("LM_ORCH_API_DRY_RUN"))
STREAM_INTERVAL = float(os.environ.get("LM_ORCH_STREAM_INTERVAL", "3.0"))
CPUINFO_PATH = Path(os.environ.get("LM_ORCH_CPUINFO", "/proc/cpuinfo"))
API_VERSION = "1.0.0"
SHIPPED_IN = "D-21-lm-orchestration"

METRICS_DIR = os.environ.get(
    "SOVEREIGN_OS_METRICS_DIR", "/var/lib/node_exporter/textfile_collector",
)
METRIC_NAME = "sovereign_os_operator_lm_orchestration_api_request_total"

_REPO_ROOT = Path(__file__).resolve().parents[2]
WEBAPP_PATH = Path(os.environ.get(
    "LM_ORCH_WEBAPP_PATH",
    str(_REPO_ROOT / "webapp" / "d-21-lm-orchestration" / "index.html"),
))


def _import(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        sys.stderr.write(f"[FATAL STRUCTURAL FRICTION] cannot load {path}\n")
        sys.exit(1)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _import_optional(name: str, path: Path):
    """Load a NON-essential reused source. Unlike _import, a missing or
    broken module degrades the corresponding panel row (empty) rather than
    killing the daemon — production resilience for the optional Profiles
    row (the grid + features remain fully functional)."""
    try:
        return _import(name, path)
    except (OSError, ImportError, SyntaxError, SystemExit) as e:
        sys.stderr.write(f"[degraded] optional source {path} unavailable: {e}\n")
        return None


# Reuse the SAME shipped data sources (no new model, no drift). model-health
# is essential (the assignment grid); runtime-modes is optional (Profiles row).
_core = _import("_modelhealth_core", _REPO_ROOT / "scripts" / "inference" / "model-health.py")
_rtmodes = _import_optional("_runtimemodes_api", _REPO_ROOT / "scripts" / "operator" / "runtime-modes-api.py")

# The panel's four hardware cells (M075 SRP topology + the sketched Ext-GPU).
GRID = [
    {"slot": "GPU0", "role": "logic", "label": "Logic Engine (GPU 0)"},
    {"slot": "GPU1", "role": "oracle", "label": "Oracle Core (GPU 1, Blackwell)"},
    {"slot": "EXT_GPU", "role": None, "label": "Future / External GPU"},
    {"slot": "CPU0", "role": "conductor", "label": "Ryzen 9 9900X AM5 AVX-512"},
]

# CPU-core → Model slot ranges the sketch shows for the Conductor CPU.
CPU_CORE_RANGES = ["1-7", "8-15", "16-24"]

# AVX-512 capability flags the Features CPU panel surfaces (from /proc/cpuinfo).
CPU_FEATURE_FLAGS = [
    ("avx512f", "AVX-512 Foundation"),
    ("avx512_vnni", "AVX-512 VNNI (VPDPBUSD — single-cycle INT8 dot)"),
    ("avx512vbmi", "AVX-512 VBMI"),
    ("avx512_vpopcntdq", "AVX-512 VPOPCNTDQ (pop count)"),
    ("avx512vl", "AVX-512 VL"),
    ("avx512bw", "AVX-512 BW"),
    ("avx512dq", "AVX-512 DQ"),
]


def _emit_metric(endpoint: str, result: str) -> None:
    if DRY_RUN:
        return
    try:
        os.makedirs(METRICS_DIR, exist_ok=True)
        prom = os.path.join(METRICS_DIR, "sovereign-os-lm-orchestration-api.prom")
        with open(prom, "a") as f:
            f.write(f'{METRIC_NAME}{{endpoint="{endpoint}",result="{result}"}} 1\n')
    except OSError:
        pass


def grid_view() -> dict[str, Any]:
    """Reshape the shared model-health snapshot into the assignment grid:
    one cell per GPU0/GPU1/Ext-GPU/CPU0 with its bound Model 0/1/2 and a
    per-device Mode. Ext-GPU is N/A until an external card is registered.
    Degrades to empty cells / `—` when a device is absent, never raises."""
    snap = _core.snapshot()
    roles = snap.get("roles", {})
    cells: list[dict[str, Any]] = []
    for cell in GRID:
        role = cell["role"]
        if role is None:
            cells.append({
                "slot": cell["slot"], "label": cell["label"],
                "present": False, "models": [], "mode": None,
            })
            continue
        r = roles.get(role, {})
        models = r.get("models") or []
        model_slots = []
        for idx in range(3):
            m = models[idx] if idx < len(models) else None
            entry = {"slot": idx, "id": (m or {}).get("id"),
                     "precision": (m or {}).get("precision")}
            if role == "conductor":
                entry["core_range"] = CPU_CORE_RANGES[idx]
            model_slots.append(entry)
        cells.append({
            "slot": cell["slot"],
            "label": r.get("gpu_name") or cell["label"],
            "present": True,
            "role": role,
            "util_pct": r.get("util_pct"),
            "vram_used_gb": r.get("vram_used_gb"),
            "vram_total_gb": r.get("vram_total_gb"),
            "tokens_per_sec": r.get("tokens_per_sec"),
            "model_source": r.get("model_source"),
            "mode": "active" if (r.get("util_pct") or 0) > 0 else "idle",
            "models": model_slots,
        })
    return {"schema_version": snap.get("schema_version"),
            "summary": snap.get("summary", {}), "cells": cells}


def profiles_view() -> dict[str, Any]:
    """The M076 runtime profiles the Profiles row renders — reuses the
    shipped runtime-modes lister so the two panels never drift. Each entry
    carries the id/name/description + its Apply verb (clipboard-copied)."""
    try:
        profiles = _rtmodes._list_profiles() if _rtmodes is not None else []
    except Exception:  # noqa: BLE001
        profiles = []
    for p in profiles:
        pid = p.get("id") or p.get("mode_id") or "?"
        p["apply_cmd"] = f"sovereign-osctl runtime-modes apply {pid}"
    return {"profiles": profiles, "count": len(profiles),
            "note": "orchestration-intent profile family (Coding/Thinking/"
                    "Hybrid) is operator-decision-pending — the 3 M076 "
                    "load-balancing profiles render here today"}


def features_view() -> dict[str, Any]:
    """Features CPU (AVX-512 flags from /proc/cpuinfo) + Features GPUs
    (capability flags from the model-health GPU probe). Absent cpuinfo →
    all unknown; absent GPUs → empty (honest, never raises)."""
    flags: set[str] = set()
    try:
        for line in CPUINFO_PATH.read_text().splitlines():
            if line.startswith("flags") and ":" in line:
                flags = set(line.split(":", 1)[1].split())
                break
    except OSError:
        flags = set()
    cpu = [{"flag": f, "label": lbl, "present": f in flags}
           for f, lbl in CPU_FEATURE_FLAGS]
    gpus = _core.collect_gpus()
    gpu = [{
        "index": g.get("index"), "name": g.get("name"),
        "compute_cap": g.get("compute_cap"),
        "nvfp4_capable": bool(g.get("is_blackwell")),  # Blackwell → NVFP4
        "tensor_cores": g.get("compute_cap") is not None and g["compute_cap"] >= 7.0,
    } for g in gpus]
    return {"cpu": cpu, "cpu_flags_readable": bool(flags), "gpu": gpu}


def _version_payload() -> dict:
    return {
        "service": "lm-orchestration-api",
        "version": API_VERSION,
        "module": "d-21-lm-orchestration",
        "shipped_in": SHIPPED_IN,
        "catalog_source": "reuses model-health.py (M060 D-03 grid) + "
                          "runtime-modes-api._list_profiles (M076) + /proc/cpuinfo",
        "core": str(_REPO_ROOT / "scripts" / "inference" / "model-health.py"),
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


class LmOrchAPIHandler(BaseHTTPRequestHandler):
    server_version = f"sovereign-os-lm-orchestration-api/{API_VERSION}"
    sys_version = ""

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write(f"[api] {self.address_string()} {fmt % args}\n")

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Sovereign-Module", "lm-orchestration-api")
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
        self.send_header("X-Sovereign-Module", "d-21-lm-orchestration-webapp")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(body)
        _emit_metric("webapp", "ok")

    def _send_stream(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Sovereign-Module", "lm-orchestration-api")
        self.end_headers()
        _emit_metric("stream", "open")
        try:
            while True:
                payload = json.dumps(grid_view())
                self.wfile.write(
                    f"event: state-change\ndata: {payload}\n\n".encode("utf-8")
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
        if path == "/api/lm-orchestration/stream":
            self._send_stream()
            return
        try:
            if path == "/version":
                self._send_json(200, _version_payload())
                _emit_metric("version", "ok")
                return
            if path == "/api/lm-orchestration/grid":
                self._send_json(200, grid_view())
                _emit_metric("grid", "ok")
                return
            if path == "/api/lm-orchestration/profiles":
                self._send_json(200, profiles_view())
                _emit_metric("profiles", "ok")
                return
            if path == "/api/lm-orchestration/features":
                self._send_json(200, features_view())
                _emit_metric("features", "ok")
                return
        except Exception as e:  # noqa: BLE001
            self._send_json(500, {"error": str(e)})
            _emit_metric(path.lstrip("/") or "unknown", "500")
            return
        self._send_json(404, {
            "error": f"unknown endpoint: {path!r}",
            "available": ["/api/lm-orchestration/grid",
                          "/api/lm-orchestration/profiles",
                          "/api/lm-orchestration/features",
                          "/api/lm-orchestration/stream",
                          "/version", "/healthz", "/webapp/"],
        })
        _emit_metric(path.lstrip("/") or "unknown", "404")

    def do_HEAD(self) -> None:  # noqa: N802
        self._send_json(200, {"status": "ok"})

    def _reject(self) -> None:
        self._send_json(405, {
            "error": "read-only surface — model→hardware assignment is "
                     "MS003-signed CLI verbs, never web mutations (R10212)",
            "allowed": ["GET", "HEAD"],
        })
        _emit_metric(self.command.lower(), "405")

    def do_POST(self):    self._reject()  # noqa: E704 N802
    def do_PUT(self):     self._reject()  # noqa: E704 N802
    def do_DELETE(self):  self._reject()  # noqa: E704 N802


def serve(bind: str = API_BIND, port: int = API_PORT) -> int:
    print(f"[*] lm-orchestration-api {API_VERSION} on http://{bind}:{port}/",
          flush=True)
    httpd = ThreadingHTTPServer((bind, port), LmOrchAPIHandler)
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
        description="lm-orchestration read-only API + webapp host")
    p.add_argument("--bind", default=API_BIND)
    p.add_argument("--port", type=int, default=API_PORT)
    p.add_argument("--self-check", action="store_true",
                   help="build one grid/profiles/features view + exit 0 (CI smoke)")
    args = p.parse_args(argv)
    if args.self_check or DRY_RUN:
        print(json.dumps({"config": _version_payload(),
                          "sample_grid": grid_view(),
                          "sample_profiles": profiles_view(),
                          "sample_features": features_view()}, indent=2))
        return 0
    return serve(args.bind, args.port)


if __name__ == "__main__":
    sys.exit(main())
