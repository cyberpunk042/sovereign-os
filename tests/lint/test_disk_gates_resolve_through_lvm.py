"""The "don't touch the running system" gate must survive an LVM root.

2026-07-27. Both installers resolved the running root's disk with:

    /dev/$(lsblk -no PKNAME "$(findmnt -no SOURCE /)" | head -1)

PKNAME is the IMMEDIATE parent. For a plain partition root (/dev/nvme1n1p2)
that yields /dev/nvme1n1 and the gate works. But sovereign-os installs an LVM
root, and PKNAME of /dev/mapper/sovereign-root is the PV PARTITION
(/dev/nvme0n1p2) -- which never equals a TARGET of /dev/nvme0n1.

So on the layout these scripts create, the gate protecting the running system
compared a partition against a disk, never matched, and let the disk hosting the
running OS be zapped. setup-lvm-dualboot.sh opens with `sgdisk --zap-all`.

The fix walks up until there is no parent left, which also covers LUKS and md.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ("scripts/install/setup-lvm-dualboot.sh",
           "scripts/install/install-sovereign-root.sh")


@pytest.mark.parametrize("rel", SCRIPTS)
def test_the_gate_does_not_use_a_single_pkname_hop(rel: str):
    body = (REPO_ROOT / rel).read_text(encoding="utf-8")
    code = "\n".join(l for l in body.splitlines() if not l.lstrip().startswith("#"))
    assert "_parent_disk_of" in code, (
        f"{rel} must resolve to the physical disk; a single PKNAME hop stops at "
        "the PV partition on an LVM root and the safety gate never fires"
    )
    for var in ("RUN_ROOT_DISK=", "ROOT_DISK="):
        for line in code.splitlines():
            if line.startswith(var):
                assert "_parent_disk_of" in line, f"{rel}: {line.strip()!r}"


def test_the_walker_actually_reaches_a_disk():
    """Run the real helper against this machine's own devices."""
    body = (REPO_ROOT / "scripts/install/setup-lvm-dualboot.sh").read_text(encoding="utf-8")
    start = body.index("_parent_disk_of() {")
    helper = body[start:body.index("\n}\n", start) + 3]
    script = helper + '_parent_disk_of "$(findmnt -no SOURCE /)"\n'
    out = subprocess.run(["sh", "-c", script], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    disk = out.stdout.strip()
    assert disk.startswith("/dev/"), f"unexpected result: {disk!r}"
    # A disk has no parent; a partition does. Use the SAME semantics as the
    # walker: `lsblk -no PKNAME <disk>` prints a row for the disk (empty) AND a
    # row per child (naming the disk), so only the first line is the device's
    # own parent. Omitting head -1 made this test read the children and fail on
    # a correct walker (2026-07-27).
    first = subprocess.run(["lsblk", "-no", "PKNAME", disk],
                           capture_output=True, text=True).stdout.split("\n")[0].strip()
    assert first == "", (
        f"{disk} still has a parent ({first!r}) — the walk stopped short"
    )
