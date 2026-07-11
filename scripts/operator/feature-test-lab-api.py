#!/usr/bin/env python3
"""scripts/operator/feature-test-lab-api.py — the Feature Test Lab surface.

Read-only observability daemon for the operator's LIVE feature-test panel: it
serves the webapp and, on demand, runs a feature's real self-test and returns
what happened (result / path-taken / timing / checks). These are NOT unit
tests — each backend self-test RUNS the shipped feature (e.g. the AVX-512
sum_of_squares kernel) via the `sovereign-feature-selftest` binary and reports
the truth.

Running a self-test is a read-only computation (no host mutation), so it is a
GET. do_POST → 405 (nothing here mutates the box). Client-side features
(speaker, deep-links, keyboard) are exercised entirely in the panel's own JS
and need no endpoint.

Endpoints:
  GET  /                          — the feature-test-lab webapp (single file)
  GET  /feature-test-lab.json     — the registry: list of self-testable features
  GET  /api/feature-test/list     — same list (explicit)
  GET  /api/feature-test/run/<id> — run ONE feature's self-test, return its result
  GET  /api/feature-test/run-all  — run every backend self-test
  GET  /version | /healthz
  GET  /control-systems           — the shared control-surface registry (same-origin)

Env vars:
  FEATURE_TEST_LAB_API_BIND   (default: 127.0.0.1)
  FEATURE_TEST_LAB_API_PORT   (default: 8135)
  FEATURE_SELFTEST_BIN        (override the self-test binary path)
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

API_BIND = os.environ.get("FEATURE_TEST_LAB_API_BIND", "127.0.0.1")
API_PORT = int(os.environ.get("FEATURE_TEST_LAB_API_PORT", "8135"))
VERSION = "0.1.0"

REPO = Path(__file__).resolve().parents[2]
WEBAPP_ROOT = REPO / "webapp"
WEBAPP = WEBAPP_ROOT / "feature-test-lab" / "index.html"

# Self-test feature ids are simple slugs; validate before shelling (defense in
# depth even though this is loopback + read-only).
_FEATURE_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")

STATIC_TYPES = {
    ".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8", ".json": "application/json",
    ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon",
    ".woff2": "font/woff2",
}


def _selftest_bin() -> str | None:
    """Locate the sovereign-feature-selftest binary: explicit override →
    installed (PATH) → cargo target dirs. Returns None if not found."""
    override = os.environ.get("FEATURE_SELFTEST_BIN")
    if override and Path(override).is_file():
        return override
    import shutil
    onpath = shutil.which("sovereign-feature-selftest")
    if onpath:
        return onpath
    for sub in ("release", "debug"):
        cand = REPO / "target" / sub / "sovereign-feature-selftest"
        if cand.is_file():
            return str(cand)
    return None


def _run_selftest(*args: str) -> dict:
    """Run `sovereign-feature-selftest <args>`; return parsed JSON, or an
    {'error': ...} envelope so the panel degrades gracefully rather than 500ing.
    Read-only: the binary computes + prints; it never mutates the host."""
    binp = _selftest_bin()
    if binp is None:
        return {"error": "sovereign-feature-selftest binary not found — "
                         "build it (cargo build -p sovereign-feature-selftest) or set "
                         "FEATURE_SELFTEST_BIN"}
    try:
        r = subprocess.run(
            [binp, *args], capture_output=True, text=True, timeout=60,
            cwd=str(REPO), check=False)
        if r.stdout.strip():
            return json.loads(r.stdout)
        return {"error": r.stderr.strip()[:300] or "no output"}
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
            return self._send(200, json.dumps({"module": "feature-test-lab-api", "version": VERSION}))
        if path in ("/feature-test-lab.json", "/api/feature-test/list"):
            return self._send(200, json.dumps(_run_selftest("list"), indent=2))
        if path == "/api/feature-test/run-all":
            return self._send(200, json.dumps(_run_selftest("run-all"), indent=2))
        if path.startswith("/api/feature-test/run/"):
            feat = path[len("/api/feature-test/run/"):]
            if not _FEATURE_RE.match(feat):
                return self._send(400, json.dumps({"error": "bad feature id"}))
            return self._send(200, json.dumps(_run_selftest("run", feat), indent=2))
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
        # deliberately read-only: a self-test is a GET (read-only computation);
        # nothing here mutates the box.
        return self._send(405, json.dumps({
            "error": "feature-test-lab-api is read-only",
            "hint": "run a self-test via GET /api/feature-test/run/<feature>"}))


def main():
    if "--self-check" in sys.argv:
        listing = _run_selftest("list")
        print(json.dumps({
            "module": "feature-test-lab-api", "version": VERSION,
            "selftest_bin": _selftest_bin(),
            "feature_count": len(listing.get("features", [])),
            "features": [f.get("feature") for f in listing.get("features", [])],
        }, indent=2))
        return
    httpd = ThreadingHTTPServer((API_BIND, API_PORT), Handler)
    print(f"feature-test-lab-api on http://{API_BIND}:{API_PORT}/ "
          f"(webapp at /, run at /api/feature-test/run/<feature>) — Ctrl-C to stop",
          file=sys.stderr)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
