#!/usr/bin/env python3
"""cockpit-bridge-api — serve the wasm Cockpit Bridge panel (audit F-2026-001).

Read-only static server for the shared wasm asset `webapp/_shared/cockpit-wasm/`
(the wasm-bindgen facade over the typed `sovereign-cockpit-*` crates — first
crate bridged: sovereign-cockpit-banner-state) and its `demo.html`.

It is also the PRODUCER half of the banner-state loop (F-2026-001): `/signals.json`
gathers the raw banner inputs from real host state (live hwmon temp, etc.), each
tagged with its provenance. It never computes the banner severity — the
sovereign-cockpit-banner-state crate does that in wasm on the panel, so the
rendered banner cannot drift from the crate the daemon trusts. That is the crate
doing its designed job: the daemon-side produces signals, the crate is the
authoritative logic, the cockpit renders.

Serves the panel with the correct `application/wasm` MIME. Read-only; POST → 405.
Endpoints: GET /healthz · /version · /bridge.json · /signals.json · / (panel) · static.
"""
from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

VERSION = "0.1.0"
API_BIND = os.environ.get("COCKPIT_BRIDGE_API_BIND", "127.0.0.1")
API_PORT = int(os.environ.get("COCKPIT_BRIDGE_API_PORT", "8137"))

REPO = Path(__file__).resolve().parents[2]
WEBAPP_ROOT = REPO / "webapp"
WASM_DIR = WEBAPP_ROOT / "_shared" / "cockpit-wasm"
# The demo page lives beside the wasm it loads (under _shared, so it is a served
# demonstrator, not a nav panel — nav-panel promotion is a follow-up per SDD-800).
PANEL = WASM_DIR / "demo.html"

STATIC_TYPES = {
    ".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8", ".json": "application/json",
    ".wasm": "application/wasm", ".svg": "image/svg+xml", ".png": "image/png",
    ".ico": "image/x-icon", ".woff2": "font/woff2", ".ts": "application/typescript",
}

# The wasm-bindgen exports the panel binds to — the bridge's public surface.
BRIDGE_EXPORTS = ["banner_severity", "banner_state", "banner_validate", "schema_version"]


def assemble_bridge() -> dict:
    """Report the bridge's build state (read-only). The panel does the compute;
    this just tells the operator whether the wasm asset is present + wired."""
    js = WASM_DIR / "cockpit_wasm.js"
    wasm = WASM_DIR / "cockpit_wasm_bg.wasm"
    js_text = js.read_text(encoding="utf-8") if js.is_file() else ""
    return {
        "module": "cockpit-bridge-api",
        "version": VERSION,
        "panel_present": PANEL.is_file(),
        "wasm_present": wasm.is_file(),
        "wasm_bytes": wasm.stat().st_size if wasm.is_file() else 0,
        "glue_present": js.is_file(),
        "exports": [e for e in BRIDGE_EXPORTS if e in js_text],
        "first_crate": "sovereign-cockpit-banner-state",
        "finding": "F-2026-001",
    }


# --- the PRODUCER half of the banner-state loop (F-2026-001) ----------------
# The crate is the typed source-of-truth the daemon PRODUCES and the cockpit
# RENDERS. This gathers the raw banner signals from real host state (each tagged
# with its provenance) — it does NOT compute the banner severity: the
# sovereign-cockpit-banner-state crate does that in wasm on the panel, so the
# rendered banner can never drift from the crate's own logic.

def _max_hwmon_temp_c():
    """Highest live hwmon temperature in °C, or None if unreadable."""
    best = None
    try:
        for p in Path("/sys/class/hwmon").glob("hwmon*/temp1_input"):
            try:
                v = int(p.read_text().strip()) / 1000.0
            except (OSError, ValueError):
                continue
            if v > 0 and (best is None or v > best):
                best = v
    except OSError:
        pass
    return best


def _thermal_verdict(temp_c):
    """Map a live max temp to a ThermalVerdict token. Gather-step generic
    thresholds — the real per-target policy is sovereign-hardware-thermal-policy
    (a separate integration). Returns (verdict, provenance)."""
    if temp_c is None:
        return "cool", "default (no live temp readable)"
    if temp_c >= 90:
        v = "shutdown"
    elif temp_c >= 80:
        v = "throttle"
    elif temp_c >= 65:
        v = "warm"
    else:
        v = "cool"
    return v, f"live (max hwmon {temp_c:.1f}°C → generic threshold)"


def assemble_signals() -> dict:
    """The raw banner-state inputs from real host state, with per-signal
    provenance. Read-only; degrades to honest defaults."""
    temp_c = _max_hwmon_temp_c()
    verdict, thermal_src = _thermal_verdict(temp_c)
    return {
        "mode": "plan",
        "bundle": "careful",
        "worst_thermal": verdict,
        "open_alerts": 0,
        "temp_c": round(temp_c, 1) if temp_c is not None else None,
        "sources": {
            "mode": "default — no persistent execution-mode source wired yet",
            "bundle": "default — active-bundle source not wired yet",
            "worst_thermal": thermal_src,
            "open_alerts": "default — alerts source not wired yet",
        },
        "computed_by": "NOT here — sovereign-cockpit-banner-state computes the "
                       "severity + envelope in wasm on the panel from these signals",
    }


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
            return self._send(200, json.dumps({"module": "cockpit-bridge-api", "version": VERSION}))
        if path in ("/bridge.json", "/bridge"):
            return self._send(200, json.dumps(assemble_bridge(), indent=2))
        if path in ("/signals.json", "/signals"):
            return self._send(200, json.dumps(assemble_signals(), indent=2))
        if path == "/":
            if PANEL.is_file():
                return self._send(200, PANEL.read_bytes(), "text/html; charset=utf-8")
            return self._send(404, json.dumps({"error": "panel not found"}))
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
        # Read-only: the bridge computes in-browser; there is nothing to mutate.
        return self._send(405, json.dumps({
            "error": "cockpit-bridge-api is read-only",
            "hint": "the bridge runs entirely client-side in wasm"}))


def main():
    if "--self-check" in sys.argv:
        print(json.dumps(assemble_bridge(), indent=2))
        return
    httpd = ThreadingHTTPServer((API_BIND, API_PORT), Handler)
    print(f"cockpit-bridge-api on http://{API_BIND}:{API_PORT}/ "
          f"(panel at /, wasm at /_shared/cockpit-wasm/, meta at /bridge.json) "
          f"— Ctrl-C to stop", file=sys.stderr)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.shutdown()


if __name__ == "__main__":
    main()
