"""If the safety check cannot run, nothing may be flashable.

2026-07-27. flash-api's _run() returns "" for ANY failure — a timeout, a missing
binary, an OSError. protected_disks() built its never-flash set from those
results, so a failed `findmnt /` silently dropped the disk hosting the RUNNING
system out of the protected set. The panel would then offer it as a target,
looking exactly like a spare drive.

This is the same shape as three other bugs found the same day: a failed READ
reported as a definitive NEGATIVE. Elsewhere it merely misled (packages read as
[MISSING]; the display manager read as "<NOT SET>"). Here it would erase the
operator's system.

So: "/" is probed separately and its absence is treated as probe failure, not as
"nothing is mounted there". The listing then marks EVERY disk unflashable and
carries the reason, rather than raising — an uncaught exception kills the
request thread and the browser shows only "NetworkError", which already cost an
hour in this same session.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
API = REPO_ROOT / "scripts" / "operator" / "flash-api.py"


def load():
    spec = importlib.util.spec_from_file_location("flash_api", API)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except SystemExit:
        pass
    return mod


def test_the_root_probe_failing_is_not_silent():
    mod = load()
    mod._run = lambda *a, **k: ""
    with pytest.raises(RuntimeError):
        mod.protected_disks()


def test_nothing_is_flashable_when_the_check_fails():
    mod = load()
    real = mod._run
    mod._run = lambda a, *x, **k: "" if a and a[0] == "findmnt" else real(a, *x, **k)
    devs = mod.list_block_devices()
    assert devs, "no devices listed at all — cannot conclude anything"
    offered = [d["path"] for d in devs if d["flashable"]]
    assert not offered, (
        f"the safety check failed yet these are still offered: {offered}"
    )


def test_the_reason_matches_the_verdict():
    """A disk marked unflashable must not carry 'allowed, and it will be ERASED'.

    The override was placed BEFORE the branches that set `reason`, so they
    overwrote it and the panel showed a flat contradiction at the riskiest
    moment (2026-07-27).
    """
    mod = load()
    real = mod._run
    mod._run = lambda a, *x, **k: "" if a and a[0] == "findmnt" else real(a, *x, **k)
    for d in mod.list_block_devices():
        if not d["flashable"]:
            assert "allowed" not in d.get("reason", ""), (
                f"{d['path']}: unflashable but reason says {d['reason']!r}"
            )


def test_the_running_disk_is_protected_in_the_normal_case():
    """Guard against fixing the failure mode by breaking the working one."""
    mod = load()
    import subprocess
    root_src = subprocess.run(["findmnt", "-nr", "-o", "SOURCE", "--target", "/"],
                              capture_output=True, text=True).stdout.strip()
    expected = mod._parent_disk(root_src)
    devs = {d["name"]: d for d in mod.list_block_devices()}
    assert expected in devs, f"{expected} not listed among {sorted(devs)}"
    assert not devs[expected]["flashable"], (
        f"{expected} hosts the running system and is offered as a flash target"
    )
