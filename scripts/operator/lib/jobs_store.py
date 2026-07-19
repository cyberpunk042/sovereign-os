#!/usr/bin/env python3
"""
scripts/operator/lib/jobs_store.py — the persisted background-job registry.

The single source of truth for Background Tasks: a registry of jobs that SURVIVES
a restart, shared by the jobs-api runtime (scripts/operator/jobs-api.py) and the
`sovereign-osctl jobs` CLI. Stdlib only.

A job is a long-running unit of work the box runs off the request path — a
background CoAT deliberation, a model eval, a secondary-model load, a GPU job, or
a job mirrored from the RTX-4090 passthrough VM. The registry is the read model
the Code Console's Background Tasks pane renders.

Location: /var/lib/sovereign-os/jobs/ (override SOVEREIGN_OS_JOBS_DIR).

## Two interchangeable backends — the `SOVEREIGN_OS_JOBS_STORE` toggle

The registry is pluggable; both backends implement the identical `create` / `get`
/ `list` / `update` / `ingest` / `prune` contract and the same on-disk job-record
shape, so nothing downstream (the pane, the CLI, the summary) can tell them apart.
Pick one with `SOVEREIGN_OS_JOBS_STORE` (default **json**):

- **json** (default) — one `registry.json`, rewritten WHOLE on every mutation via
  atomic temp+rename. **Human-readable** (cat/jq/edit it), zero moving parts, and
  a crash never leaves a torn file. The trade-off is that every write serializes +
  re-encodes the entire registry, so cost grows with the job count; at Background-
  Tasks scale (hundreds of bounded, pruned jobs) that is a non-issue — which is why
  it stays the default.
- **sqlite** (opt-in) — one `registry.db` (Python stdlib `sqlite3`, **no new
  dependency**) in WAL mode. Each mutation is an atomic **per-row** upsert, so a
  write touches only the one job (no whole-file rewrite) and concurrent readers
  never block writers. Choose it when the registry grows large or several processes
  touch it at once. The trade-off is a binary file (not hand-editable) and the
  `sqlite3` module.

Switching is safe + reversible: enabling sqlite with an empty db AUTO-SEEDS from an
existing `registry.json` (one-way json→sqlite), and `jobs-api.py --migrate-to
{json,sqlite}` copies every job either direction on demand (see `migrate`).
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import threading
import time
import uuid
from pathlib import Path

JOBS_DIR = Path(os.environ.get("SOVEREIGN_OS_JOBS_DIR", "/var/lib/sovereign-os/jobs"))
REGISTRY = JOBS_DIR / "registry.json"
SQLITE_REGISTRY = JOBS_DIR / "registry.db"
# Per-job scratch lives UNDER the jobs dir (already the unit's sole ReadWritePaths)
# so a runner's cwd + log never hit read-only REPO or PrivateTmp — the F-2026-091
# sandbox-breakage fix. One subdir per job id; dropped when the job is pruned.
WORK_ROOT = JOBS_DIR / "work"

# The registry backends. `json` (whole-file rewrite) is the default; `sqlite`
# (per-row upsert, stdlib) is opt-in via SOVEREIGN_OS_JOBS_STORE.
BACKENDS = ("json", "sqlite")
DEFAULT_BACKEND = "json"

# The v1 job kinds. `vm-job` entries are mirrored from the passthrough VM bridge
# and are not executed by the host worker.
KINDS = ("deliberation", "eval", "model-load", "gpu-job", "vm-job", "demo", "model-serve")
# Lifecycle states.
STATES = ("queued", "running", "done", "failed", "cancelled")
# Terminal states (the worker never resumes these).
TERMINAL = ("done", "failed", "cancelled")
# Scheduling priorities (high runs before normal runs before low); best-effort
# ordering at admission, not preemption.
PRIORITIES = ("high", "normal", "low")
_DEFAULT_PRIORITY = "normal"
# The default attempt ceiling for a resumable job that is re-enqueued after a
# runtime restart (see jobs-api.resume_orphans).
DEFAULT_MAX_ATTEMPTS = 3

_lock = threading.RLock()


def _now() -> int:
    return int(time.time())


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def _new_record(kind: str, title: str, device: str, meta: dict | None,
                priority: str, max_attempts: int, jid: str | None = None) -> dict:
    """The canonical shape of a freshly-created job — the single source of truth
    for the record both backends persist, so a json job and a sqlite job are
    byte-identical dicts."""
    if kind not in KINDS:
        raise ValueError(f"unknown job kind {kind!r} (want {'/'.join(KINDS)})")
    if priority not in PRIORITIES:
        raise ValueError(f"unknown priority {priority!r} (want {'/'.join(PRIORITIES)})")
    return {
        "id": jid or new_id(),
        "kind": kind,
        "title": title,
        "device": device,
        "state": "queued",
        "priority": priority,
        "progress": 0,
        "created": _now(),
        "updated": _now(),
        "started": None,
        "finished": None,
        "output": "",
        "error": "",
        "pid": None,
        "workdir": None,
        # Restart bookkeeping: `attempt` counts runs; a resumable job that is
        # re-enqueued after a runtime restart bumps it, up to `max_attempts`.
        # `checkpoint` is a per-runner opaque dict the worker persists so a
        # resumed run can skip already-finished work instead of redoing it.
        "attempt": 1,
        "max_attempts": max(1, int(max_attempts)),
        "checkpoint": {},
        "meta": meta or {},
    }


def _vm_record(job: dict, prior_created: int | None) -> dict:
    """The shape of a job mirrored from the passthrough-VM bridge (upserted by id).
    Preserves the original `created` when the id already existed."""
    jid = str(job.get("id") or ("vm-" + new_id()))
    return {
        "id": jid,
        "kind": "vm-job",
        "title": job.get("title", "vm job"),
        "device": job.get("device", "rtx-4090-vm"),
        "state": job.get("state", "running"),
        "priority": _DEFAULT_PRIORITY,
        "progress": int(job.get("progress", 0)),
        "created": prior_created if prior_created is not None else _now(),
        "updated": _now(),
        "started": job.get("started"),
        "finished": job.get("finished"),
        "output": job.get("output", ""),
        "error": job.get("error", ""),
        "pid": job.get("pid"),
        "workdir": None,
        "attempt": 1,
        "max_attempts": DEFAULT_MAX_ATTEMPTS,
        "checkpoint": {},
        "meta": job.get("meta", {}),
    }


class _ScratchMixin:
    """Per-job filesystem scratch — identical for every backend, since job OUTPUT
    always lives on disk under the jobs tree (the one ReadWritePaths the unit
    grants) regardless of where the registry METADATA is stored."""

    path: Path  # the registry file/db; its parent is the jobs dir

    @property
    def work_root(self) -> Path:
        """The per-job scratch root, sibling to the registry (so it lands under
        the same ReadWritePaths-granted jobs dir the registry lives in)."""
        return self.path.parent / "work"

    def workdir(self, jid: str) -> Path:
        """The scratch dir for one job (created on demand). A runner sets its cwd
        + log here so all job output stays inside the sandbox-granted jobs tree."""
        wd = self.work_root / jid
        wd.mkdir(parents=True, exist_ok=True)
        return wd

    def drop_workdir(self, jid: str) -> None:
        """Best-effort removal of a job's scratch dir (called on prune)."""
        shutil.rmtree(self.work_root / jid, ignore_errors=True)


