#!/usr/bin/env python3
"""
scripts/operator/chromofold-api.py — SDD-500 ChromoFold panel HTTP API + webapp.

Read-only observability for the ChromoFold compressed-domain search engine (the
../chromoFold C++/CUDA engine + its ../warp-solar-system-shaders Warp oracle):
the capability descriptor (which primitives the ABI offers, the library/headers,
the resolved engine root) and a no-GPU header-seam selftest.

It shells to scripts/inference/chromofold.py (which reads the native
packaging/chromofold_capability.json from CHROMOFOLD_ROOT / WARP_SHADERS_ROOT).
This daemon is stdlib-only — it NEVER imports the engine, NEVER touches a GPU,
and NEVER runs a search. The real device query is the hardware-gated SDD-500
step 7; this daemon fail-closes 405 on writes (R10212 / SB-077).

Endpoints:
  GET  /                    — the chromofold webapp (single file)
  GET  /chromofold.json     — the capability descriptor (offline-honest)
  GET  /chromofold/selftest — the no-GPU header-seam selftest result
  GET  /version             — service version + module identity
  GET  /healthz             — liveness (always 200)
  GET  /control-systems     — the shared control-surface registry (same-origin)

Env vars:
  CHROMOFOLD_API_BIND   (default: 127.0.0.1)
  CHROMOFOLD_API_PORT   (default: 8147)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

API_BIND = os.environ.get("CHROMOFOLD_API_BIND", "127.0.0.1")
API_PORT = int(os.environ.get("CHROMOFOLD_API_PORT", "8147"))
VERSION = "0.1.0"

REPO = Path(__file__).resolve().parents[2]
WEBAPP_ROOT = REPO / "webapp"
WEBAPP = WEBAPP_ROOT / "chromofold" / "index.html"
CLI = REPO / "scripts" / "inference" / "chromofold.py"

STATIC_TYPES = {
    ".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8", ".json": "application/json",
    ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon",
    ".woff2": "font/woff2",
}


def _cli(*args: str) -> dict:
    """Run `chromofold.py <args> --json`; return {'error': ...} on any failure so
    the panel degrades gracefully instead of 500ing."""
    if not CLI.is_file():
        return {"error": "chromofold.py not found"}
    try:
        r = subprocess.run(
            [sys.executable, str(CLI), *args, "--json"],
            capture_output=True, text=True, timeout=30, cwd=str(REPO), check=False)
        return json.loads(r.stdout) if r.stdout.strip() else {"error": r.stderr.strip()[:200] or "no output"}
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as e:
        return {"error": str(e)}


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
            return self._send(200, json.dumps({"module": "chromofold-api", "version": VERSION}))
        if path in ("/chromofold.json", "/chromofold"):
            return self._send(200, json.dumps(_cli("info"), indent=2))
        if path == "/chromofold/selftest":
            return self._send(200, json.dumps(_cli("selftest")))
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
        # deliberately read-only: a real device search is the hardware-gated
        # SDD-500 step 7, not a web verb. Fail closed.
        return self._send(405, json.dumps({
            "error": "chromofold-api is read-only",
            "hint": "info/selftest are diagnostics; device search is the "
                    "hardware-gated engine path (SDD-500 step 7), never a web write"}))


def main():
    if "--self-check" in sys.argv:
        d = _cli("info")
        print(json.dumps({
            "module": "chromofold-api", "version": VERSION,
            "availability": d.get("availability", d.get("resolved", {}).get("availability", "offline")),
            "abi_version": d.get("abi_version"),
            "capabilities": len(d.get("capabilities", [])),
        }, indent=2))
        return
    httpd = ThreadingHTTPServer((API_BIND, API_PORT), Handler)
    print(f"chromofold-api on http://{API_BIND}:{API_PORT}/ (webapp at /, data at /chromofold.json) "
          f"— Ctrl-C to stop", file=sys.stderr)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
