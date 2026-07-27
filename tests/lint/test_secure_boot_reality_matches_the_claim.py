"""A profile that claims secure_boot=signed must not ship an unsigned kernel silently.

2026-07-27. On this hardware:

    SecureBoot disabled / Platform is in Setup Mode
    custom znver5 kernel: "No signature table present"
    profile sain-01:      secure_boot=signed

Step 08-image-sign skips MOK signing for the ISO artifact — correct, the disc
rides Debian's signed shim/grub chain — but the custom kernel .deb installed
onto the target carries no signature at all. That is fine while Secure Boot is
off, and becomes an unbootable machine the day it is switched on, with nothing
anywhere to explain why.

Step 08 also tells the operator to "enroll the MOK cert via mokutil
post-install". mokutil was not in the installed package set, so that
instruction could not be followed on any machine we built — the same
declared-but-not-applied shape as the rest of this session.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VERIFY = REPO_ROOT / "scripts" / "install" / "verify-installed-system.sh"


def installed_packages() -> set[str]:
    out = subprocess.run(
        ["bash", "-c", ". scripts/install/lib/installed-system.sh; "
                       "sovereign_os_installed_packages"],
        capture_output=True, text=True, check=True, cwd=REPO_ROOT).stdout
    return set(out.split())


def test_mokutil_is_installed_since_we_tell_the_operator_to_use_it():
    sign = (REPO_ROOT / "scripts" / "build" / "08-image-sign.sh").read_text(encoding="utf-8")
    if "mokutil" not in sign:
        return  # the instruction was removed; nothing to guarantee
    assert "mokutil" in installed_packages(), (
        "08-image-sign tells the operator to enroll the MOK via mokutil, but "
        "mokutil is not installed on the system they would run it on"
    )


def test_the_selfcheck_reports_secure_boot_state():
    body = VERIFY.read_text(encoding="utf-8")
    assert "secure boot" in body.lower(), (
        "the install report must state whether Secure Boot is on — it decides "
        "whether the unsigned custom kernel can boot at all"
    )


def test_the_selfcheck_does_not_depend_on_mokutil_being_present():
    """A diagnostic must not go blind because a convenience tool is missing."""
    body = VERIFY.read_text(encoding="utf-8")
    assert "efivars" in body, (
        "read the SecureBoot EFI variable directly when mokutil is absent"
    )


def test_it_warns_when_secure_boot_is_on():
    body = VERIFY.read_text(encoding="utf-8")
    assert "UNSIGNED" in body, (
        "with Secure Boot enabled the unsigned znver5 kernel will not load; the "
        "report must say so rather than leave the operator to discover it at "
        "the next reboot"
    )
