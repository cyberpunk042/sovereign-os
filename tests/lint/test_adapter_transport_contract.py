"""SDD-716 — adapter-transport planner contract (Slice 2b; M046 E0444/E0446).

adapter-transport.py is the missing "ship a promoted adapter SAIN-01 → box on a
ZFS-versioned layout" link. It is a PLANNER (prints rsync + zfs commands, DRY-RUN
by default) — cross-box transport can't be CI-verified, so these pin the plan
SHAPE + the sovereignty posture:

  1. present + executable + stdlib-only (no third-party imports).
  2. reuses adapter-foundry's registry reader (never invents an adapter).
  3. `plan` emits an rsync step into /var/lib/sovereign-os/adapters/<id>/<version>/
     + a `zfs snapshot <dataset>@adapter-<id>-<version>` step (E0446 versioning).
  4. `rollback` emits a `zfs rollback` of that snapshot.
  5. DRY-RUN default — no host mutation without --apply.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "inference" / "adapter-transport.py"


def _load():
    spec = importlib.util.spec_from_file_location("_adapter_transport", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_script_present_and_executable():
    assert SCRIPT.is_file(), f"missing {SCRIPT}"
    import os
    assert os.access(SCRIPT, os.X_OK), "adapter-transport.py must be executable"


def test_stdlib_only():
    body = SCRIPT.read_text(encoding="utf-8")
    for banned in ("import yaml", "import requests", "import boto3"):
        assert banned not in body, f"adapter-transport.py must be stdlib-only ({banned})"


def test_reuses_foundry_registry_reader():
    body = SCRIPT.read_text(encoding="utf-8")
    assert "adapter-foundry.py" in body and "ADAPTER_REGISTRY" in body, (
        "adapter-transport.py must reuse adapter-foundry's registry reader "
        "(single source of truth; never invents an adapter)"
    )


def test_plan_shape():
    mod = _load()
    p = mod.plan("my-adapter", source=None, version="v3")
    kinds = [s["kind"] for s in p["steps"]]
    assert kinds == ["rsync", "zfs-snapshot"], f"unexpected plan steps: {kinds}"
    assert p["dest"].endswith("/adapters/my-adapter/v3"), p["dest"]
    assert p["snapshot"].endswith("@adapter-my-adapter-v3"), p["snapshot"]
    # rsync pulls into the versioned dest dir
    rsync = next(s for s in p["steps"] if s["kind"] == "rsync")
    assert rsync["cmd"][0] == "rsync" and rsync["cmd"][-1].endswith("/my-adapter/v3/")


def test_rollback_shape():
    mod = _load()
    r = mod.rollback("my-adapter", "v2")
    assert r["steps"][0]["kind"] == "zfs-rollback"
    assert r["steps"][0]["cmd"][:2] == ["zfs", "rollback"]
    assert r["snapshot"].endswith("@adapter-my-adapter-v2")


def test_dry_run_default_no_apply():
    """`plan` without --apply must exit 0 and NOT execute (no --apply flag → the
    subprocess runner is never reached). We assert the CLI returns 0 and prints
    the plan, without needing rsync/zfs present."""
    out = subprocess.run(
        [sys.executable, str(SCRIPT), "plan", "some-adapter"],
        capture_output=True, text=True, timeout=15,
    )
    assert out.returncode == 0, out.stderr
    assert "zfs snapshot" in out.stdout and "rsync" in out.stdout