class JsonStore(_ScratchMixin):
    """A persisted, thread-safe job registry — one `registry.json` rewritten WHOLE
    on every mutation via atomic temp+rename. The default backend."""

    backend = "json"

    def __init__(self, path: Path | str = REGISTRY):
        self.path = Path(path)
        self._jobs: dict[str, dict] = {}
        self.load()

    def load(self) -> None:
        with _lock:
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                self._jobs = data.get("jobs", {}) if isinstance(data, dict) else {}
            except (FileNotFoundError, ValueError, OSError):
                self._jobs = {}

    def save(self) -> None:
        with _lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps({"jobs": self._jobs}, indent=2), encoding="utf-8")
            os.replace(tmp, self.path)  # atomic — a crash never leaves a torn file

    def create(self, kind: str, title: str, device: str = "cpu", meta: dict | None = None,
               priority: str = _DEFAULT_PRIORITY, max_attempts: int = DEFAULT_MAX_ATTEMPTS) -> dict:
        job = _new_record(kind, title, device, meta, priority, max_attempts)
        with _lock:
            self._jobs[job["id"]] = job
            self.save()
        return dict(job)

    def get(self, jid: str) -> dict | None:
        with _lock:
            j = self._jobs.get(jid)
            return dict(j) if j else None

    def list(self) -> list[dict]:
        with _lock:
            return sorted((dict(j) for j in self._jobs.values()), key=lambda j: -j["created"])

    def update(self, jid: str, **fields) -> dict | None:
        with _lock:
            if jid not in self._jobs:
                return None
            self._jobs[jid].update(fields)
            self._jobs[jid]["updated"] = _now()
            self.save()
            return dict(self._jobs[jid])

    def ingest(self, job: dict) -> dict:
        """Upsert a job mirrored from the VM bridge (keyed by its `id`)."""
        with _lock:
            jid = str(job.get("id") or ("vm-" + new_id()))
            merged = _vm_record(job, self._jobs.get(jid, {}).get("created"))
            self._jobs[merged["id"]] = merged
            self.save()
            return dict(merged)

    def prune(self, keep: int = 200) -> int:
        """Drop the oldest terminal jobs beyond `keep`. Returns how many removed.
        A pruned job's scratch dir (WORK_ROOT/<id>) is removed too, so log files
        can't accumulate under the jobs tree after the registry row is gone."""
        with _lock:
            terminal = [j for j in self._jobs.values() if j["state"] in TERMINAL]
            terminal.sort(key=lambda j: j["updated"])
            removed = 0
            while len(self._jobs) > keep and terminal:
                victim = terminal.pop(0)
                self._jobs.pop(victim["id"], None)
                self.drop_workdir(victim["id"])
                removed += 1
            if removed:
                self.save()
            return removed

    def _upsert(self, job: dict) -> None:
        """Store a full record verbatim (id + all fields preserved) — the write
        side of a backend migration. Not for runtime callers (use create/update)."""
        with _lock:
            self._jobs[str(job["id"])] = dict(job)
            self.save()


