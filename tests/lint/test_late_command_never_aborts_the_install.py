"""No late_command step may fail the install.

2026-07-27. preseed/late_command runs AFTER partitioning, formatting and
unpacking. A step that exits non-zero aborts d-i at that point, leaving a disk
that is partitioned, written, and unbootable — the worst possible moment to
fail, and the hardest to recover from without a full reinstall.

Six steps were exposed: those ending in a `for` loop or a bare `echo >`, where
`sh -c` returns the last command's status. (An INNER `|| true` on the last
command is equally protective — `sh -c 'a; b || true'` exits 0 — but relying on
that makes the invariant depend on reading the whole string correctly, which is
how the exposure went unnoticed.)

Guarding uniformly does not hide real failures: verify-installed-system.sh
records what actually landed — cmdline, blacklist, packages, display manager,
apt sources, the dashboards deploy — and `install logs --from` reads it back off
the unmounted disk.
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PROFILES = REPO_ROOT / "scripts" / "build" / "installer-cdd" / "profiles"
PRESEEDS = ("default.preseed", "sovereign.preseed")


def late_command_steps(name: str) -> list[str]:
    lines = (PROFILES / name).read_text(encoding="utf-8").splitlines()
    start = next(i for i, l in enumerate(lines)
                 if l.startswith("d-i preseed/late_command"))
    out, i = [], start
    while True:
        if "in-target" in lines[i]:
            out.append(lines[i].strip().rstrip("\\").rstrip().rstrip(";"))
        if not lines[i].rstrip().endswith("\\"):
            break
        i += 1
    return out


@pytest.mark.parametrize("name", PRESEEDS)
def test_every_step_is_guarded(name: str):
    steps = late_command_steps(name)
    assert steps, f"{name}: no in-target steps found — did the format change?"
    unguarded = [s for s in steps if not s.endswith("|| true")]
    assert not unguarded, (
        f"{name}: {len(unguarded)} late_command step(s) can abort the install "
        f"after the disk has been partitioned and written: {unguarded}"
    )


@pytest.mark.parametrize("name", PRESEEDS)
def test_the_value_is_one_unbroken_continuation(name: str):
    """A dropped trailing backslash silently truncates the command.

    Everything after it stops running, with no error anywhere — the self-check
    and `systemctl enable sddm` would simply never happen.
    """
    text = (PROFILES / name).read_text(encoding="utf-8")
    total = sum(1 for l in text.splitlines() if l.strip().startswith("in-target"))
    assert len(late_command_steps(name)) == total, (
        f"{name}: {total - len(late_command_steps(name))} in-target line(s) fall "
        "outside the continued late_command value"
    )
