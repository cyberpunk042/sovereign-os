"""A device name is not an identity — never default a destructive target to one.

2026-07-27, operator: "would it install even if I wasn't on SAIN? I think I will
test with my other computer."

Two installers defaulted their target to /dev/nvme1n1:

    install-sovereign-root.sh   SOVEREIGN_OS_TARGET_DISK:-/dev/nvme1n1
    setup-lvm-dualboot.sh       SOVEREIGN_OS_LVM_DISK:-/dev/nvme1n1

On this machine /dev/nvme1n1 is the RUNNING Debian (root=/dev/nvme1n1p2). The
default was stale — written when the two NVMes had opposite roles — and only
the safety gates stopped it. On any other machine that name means something
else entirely, chosen by enumeration order.

This is the third instance of the same mistake: the d-i preseed's disk picker
skipped nvme0n1 to "protect the running OS" and thereby selected it, and the
gates themselves resolved a partition where a disk was meant. Naming a disk is
the operator's call; guessing one is how the wrong disk gets erased.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
# Every script that can select a destructive target.
SCRIPTS = ("scripts/install/install-sovereign-root.sh",
           "scripts/install/setup-lvm-dualboot.sh",
           "scripts/install/installer-tui.sh")

# The non-interactive ones must REFUSE when no target is named. installer-tui.sh
# is excluded from that contract on purpose: it presents a picker, so "no target
# named" is its normal starting state, not an error. It is still held to the
# no-hardcoded-default and no-stale-role-claim rules above.
NONINTERACTIVE = ("scripts/install/install-sovereign-root.sh",
                  "scripts/install/setup-lvm-dualboot.sh")


@pytest.mark.parametrize("rel", SCRIPTS)
def test_no_hardcoded_device_default(rel: str):
    code = "\n".join(l for l in (REPO_ROOT / rel).read_text(encoding="utf-8").splitlines()
                     if not l.lstrip().startswith("#"))
    bad = re.findall(r"\$\{SOVEREIGN_OS_\w*DISK\w*:-(/dev/\w+)\}", code)
    assert not bad, (
        f"{rel} defaults a destructive target to {bad} — a device name means a "
        "different disk on every machine, and on this one it is the running system"
    )


@pytest.mark.parametrize("rel", NONINTERACTIVE)
def test_it_refuses_and_helps_instead_of_guessing(rel: str):
    text = (REPO_ROOT / rel).read_text(encoding="utf-8")
    assert "ABORT: no target disk" in text, (
        f"{rel} must refuse when no target is named"
    )
    assert "Candidates" in text and "MOUNTPOINTS" in text, (
        "refusing is only half of it — list the disks with nothing mounted, so "
        "the operator picks from facts rather than from memory"
    )


@pytest.mark.parametrize("rel", NONINTERACTIVE)
def test_the_refusal_precedes_any_destructive_work(rel: str):
    text = (REPO_ROOT / rel).read_text(encoding="utf-8")
    abort = text.index("ABORT: no target disk")
    for op in ("sgdisk", "mkfs", "pvcreate", "debootstrap", "unsquashfs"):
        i = text.find(op)
        if i != -1:
            assert abort < i, f"{rel}: {op} appears before the empty-target check"


@pytest.mark.parametrize("rel", SCRIPTS)
def test_no_stale_role_claims_in_comments(rel: str):
    """Comments that name a disk's ROLE go stale silently.

    installer-tui.sh said "your dev Debian on nvme0n1" and the preseed said
    "never nvme0n1 -- that is the running OS". The two NVMes swapped roles at
    some point, so both statements became exactly backwards, and the preseed's
    rule then selected the disk it was written to protect (2026-07-27).
    """
    import re
    text = (REPO_ROOT / rel).read_text(encoding="utf-8")
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("#"):
            continue
        # A comment may MENTION a device while explaining history; it must not
        # assert what currently lives there.
        if re.search(r"(dev|running|your)\s+\w*\s*(Debian|OS|system)\s+(on|is)\s+/?dev/\w+", s, re.I):
            raise AssertionError(
                f"{rel}: comment claims a disk's current role, which goes stale: {s!r}"
            )


def test_the_tui_still_refuses_when_reflash_discovery_fails():
    """Its interactive picker covers the fresh path; the REFLASH path is where
    it used to fall back to a hardcoded device name — at the one moment it had
    just failed to determine anything (2026-07-27)."""
    text = (REPO_ROOT / "scripts/install/installer-tui.sh").read_text(encoding="utf-8")
    assert "could not be resolved" in text, (
        "the reflash path must refuse when the sovereign VG's disk cannot be "
        "resolved, rather than guess a device name"
    )
    assert "SOVEREIGN_OS_TARGET_DISK:-}" in text, (
        "an explicit override must still be honoured"
    )