class SqliteStore(_ScratchMixin):
    """A persisted, thread-safe job registry — one `registry.db` (stdlib sqlite3,
    WAL) where each mutation is an atomic PER-ROW upsert (no whole-file rewrite).
    Opt-in via SOVEREIGN_OS_JOBS_STORE=sqlite. The full job dict lives in a `data`
    JSON column so the record shape stays identical to the json backend; `created`
    + `state` are shadowed as columns for ordering + prune without decoding every
    row."""

    backend = "sqlite"

    def __init__(self, path: Path | str = SQLITE_REGISTRY):
        self.path = Path(path)
        self._lock = threading.RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False: the dispatcher pool touches one connection; the
        # per-store RLock serializes access. WAL: readers never block the writer.
        self._db = sqlite3.connect(str(self.path), check_same_thread=False)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=NORMAL")
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS jobs ("
            " id TEXT PRIMARY KEY, created INTEGER NOT NULL,"
            " state TEXT NOT NULL, data TEXT NOT NULL)"
        )
        self._db.commit()

    def _write(self, job: dict) -> None:
        self._db.execute(
            "INSERT OR REPLACE INTO jobs(id, created, state, data) VALUES(?,?,?,?)",
            (str(job["id"]), int(job["created"]), str(job["state"]), json.dumps(job)),
        )
        self._db.commit()

    def create(self, kind: str, title: str, device: str = "cpu", meta: dict | None = None,
               priority: str = _DEFAULT_PRIORITY, max_attempts: int = DEFAULT_MAX_ATTEMPTS) -> dict:
        job = _new_record(kind, title, device, meta, priority, max_attempts)
        with self._lock:
            self._write(job)
        return dict(job)

    def get(self, jid: str) -> dict | None:
        with self._lock:
            row = self._db.execute("SELECT data FROM jobs WHERE id=?", (jid,)).fetchone()
        return json.loads(row[0]) if row else None

    def list(self) -> list[dict]:
        with self._lock:
            rows = self._db.execute("SELECT data FROM jobs ORDER BY created DESC").fetchall()
        return [json.loads(r[0]) for r in rows]

    def update(self, jid: str, **fields) -> dict | None:
        with self._lock:
            row = self._db.execute("SELECT data FROM jobs WHERE id=?", (jid,)).fetchone()
            if not row:
                return None
            job = json.loads(row[0])
            job.update(fields)
            job["updated"] = _now()
            self._write(job)
            return dict(job)

    def ingest(self, job: dict) -> dict:
        """Upsert a job mirrored from the VM bridge (keyed by its `id`)."""
        with self._lock:
            jid = str(job.get("id") or ("vm-" + new_id()))
            prior = self._db.execute("SELECT created FROM jobs WHERE id=?", (jid,)).fetchone()
            merged = _vm_record(job, prior[0] if prior else None)
            self._write(merged)
            return dict(merged)

    def prune(self, keep: int = 200) -> int:
        """Drop the oldest terminal jobs beyond `keep` (same policy as the json
        backend); each victim's scratch dir is removed too."""
        with self._lock:
            total = self._db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
            if total <= keep:
                return 0
            rows = self._db.execute("SELECT data FROM jobs").fetchall()
            jobs = [json.loads(r[0]) for r in rows]
            terminal = sorted(
                (j for j in jobs if j["state"] in TERMINAL), key=lambda j: j["updated"]
            )
            removed = 0
            while total - removed > keep and terminal:
                victim = terminal.pop(0)
                self._db.execute("DELETE FROM jobs WHERE id=?", (str(victim["id"]),))
                self.drop_workdir(str(victim["id"]))
                removed += 1
            if removed:
                self._db.commit()
            return removed

    def _upsert(self, job: dict) -> None:
        """Store a full record verbatim — the write side of a backend migration."""
        with self._lock:
            self._write(dict(job))


