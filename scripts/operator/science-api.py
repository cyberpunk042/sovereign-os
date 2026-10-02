#!/usr/bin/env python3
"""
scripts/operator/science-api.py — R558 (SDD-070) HTTP API + webapp for the
science-tools surface: the operator's Image-2 science catalog (DNA / protein /
particles) and the integrated NVIDIA Warp particle-sim status.

Read-only observability. It shells to scripts/science/science.py (which reads
config/science-tools.yaml and, for Warp, delegates to the warp-importing
scripts/science/warp-runner.py). This daemon is stdlib-only — it NEVER imports
warp/CUDA and NEVER runs a sim. Running a sim is the operator's gated CLI
(`sovereign-osctl science run`), surfaced as a copy-able command via the
control-surface.

Endpoints:
  GET  /                 — the science webapp (single file)
  GET  /science.json     — { tools, integrated_tools, warp, tools_status,
                             recent_runs, run_stats, gpu } assembled live
  GET  /version          — service version + module identity
  GET  /healthz          — liveness (always 200)
  GET  /control-systems  — the shared control-surface registry (same-origin)

Env vars:
  SCIENCE_API_BIND   (default: 127.0.0.1)
  SCIENCE_API_PORT   (default: 8134)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

API_BIND = os.environ.get("SCIENCE_API_BIND", "127.0.0.1")
API_PORT = int(os.environ.get("SCIENCE_API_PORT", "8134"))
VERSION = "0.2.0"

REPO = Path(__file__).resolve().parents[2]
WEBAPP_ROOT = REPO / "webapp"
WEBAPP = WEBAPP_ROOT / "science" / "index.html"
SCIENCE = REPO / "scripts" / "science" / "science.py"

STATIC_TYPES = {
    ".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8", ".json": "application/json",
    ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon",
    ".woff2": "font/woff2",
}


def _science(*args: str) -> dict:
    """Run `science.py <args> --json`; return {'error': ...} on any failure so
    the panel degrades gracefully instead of 500ing."""
    if not SCIENCE.is_file():
        return {"error": "science.py not found"}
    try:
        r = subprocess.run(
            [sys.executable, str(SCIENCE), *args, "--json"],
            capture_output=True, text=True, timeout=30, cwd=str(REPO), check=False)
        return json.loads(r.stdout) if r.stdout.strip() else {"error": r.stderr.strip()[:200] or "no output"}
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as e:
        return {"error": str(e)}


def assemble_science() -> dict:
    cat = _science("list")
    st = _science("status")
    hist = _science("history", "--json", "--limit", "30")
    return {
        "tools": cat.get("tools", []),
        "integrated_tools": st.get("integrated_tools", []),
        "warp": st.get("warp", {}),
        "tools_status": st.get("tools_status", []),
        "recent_runs": hist.get("runs", []),
        "run_stats": hist.get("stats", {}),
        "gpu": gpu_context(),
    }


def gpu_context() -> dict:
    """Per-GPU capacity/utilisation from nvidia-smi (the hardware truth),
    honestly degraded when the driver/CLI is absent (dev/CI box). NOTE: warp's
    cuda:N device order is NOT nvidia-smi's index order on multi-GPU hosts —
    the panel shows both, each labelled with its source; they are never
    conflated (SB-077)."""
    try:
        r = subprocess.run(
            ["nvidia-smi",
             "--query-gpu=index,name,memory.total,memory.free,utilization.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5, check=False)
        if r.returncode != 0:
            return {"available": False,
                    "reason": (r.stderr.strip() or "nvidia-smi failed")[:200]}
        gpus = []
        for line in r.stdout.splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 5:
                continue
            gpus.append({"index": int(parts[0]), "name": parts[1],
                         "memory_total_mib": int(float(parts[2])),
                         "memory_free_mib": int(float(parts[3])),
                         "utilization_pct": int(float(parts[4]))})
        return {"available": True, "gpus": gpus}
    except (OSError, subprocess.SubprocessError, ValueError):
        return {"available": False, "reason": "nvidia-smi unavailable"}


def load_control_systems() -> dict:
    try:
        import yaml
        data = yaml.safe_load((REPO / "config" / "control-systems.yaml").read_text(encoding="utf-8"))
        return data or {"systems": []}
    except Exception as e:  # read-only graceful degradation
        return {"error": f"control-systems unavailable: {e}"}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):  # quiet loopback daemon; journal captures stderr
        pass

    def do_GET(self):
        path = self.path.split("?", 1)[0].rstrip("/") or "/"
        if path == "/healthz":
            return self._send(200, json.dumps({"ok": True}))
        if path == "/version":
            return self._send(200, json.dumps({"module": "science-api", "version": VERSION}))
        if path in ("/science.json", "/science"):
            return self._send(200, json.dumps(assemble_science(), indent=2))
        if path in ("/control-systems", "/control-systems.json"):
            return self._send(200, json.dumps(load_control_systems()))
        if path == "/":
            if WEBAPP.exists():
                return self._send(200, WEBAPP.read_bytes(), "text/html; charset=utf-8")
            return self._send(404, json.dumps({"error": "webapp not found"}))
        try:
            target = (WEBAPP_ROOT / path.lstrip("/")).resolve()
            target.relative_to(WEBAPP_ROOT.resolve())
        except (ValueError, OSError):
            return self._send(404, json.dumps({"error": "not found", "path": path}))
        if target.is_dir():
            target = target / "index.html"
        if target.is_file():
            ctype = STATIC_TYPES.get(target.suffix.lower())
            if ctype:
                return self._send(200, target.read_bytes(), ctype)
        return self._send(404, json.dumps({"error": "not found", "path": path}))

    def do_POST(self):
        # deliberately read-only: running a sim is a gated CLI, not a web verb
        return self._send(405, json.dumps({
            "error": "science-api is read-only",
            "hint": "run a sim via `sovereign-osctl science run` (gated CLI)"}))


def main():
    if "--self-check" in sys.argv:
        d = assemble_science()
        warp = d.get("warp", {})
        print(json.dumps({
            "module": "science-api", "version": VERSION,
            "tool_count": len(d.get("tools", [])),
            "integrated_tools": d.get("integrated_tools", []),
            "warp_installed": bool(warp.get("installed")),
            "warp_cuda_available": bool(warp.get("cuda_available")),
            "tools_status_count": len(d.get("tools_status", [])),
            "recent_runs": len(d.get("recent_runs", [])),
            "run_stats_count": (d.get("run_stats") or {}).get("count", 0),
            "gpu_available": bool((d.get("gpu") or {}).get("available")),
            "gpu_count": len((d.get("gpu") or {}).get("gpus", [])),
        }, indent=2))
        return
    httpd = ThreadingHTTPServer((API_BIND, API_PORT), Handler)
    print(f"science-api on http://{API_BIND}:{API_PORT}/ (webapp at /, data at /science.json) "
          f"— Ctrl-C to stop", file=sys.stderr)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
