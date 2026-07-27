"""A report nobody knows about does not help anyone.

2026-07-27. verify-installed-system.sh writes a thorough report to
/var/log/sovereign-os/install-verify.log — and a first-time operator has no
reason to know it exists. So an install that went wrong presents as a SYMPTOM
(dark screen, missing cockpit) with the explanation sitting unread on disk.
That is precisely the day this project just spent.

motd.d is the right surface: when the desktop does not come up the operator
drops to a console (Ctrl+Alt+F3), and the explanation is waiting there. Debian
13's `pam_motd.so noupdate` reads the default motd.d directories, so no PAM
change is needed.

Only PROBLEMS are surfaced, and a clean install must actively REMOVE a stale
warning from a previous one — a motd that lies about the current state is worse
than none.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VERIFY = REPO_ROOT / "scripts" / "install" / "verify-installed-system.sh"


def test_problems_are_written_to_motd():
    body = VERIFY.read_text(encoding="utf-8")
    assert "motd.d" in body, (
        "install problems must reach the operator without them knowing a "
        "command; the console is where they land when the desktop fails"
    )
    assert "sovereign-osctl install logs" in body, (
        "the notice must say how to see the full report"
    )


def test_a_clean_install_clears_a_stale_notice():
    body = VERIFY.read_text(encoding="utf-8")
    i = body.index("_problems")
    window = body[i:i + 1400]
    assert "rm -f" in window, (
        "a clean install must remove a previous install's warning; a motd that "
        "describes a state that no longer exists is worse than silence"
    )


def test_the_notice_never_fails_the_script():
    """This runs inside d-i's late_command, which must not abort."""
    body = VERIFY.read_text(encoding="utf-8")
    i = body.index("_motd=")
    for line in body[i:i + 1200].splitlines():
        s = line.strip()
        if s.startswith(("mkdir ", "rm -f", "}")) and ">" not in s:
            assert "|| true" in s or "2>/dev/null" in s, f"unguarded: {s!r}"
    assert body.rstrip().endswith("exit 0")


def test_it_runs_end_to_end(tmp_path: Path):
    """Execute the script against a throwaway root; it must exit 0 either way."""
    root = tmp_path / "r"
    (root / "etc/motd.d").mkdir(parents=True)
    src = (VERIFY.read_text(encoding="utf-8")
           .replace("OUT=/var/log/sovereign-os/install-verify.log", f"OUT={root}/report")
           .replace("mkdir -p /var/log/sovereign-os", ":")
           .replace("_motd=/etc/motd.d", f"_motd={root}/etc/motd.d")
           .replace("mkdir -p /etc/motd.d", f"mkdir -p {root}/etc/motd.d"))
    out = subprocess.run(["sh"], input=src, capture_output=True, text=True)
    assert out.returncode == 0, f"self-check exited {out.returncode}: {out.stderr[-400:]}"
    assert (root / "report").exists(), "no report was written"
