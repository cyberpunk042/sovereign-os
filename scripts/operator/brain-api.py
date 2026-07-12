#!/usr/bin/env python3
"""
scripts/operator/brain-api.py — HTTP API + webapp for the SOVEREIGN BRAIN: a
dedicated observatory + console for the Rust intelligence layer (the M048
gateway over the deterministic cortex) and its Memory-OS.

Where the trinity/model-health panels carry a *status strip*, this is the real
thing — you look INTO the brain and drive it:

  OBSERVE
    - the live gateway: model loaded, surfaces, never-cloud-spill tripwire, the
      cost/route ledger (via scripts/operator/lib/gateway_probe.py);
    - the MEMORY, decoded (not a count): every learned item's type (the 8 CoALA
      kinds), trust, value, freshness, flags + its cold ground-truth (the raw
      episode, the summary, the derived facts) — read from the Rust cortex store;
    - the SECOND brain beside it: the Python Memory-OS operational store
      (entries + change-ledger count);
    - the daemon/crate map — what the intelligence layer actually is.

  OPERATE
    - routing probe: send the 7 task axes + a quality dial and watch the brain
      DECIDE (route → device → compute → score). Uses POST /v1/simple, so it is a
      real request the brain also LEARNS from (surfaced honestly — the memory
      browser then shows it);
    - chat: talk to the brain via the :8787 OpenAI shim (streamed).

Read-only over the gateway's own read surfaces + a non-mutating decide/chat
compute (R10212). It never edits memory; forget/clear stay CLI-gated (SDD-052).

Endpoints:
  GET  /                     — the brain webapp
  GET  /brain.json           — status + memory summary + daemon map (panel feed)
  GET  /brain/memory         — the FULL decoded memory (both stores)
  GET  /brain/daemons        — the intelligence-layer daemon/crate map
  GET  /brain/route?complexity=…&privacy=…&…&expected_quality=0.9
                             — one routing decision (decide + learn)
  POST /brain/chat           — {messages:[…]} → streamed SSE from the :8787 shim
  GET  /version /healthz /control-systems

Env:
  BRAIN_API_BIND            (default 127.0.0.1)
  BRAIN_API_PORT            (default 8141)
  SOVEREIGN_GATEWAY_ADDR    (default 127.0.0.1:8787)
  SOVEREIGN_GATEWAY_MEMORY  (default /var/lib/sovereign-os/memory/cortex.json)
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

API_BIND = os.environ.get("BRAIN_API_BIND", "127.0.0.1")
API_PORT = int(os.environ.get("BRAIN_API_PORT", "8141"))
VERSION = "0.1.0"
GATEWAY_ADDR = os.environ.get("SOVEREIGN_GATEWAY_ADDR", "127.0.0.1:8787")

REPO = Path(__file__).resolve().parents[2]
WEBAPP_ROOT = REPO / "webapp"
WEBAPP = WEBAPP_ROOT / "brain" / "index.html"

STATIC_TYPES = {
    ".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8", ".json": "application/json",
    ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon",
    ".woff2": "font/woff2",
}

# ── shared gateway probe (status/ledger/tripwire) ────────────────────────────
_gp_spec = importlib.util.spec_from_file_location(
    "_gateway_probe", REPO / "scripts" / "operator" / "lib" / "gateway_probe.py")
_gp = importlib.util.module_from_spec(_gp_spec)
_gp_spec.loader.exec_module(_gp)

# ── the 8 CoALA memory types (HotMeta.type_code 1..8) + flags ────────────────
MEMORY_TYPES = {
    1: "working", 2: "episodic", 3: "semantic", 4: "procedural",
    5: "temporal-graph", 6: "value", 7: "kv", 8: "reward",
}
FLAG_READABLE = 1 << 0
FLAG_FAILURE_RELEVANT = 1 << 1

PY_STORE = os.environ.get(
    "SOVEREIGN_OS_MEMORY_STORE_DB", "/var/lib/sovereign-os/memory/store.json")
PY_CHANGES = os.environ.get(
    "SOVEREIGN_OS_MEMORY_CHANGE_LEDGER", "/var/lib/sovereign-os/memory/changes.json")

# The intelligence-layer daemons — de-nebulize the crates: what each binary is.
DAEMONS = [
    ("sovereign-gatewayd", "gateway",
     "M048 provider-inversion gateway over the cortex — routing decisions + the OpenAI chat shim (:8787)"),
    ("sovereign-cortex", "engine",
     "the deterministic Cortex runtime: route → place → recall → assess → compute → learn"),
    ("sovereign-serve", "serve",
     "load a real safetensors model + generate (the --model CLI)"),
    ("sovereign-chat", "chat", "interactive text-to-text chat runtime"),
    ("sovereign-agent-runtime", "agent",
     "a tool-using ReAct agent on the real quantized inference engine"),
    ("sovereign-inference-demo", "demo", "end-to-end quantized inference demonstration"),
    ("sovereign-resource-control", "resource", "resource / hardware-pressure control"),
    ("sovereign-telemetry", "telemetry", "telemetry emission surface"),
    ("sovereign-feature-selftest", "selftest", "the feature self-test harness"),
]


def _popcount(n: int) -> int:
    return bin(int(n or 0) & 0xFFFFFFFFFFFFFFFF).count("1")


def _flags(f: int) -> list[str]:
    out = []
    if f & FLAG_READABLE:
        out.append("readable")
    if f & FLAG_FAILURE_RELEVANT:
        out.append("failure-relevant")
    return out


def cortex_memory(limit: int = 300) -> dict:
    """Decode the Rust cortex store (hot metas + cold ground-truths) into
    human-readable memory items — the actual learned content, not a count."""
    path = _gp._memory_path()
    out = {"path": path, "exists": False, "count": 0, "cold_count": 0,
           "by_type": {}, "items": [], "error": None}
    try:
        with open(path, encoding="utf-8") as f:
            store = json.load(f)
    except (OSError, ValueError) as e:
        out["error"] = str(e)
        return out
    out["exists"] = True
    hot = store.get("hot") or []
    cold = store.get("cold") or {}
    out["count"] = len(hot)
    out["cold_count"] = len(cold)
    for idx, m in enumerate(hot):
        t = MEMORY_TYPES.get(m.get("type_code"), "?")
        out["by_type"][t] = out["by_type"].get(t, 0) + 1  # by_type covers ALL items
        if idx >= limit:
            continue                                       # cap only the detail list
        mid = m.get("id")
        gt = cold.get(str(mid)) or cold.get(mid) or {}
        out["items"].append({
            "id": mid,
            "type": t,
            "trust": m.get("trust"),          # 0..1000
            "value_score": m.get("value_score"),
            "freshness": m.get("freshness"),
            "topic_bits": _popcount(m.get("topic_sketch")),
            "entity_bits": _popcount(m.get("entity_sketch")),
            "flags": _flags(int(m.get("flags") or 0)),
            "summary": gt.get("summary"),
            "raw_episode": gt.get("raw_episode"),
            "derived_facts": gt.get("derived_facts") or [],
            "summary_suspect": bool(gt.get("summary_suspect", False)),
        })
    return out


def python_memory(limit: int = 300) -> dict:
    """Read the Python Memory-OS operational store (the second brain): the M028
    entries + the change-ledger size. Read-only."""
    out = {"path": PY_STORE, "exists": False, "count": 0, "active": 0,
           "changes": 0, "entries": [], "error": None}
    try:
        with open(PY_STORE, encoding="utf-8") as f:
            store = json.load(f)
    except (OSError, ValueError) as e:
        out["error"] = str(e)
        return out
    out["exists"] = True
    ents = store.get("entries") or {}
    out["count"] = len(ents)
    out["active"] = sum(1 for e in ents.values()
                        if isinstance(e, dict) and e.get("state") != "forgotten")
    for e in list(ents.values())[:limit]:
        if not isinstance(e, dict):
            continue
        out["entries"].append({k: e.get(k) for k in
                               ("id", "type", "stage", "state", "summary", "created", "updated")})
    try:
        with open(PY_CHANGES, encoding="utf-8") as f:
            out["changes"] = len(json.load(f).get("changes") or [])
    except (OSError, ValueError):
        pass
    return out


def daemon_map() -> list[dict]:
    """The intelligence-layer daemons + whether each binary is installed."""
    bindir = os.environ.get("SOVEREIGN_OS_RUST_BINDIR", "/usr/local/bin")
    return [{"bin": b, "role": r, "what": w,
             "installed": os.path.exists(os.path.join(bindir, b))}
            for (b, r, w) in DAEMONS]


def route_probe(params: dict) -> dict:
    """Send one 7-axis request to the gateway (POST /v1/simple) and return the
    decision. This is a REAL request the brain also learns from (honest)."""
    axes = {k: (params.get(k, [d])[0] if isinstance(params.get(k), list) else params.get(k, d))
            for k, d in (("complexity", "complex"), ("privacy", "private"),
                         ("safety", "safe"), ("domain", "research"),
                         ("locality", "local"), ("latency", "careful"),
                         ("quality", "oracle"))}
    try:
        q = float((params.get("expected_quality") or ["0.9"])[0])
    except (TypeError, ValueError):
        q = 0.9
    body = json.dumps({"axes": axes, "expected_quality": max(0.0, min(1.0, q))}).encode()
    req = urllib.request.Request(f"http://{GATEWAY_ADDR}/v1/simple", data=body,
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=8) as r:  # noqa: S310 (loopback)
            resp = json.loads(r.read().decode("utf-8", "replace"))
    except (urllib.error.URLError, OSError, ValueError) as e:
        return {"error": f"gateway unreachable at {GATEWAY_ADDR}: {e}", "axes": axes}
    dec = resp.get("decision") or {}
    return {
        "axes": axes,
        "kind": resp.get("kind"),
        "learned": resp.get("learned"),
        "role": (dec.get("route") or {}).get("role"),
        "reason": (dec.get("route") or {}).get("reason"),
        "summary": dec.get("summary"),
        "error": resp.get("message"),
    }


def assemble_brain() -> dict:
    """The panel's primary feed: live status + memory summary + daemon map."""
    mem = cortex_memory(limit=0)          # summary only (counts + by_type)
    pym = python_memory(limit=0)
    return {
        "gateway": _gp.probe_gateway(GATEWAY_ADDR),
        "cortex_memory": {k: mem[k] for k in ("path", "exists", "count", "cold_count", "by_type", "error")},
        "python_memory": {k: pym[k] for k in ("path", "exists", "count", "active", "changes", "error")},
        "daemons": daemon_map(),
        "gateway_addr": GATEWAY_ADDR,
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # quiet loopback daemon
        pass

    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urllib.parse.urlsplit(self.path)
        path = parsed.path.rstrip("/") or "/"
        if path == "/healthz":
            return self._send(200, json.dumps({"ok": True}))
        if path == "/version":
            return self._send(200, json.dumps({"module": "brain-api", "version": VERSION}))
        if path == "/brain.json":
            return self._send(200, json.dumps(assemble_brain(), indent=2))
        if path == "/brain/memory":
            return self._send(200, json.dumps(
                {"cortex": cortex_memory(), "python": python_memory()}, indent=2))
        if path == "/brain/daemons":
            return self._send(200, json.dumps({"daemons": daemon_map()}, indent=2))
        if path == "/brain/route":
            q = urllib.parse.parse_qs(parsed.query)
            return self._send(200, json.dumps(route_probe(q), indent=2))
        if path in ("/control-systems", "/control-systems.json"):
            return self._send(200, json.dumps(_load_control_systems()))
        if path == "/":
            if WEBAPP.exists():
                return self._send(200, WEBAPP.read_bytes(), "text/html; charset=utf-8")
            return self._send(404, json.dumps({"error": "webapp not found"}))
        return self._static(path)

    def _static(self, path):
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
        parsed = urllib.parse.urlsplit(self.path)
        if parsed.path.rstrip("/") != "/brain/chat":
            return self._send(405, json.dumps({"error": "only POST /brain/chat"}))
        # Proxy a chat to the :8787 OpenAI shim and stream the SSE straight back.
        try:
            n = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(n).decode("utf-8")) if n else {}
        except (ValueError, OSError):
            return self._send(400, json.dumps({"error": "bad chat body"}))
        msgs = payload.get("messages") or []
        body = json.dumps({"model": "sovereign", "messages": msgs, "stream": True,
                           "max_tokens": int(payload.get("max_tokens") or 96)}).encode()
        req = urllib.request.Request(f"http://{GATEWAY_ADDR}/v1/chat/completions",
                                     data=body, headers={"Content-Type": "application/json"},
                                     method="POST")
        try:
            up = urllib.request.urlopen(req, timeout=300)  # noqa: S310 (loopback)
        except (urllib.error.URLError, OSError) as e:
            return self._send(503, json.dumps({
                "error": f"gateway chat unavailable at {GATEWAY_ADDR}: {e} — "
                         "load a model (SOVEREIGN_GATEWAY_MODEL) or fetch one via "
                         "scripts/intelligence/fetch-model.sh"}))
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            with up:
                for raw in up:
                    self.wfile.write(raw)
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass


def _load_control_systems() -> dict:
    try:
        import yaml
        return yaml.safe_load((REPO / "config" / "control-systems.yaml").read_text(encoding="utf-8")) \
            or {"systems": []}
    except Exception as e:  # read-only graceful degradation
        return {"error": f"control-systems unavailable: {e}"}


def main():
    if "--self-check" in sys.argv:
        b = assemble_brain()
        print(json.dumps({
            "module": "brain-api", "version": VERSION,
            "gateway_up": b["gateway"]["up"],
            "cortex_memory_items": b["cortex_memory"]["count"],
            "python_memory_entries": b["python_memory"]["count"],
            "daemons": len(b["daemons"]),
            "daemons_installed": sum(1 for d in b["daemons"] if d["installed"]),
        }, indent=2))
        return
    httpd = ThreadingHTTPServer((API_BIND, API_PORT), Handler)
    print(f"brain-api on http://{API_BIND}:{API_PORT}/ (webapp at /, feed at /brain.json, "
          f"memory at /brain/memory) — probing gateway {GATEWAY_ADDR} — Ctrl-C to stop",
          file=sys.stderr)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
