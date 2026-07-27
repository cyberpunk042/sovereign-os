"""A malformed preseed is only discovered at install time, an hour too late.

2026-07-26. The preseeds were edited many times in one session — package lists
merged, late_command entries inserted, kernel options added. Every mistake in
them costs a full build → flash → install → boot cycle to discover, and d-i
does not fail loudly on a line it cannot parse: it ignores it and carries on
with defaults, which is how a system installs "successfully" and boots to a
dark screen.

debconf-set-selections --checkonly parses a preseed exactly as d-i does,
without applying anything. It turns an hour-long feedback loop into
milliseconds.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PROFILES = REPO_ROOT / "scripts" / "build" / "installer-cdd" / "profiles"
PRESEEDS = ("default.preseed", "sovereign.preseed")

pytestmark = pytest.mark.skipif(
    shutil.which("debconf-set-selections") is None,
    reason="debconf-set-selections not installed",
)


@pytest.mark.parametrize("name", PRESEEDS)
def test_debconf_accepts_it(name: str):
    out = subprocess.run(
        ["debconf-set-selections", "--checkonly", str(PROFILES / name)],
        capture_output=True, text=True)
    assert out.returncode == 0, (
        f"{name} is not a valid preseed:\n{out.stderr}{out.stdout}"
    )
    assert not out.stderr.strip(), f"{name}: {out.stderr}"


@pytest.mark.parametrize("name", PRESEEDS)
def test_the_late_command_is_a_single_unbroken_value(name: str):
    """late_command is one debconf value continued with backslashes.

    A continuation line that loses its trailing backslash silently truncates
    the command — everything after it becomes an unparsed stray line, so the
    steps at the end (the self-check, enabling sddm) just never run.
    """
    lines = (PROFILES / name).read_text(encoding="utf-8").splitlines()
    start = next(i for i, l in enumerate(lines) if "late_command" in l and l.startswith("d-i"))
    i = start
    while lines[i].rstrip().endswith("\\"):
        i += 1
    body = "\n".join(lines[start:i + 1])
    assert "in-target" in body, f"{name}: late_command body looks empty"
    # Each in-target step must be inside the continued value, not orphaned after it.
    total = sum(1 for l in lines if l.strip().startswith("in-target"))
    inside = sum(1 for l in body.splitlines() if l.strip().startswith("in-target"))
    assert inside == total, (
        f"{name}: {total - inside} 'in-target' line(s) fall OUTSIDE the "
        "late_command value — a dropped trailing backslash truncated it, and "
        "those steps will never run"
    )
