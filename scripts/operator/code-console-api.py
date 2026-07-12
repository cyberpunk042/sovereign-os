#!/usr/bin/env python3
"""scripts/operator/code-console-api.py — read-only HTTP API + webapp host for the
Code Console cockpit panel (SDD-112): a claude.ai/code-style surface for the
sovereign LOCAL LM.

The `api` + `service` + `webapp` surfaces of the §1g 8-surface ladder for the
code-console module. It composes two SHIPPED cores so the console never drifts
from the CLI / the D-22 chat:

  * the M057 session registry (scripts/lifecycle/session-registry.py) → the LEFT
    session rail (real OS task-sessions; honest-empty when the registry is absent).
  * the SDD-062/103 inference prompt engine (scripts/inference/prompt.py) → the
    bottom composer's ONE sanctioned POST (a loopback-only, NON-mutating inference
    read-compute streamed back as SSE — the exact contract D-22 uses).

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
Read-only surface (R10212) — the ONLY mutating-looking POST is the loopback chat
(a read-compute to a local model, no host/state mutation); every real action is an
MS003-signed CLI verb the console copies to the clipboard. There is NO conversation
persistence, NO plan/artifact, NO repo-attach producer on the box → the center
persisted-thread, the right Plan pane, and the repo chips are HONEST-DEFERRED in the
webapp (SB-077), never fabricated here.

Endpoints (the exact contract webapp/code-console/index.html fetches):
  GET  /api/code-console/sessions   M057 task-session model (sessions + summary)
  GET  /api/code-console/stream     Server-Sent Events (session-step-advance)
  POST /api/code-console/chat       the ONE sanctioned POST — loopback inference SSE
  GET  /webapp/ | /webapp/index.html   the Code Console SPA
  GET  /version | /healthz | /

Env (all overridable):
  CODE_CONSOLE_API_BIND             (default 127.0.0.1)
  CODE_CONSOLE_API_PORT             (default 8140)
  CODE_CONSOLE_API_DRY_RUN          (set=1 → print config + exit)
  CODE_CONSOLE_WEBAPP_PATH          (override the on-disk webapp asset)
  CODE_CONSOLE_STREAM_INTERVAL      (SSE poll seconds, default 3.0)
  SOVEREIGN_OS_SESSION_REGISTRY     (the M057 lifecycle-engine session registry)
  SOVEREIGN_OS_METRICS_DIR          (node_exporter textfile collector dir)
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

API_BIND = os.environ.get("CODE_CONSOLE_API_BIND", "127.0.0.1")
API_PORT = int(os.environ.get("CODE_CONSOLE_API_PORT", "8140"))
DRY_RUN = bool(os.environ.get("CODE_CONSOLE_API_DRY_RUN"))
STREAM_INTERVAL = float(os.environ.get("CODE_CONSOLE_STREAM_INTERVAL", "3.0"))
API_VERSION = "1.0.0"

METRICS_DIR = os.environ.get(
    "SOVEREIGN_OS_METRICS_DIR", "/var/lib/node_exporter/textfile_collector",
)
METRIC_NAME = "sovereign_os_operator_code_console_api_request_total"

_REPO_ROOT = Path(__file__).resolve().parents[2]
WEBAPP_PATH = Path(os.environ.get(
    "CODE_CONSOLE_WEBAPP_PATH",
    str(_REPO_ROOT / "webapp" / "code-console" / "index.html"),
))


def _load(mod_name: str, rel_path: str):
    """Import a hyphenated-filename core module via importlib (shared with the CLI
    so the console never drifts). Returns None on failure (degrade honestly)."""
    path = _REPO_ROOT / rel_path
    spec = importlib.util.spec_from_file_location(mod_name, path)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as e:  # noqa: BLE001 — a missing core degrades, never crashes the daemon
        sys.stderr.write(f"[warn] {rel_path} unavailable ({e})\n")
        return None
    return mod


# The M057 session-registry core (LEFT rail). Same module the sessions CLI + D-01 use.
_sessions = _load("_cc_sessionregistry_core", "scripts/lifecycle/session-registry.py")
# The SDD-062/103 inference prompt engine (composer). Same engine `inference prompt`
# + D-22 chat use, so the console's composer and the CLI never drift.
_prompt = _load("_cc_inference_prompt_engine", "scripts/inference/prompt.py")


def _emit_metric(endpoint: str, result: str) -> None:
    if DRY_RUN:
        return
    try:
        os.makedirs(METRICS_DIR, exist_ok=True)
        prom = os.path.join(METRICS_DIR, "sovereign-os-code-console-api.prom")
        with open(prom, "a") as f:
            f.write(f'{METRIC_NAME}{{endpoint="{endpoint}",result="{result}"}} 1\n')
    except OSError:
        pass


def _sessions_view() -> dict:
    """The LEFT rail model: the M057 task-sessions (honest-empty when the registry
    is absent — never fabricated). Relabelled in the UI as OS task-sessions, not
    Claude-Code chat threads (the box holds no conversation store)."""
    if _sessions is None:
        return {"sessions": [], "summary": {}, "producer": "absent",
                "note": "session-registry core unavailable"}
    try:
        model = _sessions.active()
        model.setdefault("producer", "m057-session-registry")
        return model
    except Exception as e:  # noqa: BLE001
        return {"sessions": [], "summary": {}, "producer": "error", "note": str(e)}


def _jobs_view() -> dict:
    """The RIGHT pane's Background Tasks half: a read-only proxy of the jobs-api
    runtime (:8142). Graceful when the runtime is down — the pane then shows
    'runtime offline' rather than erroring. Submission/cancel are NOT here; they
    are MS003-signed `sovereign-osctl jobs …` verbs through control-exec (R10212)."""
    addr = os.environ.get("SOVEREIGN_JOBS_API_ADDR", "127.0.0.1:8142")
    try:
        with urllib.request.urlopen(f"http://{addr}/jobs.json", timeout=5) as r:  # noqa: S310 (loopback)
            return json.loads(r.read().decode("utf-8", "replace"))
    except (urllib.error.URLError, OSError, ValueError) as e:
        return {"jobs": [], "summary": {"total": 0, "running": 0, "queued": 0},
                "offline": True, "note": f"jobs-api unreachable at {addr}: {e}"}


def _models_view() -> dict:
    """The gateway's live model registry (primary + CPU secondaries + GPU proxies,
    with device/VRAM) + the designated `background` model — a read-only proxy of the
    gateway (:8787 `GET /v1/models`) so the composer's model picker + a status strip
    show what the box can serve. Graceful when the gateway is down/modelless."""
    base = os.environ.get("SOVEREIGN_OS_ROUTER_URL", "http://127.0.0.1:8787")
    try:
        with urllib.request.urlopen(f"{base}/v1/models", timeout=3) as r:  # noqa: S310 (loopback)
            data = json.loads(r.read().decode("utf-8", "replace"))
        # a valid-JSON-but-wrong-type body (a list / string) must degrade, not raise
        # AttributeError on `.get` (which would surface as a 500, not an offline flag).
        if not isinstance(data, dict):
            data = {}
        models = [
            {"id": m.get("id"), "display_name": m.get("display_name"),
             "device": m.get("device"), "vram_gb": m.get("vram_gb")}
            for m in data.get("data", []) if isinstance(m, dict)
        ]
        return {"models": models, "background": data.get("background"),
                "producer": "sovereign-gatewayd"}
    except (urllib.error.URLError, OSError, ValueError) as e:
        return {"models": [], "background": None, "offline": True,
                "note": f"gateway unreachable at {base}: {e}"}


def _version_payload() -> dict:
    return {
        "service": "code-console-api",
        "version": API_VERSION,
        "module": "code-console",
        "catalog_source": "SDD-112 · M057 session-registry (rail) + SDD-062/103 prompt engine (composer) + M075 SRP",
        "session_registry": str(getattr(_sessions, "SESSION_REGISTRY", "unavailable")),
        "prompt_engine": "available" if _prompt is not None else "unavailable",
        "webapp_path": str(WEBAPP_PATH),
        "honest_deferred": ["persisted-thread", "plan-artifact-pane", "repo-chips"],
        "surfaces": ["core", "cli", "api", "webapp", "service"],
        "standing_rule": "We do not minimize anything.",
    }


class CodeConsoleAPIHandler(BaseHTTPRequestHandler):
    server_version = f"sovereign-os-code-console-api/{API_VERSION}"
    sys_version = ""

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write(f"[api] {self.address_string()} {fmt % args}\n")

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Sovereign-Module", "code-console-api")
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
        self.send_header("X-Sovereign-Module", "code-console-webapp")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(body)
        _emit_metric("webapp", "ok")

    def _send_stream(self) -> None:
        """SSE: emit `session-step-advance` (the name the console listens for) only
        when the M057 registry changes; heartbeat otherwise."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Sovereign-Module", "code-console-api")
        self.end_headers()
        _emit_metric("stream", "open")
        last_sig = None
        registry = getattr(_sessions, "SESSION_REGISTRY", None)
        try:
            while True:
                try:
                    st = registry.stat() if registry is not None else None
                    sig = (st.st_size, st.st_mtime) if st else (0, 0.0)
                except OSError:
                    sig = (0, 0.0)
                if sig != last_sig:
                    last_sig = sig
                    summary = _sessions_view().get("summary", {})
                    self.wfile.write(
                        f"event: session-step-advance\ndata: {json.dumps(summary)}\n\n".encode("utf-8")
                    )
                else:
                    self.wfile.write(b": heartbeat\n\n")
                self.wfile.flush()
                time.sleep(STREAM_INTERVAL)
        except (BrokenPipeError, ConnectionResetError, OSError):
            return  # client went away — normal SSE lifecycle

    def _send_chat(self) -> None:
        """SDD-112 (reuse of SDD-062/103) — the ONE sanctioned POST: a bounded,
        loopback-only inference-query proxy. A chat completion is a NON-MUTATING
        read-compute to a local model (no host/state mutation, no shell, no new
        process) — it streams token deltas back as SSE. Every REAL state mutation
        stays 405 + exec-rail-only. SB-077: an unreachable backend streams an honest
        `error` event, never a fabricated reply."""
        if _prompt is None:
            self._send_json(503, {"error": "inference prompt engine unavailable"})
            _emit_metric("chat", "503")
            return
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > 64_000:  # bounded request body
            self._send_json(400, {"error": "missing or oversize JSON body {messages|prompt}"})
            _emit_metric("chat", "400")
            return
        try:
            req = json.loads(self.rfile.read(length).decode("utf-8"))
        except (json.JSONDecodeError, ValueError, UnicodeDecodeError):
            self._send_json(400, {"error": "body must be JSON {messages} or {prompt}"})
            _emit_metric("chat", "400")
            return
        # {messages:[{role,content}]} multi-turn (bounded client-side, server holds
        # NO conversation state — R10212 read-compute); {prompt:text} stays valid.
        messages = req.get("messages")
        if messages is not None and not isinstance(messages, list):
            self._send_json(400, {"error": "messages must be a list of {role,content}"})
            _emit_metric("chat", "400")
            return
        text = str(req.get("prompt", ""))
        target = str(req.get("target", ""))  # M075 device target (auto|CPU0|GPU0|GPU1); router honors + strips it
        model = str(req.get("model", "") or "auto")  # gateway model id / "background" alias / "auto"
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Sovereign-Module", "code-console-api")
        self.end_headers()
        _emit_metric("chat", "open")
        done = None
        try:
            for ev in (_prompt.run(messages=messages, model=model, target=target) if messages is not None
                       else _prompt.run(text, model=model, target=target)):
                self.wfile.write(
                    f"event: {ev['type']}\ndata: {json.dumps(ev)}\n\n".encode("utf-8"))
                self.wfile.flush()
                if ev["type"] == "done":
                    done = ev
        except (BrokenPipeError, ConnectionResetError, OSError):
            return  # client went away mid-stream
        if done and done.get("tokens"):
            latency = done["elapsed_s"] * 1000.0 / done["tokens"]
            try:
                _prompt.publish_telemetry(done["tier"], done["tokens_per_sec"], latency)
            except Exception:  # noqa: BLE001 — telemetry is best-effort
                pass

    def do_GET(self) -> None:  # noqa: N802
        path = urllib.parse.urlsplit(self.path).path.rstrip("/") or "/"
        if path in ("/", "/healthz"):
            self._send_json(200, {"status": "ok", "version": API_VERSION})
            _emit_metric("healthz" if path == "/healthz" else "root", "ok")
            return
        if path in ("/webapp", "/webapp/index.html"):
            self._send_webapp()
            return
        if path == "/api/code-console/stream":
            self._send_stream()
            return
        try:
            if path == "/version":
                self._send_json(200, _version_payload())
                _emit_metric("version", "ok")
                return
            if path == "/api/code-console/sessions":
                self._send_json(200, _sessions_view())
                _emit_metric("sessions", "ok")
                return
            if path == "/api/code-console/jobs":
                # read-only proxy of the Background Tasks runtime (jobs-api :8142)
                self._send_json(200, _jobs_view())
                _emit_metric("jobs", "ok")
                return
            if path == "/api/code-console/models":
                # read-only proxy of the gateway's model registry (:8787 /v1/models)
                self._send_json(200, _models_view())
                _emit_metric("models", "ok")
                return
        except Exception as e:  # noqa: BLE001
            self._send_json(500, {"error": str(e)})
            _emit_metric(path.lstrip("/") or "unknown", "500")
            return
        self._send_json(404, {
            "error": f"unknown endpoint: {path!r}",
            "available": ["/api/code-console/sessions", "/api/code-console/jobs",
                          "/api/code-console/models", "/api/code-console/stream",
                          "/api/code-console/chat (POST)", "/version", "/healthz", "/webapp/"],
        })
        _emit_metric(path.lstrip("/") or "unknown", "404")

    def do_HEAD(self) -> None:  # noqa: N802
        self._send_json(200, {"status": "ok"})

    def _reject(self) -> None:
        self._send_json(405, {
            "error": "read-only surface — model/agent actions are MS003-signed CLI "
                     "verbs, never web mutations (R10212). The single exception is "
                     "POST /api/code-console/chat (a non-mutating inference read-compute "
                     "to the loopback router, SDD-062/112).",
            "allowed": ["GET", "HEAD", "POST /api/code-console/chat"],
        })
        _emit_metric(self.command.lower(), "405")

    def do_POST(self):  # noqa: N802
        path = urllib.parse.urlsplit(self.path).path.rstrip("/") or "/"
        if path == "/api/code-console/chat":
            self._send_chat()
            return
        self._reject()  # every other mutation stays 405 + exec-rail-only

    def do_PUT(self):     self._reject()  # noqa: E704 N802
    def do_DELETE(self):  self._reject()  # noqa: E704 N802


def serve(bind: str = API_BIND, port: int = API_PORT) -> int:
    print(f"[*] code-console-api {API_VERSION} on http://{bind}:{port}/", flush=True)
    httpd = ThreadingHTTPServer((bind, port), CodeConsoleAPIHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] shutting down", flush=True)
    finally:
        httpd.server_close()
    return 0


def main(argv: list[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser(description="code-console read-only API + webapp host")
    p.add_argument("--bind", default=API_BIND)
    p.add_argument("--port", type=int, default=API_PORT)
    p.add_argument("--self-check", action="store_true",
                   help="build one snapshot, print it, and exit 0 (CI smoke)")
    args = p.parse_args(argv)
    if args.self_check or DRY_RUN:
        print(json.dumps({"config": _version_payload(),
                          "sample_sessions": _sessions_view()}, indent=2))
        return 0
    return serve(args.bind, args.port)


if __name__ == "__main__":
    sys.exit(main())
