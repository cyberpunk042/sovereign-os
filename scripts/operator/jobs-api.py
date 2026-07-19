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
    endpoints here. This is now ENFORCED, not merely documented: `mutation_guard`
    refuses non-loopback peers and any request carrying a cross-site
    Origin/Referer (browser CSRF), and the command-executing submit path
    additionally requires Content-Type: application/json (no browser
    simple-request vector) plus, when SOVEREIGN_OS_JOBS_TOKEN is provisioned,
    a matching X-Sovereign-Jobs-Token. The machine callers (osctl, the gateway's
    /plane/* calls, the VM /jobs/ingest bridge) send no Origin and pass cleanly.
  - The worker runs each kind's runner off a priority queue with a fixed number
    of dispatcher threads (high before normal before low; FIFO within a priority);
    progress + output + a checkpoint land in the persisted registry
    (scripts/operator/lib/jobs_store.py).
  - Each job gets a scratch dir under the jobs tree (WORK_ROOT/<id>) — a runner's
    cwd + log live there, so job output stays inside the one ReadWritePaths the
    unit grants (never read-only REPO or PrivateTmp). Command runners also apply
    per-job resource limits (CPU/memory/file-size/open-files via setrlimit) and a
    wall-clock timeout, so a runaway `eval` can't burn the box or hang forever.
  - On a runtime restart, a job that was mid-flight is RESUMED if its kind is
    idempotent (demo / deliberation) and it's under its attempt cap — re-enqueued
    with its checkpoint intact; a side-effecting command kind stays failed.

Endpoints:
  GET  /healthz /version
  GET  /jobs.json                 — the registry + summary (poll @2s)
  GET  /jobs/<id>                 — one job
  GET  /control-systems           — the control registry (for the pane's controls)
  POST /jobs   {kind,title,device,priority,meta}  — submit (runtime; via osctl)
  POST /jobs/<id>/cancel                          — cancel (runtime; via osctl)
  POST /jobs/ingest {id,state,progress,…}         — VM bridge upsert (loopback)

ENVIRONMENT:
  SOVEREIGN_JOBS_API_PORT    (default 8142)
  SOVEREIGN_OS_JOBS_DIR      registry dir (default /var/lib/sovereign-os/jobs)
  SOVEREIGN_OS_JOBS_STORE    registry backend: json (default, whole-file rewrite,
                             human-readable) | sqlite (opt-in, per-row atomic, WAL,
                             stdlib). Enabling sqlite auto-seeds from an existing
                             registry.json; see jobs_store.py + `--migrate-to`.
  SOVEREIGN_GATEWAY_ADDR     for deliberation jobs (default 127.0.0.1:8787)

CLI: `--self-check` (run a demo job) · `--migrate-to {json,sqlite}` (copy every
job into that backend from the other — the manual side of the store toggle).
  SOVEREIGN_OS_JOBS_WORKERS  max concurrent jobs (default 2)
  SOVEREIGN_OS_JOBS_TOKEN    optional shared secret required on command submits
  SOVEREIGN_OS_JOBS_ALLOW_NONLOOPBACK  '1' to permit non-loopback peers (unsafe)
  SOVEREIGN_OS_JOBS_MAX_CPU_SECS / _MAX_MEM_GB / _MAX_FSIZE_GB / _MAX_NOFILE
                             hard ceilings a per-job limit can only tighten below
  SOVEREIGN_OS_JOBS_MAX_TIMEOUT_SECS   wall-clock ceiling for a command job
"""
from __future__ import annotations

import itertools
import json
import os
import queue
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

try:
    import resource  # POSIX-only; the per-job rlimits degrade to no-op without it
except ImportError:  # pragma: no cover - non-POSIX
    resource = None

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
import jobs_store as _js  # noqa: E402
import compute_plane as _plane  # noqa: E402
import request_guard as _guard  # noqa: E402

VERSION = "1"
PORT = int(os.environ.get("SOVEREIGN_JOBS_API_PORT", "8142"))
GATEWAY_ADDR = os.environ.get("SOVEREIGN_GATEWAY_ADDR", "127.0.0.1:8787")
MAX_WORKERS = max(1, int(os.environ.get("SOVEREIGN_OS_JOBS_WORKERS", "2")))
REPO = Path(__file__).resolve().parents[2]
CONTROL_SYSTEMS = REPO / "config" / "control-systems.yaml"

STORE = _js.open_store()  # the active registry backend (SOVEREIGN_OS_JOBS_STORE)
PLANE = _plane.ComputePlane()   # the Sovereign Compute Plane — VRAM-fit placement

# ── request-authenticity guard (F-2026-1xx: jobs-api RCE hardening) ──────────
# `POST /jobs {kind:"eval",meta:{command:[...]}}` launches an argv as this
# daemon's user (root under the shipped unit). Before this guard it had NO
# authenticity check and `_body()` parses JSON regardless of Content-Type, so a
# web page the operator visits could drive it cross-origin (a "simple request"
# CSRF) — arbitrary command execution as root from the browser. The daemon is
# meant to be reached only by the loopback osctl/control-exec path, never a
# browser. This guard enforces exactly that, without breaking the machine
# callers (osctl, the gateway's /plane/* calls, the VM /jobs/ingest bridge)
# which send NO Origin and connect over loopback.
_ALLOW_NONLOOPBACK = os.environ.get("SOVEREIGN_OS_JOBS_ALLOW_NONLOOPBACK") == "1"
# Optional shared secret: when set, the command-executing submit path ALSO
# requires it (jobs_cli.py forwards it). Same-host defense beyond loopback.
_JOBS_TOKEN = os.environ.get("SOVEREIGN_OS_JOBS_TOKEN", "").strip()
# kinds whose runner executes an operator-supplied argv (the RCE surface).
_COMMAND_KINDS = frozenset({"eval", "model-load", "gpu-job", "model-serve"})


def mutation_guard(headers, client_host: str, *, path: str = "",
                   body: dict | None = None) -> tuple[int, str] | None:
    """Return (code, reason) to REJECT a mutating request, or None to allow.
    Pure over (headers, peer, path, body) so it is unit-testable without a
    live socket. The command-executing submit path is the RCE surface, so it
    requires application/json (via the shared guard) + an optional token; other
    mutations get the universal loopback + cross-site-Origin refusal only (the
    gateway's /plane/* + the VM /jobs/ingest bridge send no Content-Type)."""
    is_command_submit = path.rstrip("/") == "/jobs" and isinstance(body, dict) and (
        str(body.get("kind", "")) in _COMMAND_KINDS
        or isinstance((body.get("meta") or {}).get("command"), list)
    )
    rej = _guard.guard(headers, client_host,
                       require_json=is_command_submit,
                       allow_nonloopback=_ALLOW_NONLOOPBACK)
    if rej:
        return rej
    if is_command_submit and _JOBS_TOKEN:
        import hmac
        tok = (headers.get("X-Sovereign-Jobs-Token") or "").strip()
        if not hmac.compare_digest(tok, _JOBS_TOKEN):
            return 401, "command submit requires a valid X-Sovereign-Jobs-Token"
    return None
_CANCELS: dict[str, threading.Event] = {}
_CANCELS_LOCK = threading.Lock()

# ── scheduling: a priority queue drained by a fixed set of dispatcher threads ──
# High before normal before low; FIFO within a priority via a monotonic sequence.
# Replaces the flat ThreadPoolExecutor so a `high` job overtakes a backlog of
# `low` ones instead of waiting behind them. Bounded concurrency (MAX_WORKERS)
# is preserved; a VRAM-waiting job blocks its dispatcher exactly as before.
_PRIORITY_RANK = {"high": 0, "normal": 1, "low": 2}
_PQ: "queue.PriorityQueue[tuple[int, int, str]]" = queue.PriorityQueue()
_SEQ = itertools.count()
_DISPATCH_LOCK = threading.Lock()
_DISPATCHERS_STARTED = False

GB = 1024 ** 3
# Per-kind resource-limit defaults for the command runners (the argv-executing
# kinds). A per-job `meta.limits` may override, but only DOWNWARD from these +
# the global env ceilings. 0/unset = unlimited for that axis.
_KIND_LIMIT_DEFAULTS: dict[str, dict[str, int]] = {
    "eval":       {"cpu_secs": 900,  "mem_bytes": 4 * GB,  "fsize_bytes": 2 * GB,  "nofile": 1024},
    "model-load": {"cpu_secs": 1800, "mem_bytes": 32 * GB, "fsize_bytes": 64 * GB, "nofile": 4096},
    "gpu-job":    {"cpu_secs": 3600, "mem_bytes": 32 * GB, "fsize_bytes": 64 * GB, "nofile": 4096},
    # model-serve is long-lived (no CPU/wall cap); it still gets file/handle caps.
    "model-serve": {"fsize_bytes": 8 * GB, "nofile": 8192},
}
# Per-kind wall-clock timeout (seconds) for the one-shot command kinds. A hung
# child is terminated at the deadline. model-serve is deliberately absent — it is
# meant to stay up until cancelled (its readiness has its own `ready_timeout`).
_KIND_TIMEOUT_DEFAULTS: dict[str, int] = {"eval": 1800, "model-load": 3600, "gpu-job": 7200}
# Kinds safe to RE-RUN after a runtime restart: pure/idempotent, no external
# side effects. A command kind (eval/model-load/gpu-job/model-serve) may have
# already mutated the world, so it is NOT auto-resumed. vm-job is mirrored, not run.
_RESUMABLE_KINDS = frozenset({"demo", "deliberation"})
# The writable roots each kind's runner may need BEYOND its own scratch dir.
# The systemd unit's ReadWritePaths must be a superset (drift-locked by
# tests/lint/test_jobs_sandbox_readwrite_lockstep.py). The jobs dir itself is
# always granted (registry + per-job scratch live there).
KIND_WRITABLE_ROOTS: dict[str, tuple[str, ...]] = {
    "model-load":  ("/var/lib/sovereign-os/models",),
    "gpu-job":     ("/var/lib/sovereign-os/models",),
    "model-serve": ("/var/lib/sovereign-os/models",),
}


def _env_int(name: str) -> int | None:
    raw = os.environ.get(name, "").strip()
    try:
        v = int(raw)
        return v if v > 0 else None
    except ValueError:
        return None


def _resolve_limits(job: dict) -> dict[str, int]:
    """Per-job rlimits: per-kind defaults, overridden by `meta.limits`, then
    clamped to the global env ceilings (a job can tighten, never loosen past the
    operator's ceiling)."""
    limits = dict(_KIND_LIMIT_DEFAULTS.get(job["kind"], {}))
    req = (job.get("meta") or {}).get("limits") or {}
    for k in ("cpu_secs", "mem_bytes", "fsize_bytes", "nofile"):
        if isinstance(req.get(k), int) and req[k] > 0:
            limits[k] = req[k]
    ceilings = {
        "cpu_secs": _env_int("SOVEREIGN_OS_JOBS_MAX_CPU_SECS"),
        "mem_bytes": (_env_int("SOVEREIGN_OS_JOBS_MAX_MEM_GB") or 0) * GB or None,
        "fsize_bytes": (_env_int("SOVEREIGN_OS_JOBS_MAX_FSIZE_GB") or 0) * GB or None,
        "nofile": _env_int("SOVEREIGN_OS_JOBS_MAX_NOFILE"),
    }
    for k, cap in ceilings.items():
        if cap and (k not in limits or limits[k] > cap):
            limits[k] = cap
    return {k: v for k, v in limits.items() if v and v > 0}


def _resolve_timeout(job: dict) -> float | None:
    """Wall-clock timeout (s) for a one-shot command job, or None for no cap."""
    if job["kind"] not in _KIND_TIMEOUT_DEFAULTS:
        return None
    meta = job.get("meta") or {}
    t = meta.get("timeout_secs")
    t = float(t) if isinstance(t, (int, float)) and t > 0 else float(_KIND_TIMEOUT_DEFAULTS[job["kind"]])
    ceiling = _env_int("SOVEREIGN_OS_JOBS_MAX_TIMEOUT_SECS")
    if ceiling:
        t = min(t, float(ceiling))
    return t


def _rlimit_preexec(limits: dict[str, int]):
    """Build a preexec_fn that applies the resolved rlimits in the child, or None
    when unsupported/empty. Each cap is clamped to the inherited hard limit so an
    unprivileged daemon never raises a ValueError trying to exceed it."""
    if not resource or not limits:
        return None
    axes = [
        (resource.RLIMIT_CPU, limits.get("cpu_secs")),
        (resource.RLIMIT_AS, limits.get("mem_bytes")),
        (resource.RLIMIT_FSIZE, limits.get("fsize_bytes")),
        (resource.RLIMIT_NOFILE, limits.get("nofile")),
    ]

    def _apply():  # runs in the forked child, before exec
        for res, val in axes:
            if not val or val <= 0:
                continue
            try:
                _soft, hard = resource.getrlimit(res)
                cap = val if hard == resource.RLIM_INFINITY else min(val, hard)
                resource.setrlimit(res, (cap, cap if hard == resource.RLIM_INFINITY else hard))
            except (ValueError, OSError):
                pass  # best-effort — never block the launch on a cap we can't set

    return _apply


def _resolve_cwd(job: dict, workdir: Path) -> str:
    """The subprocess cwd: the job's writable scratch dir by default. A job may
    request `meta.cwd` only if it resolves under REPO (read-only source tree — a
    legitimate cwd for a script that reads repo files) or under the jobs tree;
    anything else falls back to the scratch dir rather than escaping the sandbox."""
    req = (job.get("meta") or {}).get("cwd")
    if isinstance(req, str) and req:
        try:
            cand = Path(req).resolve()
            for root in (REPO.resolve(), STORE.work_root.resolve(), _js.JOBS_DIR.resolve()):
                if cand == root or root in cand.parents:
                    if cand.is_dir():
                        return str(cand)
        except (OSError, ValueError):
            pass
    return str(workdir)


def _enqueue(jid: str, priority: str = "normal") -> None:
    _PQ.put((_PRIORITY_RANK.get(priority, 1), next(_SEQ), jid))


def _dispatch_loop() -> None:
    while True:
        _, _, jid = _PQ.get()
        try:
            run_job(jid)
        except Exception:  # a dispatcher must never die on a runner crash
            pass
        finally:
            _PQ.task_done()


def _ensure_dispatchers() -> None:
    """Start the fixed dispatcher pool once (idempotent)."""
    global _DISPATCHERS_STARTED
    with _DISPATCH_LOCK:
        if _DISPATCHERS_STARTED:
            return
        for _ in range(MAX_WORKERS):
            threading.Thread(target=_dispatch_loop, name="jobs-dispatch", daemon=True).start()
        _DISPATCHERS_STARTED = True


# ── job runners ─────────────────────────────────────────────────────────

def _cancel_event(jid: str) -> threading.Event:
    with _CANCELS_LOCK:
        ev = _CANCELS.get(jid)
        if ev is None:
            ev = threading.Event()
            _CANCELS[jid] = ev
        return ev


def _run_demo(job: dict, cancel: threading.Event) -> tuple[bool, str]:
    """A self-contained job for exercising the lifecycle without dependencies.
    Checkpoints its completed-step count so a run resumed after a runtime restart
    picks up where it left off instead of redoing finished steps."""
    steps = int(job["meta"].get("steps", 5))
    start = int((job.get("checkpoint") or {}).get("step", 0))
    for i in range(start, steps):
        if cancel.is_set():
            return False, "cancelled"
        time.sleep(float(job["meta"].get("delay", 0.2)))
        STORE.update(job["id"], progress=int((i + 1) * 100 / steps), checkpoint={"step": i + 1})
    resumed = " (resumed)" if start else ""
    return True, f"demo completed in {steps} steps{resumed}"


def _run_deliberation(job: dict, cancel: threading.Event) -> tuple[bool, str]:
    """Run a background CoAT deliberation via the gateway (:8787 /v1/coat). Being
    background work, it targets the secondary via the `"background"` model alias
    (meta.model overrides) so the interactive primary stays free — the gateway
    honestly falls back to the primary when no background model is designated."""
    meta = job["meta"]
    body = json.dumps({
        "problem": meta.get("problem", job["title"]),
        "rung": meta.get("rung", "coat"),
        "topic": int(meta.get("topic", 15)),
        "model": meta.get("model", "background"),
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
    # Keep a COMPACT trace on the job (best path + values + recall) so the Code
    # Console can render the reasoning when the task is clicked — not just a line.
    best = [{
        "depth": s.get("depth"), "category": s.get("category"), "text": s.get("text"),
        "prior": s.get("prior"), "value": s.get("value"), "visits": s.get("visits"),
        "recall": [{"id": r.get("id"), "relevance": r.get("relevance")} for r in s.get("recall", [])],
    } for s in trace.get("best_path", [])]
    STORE.update(job["id"], meta={**job["meta"], "trace": {
        "rung": trace.get("rung"), "summary": trace.get("summary"),
        "path_value": trace.get("path_value"), "recalled_total": trace.get("recalled_total"),
        "thought_source": trace.get("thought_source"), "best_path": best,
    }})
    return True, trace.get("summary", "deliberation complete")


def _run_command(job: dict, cancel: threading.Event) -> tuple[bool, str]:
    """Generic runner: launch job.meta.command (a LIST, no shell) as a subprocess,
    capture output, honor cancellation by terminating the process. Output is
    redirected to a file (NOT a PIPE): a PIPE the runner only drains after the
    process exits deadlocks a chatty child that fills the ~64 KB pipe buffer (it
    blocks on write() and never exits).

    The child runs with its cwd + log inside the job's scratch dir (under the
    sandbox-granted jobs tree, not read-only REPO / PrivateTmp), under per-job
    rlimits (CPU/memory/file-size/open-files), and is terminated at a wall-clock
    deadline so a runaway job can neither burn the box nor hang forever."""
    cmd = job["meta"].get("command")
    if not isinstance(cmd, list) or not cmd:
        return False, "job has no command list to run"
    workdir = STORE.workdir(job["id"])
    log_path = workdir / "run.log"
    cwd = _resolve_cwd(job, workdir)
    limits = _resolve_limits(job)
    timeout = _resolve_timeout(job)
    deadline = time.monotonic() + timeout if timeout else None
    try:
        with open(log_path, "w", encoding="utf-8") as out:
            proc = subprocess.Popen(cmd, stdout=out, stderr=subprocess.STDOUT,
                                    text=True, cwd=cwd, preexec_fn=_rlimit_preexec(limits))
    except (OSError, ValueError) as e:
        return False, f"failed to launch: {e}"
    try:
        STORE.update(job["id"], pid=proc.pid, progress=10, workdir=str(workdir))
        while proc.poll() is None:
            if cancel.is_set():
                _terminate(proc)
                return False, "cancelled"
            if deadline and time.monotonic() > deadline:
                _terminate(proc)
                tail = _tail_file(str(log_path))
                return False, f"timeout after {timeout:g}s" + (f"\n{tail}" if tail else "")
            time.sleep(0.3)
        tail = _tail_file(str(log_path))
        if proc.returncode == 0:
            return True, tail or "completed"
        return False, tail or f"exited {proc.returncode}"
    finally:
        _terminate(proc)


def _gateway_post(path: str, obj: dict) -> tuple[bool, str]:
    """POST JSON to the local gateway (loopback). Returns (ok, message)."""
    body = json.dumps(obj).encode("utf-8")
    req = urllib.request.Request(f"http://{GATEWAY_ADDR}{path}", data=body,
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:  # noqa: S310 (loopback)
            return True, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:200]}"
    except (urllib.error.URLError, OSError, ValueError) as e:
        return False, f"gateway unreachable at {GATEWAY_ADDR}: {e}"


def _wait_endpoint(endpoint: str, proc: subprocess.Popen, cancel: threading.Event, timeout: float) -> bool:
    """Poll a `host:port` until it accepts a TCP connection, the serve process dies,
    the deadline passes, or cancellation. True iff the endpoint came up."""
    host, _, port = endpoint.partition(":")
    try:
        port_n = int(port)
    except ValueError:
        return False
    deadline = time.monotonic() + max(1.0, float(timeout))
    while time.monotonic() < deadline:
        if cancel.is_set() or proc.poll() is not None:
            return False
        try:
            with socket.create_connection((host or "127.0.0.1", port_n), timeout=1):
                return True
        except OSError:
            time.sleep(0.5)
    return False


def _terminate(proc: subprocess.Popen) -> None:
    """Stop a serve process: SIGTERM, then SIGKILL if it lingers."""
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        try:  # reap after SIGKILL so it doesn't linger as a zombie
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass


def _tail_file(path: str, n: int = 12) -> str:
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return "\n".join(f.read().strip().splitlines()[-n:])
    except OSError:
        return ""


def _run_model_serve(job: dict, cancel: threading.Event) -> tuple[bool, str]:
    """Launch a GPU serve-process (llama-server / vLLM) on the plane-placed device,
    register it as a gateway PROXY backend, and keep it alive until cancelled. On any
    exit it terminates the process + unregisters the proxy; run_job's finally releases
    the plane VRAM claim. `meta`: command[] (argv, no shell), endpoint 'host:port',
    model_id, dialect (openai|anthropic), ready_timeout."""
    job = STORE.get(job["id"]) or job  # pick up the plane-placed device key
    meta = job.get("meta") or {}
    cmd = meta.get("command")
    if not isinstance(cmd, list) or not cmd:
        return False, "model-serve needs meta.command (the serve-process argv, no shell)"
    endpoint = str(meta.get("endpoint") or "")
    if ":" not in endpoint:
        return False, "model-serve needs meta.endpoint ('host:port' the serve-process listens on)"
    model_id = str(meta.get("model_id") or job["title"])
    dialect = "anthropic" if str(meta.get("dialect", "")).lower() == "anthropic" else "openai"
    device = str(job.get("device") or "gpu")
    vram = float(meta.get("vram_gb", 0) or 0)
    ready_timeout = float(meta.get("ready_timeout", 120) or 120)

    workdir = STORE.workdir(job["id"])
    log_path = str(workdir / "serve.log")
    cwd = _resolve_cwd(job, workdir)
    try:
        with open(log_path, "w", encoding="utf-8") as out:
            proc = subprocess.Popen(cmd, stdout=out, stderr=subprocess.STDOUT, text=True,
                                    cwd=cwd, preexec_fn=_rlimit_preexec(_resolve_limits(job)))
    except (OSError, ValueError) as e:
        return False, f"failed to launch serve process: {e}"
    # From here the process is LIVE — every post-launch statement (including the first
    # STORE.update, which rewrites the registry and can raise) must be under the
    # try/finally so a failure still terminates the process + unregisters.
    try:
        STORE.update(job["id"], pid=proc.pid, progress=15, workdir=str(workdir),
                     output=f"launching {model_id} on {device}…")
        if not _wait_endpoint(endpoint, proc, cancel, ready_timeout):
            if cancel.is_set():
                return False, "cancelled before ready"
            return False, _tail_file(log_path) or f"serve process never opened {endpoint} (timeout {ready_timeout:g}s)"
        ok, why = _gateway_post("/v1/models/register",
                                {"id": model_id, "endpoint": endpoint, "device": device,
                                 "vram_gb": vram, "dialect": dialect})
        if not ok:
            return False, f"gateway register failed: {why}"
        STORE.update(job["id"], progress=100,
                     output=f"serving {model_id} at {endpoint} ({device}, {dialect}) — cancel to stop")
        while proc.poll() is None:
            if cancel.is_set():
                return False, "cancelled"
            time.sleep(0.5)
        # the serve process exited on its own
        tail = _tail_file(log_path)
        if proc.returncode == 0:
            return True, tail or "serve process exited cleanly"
        return False, tail or f"serve process exited {proc.returncode}"
    finally:
        _terminate(proc)
        _gateway_post("/v1/models/unload", {"id": model_id})  # idempotent best-effort


_RUNNERS = {
    "demo": _run_demo,
    "deliberation": _run_deliberation,
    "eval": _run_command,
    "model-load": _run_command,
    "gpu-job": _run_command,
    "model-serve": _run_model_serve,
}


def _role_pref(job: dict) -> str | None:
    """Map a job's requested device label to an SRP role for placement."""
    dev = str(job.get("device", "")).lower()
    if "4090" in dev or "3090" in dev or dev == "logic":
        return _plane.ROLE_LOGIC
    if "pro" in dev or "oracle" in dev or "blackwell" in dev:
        return _plane.ROLE_ORACLE
    return None


def run_job(jid: str) -> None:
    """Execute one job to a terminal state, updating the registry as it goes.
    A VRAM-needing job is PLACED on a device by the compute plane first (or waits
    for one to free), and releases its claim when it finishes — so a GPU job never
    OOMs the box."""
    job = STORE.get(jid)
    if not job or job["state"] in _js.TERMINAL:
        return
    cancel = _cancel_event(jid)

    # ── admission: ATOMICALLY place + claim a device by live free VRAM, or wait ──
    # place_and_claim commits the VRAM under one lock, so two concurrent admissions
    # can't both pass the fit check on the same device and over-commit it.
    need = float((job.get("meta") or {}).get("vram_gb", 0) or 0)
    claimed = False
    if need > 0:
        announced = False
        while True:
            if cancel.is_set():
                STORE.update(jid, state="cancelled", finished=_js._now())
                return
            device = PLANE.place_and_claim(jid, need, _role_pref(job),
                                           kind=job["kind"], job=job["title"])
            if device:
                STORE.update(jid, device=device)
                claimed = True
                break
            # Announce the wait ONCE (not every 2s) — each STORE.update rewrites the
            # whole registry, so a long wait must not become a disk-write storm.
            if not announced:
                STORE.update(jid, state="queued",
                             output=f"waiting for {need:g} GB free VRAM (compute plane)…")
                announced = True
            time.sleep(2)

    try:
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
    finally:
        if claimed:
            PLANE.release(jid)
        # the job is terminal — drop its cancel Event so `_CANCELS` can't grow
        # unbounded over a long-lived daemon (one entry per job otherwise).
        with _CANCELS_LOCK:
            _CANCELS.pop(jid, None)


def submit(kind: str, title: str, device: str = "cpu", meta: dict | None = None,
           priority: str = "normal") -> dict:
    """Create + enqueue a job at its priority. Returns the created job."""
    if priority not in _js.PRIORITIES:
        priority = "normal"
    job = STORE.create(kind, title, device=device, meta=meta, priority=priority)
    if kind != "vm-job":
        _ensure_dispatchers()
        _enqueue(job["id"], priority)
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
    """On startup, reconcile jobs the previous runtime left mid-flight. A job that
    was `running` is RESUMED (re-enqueued with its checkpoint) when its kind is
    idempotent and it is under its attempt cap; otherwise it is failed loudly so
    the pane never shows a zombie 'running' forever. A side-effecting command kind
    is never auto-resumed (it may have already mutated the world). Previously-
    `queued` jobs are re-enqueued at their stored priority."""
    _ensure_dispatchers()
    for j in STORE.list():
        if j["state"] == "running":
            attempt = int(j.get("attempt", 1))
            maxa = int(j.get("max_attempts", _js.DEFAULT_MAX_ATTEMPTS))
            if j["kind"] in _RESUMABLE_KINDS and attempt < maxa:
                STORE.update(j["id"], state="queued", attempt=attempt + 1, pid=None,
                             output=f"resumed after runtime restart (attempt {attempt + 1}/{maxa})")
                _enqueue(j["id"], j.get("priority", "normal"))
            else:
                reason = ("max attempts reached" if attempt >= maxa
                          else "runtime restarted (non-resumable kind)")
                STORE.update(j["id"], state="failed", error=reason, finished=_js._now())
        elif j["state"] == "queued":
            _enqueue(j["id"], j.get("priority", "normal"))


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
                "plane": PLANE.state(),
                # The active registry backend, so the pane can show it (read-only;
                # switching is the signed `jobs store` control, not a web mutation).
                "store": {"backend": STORE.backend, "backends": list(_js.BACKENDS),
                          "path": str(STORE.path)},
            }, indent=2))
        if path == "/plane.json":
            return self._send(200, json.dumps(PLANE.state(), indent=2))
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
        # Authenticity gate — refuse browser-driven / non-loopback mutations
        # before any side effect (esp. the command-executing /jobs submit).
        reject = mutation_guard(self.headers, self.client_address[0],
                                path=path, body=body)
        if reject:
            code, reason = reject
            return self._send(code, json.dumps({"error": reason}))
        if path == "/jobs":
            kind = str(body.get("kind", ""))
            if kind not in _js.KINDS:
                return self._send(400, json.dumps({"error": f"bad kind (want {'/'.join(_js.KINDS)})"}))
            priority = str(body.get("priority", "normal"))
            if priority not in _js.PRIORITIES:
                return self._send(400, json.dumps({"error": f"bad priority (want {'/'.join(_js.PRIORITIES)})"}))
            try:
                job = submit(kind, str(body.get("title", kind)),
                             device=str(body.get("device", "cpu")), meta=body.get("meta") or {},
                             priority=priority)
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
        # ── the compute plane is the SINGLE VRAM claims authority: the gateway
        # registers model residents here so models + jobs share one VRAM view ──
        if path == "/plane/place":
            device = PLANE.place(float(body.get("need_gb", 0) or 0), body.get("role"))
            return self._send(200, json.dumps({"device": device}))
        if path == "/plane/claim":
            cid = str(body.get("id") or _js.new_id())
            rec = PLANE.claim(cid, str(body.get("device", "")), float(body.get("vram_gb", 0) or 0),
                              kind=str(body.get("kind", "model")), job=str(body.get("job", "")))
            return self._send(200, json.dumps(rec))
        if path == "/plane/release":
            return self._send(200, json.dumps({"released": PLANE.release(str(body.get("id", "")))}))
        return self._send(404, json.dumps({"error": "unknown route"}))


def main():
    argv = sys.argv[1:]
    if "--migrate-to" in argv:
        # Copy every job from the OTHER backend into the named one — the manual
        # side of the SOVEREIGN_OS_JOBS_STORE toggle. json→sqlite (enable) or
        # sqlite→json (revert); idempotent, non-destructive to the source.
        i = argv.index("--migrate-to")
        dst_b = argv[i + 1] if i + 1 < len(argv) else ""
        if dst_b not in _js.BACKENDS:
            print(json.dumps({"error": f"--migrate-to wants {'|'.join(_js.BACKENDS)}"}))
            sys.exit(2)
        src_b = "sqlite" if dst_b == "json" else "json"
        mk = lambda b: _js.SqliteStore() if b == "sqlite" else _js.JsonStore()  # noqa: E731
        src, dst = mk(src_b), mk(dst_b)
        n = _js.migrate(src, dst)
        print(json.dumps({"migrated": n, "from": src_b, "to": dst_b,
                          "src": str(src.path), "dst": str(dst.path)}, indent=2))
        sys.exit(0)
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
          f"registry {STORE.path} ({STORE.backend}) — gateway {GATEWAY_ADDR} — Ctrl-C to stop")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
