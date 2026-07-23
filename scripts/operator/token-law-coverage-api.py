#!/usr/bin/env python3
"""
scripts/operator/token-law-coverage-api.py — SDD-511 (F00796) token-law
mask-coverage heatmap panel HTTP API + webapp.

Read-only observability over the M00117 token-law engine's per-layer COVERAGE —
how much each named law (grammar / regex / denylist / regex_denylist / policy)
restricts the vocabulary at a prefix. It is checkpoint-free: the daemon POSTs a
built-in SAMPLE scenario (one representative source per layer over a fixed
sample vocab) to the gateway's `POST /v1/data-plane/token-law/fuse` route (F00797)
and reads `allowed_tokens` per layer. No model, no mutation — the same pure
decision the osctl `token-law` verb inspects, surfaced as a heatmap.

This daemon is stdlib-only. It POSTs ONLY to the sanctioned fuse route (a
read-compute, never a state mutation — the same server-side pattern brain-api
uses for /v1/simple-explain), and honest-degrades to `{up:false, error}` when
sovereign-gatewayd is unreachable so the panel renders "offline" instead of 500.

Endpoints:
  GET  /                             — the webapp (single file)
  GET  /api/token-law-coverage/coverage — per-layer coverage over the sample scenario
  GET  /version                      — service version + module identity
  GET  /healthz                      — liveness (always 200)
  GET  /control-systems              — the shared control-surface registry (same-origin)

Env vars:
  TOKEN_LAW_COVERAGE_API_BIND   (default: 127.0.0.1)
  TOKEN_LAW_COVERAGE_API_PORT   (default: 8148)
  SOVEREIGN_GATEWAY_ADDR        (default: 127.0.0.1:8787)
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

API_BIND = os.environ.get("TOKEN_LAW_COVERAGE_API_BIND", "127.0.0.1")
API_PORT = int(os.environ.get("TOKEN_LAW_COVERAGE_API_PORT", "8148"))
GATEWAY_ADDR = os.environ.get("SOVEREIGN_GATEWAY_ADDR", "127.0.0.1:8787")
VERSION = "0.1.0"

REPO = Path(__file__).resolve().parents[2]
WEBAPP_ROOT = REPO / "webapp"
WEBAPP = WEBAPP_ROOT / "token-law-coverage" / "index.html"

STATIC_TYPES = {
    ".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8", ".json": "application/json",
    ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon",
    ".woff2": "font/woff2",
}

# The built-in SAMPLE scenario: a fixed vocab + one representative source per
# layer, chosen so each law restricts a DIFFERENT slice (a meaningful heatmap).
# The engine plane names are canonical (crates/sovereign-token-law-fuse).
SAMPLE_VOCAB = [
    "the", "5", "cat", "99", "dog", "x", "1234", "hello", "a", "bad", "7", "{",
    "}", ":", "world", "3", "yes", "no", "foo", "bar", "baz", "qux", "zap", "end",
]
# per-layer isolated source (only that layer's field populated)
SAMPLE_LAYERS = [
    ("grammar", {"schema": {"type": "string"}}),
    ("regex", {"regex": "[a-z]+"}),
    ("denylist", {"denylist": ["bad", "x"]}),
    ("regex_denylist", {"regex_denylist": ["[0-9]{2,}"]}),
    # 24-token vocab → one u64 word; allow the first 12 ids (0xFFF).
    ("policy", {"policy_planes": [[0xFFF]]}),
]


def _fuse(req: dict, timeout: float = 3.0) -> dict:
    """POST a FuseRequest to the gateway's checkpoint-free fuse route; return the
    parsed reply or raise. Read-compute only (never mutates state)."""
    url = f"http://{GATEWAY_ADDR}/v1/data-plane/token-law/fuse"
    body = json.dumps(req).encode("utf-8")
    r = urllib.request.Request(url, data=body, method="POST",
                               headers={"Content-Type": "application/json",
                                        "Accept": "application/json"})
    with urllib.request.urlopen(r, timeout=timeout) as resp:  # noqa: S310 (loopback)
        return json.loads(resp.read().decode("utf-8", "replace"))


def _total_fusions(timeout: float = 2.0) -> int | None:
    """The cumulative sovereign_data_plane_token_law_mask_layers counter off the
    gateway's /metrics (a 'fusions served' stat tile; NOT per-layer coverage)."""
    try:
        url = f"http://{GATEWAY_ADDR}/metrics"
        with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310 (loopback)
            for line in resp.read().decode("utf-8", "replace").splitlines():
                if line.startswith("sovereign_data_plane_token_law_mask_layers"):
                    return int(line.split()[-1])
    except (urllib.error.URLError, OSError, ValueError):
        return None
    return None


def compute_coverage() -> dict:
    """Derive per-layer coverage over the sample scenario by POSTing to the fuse
    route. Honest-degrades to {up:false, error} when the gateway is unreachable."""
    n = len(SAMPLE_VOCAB)
    layers = []
    try:
        for name, source in SAMPLE_LAYERS:
            req = {"vocab": SAMPLE_VOCAB, "generated": "", "mask_layers": [name], **source}
            out = _fuse(req)
            layers.append({"layer": name, "allowed": int(out.get("allowed_tokens", 0)), "total": n})
        # the fused intersection of every layer (all sources, all layers active)
        combined = {"vocab": SAMPLE_VOCAB, "generated": ""}
        for _name, source in SAMPLE_LAYERS:
            combined.update(source)
        fused = _fuse(combined)
    except (urllib.error.URLError, OSError, ValueError) as e:
        return {"up": False, "error": f"gateway {GATEWAY_ADDR} unreachable: {e}"}
    return {
        "up": True,
        "error": None,
        "scenario": "sample",
        "vocab_size": n,
        "layers": layers,
        "fused_allowed": int(fused.get("allowed_tokens", 0)),
        "stop": bool(fused.get("stop", False)),
        "total_fusions": _total_fusions(),
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
            return self._send(200, json.dumps({"module": "token-law-coverage-api", "version": VERSION}))
        if path == "/api/token-law-coverage/coverage":
            return self._send(200, json.dumps(compute_coverage(), indent=2))
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
        # read-only: coverage is derived server-side from a built-in sample; the
        # panel never drives a fuse from the browser. Fail closed.
        return self._send(405, json.dumps({
            "error": "token-law-coverage-api is read-only",
            "hint": "coverage is computed from a built-in sample scenario; drive "
                    "custom fuses from the CLI (sovereign-osctl token-law fuse)"}))


def main():
    if "--self-check" in sys.argv:
        print(json.dumps({"module": "token-law-coverage-api", "version": VERSION,
                          "gateway": GATEWAY_ADDR, "sample_vocab": len(SAMPLE_VOCAB),
                          "layers": [n for n, _ in SAMPLE_LAYERS]}, indent=2))
        return
    httpd = ThreadingHTTPServer((API_BIND, API_PORT), Handler)
    print(f"token-law-coverage-api on http://{API_BIND}:{API_PORT}/ "
          f"(webapp at /, data at /api/token-law-coverage/coverage) — Ctrl-C to stop",
          file=sys.stderr)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
