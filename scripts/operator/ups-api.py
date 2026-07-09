#!/usr/bin/env python3
"""
scripts/operator/ups-api.py — HTTP API + webapp for the UPS / power surface:
live APC Smart-UPS state (SMT2200C SmartConnect via NUT apc_modbus — Modbus over
TCP :502 or serial) and the graceful soft-shutdown posture (fires when battery
runtime < 30 min).

Read-only observability over the existing R252/R253 framework — it shells to
scripts/hardware/power-status.py (which reads NUT `upsc`) and reads the
[graceful_shutdown] arming from /etc/sovereign-os/power.toml. It NEVER mutates
power state; arming/disarming is the operator's gated CLI
(`sovereign-osctl power-shutdown …`, edit power.toml), surfaced as copy-able
commands via the control-surface.

Endpoints:
  GET  /               — the UPS webapp (single file)
  GET  /ups.json       — { ups, shutdown, advisories, nut } assembled live
  GET  /version        — service version + module identity
  GET  /healthz        — liveness (always 200)
  GET  /control-systems — the shared control-surface registry (same-origin)

Env vars:
  UPS_API_BIND   (default: 127.0.0.1)
  UPS_API_PORT   (default: 8128)
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

API_BIND = os.environ.get("UPS_API_BIND", "127.0.0.1")
API_PORT = int(os.environ.get("UPS_API_PORT", "8128"))
VERSION = "0.1.0"

REPO = Path(__file__).resolve().parents[2]
WEBAPP_ROOT = REPO / "webapp"
WEBAPP = WEBAPP_ROOT / "ups" / "index.html"
POWER_STATUS = REPO / "scripts" / "hardware" / "power-status.py"
POWER_TOML = Path("/etc/sovereign-os/power.toml")
POWER_TOML_DEV = REPO / "config" / "power.toml.example"

STATIC_TYPES = {
    ".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8", ".json": "application/json",
    ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon",
    ".woff2": "font/woff2",
}


def _power_status(verb: str) -> dict:
    """Run `power-status.py <verb> --json`; return {} on any failure so the panel
    degrades gracefully instead of 500ing."""
    if not POWER_STATUS.is_file():
        return {"error": "power-status.py not found"}
    try:
        r = subprocess.run(
            [sys.executable, str(POWER_STATUS), verb, "--json"],
            capture_output=True, text=True, timeout=8, cwd=REPO)
        return json.loads(r.stdout) if r.stdout.strip() else {"error": r.stderr.strip()[:200] or "no output"}
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as e:
        return {"error": str(e)}


def _graceful_shutdown_cfg() -> dict:
    """Parse the [graceful_shutdown] block from power.toml (installed) or the
    example. Tiny stdlib TOML-ish reader — no dependency."""
    path = POWER_TOML if POWER_TOML.is_file() else (POWER_TOML_DEV if POWER_TOML_DEV.is_file() else None)
    cfg = {"config_path": str(path) if path else None}
    if not path:
        return cfg
    try:
        section = None
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            m = re.match(r"\[([^\]]+)\]", line)
            if m:
                section = m.group(1)
                continue
            if section != "graceful_shutdown":
                continue
            km = re.match(r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)", line)
            if not km:
                continue
            key, val = km.group(1), km.group(2).strip()
            if val in ("true", "false"):
                cfg[key] = (val == "true")
            else:
                try:
                    cfg[key] = float(val) if "." in val else int(val)
                except ValueError:
                    cfg[key] = val.strip('"')
    except OSError as e:
        cfg["error"] = str(e)
    return cfg


def _nut_running() -> bool:
    """True if NUT's upsd (nut-server) is active — the panel's live data source."""
    try:
        r = subprocess.run(["systemctl", "is-active", "nut-server.service"],
                           capture_output=True, text=True, timeout=4)
        return r.stdout.strip() == "active"
    except (OSError, subprocess.SubprocessError):
        return False


def assemble_ups() -> dict:
    ups = _power_status("ups")
    adv = _power_status("advisories")
    return {
        "detected": bool(ups.get("detected")),
        "ups": ups.get("ups"),
        "ups_error": ups.get("error"),
        "shutdown": _graceful_shutdown_cfg(),
        "advisories": adv.get("advisories", []),
        "verdict": adv.get("verdict") or adv.get("shutdown_verdict"),
        "nut_active": _nut_running(),
        "upsc_present": bool(shutil.which("upsc")),
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
            return self._send(200, json.dumps({"module": "ups-api", "version": VERSION}))
        if path in ("/ups.json", "/ups"):
            return self._send(200, json.dumps(assemble_ups(), indent=2))
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
        # deliberately read-only: arming/disarming is a gated CLI, not a web verb
        return self._send(405, json.dumps({
            "error": "ups-api is read-only",
            "hint": "arm/disarm via power.toml [graceful_shutdown] + sovereign-osctl power-shutdown"}))


def main():
    if "--self-check" in sys.argv:
        d = assemble_ups()
        print(json.dumps({
            "module": "ups-api", "version": VERSION,
            "detected": d["detected"], "upsc_present": d["upsc_present"],
            "nut_active": d["nut_active"],
            "shutdown_minutes": d["shutdown"].get("shutdown_minutes"),
            "shutdown_enabled": d["shutdown"].get("enabled"),
        }, indent=2))
        return
    httpd = ThreadingHTTPServer((API_BIND, API_PORT), Handler)
    print(f"ups-api on http://{API_BIND}:{API_PORT}/ (webapp at /, data at /ups.json) "
          f"— Ctrl-C to stop", file=sys.stderr)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
