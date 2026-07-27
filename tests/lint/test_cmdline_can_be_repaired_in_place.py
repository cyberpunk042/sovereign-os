"""An existing install must be repairable without reinstalling it.

2026-07-27. A one-time `e` at the GRUB menu adding nomodeset produced a booting
machine with a functional KDE Plasma desktop — confirming the diagnosis: without
it, nouveau attempts KMS on the Blackwell cards, fails with "unknown chipset
(1b2000a1)", no EFI framebuffer is established, /dev/fb0 never appears, and X
has no device to open.

That edit does not survive reboot. New installs get the option through the
preseed (debian-installer/add-kernel-opts). This script exists so an already
installed machine can be fixed in place rather than reinstalled.

It must read the SHARED definition rather than hardcode "nomodeset", or it
becomes a fifth copy of the kernel cmdline to drift out of sync — the exact
failure mode behind most of this session.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "install" / "persist-kernel-cmdline.sh"
LIB = REPO_ROOT / "scripts" / "install" / "lib" / "installed-system.sh"


def test_it_exists_and_is_executable():
    assert SCRIPT.exists()
    assert SCRIPT.stat().st_mode & 0o111


def test_it_reads_the_shared_definition():
    body = SCRIPT.read_text(encoding="utf-8")
    assert "SOVEREIGN_OS_KERNEL_CMDLINE" in body, (
        "it must take the option set from installed-system.sh, not hardcode a "
        "fifth copy of the kernel cmdline"
    )
    assert "installed-system.sh" in body


def test_its_fallback_matches_the_shared_definition():
    """The fallback only fires when the payload is absent — it must still agree."""
    shared = re.search(
        # `:?-` so this matches BOTH ${VAR:-d} and ${VAR-d}. installed-system.sh
        # moved to the colon-less form so an explicitly EMPTY value survives
        # (blacklist nothing / no extra cmdline); three lints parsed the old
        # spelling and broke (2026-07-27).
        r'SOVEREIGN_OS_KERNEL_CMDLINE="\$\{SOVEREIGN_OS_KERNEL_CMDLINE:?-([^}]*)\}"',
        LIB.read_text(encoding="utf-8"))
    assert shared, "installed-system.sh must define the cmdline"
    for opt in shared.group(1).split():
        assert opt in SCRIPT.read_text(encoding="utf-8"), (
            f"fallback omits {opt!r}, which a fresh install would receive"
        )


def test_it_is_idempotent_and_keeps_a_backup(tmp_path: Path):
    """Run it twice against a throwaway grub file."""
    grub = tmp_path / "grub"
    grub.write_text('GRUB_TIMEOUT=2\nGRUB_CMDLINE_LINUX_DEFAULT="quiet"\n', encoding="utf-8")
    src = (SCRIPT.read_text(encoding="utf-8")
           .replace("DEFAULT=/etc/default/grub", f"DEFAULT={grub}")
           .replace('[ "$(id -u)" -eq 0 ] || { echo "must run as root: sudo $0" >&2; exit 1; }', "")
           .replace("\nupdate-grub\n", "\n:\n"))
    first = subprocess.run(["sh"], input=src, capture_output=True, text=True)
    assert first.returncode == 0, first.stderr
    assert 'GRUB_CMDLINE_LINUX_DEFAULT="quiet nomodeset"' in grub.read_text(encoding="utf-8")
    assert (tmp_path / "grub.sovereign-bak").exists(), "no backup was kept"

    second = subprocess.run(["sh"], input=src, capture_output=True, text=True)
    assert second.returncode == 0, second.stderr
    assert grub.read_text(encoding="utf-8").count("nomodeset") == 1, (
        "running twice duplicated the option"
    )
