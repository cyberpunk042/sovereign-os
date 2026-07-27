"""No preseed may repartition a disk without asking.

2026-07-27. sovereign.preseed answered all EIGHT of d-i's destructive
partitioning confirmations — partman/confirm, confirm_nooverwrite,
confirm_write_new_label, partman-lvm/{confirm,confirm_nooverwrite,
device_remove_lvm}, partman-md/device_remove_md, choose_partition=finish —
making the install fully unattended.

It also carried a partman/early_command that picked a target by SKIPPING
nvme0n1, on the assumption that nvme0n1 was the running OS. That assumption
expired. On this machine:

    /dev/nvme0n1  S7U7NU1YA16134D   the sovereign-os TARGET
    /dev/nvme1n1  S7U7NU1YA16121D   the operator's working Debian (root)

So the rule selected exactly the disk it was written to protect. Unattended,
that is a silent wipe of the working system. The file is currently inert — it
loads only through the simple-cdd-profiles udeb, which silently no-ops — but
"make the udeb path work" is an obvious future fix, and it would have armed it.

default.preseed, the file that actually runs, preseeds none of these: d-i stops
for the disk pick and every destructive write. Both files must stay that way.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PROFILES = REPO_ROOT / "scripts" / "build" / "installer-cdd" / "profiles"
PRESEEDS = ("default.preseed", "sovereign.preseed")

# Each of these, preseeded, removes one prompt that stands between a keypress
# and an irreversible write.
# NOT included: partman/choose_partition. That selects the "finish
# partitioning" MENU ITEM; d-i still asks "Write the changes to disks?" via
# partman/confirm afterwards. default.preseed sets it and remains safe, so
# treating it as a write gate would flag correct, working behaviour.
DESTRUCTIVE = re.compile(
    r"^d-i\s+(partman/confirm|partman/confirm_nooverwrite|"
    r"partman-lvm/confirm|partman-lvm/confirm_nooverwrite|partman-lvm/device_remove_lvm|"
    r"partman-md/device_remove_md|partman-partitioning/confirm_write_new_label)\b",
    re.M)


@pytest.mark.parametrize("name", PRESEEDS)
def test_destructive_writes_stay_interactive(name: str):
    text = (PROFILES / name).read_text(encoding="utf-8")
    hits = [m.group(0) for m in DESTRUCTIVE.finditer(text)]
    assert not hits, (
        f"{name} preseeds destructive partitioning confirmation(s): {hits}. "
        "That makes the install unattended — it repartitions whatever disk it "
        "picked with no prompt. Re-enabling this is an explicit operator "
        "decision, never a default."
    )


@pytest.mark.parametrize("name", PRESEEDS)
def test_no_target_disk_is_chosen_for_the_operator(name: str):
    """Choosing the disk AND skipping the confirmations is the dangerous pair."""
    text = (PROFILES / name).read_text(encoding="utf-8")
    for key in ("partman-auto/disk", "partman/early_command"):
        live = [l for l in text.splitlines()
                if l.startswith(f"d-i {key}") and not l.lstrip().startswith("#")]
        assert not live, (
            f"{name} selects the target disk itself ({key}). d-i must ask: a "
            "device name is not a stable identity, and the previous rule "
            "selected the very disk it was written to protect."
        )


def test_the_expired_assumption_is_recorded_not_repeated():
    """Whoever re-enables this must see why it was disabled."""
    text = (PROFILES / "sovereign.preseed").read_text(encoding="utf-8")
    assert "nvme1n1" in text and "nvme0n1" in text, (
        "the rationale must name both disks and their roles, or the same "
        "hardcoded-device-name mistake gets made again"
    )
