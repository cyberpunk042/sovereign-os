#!/usr/bin/env python3
"""
tests/lint/test_jobs_sandbox_readwrite_lockstep.py — F-2026-091 sandbox lockstep.

The jobs-api runtime confines each job's scratch (cwd + log) to WORK_ROOT under
the jobs dir, but the command kinds (model-load / gpu-job / model-serve) also
declare, in `jobs-api.py::KIND_WRITABLE_ROOTS`, the extra writable roots they
stage weights into. The systemd unit's `ReadWritePaths=` MUST be a superset of
those roots, or a hardened `ProtectSystem=strict` daemon would EACCES exactly the
kinds the runtime claims to run — the drift this lint forbids in both directions:
  * every KIND_WRITABLE_ROOTS entry is granted by the unit (a leading '-' optional
    prefix counts — the path is still writable when present);
  * the jobs dir itself (registry + per-job scratch) is granted.

Stdlib + pytest only; reads the two source-of-truth files, never a live system.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
UNIT = REPO / "systemd" / "system" / "sovereign-jobs-api.service"
API = REPO / "scripts" / "operator" / "jobs-api.py"
JOBS_DIR = "/var/lib/sovereign-os/jobs"


def _granted_readwrite_paths() -> set[str]:
    granted: set[str] = set()
    for line in UNIT.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("ReadWritePaths="):
            for tok in line.split("=", 1)[1].split():
                granted.add(tok.lstrip("-"))  # '-' = optional-if-missing, still RW
    return granted


def _kind_writable_roots() -> dict[str, tuple[str, ...]]:
    spec = importlib.util.spec_from_file_location("_jobs_api_roots", API)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return dict(mod.KIND_WRITABLE_ROOTS)


def test_jobs_dir_is_granted():
    assert JOBS_DIR in _granted_readwrite_paths(), (
        f"the unit must grant ReadWritePaths={JOBS_DIR} (registry + per-job scratch live there)"
    )


def test_every_kind_writable_root_is_granted_by_the_unit():
    granted = _granted_readwrite_paths()
    needed = {root for roots in _kind_writable_roots().values() for root in roots}
    missing = needed - granted
    assert not missing, (
        "sovereign-jobs-api.service is missing ReadWritePaths for kinds' writable "
        f"roots (jobs-api.py KIND_WRITABLE_ROOTS): {sorted(missing)} — add them "
        "(a leading '-' keeps boot resilient if the path is absent)."
    )


def test_runtime_still_declares_the_writable_roots_manifest():
    """Guard against the manifest being silently deleted (which would make the
    lockstep vacuously pass)."""
    src = API.read_text(encoding="utf-8")
    assert re.search(r"KIND_WRITABLE_ROOTS\s*:\s*dict", src), (
        "jobs-api.py must keep the KIND_WRITABLE_ROOTS manifest the unit is linted against"
    )
