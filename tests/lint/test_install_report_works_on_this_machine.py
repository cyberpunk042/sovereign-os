"""The commonest question must be answerable on the machine that just booted.

2026-07-27. `sovereign-osctl install logs` REQUIRED --from <disk>. So "I just
installed and rebooted — did it work?" could only be answered by booting a
DIFFERENT system and pointing it at the disk. The report's sovereign-specific
sections (dashboards deploy status, app tree, units, session type vs nomodeset,
apt sources, Secure Boot) are precisely what an operator wants right after first
boot, and journalctl shows none of them.

Running it locally then exposed a worse bug: every package reported [MISSING] on
a machine that had them all, because the check grepped the dpkg status file
through sudo and a failed sudo is indistinguishable from an absent package. A
diagnostic that reports false absence is worse than one that says nothing — and
this is the tool used to diagnose everything else.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"


def test_from_is_optional():
    body = OSCTL.read_text(encoding="utf-8")
    assert "local_mode=1" in body, (
        "`install logs` with no --from must read the running system"
    )
    assert 'log_error "usage: sovereign-osctl install logs --from <disk>"' not in body, (
        "the hard usage refusal should be gone"
    )


def test_unreadable_is_not_reported_as_missing():
    body = OSCTL.read_text(encoding="utf-8")
    assert "[UNREADABLE]" in body, (
        "a package the tool cannot inspect must not be reported as absent; "
        "false absence sends the operator chasing a bug that is not there"
    )


def test_it_warns_once_when_sudo_is_unavailable():
    body = OSCTL.read_text(encoding="utf-8")
    assert "no passwordless sudo" in body, (
        "several sections read root-only paths; with no sudo they come back "
        "empty, which reads exactly like 'not there'"
    )


def test_the_local_report_actually_runs_and_is_accurate():
    """Execute it. The packages checked are installed on this machine."""
    out = subprocess.run([str(OSCTL), "install", "logs"],
                         capture_output=True, text=True, timeout=120, cwd=REPO_ROOT)
    assert out.returncode == 0, f"install logs failed locally:\n{out.stderr[-800:]}"
    report = out.stdout
    assert "packages that must be present" in report, "the report is truncated"
    # sddm and the X drivers are genuinely installed here; if they read MISSING
    # the check is lying again.
    for pkg in ("sddm", "xserver-xorg-video-fbdev"):
        line = next((l for l in report.splitlines() if l.strip().endswith(pkg)), "")
        assert "[MISSING]" not in line, (
            f"{pkg} is installed on this machine but the report says: {line.strip()!r}"
        )
