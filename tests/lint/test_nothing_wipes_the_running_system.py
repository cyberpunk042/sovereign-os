"""Every destructive-disk surface must refuse the disk hosting the running root.

2026-07-27. Four surfaces write to raw disks:

    setup-lvm-dualboot.sh   sgdisk --zap-all
    install-sovereign-root.sh  (partitions/formats via the above)
    flash-api.py            dd an image onto a device
    secure-wipe.sh          dd if=/dev/zero over the whole device

All of them resolved "which disk is the running system" with a single
`lsblk -no PKNAME` hop, which returns the IMMEDIATE parent. On a plain
partition root that is the disk and everything looks fine; on the LVM root
sovereign-os actually installs, it returns the PV PARTITION and the comparison
against a whole-disk argument can never match. The gate was decorative on
exactly the layout the project creates.

secure-wipe.sh had no running-root gate at all, and its own error message
suggested:

    SOVEREIGN_OS_WIPE_DEVICES='/dev/nvme0n1 /dev/nvme1n1'

which on a two-NVMe box names the target AND the live system.

installer-tui.sh had already solved the resolution correctly via sysfs, and its
comment describes this exact failure — it simply was never propagated.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# (path, name of the guard it must contain)
SURFACES = (
    "scripts/install/setup-lvm-dualboot.sh",
    "scripts/install/install-sovereign-root.sh",
    "scripts/hooks/decommission/secure-wipe.sh",
)


@pytest.mark.parametrize("rel", SURFACES)
def test_it_resolves_to_a_physical_disk(rel: str):
    code = "\n".join(l for l in (REPO_ROOT / rel).read_text(encoding="utf-8").splitlines()
                     if not l.lstrip().startswith("#"))
    assert "_parent_disk_of" in code, (
        f"{rel} writes to raw disks and must resolve the running root through "
        "the whole device chain; one PKNAME hop stops at the PV partition"
    )


def test_the_wipe_tool_refuses_the_running_disk():
    body = (REPO_ROOT / "scripts/hooks/decommission/secure-wipe.sh").read_text(encoding="utf-8")
    assert "REFUSING" in body and "RUNNING root" in body, (
        "secure-wipe must refuse the disk it booted from — dd over the live "
        "filesystem is not a decommission, it is a crash partway through"
    )
    # ...and the refusal must come BEFORE the confirm prompt, so the operator is
    # never asked to approve something that cannot work.
    assert body.index("REFUSING") < body.index('confirm "Wipe devices'), (
        "refuse before prompting; do not ask the operator to confirm a wipe of "
        "the disk running the tool"
    )


def test_the_example_does_not_name_every_disk_in_the_machine():
    body = (REPO_ROOT / "scripts/hooks/decommission/secure-wipe.sh").read_text(encoding="utf-8")
    assert "'/dev/nvme0n1 /dev/nvme1n1'" not in body, (
        "an example listing every NVMe in a two-disk box is one copy-paste away "
        "from erasing the live system"
    )


def test_the_gate_is_correct_on_this_machine():
    """Execute the real helper: the disk holding / must be refused."""
    body = (REPO_ROOT / "scripts/hooks/decommission/secure-wipe.sh").read_text(encoding="utf-8")
    start = body.index("_parent_disk_of() {")
    helper = body[start:body.index("\n}\n", start) + 3]
    script = helper + '''
r="$(_parent_disk_of "$(findmnt -no SOURCE /)")"
[ "$(_parent_disk_of "$(findmnt -no SOURCE /)")" = "$r" ] && echo REFUSED || echo ALLOWED
'''
    out = subprocess.run(["sh", "-c", script], capture_output=True, text=True)
    assert out.stdout.strip() == "REFUSED", f"gate did not fire: {out.stdout!r} {out.stderr!r}"
