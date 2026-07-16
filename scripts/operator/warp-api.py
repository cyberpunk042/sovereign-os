#!/usr/bin/env python3
"""
scripts/operator/warp-api.py — SDD-300 Warp management panel HTTP API + webapp.

Read-only observability for the Warp management surface: the
warp-solar-system-shaders project (an NVIDIA-Warp procedural rendering engine —
217 scenes, 20 lib packages, the scene→lib / lib→lib relation graph) plus the
executable runner surface (render / bench).

It shells to scripts/warp/warp_manage.py (which reads config/warp-catalog.yaml).
This daemon is stdlib-only — it NEVER imports warp/CUDA and NEVER runs a render.
Running a scene is the operator's gated exec-rail: the shared control-surface
executes `sovereign-osctl warp render|bench <scene>` via the control-exec-api
(port 8130) when this panel is fronted by it, and copies the command otherwise —
exactly like every other exec-wired panel. This daemon fail-closes 405 on writes.

Endpoints:
  GET  /                 — the warp webapp (single file)
  GET  /warp.json        — { catalog counts, scenes, libs, relations, status }
  GET  /warp/scenes      — scenes[] only
  GET  /warp/libs        — libs[] only
  GET  /warp/relations   — { scene_to_lib, lib_to_lib }
  GET  /version          — service version + module identity
  GET  /healthz          — liveness (always 200)
  GET  /control-systems  — the shared control-surface registry (same-origin)

Env vars:
  WARP_API_BIND   (default: 127.0.0.1)
  WARP_API_PORT   (default: 8138)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

API_BIND = os.environ.get("WARP_API_BIND", "127.0.0.1")
API_PORT = int(os.environ.get("WARP_API_PORT", "8138"))
VERSION = "0.1.0"

REPO = Path(__file__).resolve().parents[2]
WEBAPP_ROOT = REPO / "webapp"
WEBAPP = WEBAPP_ROOT / "warp" / "index.html"
WARP = REPO / "scripts" / "warp" / "warp_manage.py"

STATIC_TYPES = {
    ".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8", ".json": "application/json",
    ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon",
    ".woff2": "font/woff2",
}


def _warp(*args: str) -> dict:
    """Run `warp_manage.py <args> --json`; return {'error': ...} on any failure so
    the panel degrades gracefully instead of 500ing."""
    if not WARP.is_file():
        return {"error": "warp_manage.py not found"}
    try:
        r = subprocess.run(
            [sys.executable, str(WARP), *args, "--json"],
            capture_output=True, text=True, timeout=30, cwd=str(REPO), check=False)
        return json.loads(r.stdout) if r.stdout.strip() else {"error": r.stderr.strip()[:200] or "no output"}
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as e:
        return {"error": str(e)}


def assemble_warp() -> dict:
    scenes = _warp("list")
    libs = _warp("libs")
    rel = _warp("relations")
    status = _warp("status")
    return {
        "status": status,
        "counts": {"scenes": scenes.get("count", 0), "libs": libs.get("count", 0)},
        "scenes": scenes.get("scenes", []),
        "libs": libs.get("libs", []),
        "relations": {
            "scene_to_lib": rel.get("scene_to_lib", []),
            "lib_to_lib": rel.get("lib_to_lib", []),
        },
    }


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
            return self._send(200, json.dumps({"module": "warp-api", "version": VERSION}))
        if path in ("/warp.json", "/warp"):
            return self._send(200, json.dumps(assemble_warp(), indent=2))
        if path == "/warp/scenes":
            return self._send(200, json.dumps(_warp("list")))
        if path == "/warp/libs":
            return self._send(200, json.dumps(_warp("libs")))
        if path == "/warp/relations":
            return self._send(200, json.dumps(_warp("relations")))
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
        # deliberately read-only: rendering a scene is the gated exec-rail
        # (sovereign-osctl warp render|bench via control-exec-api), not a web verb
        return self._send(405, json.dumps({
            "error": "warp-api is read-only",
            "hint": "render/bench run via the control-exec-api rail "
                    "(`sovereign-osctl warp render <scene>`)"}))


def main():
    if "--self-check" in sys.argv:
        d = assemble_warp()
        print(json.dumps({
            "module": "warp-api", "version": VERSION,
            "scenes": d["counts"]["scenes"], "libs": d["counts"]["libs"],
            "checkout_resident": bool(d["status"].get("checkout_resident")),
            "scene_to_lib_edges": len(d["relations"]["scene_to_lib"]),
        }, indent=2))
        return
    httpd = ThreadingHTTPServer((API_BIND, API_PORT), Handler)
    print(f"warp-api on http://{API_BIND}:{API_PORT}/ (webapp at /, data at /warp.json) "
          f"— Ctrl-C to stop", file=sys.stderr)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
