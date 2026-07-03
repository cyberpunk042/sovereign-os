"""Build gate: a locked-root image is a HARD FAILURE, never a silent ship.

Caught 2026-07-03 (sain-01 flash-prep): the image built + preflight-passed with
root LOCKED — `SOVEREIGN_OS_ROOT_PASSWORD` was unset and mkosi-emit only
*warned* — so it booted on real hardware to a `login:` prompt nobody could
satisfy ("build done + preflight pass" gave false confidence). mkosi-emit now
`sys.exit()`s unless a password is set OR `SOVEREIGN_OS_ALLOW_LOCKED_ROOT` is an
explicit opt-in — parity with the secure-boot-keys gate right above it.
"""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
EMIT = REPO / "scripts" / "build" / "adapters" / "mkosi-emit.sh"


def test_locked_root_is_a_hard_failure():
    body = EMIT.read_text(encoding="utf-8")
    assert "SOVEREIGN_OS_ROOT_PASSWORD is unset" in body, (
        "mkosi-emit must name the unset-root-password failure"
    )
    assert "sys.exit(" in body, "the locked-root path must sys.exit(), not just warn"
    assert "SOVEREIGN_OS_ALLOW_LOCKED_ROOT" in body, (
        "must offer an explicit opt-in for an intentional locked-root image"
    )


def test_set_password_still_emits_rootpassword():
    body = EMIT.read_text(encoding="utf-8")
    assert "RootPassword={root_password}" in body, (
        "a set password must still emit RootPassword="
    )


def test_silent_warning_path_is_gone():
    """The old warn-and-continue path (which shipped the unusable image) must
    no longer exist — the only non-failing unset path is the explicit opt-in."""
    body = EMIT.read_text(encoding="utf-8")
    assert "WARNING — SOVEREIGN_OS_ROOT_PASSWORD unset: root will be" not in body, (
        "the silent locked-root warning must be replaced by a hard failure"
    )
