#!/usr/bin/env python3
"""
scripts/operator/jobs-api.py — the Background Tasks runtime (:8142).

The job runtime behind the Code Console's Background Tasks pane: it launches,
tracks, and can cancel long-running work the box runs OFF the request path — a
background CoAT deliberation, a model eval, a secondary-model load, a GPU job —
and mirrors jobs from the RTX-4090 passthrough VM. Stdlib only; loopback.

Doctrine:
  - READ endpoints (/jobs.json, /jobs/<id>) feed the pane and are safe to poll.
  - SUBMIT / CANCEL are ACTIONS: the webapp never POSTs here directly — it goes
    through the ONE sanctioned execute daemon (control-exec-api) which runs
    `sovereign-osctl jobs submit|cancel`, which calls the localhost runtime
    endpoints here. A job is authorized at submission; the worker then runs it.
  - The worker runs each kind's runner in a bounded pool; progress + output land
    in the persisted registry (scripts/operator/lib/jobs_store.py).

Endpoints:
  GET  /healthz /version
  GET  /jobs.json                 — the registry + summary (poll @2s)
  GET  /jobs/<id>                 — one job
  GET  /control-systems           — the control registry (for the pane's controls)
  POST /jobs        {kind,title,device,meta}     — submit (runtime; via osctl)
  POST /jobs/<id>/cancel                          — cancel (runtime; via osctl)
  POST /jobs/ingest {id,state,progress,…}         — VM bridge upsert (loopback)

ENVIRONMENT:
  SOVEREIGN_JOBS_API_PORT    (default 8142)
  SOVEREIGN_OS_JOBS_DIR      registry dir (default /var/lib/sovereign-os/jobs)
  SOVEREIGN_GATEWAY_ADDR     for deliberation jobs (default 127.0.0.1:8787)
  SOVEREIGN_OS_JOBS_WORKERS  max concurrent jobs (default 2)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
import jobs_store as _js  # noqa: E402

VERSION = "1"
PORT = int(os.environ.get("SOVEREIGN_JOBS_API_PORT", "8142"))
GATEWAY_ADDR = os.environ.get("SOVEREIGN_GATEWAY_ADDR", "127.0.0.1:8787")
MAX_WORKERS = max(1, int(os.environ.get("SOVEREIGN_OS_JOBS_WORKERS", "2")))
REPO = Path(__file__).resolve().parents[2]
CONTROL_SYSTEMS = REPO / "config" / "control-systems.yaml"

STORE = _js.JobStore()
_POOL = ThreadPoolExecutor(max_workers=MAX_WORKERS)
_CANCELS: dict[str, threading.Event] = {}
_CANCELS_LOCK = threading.Lock()


# ── job runners ─────────────────────────────────────────────────────────

def _cancel_event(jid: str) -> threading.Event:
    with _CANCELS_LOCK:
        ev = _CANCELS.get(jid)
        if ev is None:
            ev = threading.Event()
            _CANCELS[jid] = ev
        return ev


def _run_demo(job: dict, cancel: threading.Event) -> tuple[bool, str]:
    """A self-contained job for exercising the lifecycle without dependencies."""
    steps = int(job["meta"].get("steps", 5))
    for i in range(steps):
        if cancel.is_set():
            return False, "cancelled"
        time.sleep(float(job["meta"].get("delay", 0.2)))
        STORE.update(job["id"], progress=int((i + 1) * 100 / steps))
    return True, f"demo completed in {steps} steps"


def _run_deliberation(job: dict, cancel: threading.Event) -> tuple[bool, str]:
    """Run a background CoAT deliberation via the gateway (:8787 /v1/coat)."""
    meta = job["meta"]
    body = json.dumps({
        "problem": meta.get("problem", job["title"]),
        "rung": meta.get("rung", "coat"),
        "topic": int(meta.get("topic", 15)),
    }).encode()
    STORE.update(job["id"], progress=15)
    if cancel.is_set():
        return False, "cancelled"
    req = urllib.request.Request(f"http://{GATEWAY_ADDR}/v1/coat", data=body,
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310 (loopback)
            resp = json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read().decode("utf-8", "replace")).get("message", f"HTTP {e.code}")
        except (ValueError, OSError):
            msg = f"HTTP {e.code}"
        return False, f"gateway refused: {msg}"
    except (urllib.error.URLError, OSError, ValueError) as e:
        return False, f"gateway unreachable at {GATEWAY_ADDR}: {e}"
    trace = resp.get("trace") or {}
    return True, trace.get("summary", "deliberation complete")


def _run_command(job: dict, cancel: threading.Event) -> tuple[bool, str]:
    """Generic runner: launch job.meta.command (a LIST, no shell) as a subprocess,
    capture output, honor cancellation by terminating the process."""
    cmd = job["meta"].get("command")
    if not isinstance(cmd, list) or not cmd:
        return False, "job has no command list to run"
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True, cwd=str(REPO))
    except (OSError, ValueError) as e:
        return False, f"failed to launch: {e}"
    STORE.update(job["id"], pid=proc.pid, progress=10)
    while proc.poll() is None:
        if cancel.is_set():
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
            return False, "cancelled"
        time.sleep(0.3)
    out = (proc.stdout.read() if proc.stdout else "") or ""
    tail = "\n".join(out.strip().splitlines()[-12:])
    if proc.returncode == 0:
        return True, tail or "completed"
    return False, tail or f"exited {proc.returncode}"


_RUNNERS = {
    "demo": _run_demo,
    "deliberation": _run_deliberation,
    "eval": _run_command,
    "model-load": _run_command,
    "gpu-job": _run_command,
}


def run_job(jid: str) -> None:
    """Execute one job to a terminal state, updating the registry as it goes."""
    job = STORE.get(jid)
    if not job or job["state"] in _js.TERMINAL:
        return
    cancel = _cancel_event(jid)
    STORE.update(jid, state="running", started=_js._now(), progress=max(job["progress"], 5))
    runner = _RUNNERS.get(job["kind"])
    if runner is None:
        STORE.update(jid, state="failed", error=f"no runner for kind {job['kind']}", finished=_js._now())
        return
    try:
        ok, msg = runner(job, cancel)
    except Exception as e:  # a runner crash must not take down the worker
        STORE.update(jid, state="failed", error=f"runner error: {e}", finished=_js._now())
        return
    if cancel.is_set():
        STORE.update(jid, state="cancelled", finished=_js._now(), output=msg)
    elif ok:
        STORE.update(jid, state="done", progress=100, finished=_js._now(), output=msg)
    else:
        STORE.update(jid, state="failed", finished=_js._now(), error=msg)


def submit(kind: str, title: str, device: str = "cpu", meta: dict | None = None) -> dict:
    """Create + enqueue a job. Returns the created job."""
    job = STORE.create(kind, title, device=device, meta=meta)
    if kind != "vm-job":
        _POOL.submit(run_job, job["id"])
    return job


def cancel(jid: str) -> dict | None:
    """Signal cancellation; the runner stops at its next checkpoint."""
    job = STORE.get(jid)
    if not job:
        return None
    if job["state"] in _js.TERMINAL:
        return job
    _cancel_event(jid).set()
    return STORE.update(jid, state="cancelled" if job["state"] == "queued" else job["state"])


def resume_orphans() -> None:
    """On startup, mark previously-running jobs as failed (the worker that owned
    them died) so the pane never shows a zombie 'running' forever."""
    for j in STORE.list():
        if j["state"] == "running":
            STORE.update(j["id"], state="failed", error="runtime restarted", finished=_js._now())
        elif j["state"] == "queued":
            _POOL.submit(run_job, j["id"])


# ── HTTP surface ────────────────────────────────────────────────────────

def _control_systems() -> dict:
    try:
        import yaml  # optional; the pane degrades without it
        return yaml.safe_load(CONTROL_SYSTEMS.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


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
            return self._send(200, json.dumps({"module": "jobs-api", "version": VERSION}))
        if path == "/jobs.json":
            jobs = STORE.list()
            return self._send(200, json.dumps({
                "jobs": jobs, "summary": _js.summary(jobs), "gateway_addr": GATEWAY_ADDR,
            }, indent=2))
        if path.startswith("/jobs/"):
            job = STORE.get(path[len("/jobs/"):])
            if job:
                return self._send(200, json.dumps(job, indent=2))
            return self._send(404, json.dumps({"error": "no such job"}))
        if path in ("/control-systems", "/control-systems.json"):
            return self._send(200, json.dumps(_control_systems()))
        return self._send(404, json.dumps({"error": "not found", "path": path}))

    def _body(self) -> dict:
        try:
            n = int(self.headers.get("Content-Length", "0"))
            return json.loads(self.rfile.read(n).decode("utf-8", "replace")) if n else {}
        except (ValueError, OSError):
            return {}

    def do_POST(self):
        parsed = urllib.parse.urlsplit(self.path)
        path = parsed.path.rstrip("/") or "/"
        body = self._body()
        if path == "/jobs":
            kind = str(body.get("kind", ""))
            if kind not in _js.KINDS:
                return self._send(400, json.dumps({"error": f"bad kind (want {'/'.join(_js.KINDS)})"}))
            try:
                job = submit(kind, str(body.get("title", kind)),
                             device=str(body.get("device", "cpu")), meta=body.get("meta") or {})
            except ValueError as e:
                return self._send(400, json.dumps({"error": str(e)}))
            return self._send(200, json.dumps(job))
        if path.startswith("/jobs/") and path.endswith("/cancel"):
            jid = path[len("/jobs/"):-len("/cancel")]
            job = cancel(jid)
            if job:
                return self._send(200, json.dumps(job))
            return self._send(404, json.dumps({"error": "no such job"}))
        if path == "/jobs/ingest":
            return self._send(200, json.dumps(STORE.ingest(body)))
        return self._send(404, json.dumps({"error": "unknown route"}))


def main():
    argv = sys.argv[1:]
    if "--self-check" in argv:
        job = submit("demo", "self-check", meta={"steps": 3, "delay": 0.01})
        for _ in range(200):
            j = STORE.get(job["id"])
            if j and j["state"] in _js.TERMINAL:
                break
            time.sleep(0.02)
        j = STORE.get(job["id"])
        ok = bool(j and j["state"] == "done")
        print(json.dumps({"self_check": "ok" if ok else "FAIL", "job": j}, indent=2))
        sys.exit(0 if ok else 1)
    resume_orphans()
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"jobs-api on 127.0.0.1:{PORT} (Background Tasks runtime; {MAX_WORKERS} workers) — "
          f"registry {STORE.path} — gateway {GATEWAY_ADDR} — Ctrl-C to stop")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
