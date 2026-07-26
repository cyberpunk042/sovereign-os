"""Flashing an internal disk must register its NVRAM boot entry (2026-07-26).

Operator, verbatim: "why do I need to do this manually? what is this voodo that
was not included in the panel?"

Flashing a USB key needs no NVRAM work — firmware boots removable media from the
fallback path \\EFI\\BOOT\\BOOTX64.EFI by itself. An INTERNAL disk is different:
many firmwares only consult NVRAM Boot#### entries for fixed disks. The flash
panel gained internal-disk targeting the same day (the removable-only gate was
replaced by a protected-disks-only gate) and never gained the matching boot-entry
step, so a successful flash produced a disk the firmware would not offer.

Compounding it: every flash mints a NEW ESP PARTUUID, so the entry left by the
PREVIOUS flash points at a partition that no longer exists. One such "UEFI OS"
entry survived two reflashes on the operator's box.

`install image` now registers the entry and prunes dangling ones, so both the
panel (which shells this CLI) and the terminal get it.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"
BOOTSTRAP = REPO_ROOT / "scripts" / "install" / "bootstrap-host.sh"


def _fn() -> str:
    body = OSCTL.read_text(encoding="utf-8")
    start = body.index("install_register_boot_entry() {")
    return body[start:body.index("\ncmd_install() {", start)]


def test_install_image_registers_a_boot_entry():
    body = OSCTL.read_text(encoding="utf-8")
    assert "install_register_boot_entry() {" in body, (
        "the helper must exist — flashing an internal disk without an NVRAM "
        "entry produces a disk the firmware will not offer"
    )
    # it must actually be CALLED on the image-flash path, after the sync
    dump = body[body.index("image dump complete"):]
    dump = dump[:dump.index("install logs --from")]
    assert "install_register_boot_entry" in dump, (
        "the helper must be invoked after the flash completes, or it is dead code"
    )
    assert dump.index("sudo sync") < dump.index("install_register_boot_entry"), (
        "register the entry only AFTER sync — the ESP must be on the medium first"
    )


def test_boot_entry_finds_the_esp_by_type_not_by_number():
    """p1 is a convention, not a guarantee — locate the ESP by partition type."""
    fn = _fn()
    assert "PARTTYPENAME" in fn and "EFI System" in fn, (
        "the ESP must be located by partition type, never assumed to be p1"
    )


def test_stale_entries_are_pruned_only_when_truly_dangling():
    """Each flash mints a new ESP PARTUUID, orphaning the previous entry.

    The prune must key on 'this PARTUUID exists on no disk' — never on the
    label or the disk — so a live entry (the operator's Debian) is untouched.
    """
    fn = _fn()
    assert "PARTUUID" in fn, "the prune must compare partition UUIDs"
    assert "-B" in fn, "stale entries must be deleted with efibootmgr -b N -B"
    assert "no longer exists" in fn, "the removal must say WHY it removed an entry"


def test_boot_entry_failures_are_reported_not_fatal():
    """The bytes are already written; a NVRAM hiccup must not read as a failed flash."""
    fn = _fn()
    for guard in ("/sys/firmware/efi", "efibootmgr not installed"):
        assert guard in fn, f"must handle the {guard!r} case explicitly"
    assert "return 0" in fn, (
        "a non-UEFI host / missing tool / no-ESP image must skip cleanly, since "
        "the image is already on the disk and the firmware menu still works"
    )
    assert "log_warn" in fn, "a skipped registration must be visible, never silent"


def test_bootstrap_installs_efibootmgr():
    """Otherwise the registration silently degrades on a fresh host."""
    text = BOOTSTRAP.read_text(encoding="utf-8")
    block = text[text.index("HOST_PACKAGES=("):]
    block = block[:block.index("\n)")]
    assert "efibootmgr" in block, (
        "efibootmgr must be part of the one-command bootstrap — without it a "
        "flashed internal disk never gets a boot entry"
    )


def test_osctl_parses():
    proc = subprocess.run(["bash", "-n", str(OSCTL)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr


def test_registration_cannot_fail_the_flash():
    """osctl runs `set -euo pipefail` — an unmatched grep would abort the CLI.

    Real NVRAM contains entries with NO GPT device path (UEFI:CD/DVD Drive,
    UEFI:Removable Device, UEFI:Network Device, a USB entry with an MBR path).
    Each one makes the PARTUUID grep exit 1, and inside a command substitution
    that killed the whole flash AFTER every byte was written and synced — the
    operator saw "✗ exit code 1" on a flash that had actually succeeded
    (2026-07-26). Every grep in the helper must therefore be `|| true`, and the
    call site must swallow the result outright.
    """
    fn = _fn()
    import re as _re
    for line in fn.splitlines():
        s = line.strip()
        if s.startswith("#") or "grep" not in s:
            continue
        # `grep -q` used as an `if`/`!` condition is a test, not a substitution
        if _re.search(r"(^|\W)(if|while|until)\s|^!|\bgrep -q", s):
            continue
        assert "|| true" in s, (
            f"unguarded grep under `set -e` will abort the CLI: {s!r}"
        )

    body = OSCTL.read_text(encoding="utf-8")
    call = body[body.index("sudo sync"):body.index("install logs --from")]
    assert "install_register_boot_entry \"${device}\" || true" in call, (
        "the call site must be `|| true` — the image is already written, so a "
        "NVRAM hiccup must never report a failed flash"
    )
