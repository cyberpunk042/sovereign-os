"""`install logs` — read a flashed disk's boot from the build host, read-only.

Operator, 2026-07-26: "lets make the install allow us to read it."

A flashed NVMe stalled during first boot. The logs were on that disk the whole
time — the image ships a persistent journal (/var/log/journal exists) — but the
only way to see them was to walk to the box and type on a tty. `install logs`
mounts the flashed root from here and prints the markers, the sovereign logs and
the failed units.

Two properties are load-bearing:

  * READ-ONLY IN FACT, not just in intent. `mount -o ro` ALONE still replays the
    ext4 journal, writing to a filesystem we are only inspecting — mutating the
    evidence and dirtying a disk the operator may still want to boot. `noload`
    is what makes it truly non-destructive.
  * It must never touch the RUNNING root, which has its own journalctl.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"


def _subcommand() -> str:
    """The `install logs` case body.

    Anchored on its own banner comment, NOT on `logs)` — five other verbs have
    a `logs)` subcommand and the first match slices the wrong function.
    """
    body = OSCTL.read_text(encoding="utf-8")
    start = body.index("# READ the last boot off a FLASHED disk")
    return body[start:body.index("\n    suggest-modules)", start)]


def test_subcommand_exists_and_is_documented():
    body = OSCTL.read_text(encoding="utf-8")
    assert "\n    logs)" in body, "the `install logs` subcommand must exist"
    assert "sovereign-osctl install logs   --from <disk>" in body, (
        "it must appear in the install USAGE block or nobody will find it"
    )
    assert re.search(r"^logs\s+—", body, re.M), (
        "it needs a per-subcommand description like image/system have"
    )


def test_mount_is_read_only_and_does_not_replay_the_journal():
    """`ro` alone is not enough — ext4 replays its journal and WRITES."""
    fn = _subcommand()
    assert "ro,noload" in fn, (
        "mount with ro,noload: a plain `ro` mount still replays the ext4 "
        "journal, which writes to the disk being inspected"
    )
    assert "-w " not in fn and "rw," not in fn, "no writable mount option may appear"
    # nothing may write into the mounted tree
    for banned in ("> \"${mnt}", ">>\"${mnt}", "rm -rf \"${mnt}\"/"):
        assert banned not in fn, f"must not write into the mounted root: {banned}"


def test_it_refuses_the_running_root():
    fn = _subcommand()
    assert "IS the running root" in fn, (
        "reading the live root through a loopback mount is both pointless and "
        "risky — journalctl already does it"
    )
    assert "findmnt" in fn and "PKNAME" in fn, (
        "the running-root check must resolve the parent disk, not just compare "
        "the device string"
    )


def test_root_partition_is_found_by_type():
    """p2 is a convention, not a guarantee."""
    fn = _subcommand()
    assert "PARTTYPENAME" in fn, "locate the root partition by type"
    assert "Linux root" in fn, "must match the GPT Linux-root type name"


def test_it_always_unmounts():
    fn = _subcommand()
    assert "trap" in fn and "umount" in fn, (
        "a RETURN trap must unmount — leaving a flashed disk mounted after a "
        "diagnostic would block the next flash"
    )


def test_it_reports_the_things_that_actually_stalled_the_boot():
    fn = _subcommand()
    assert "/var/lib/sovereign-os" in fn, "first-boot markers"
    assert "/var/log/sovereign-os" in fn, "the sovereign log dir"
    assert "journalctl" in fn and "-D " in fn, (
        "must read the flashed root's PERSISTENT journal with journalctl -D"
    )
    assert "first-boot-complete" in fn, (
        "whether first boot completed is the single most useful marker"
    )


def test_the_flash_path_points_at_it():
    """The hint printed after a flash must name a verb that exists."""
    body = OSCTL.read_text(encoding="utf-8")
    assert "install verify --to" not in body, (
        "the post-flash hint advertised `install verify` — a verb that was "
        "never implemented. Point at the one that is."
    )
    tail = body[body.index("image dump complete"):]
    tail = tail[:tail.index("\n    system)")]
    assert "install logs --from" in tail, (
        "after flashing, tell the operator how to read that disk's boot"
    )


def test_osctl_parses():
    proc = subprocess.run(["bash", "-n", str(OSCTL)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr


def test_bootstrap_puts_the_cli_on_path():
    """The host bootstrap must leave `sovereign-osctl` runnable.

    Its own header promises a host ready to BUILD *and RUN* sovereign-os, and
    its own closing output tells the operator to run panel/CLI verbs. Only
    provision.sh linked the CLI, so an operator who ran bootstrap-host.sh — the
    script this project's error messages point at — got a full toolchain and
    then `sovereign-osctl: command not found` (reported 2026-07-26 while trying
    to read a stalled box's logs).
    """
    bootstrap = REPO_ROOT / "scripts" / "install" / "bootstrap-host.sh"
    text = bootstrap.read_text(encoding="utf-8")
    assert "link-operator-cli.sh" in text, (
        "bootstrap-host.sh must link the operator CLI onto PATH"
    )
    # and it must be a real step, not a comment
    live = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))
    assert "link-operator-cli.sh" in live, "the link must actually execute"


def test_bootstrap_step_numbering_is_consistent():
    """A mislabelled [n/N] is a small lie the operator reads every run."""
    bootstrap = REPO_ROOT / "scripts" / "install" / "bootstrap-host.sh"
    text = bootstrap.read_text(encoding="utf-8")
    steps = re.findall(r'^step "\[(\d+)/(\d+)\]', text, re.M)
    assert steps, "no numbered steps found"
    totals = {t for _, t in steps}
    assert len(totals) == 1, f"inconsistent step totals: {totals}"
    total = int(totals.pop())
    assert [int(n) for n, _ in steps] == list(range(1, total + 1)), (
        f"steps are not 1..{total}: {[n for n, _ in steps]}"
    )
