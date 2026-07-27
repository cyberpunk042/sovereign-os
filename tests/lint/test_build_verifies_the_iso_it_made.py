"""Presence is not correctness — the build must check what it produced.

2026-07-27. Step 09 logged "artifact=installer — ISO present" and exited 0. Two
properties are cheap to check there and expensive to discover later:

  * CAN IT BOOT — an ISO with no El Torito image is a coaster. `file` says
    "ISO 9660" either way.
  * IS IT CURRENT — the ISO embeds its own preseed. The one on disk had no
    `debian-installer/add-kernel-opts` (so no nomodeset → the dark-screen
    install) and still carried `passwd/root-password password sovereign`.

Both were only caught at FLASH time, which is after the operator has already
concluded the build succeeded and moved on. Checking at build time turns "an
hour, then a mysterious failure" into "the build refused, here is why".
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
STEP09 = REPO_ROOT / "scripts" / "build" / "09-image-verify.sh"


def installer_block() -> str:
    body = STEP09.read_text(encoding="utf-8")
    i = body.index("artifact=installer — ISO present")
    return body[i:body.index("exit 0", i)]


def test_it_checks_the_iso_can_boot():
    blk = installer_block()
    assert "El Torito" in blk, (
        "an ISO with no El Torito image cannot boot; `file` reports ISO 9660 "
        "regardless, so presence proves nothing"
    )


def test_it_checks_the_preseed_is_current():
    blk = installer_block()
    assert "/simple-cdd/default.preseed" in blk, (
        "the ISO embeds its own preseed — compare it to the tree that just "
        "built it, or a stale artifact passes as fresh"
    )
    for key in ("add-kernel-opts", "passwd/root-password"):
        assert key in blk, f"{key} must be compared: it is one of the two that bit"


def test_failure_is_a_hard_stop_with_a_named_state():
    blk = installer_block()
    assert "installer-iso-unusable" in blk, (
        "a distinct state, so this is not confused with 'no artifact produced'"
    )
    assert "do NOT flash" in blk


def test_a_missing_tool_degrades_rather_than_fails():
    blk = installer_block()
    assert "xorriso unavailable" in blk, (
        "without xorriso the checks cannot run; warn rather than fail a build "
        "that may be perfectly good"
    )


def test_the_counting_bug_is_not_reintroduced():
    """`grep -c` prints 0 AND exits 1; `|| echo 0` yields "0\\n0"."""
    blk = installer_block()
    assert "|| echo 0)" not in blk
    assert "head -1" in blk
