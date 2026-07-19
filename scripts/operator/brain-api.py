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
  GET  /brain/coat?problem=…&rung=coat&topic=15 — CoAT deliberation (iterative
                             MCTS + associative recall from the live Memory-OS),
                             SYNCHRONOUS on the request thread (timeout-bounded)
  GET  /brain/coat/submit?problem=…&rung=…&topic=… — submit the deliberation as a
                             background-jobs `"deliberation"` job (:8142); returns
                             {job_id} at once (F-2026-063 — the webapp's path)
  GET  /brain/coat/result?id=… — poll a submitted deliberation → {done,state,
                             progress[,trace|error]} in the CoAT render shape
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
JOBS_ADDR = os.environ.get("SOVEREIGN_JOBS_ADDR", "127.0.0.1:8142")

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
    """Preview one 7-axis routing decision (POST /v1/simple-explain) — the
    read-only sibling of /v1/simple: the gateway decides and returns the full
    decision but does NOT learn, so probing never pollutes memory."""
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
    req = urllib.request.Request(f"http://{GATEWAY_ADDR}/v1/simple-explain", data=body,
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


def coat_deliberate(params: dict) -> dict:
    """Run one CoAT deliberation (POST /v1/coat) — the `sovereign-coat` iterative
    MCTS reasoning engine, recalling associative memory from the live Cortex
    Memory-OS at every expansion (CoAT's defining mechanism). Read-only: the
    gateway decides without learning, so a deliberation never pollutes memory."""
    def _one(key, default):
        v = params.get(key, default)
        return v[0] if isinstance(v, list) else v

    problem = (_one("problem", "") or "").strip()
    if not problem:
        return {"error": "problem is required", "best_path": [], "tree": []}
    rung = (_one("rung", "coat") or "coat").strip().lower()
    try:
        topic = int(_one("topic", "15") or 15)          # 0b1111 overlaps seeded memory
    except (TypeError, ValueError):
        topic = 15
    try:
        entity = int(_one("entity", "0") or 0)
    except (TypeError, ValueError):
        entity = 0
    body = json.dumps({"problem": problem, "topic": topic,
                       "entity": entity, "rung": rung}).encode()
    req = urllib.request.Request(f"http://{GATEWAY_ADDR}/v1/coat", data=body,
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:  # noqa: S310 (loopback)
            resp = json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        # A request-level refusal (e.g. 422 unknown rung) — surface the gateway's
        # STRUCTURED message, not a misleading "unreachable". HTTPError subclasses
        # URLError, so this arm must precede the connectivity arm.
        try:
            body = json.loads(e.read().decode("utf-8", "replace"))
            msg = body.get("message") or body.get("error") or f"gateway HTTP {e.code}"
        except (ValueError, OSError):
            msg = f"gateway HTTP {e.code}"
        return {"error": msg, "best_path": [], "tree": []}
    except (urllib.error.URLError, OSError, ValueError) as e:
        return {"error": f"gateway unreachable at {GATEWAY_ADDR}: {e}",
                "best_path": [], "tree": []}
    if not isinstance(resp, dict):
        return {"error": "unexpected gateway response", "best_path": [], "tree": []}
    if resp.get("kind") == "error":
        return {"error": resp.get("message", "gateway error"), "best_path": [], "tree": []}
    trace = resp.get("trace") or {}
    if not isinstance(trace, dict):
        trace = {}
    trace.setdefault("best_path", [])
    trace.setdefault("tree", [])
    return trace


def coat_submit(params: dict) -> dict:
    """Steer a CoAT deliberation onto the background-jobs runtime (:8142) instead
    of blocking on the synchronous /brain/coat call (F-2026-063): submit a
    `"deliberation"` job and return its id, so the request thread returns at once
    and the webapp polls /brain/coat/result. A deliberation is NOT a command kind,
    so the jobs mutation-guard needs only loopback + same-origin (no token), and
    it is read-only over memory (a deliberation never learns) — consistent with
    this daemon's read-only-over-memory contract."""
    def _one(key, default):
        v = params.get(key, default)
        return v[0] if isinstance(v, list) else v

    problem = (_one("problem", "") or "").strip()
    if not problem:
        return {"error": "problem is required"}
    rung = (_one("rung", "coat") or "coat").strip().lower()
    try:
        topic = int(_one("topic", "15") or 15)
    except (TypeError, ValueError):
        topic = 15
    body = json.dumps({
        "kind": "deliberation", "title": problem[:120], "priority": "normal",
        "meta": {"problem": problem, "rung": rung, "topic": topic},
    }).encode()
    req = urllib.request.Request(f"http://{JOBS_ADDR}/jobs", data=body,
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:  # noqa: S310 (loopback)
            job = json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read().decode("utf-8", "replace")).get("error", f"HTTP {e.code}")
        except (ValueError, OSError):
            msg = f"HTTP {e.code}"
        return {"error": f"jobs runtime refused: {msg}"}
    except (urllib.error.URLError, OSError, ValueError) as e:
        return {"error": f"jobs runtime unreachable at {JOBS_ADDR}: {e}"}
    if not isinstance(job, dict) or not job.get("id"):
        return {"error": "jobs runtime returned no job id"}
    return {"job_id": job["id"], "state": job.get("state", "queued")}


def coat_result(params: dict) -> dict:
    """Poll a background deliberation job (:8142 GET /jobs/<id>) and shape it for
    the CoAT observatory. Returns {done,state,progress}; when done, the runner's
    compact trace (best_path + summary + thought_source + path_value) in the shape
    the renderer already consumes; on failure, the job's error. The webapp polls
    this until `done`."""
    def _one(key, default):
        v = params.get(key, default)
        return v[0] if isinstance(v, list) else v

    jid = (_one("id", "") or "").strip()
    if not jid:
        return {"error": "id is required", "done": True}
    url = f"http://{JOBS_ADDR}/jobs/{urllib.parse.quote(jid, safe='')}"
    try:
        with urllib.request.urlopen(url, timeout=10) as r:  # noqa: S310 (loopback)
            job = json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        return {"error": f"no such job (HTTP {e.code})", "done": True}
    except (urllib.error.URLError, OSError, ValueError) as e:
        return {"error": f"jobs runtime unreachable at {JOBS_ADDR}: {e}", "done": True}
    if not isinstance(job, dict):
        return {"error": "unexpected jobs response", "done": True}
    state = job.get("state", "queued")
    done = state in ("done", "failed", "cancelled")
    out = {"done": done, "state": state, "progress": job.get("progress", 0)}
    if state == "done":
        trace = (job.get("meta") or {}).get("trace") or {}
        out.update({
            "rung": trace.get("rung", "CoAT"),
            "best_path": trace.get("best_path", []),
            "thought_source": trace.get("thought_source"),
            "path_value": trace.get("path_value"),
            "recalled_total": trace.get("recalled_total"),
            "summary": trace.get("summary"),
        })
    elif state in ("failed", "cancelled"):
        out["error"] = job.get("error") or job.get("output") or f"deliberation {state}"
    return out


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
        if path == "/brain/coat":
            q = urllib.parse.parse_qs(parsed.query)
            return self._send(200, json.dumps(coat_deliberate(q), indent=2))
        if path == "/brain/coat/submit":
            q = urllib.parse.parse_qs(parsed.query)
            return self._send(200, json.dumps(coat_submit(q), indent=2))
        if path == "/brain/coat/result":
            q = urllib.parse.parse_qs(parsed.query)
            return self._send(200, json.dumps(coat_result(q), indent=2))
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
