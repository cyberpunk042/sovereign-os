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
import threading
import time
import uuid
from pathlib import Path

JOBS_DIR = Path(os.environ.get("SOVEREIGN_OS_JOBS_DIR", "/var/lib/sovereign-os/jobs"))
REGISTRY = JOBS_DIR / "registry.json"

# The v1 job kinds. `vm-job` entries are mirrored from the passthrough VM bridge
# and are not executed by the host worker.
KINDS = ("deliberation", "eval", "model-load", "gpu-job", "vm-job", "demo", "model-serve")
# Lifecycle states.
STATES = ("queued", "running", "done", "failed", "cancelled")
# Terminal states (the worker never resumes these).
TERMINAL = ("done", "failed", "cancelled")

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

    def create(self, kind: str, title: str, device: str = "cpu", meta: dict | None = None) -> dict:
        if kind not in KINDS:
            raise ValueError(f"unknown job kind {kind!r} (want {'/'.join(KINDS)})")
        jid = new_id()
        job = {
            "id": jid,
            "kind": kind,
            "title": title,
            "device": device,
            "state": "queued",
            "progress": 0,
            "created": _now(),
            "updated": _now(),
            "started": None,
            "finished": None,
            "output": "",
            "error": "",
            "pid": None,
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
                "progress": int(job.get("progress", 0)),
                "created": self._jobs.get(jid, {}).get("created", _now()),
                "updated": _now(),
                "started": job.get("started"),
                "finished": job.get("finished"),
                "output": job.get("output", ""),
                "error": job.get("error", ""),
                "pid": job.get("pid"),
                "meta": job.get("meta", {}),
            }
            self._jobs[jid] = merged
            self.save()
            return dict(merged)

    def prune(self, keep: int = 200) -> int:
        """Drop the oldest terminal jobs beyond `keep`. Returns how many removed."""
        with _lock:
            terminal = [j for j in self._jobs.values() if j["state"] in TERMINAL]
            terminal.sort(key=lambda j: j["updated"])
            removed = 0
            while len(self._jobs) > keep and terminal:
                victim = terminal.pop(0)
                self._jobs.pop(victim["id"], None)
                removed += 1
            if removed:
                self.save()
            return removed


def summary(jobs: list[dict]) -> dict:
    """Counts by state + by device, for the pane header."""
    by_state: dict[str, int] = {}
    by_device: dict[str, int] = {}
    for j in jobs:
        by_state[j["state"]] = by_state.get(j["state"], 0) + 1
        by_device[j["device"]] = by_device.get(j["device"], 0) + 1
    return {
        "total": len(jobs),
        "running": by_state.get("running", 0),
        "queued": by_state.get("queued", 0),
        "by_state": by_state,
        "by_device": by_device,
    }
