#!/usr/bin/env python3
"""
scripts/operator/lib/jobs_store.py — the persisted background-job registry.

The single source of truth for Background Tasks: a JSON registry of jobs that
SURVIVES a restart (atomic temp+rename write), shared by the jobs-api runtime
(scripts/operator/jobs-api.py) and the `sovereign-osctl jobs` CLI. Stdlib only.

A job is a long-running unit of work the box runs off the request path — a
background CoAT deliberation, a model eval, a secondary-model load, a GPU job, or
a job mirrored from the RTX-4090 passthrough VM. The registry is the read model
the Code Console's Background Tasks pane renders.

Location: /var/lib/sovereign-os/jobs/registry.json (override SOVEREIGN_OS_JOBS_DIR).
"""
from __future__ import annotations

import json
import os
import shutil
import threading
import time
import uuid
from pathlib import Path

JOBS_DIR = Path(os.environ.get("SOVEREIGN_OS_JOBS_DIR", "/var/lib/sovereign-os/jobs"))
REGISTRY = JOBS_DIR / "registry.json"
# Per-job scratch lives UNDER the jobs dir (already the unit's sole ReadWritePaths)
# so a runner's cwd + log never hit read-only REPO or PrivateTmp — the F-2026-091
# sandbox-breakage fix. One subdir per job id; dropped when the job is pruned.
WORK_ROOT = JOBS_DIR / "work"

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


class JobStore:
    """A persisted, thread-safe job registry."""

    def __init__(self, path: Path | str = REGISTRY):
        self.path = Path(path)
        self._jobs: dict[str, dict] = {}
        self.load()

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
        if kind not in KINDS:
            raise ValueError(f"unknown job kind {kind!r} (want {'/'.join(KINDS)})")
        if priority not in PRIORITIES:
            raise ValueError(f"unknown priority {priority!r} (want {'/'.join(PRIORITIES)})")
        jid = new_id()
        job = {
            "id": jid,
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
        with _lock:
            self._jobs[jid] = job
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
            merged = {
                "id": jid,
                "kind": "vm-job",
                "title": job.get("title", "vm job"),
                "device": job.get("device", "rtx-4090-vm"),
                "state": job.get("state", "running"),
                "priority": _DEFAULT_PRIORITY,
                "progress": int(job.get("progress", 0)),
                "created": self._jobs.get(jid, {}).get("created", _now()),
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
            self._jobs[jid] = merged
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