# Back-compat: the historical name is the default (json) backend. jobs-api + the
# CLI construct via open_store(); direct `JobStore()` callers keep the json path.
JobStore = JsonStore


def _store_for(backend: str, path: Path | str | None = None):
    if backend == "sqlite":
        return SqliteStore(path if path is not None else SQLITE_REGISTRY)
    return JsonStore(path if path is not None else REGISTRY)


def resolve_backend(backend: str | None = None) -> str:
    """The active backend: the explicit arg, else SOVEREIGN_OS_JOBS_STORE, else the
    default. An unknown value falls back to the default rather than crashing the
    daemon at import."""
    b = (backend or os.environ.get("SOVEREIGN_OS_JOBS_STORE") or DEFAULT_BACKEND).strip().lower()
    return b if b in BACKENDS else DEFAULT_BACKEND


def open_store(path: Path | str | None = None, backend: str | None = None):
    """Open the registry for the active backend (the `SOVEREIGN_OS_JOBS_STORE`
    toggle, default json). Enabling sqlite with an EMPTY db while a populated
    `registry.json` exists AUTO-SEEDS one-way json→sqlite, so flipping the toggle
    carries existing jobs across with no manual step (idempotent — a non-empty db
    is never re-seeded)."""
    b = resolve_backend(backend)
    store = _store_for(b, path)
    if b == "sqlite" and not store.list():
        # look for a legacy json registry in the SAME jobs dir as the db, so the
        # seed follows SOVEREIGN_OS_JOBS_DIR / an explicit path, not a frozen const.
        legacy = JsonStore(store.path.parent / "registry.json")
        if legacy.list():
            migrate(legacy, store)
    return store


def migrate(src, dst) -> int:
    """Copy every job (id + all fields preserved) from `src` into `dst`, verbatim.
    Idempotent — an id already in `dst` is overwritten with `src`'s copy. Returns
    the number of jobs copied. Backend-agnostic: json→sqlite (enable), sqlite→json
    (revert), or same-kind (a compaction). Scratch dirs (shared filesystem) are
    untouched."""
    jobs = src.list()
    for job in jobs:
        dst._upsert(job)
    return len(jobs)


def summary(jobs: list[dict]) -> dict:
    """Counts by state + by device, for the pane header."""
    by_state: dict[str, int] = {}
    by_device: dict[str, int] = {}
    by_priority: dict[str, int] = {}
    for j in jobs:
        by_state[j["state"]] = by_state.get(j["state"], 0) + 1
        by_device[j["device"]] = by_device.get(j["device"], 0) + 1
        by_priority[j.get("priority", _DEFAULT_PRIORITY)] = \
            by_priority.get(j.get("priority", _DEFAULT_PRIORITY), 0) + 1
    return {
        "total": len(jobs),
        "running": by_state.get("running", 0),
        "queued": by_state.get("queued", 0),
        "by_state": by_state,
        "by_device": by_device,
        "by_priority": by_priority,
    }
