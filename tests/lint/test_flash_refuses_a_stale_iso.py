"""An ISO carries its own preseed — if that disagrees with the repo, it is old.

2026-07-27. The ISO sitting in build/sain-01/output/ was built that morning,
before the day's fixes landed. It still contained:

    d-i passwd/root-password password sovereign
    d-i user-setup/allow-password-weak boolean true
    (no debian-installer/add-kernel-opts at all — so NO nomodeset)

Flashing it reproduces the exact dark-screen failure the day was spent
diagnosing, and hands out a known root password. Nothing stopped that: the
build-time pool check cannot help once the artifact exists, and the image is a
perfectly valid bootable ISO, so the `file` check passes it.

Comparing the ISO's embedded preseed against the repo's is cheap and exact —
the artifact declares its own vintage.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"


def stale_block() -> str:
    body = OSCTL.read_text(encoding="utf-8")
    i = body.index("STALE IMAGE")
    return body[body.rindex("if command -v xorriso", 0, i):body.index("dd_ok=0", i)]


def test_the_check_runs_before_the_write():
    body = OSCTL.read_text(encoding="utf-8")
    assert body.index("STALE IMAGE") < body.index('dd if="${image}"'), (
        "staleness must be detected BEFORE dd; afterwards the disk is written"
    )


def test_it_compares_the_isos_own_preseed():
    block = stale_block()
    assert "/simple-cdd/default.preseed" in block, (
        "the ISO's embedded preseed is the evidence of its vintage"
    )
    for key in ("add-kernel-opts", "passwd/root-password"):
        assert key in block, (
            f"{key} must be compared — it is one of the two things that made "
            "the stale ISO dangerous (no nomodeset; a shipped credential)"
        )


def test_the_count_cannot_double_up():
    """`grep -c` prints 0 AND exits 1 when nothing matches.

    `$(grep -c ... || echo 0)` therefore yields "0\\n0", so the values never
    compare equal and EVERY image reads as stale (caught pre-flight).
    """
    block = stale_block()
    assert "|| echo 0)" not in block, (
        "grep -c already prints 0; appending another makes every comparison differ"
    )
    assert "head -1" in block, "take a single line so the exit status is head's"


def test_there_is_a_deliberate_override():
    block = stale_block()
    assert "SOVEREIGN_OS_FLASH_STALE" in block, (
        "an operator may knowingly want an older image; refusing with no way "
        "past it is a wall"
    )
