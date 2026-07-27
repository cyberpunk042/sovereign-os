"""Three paths install a sovereign-os. All three must read ONE definition.

2026-07-26. Every bug this session had the same shape: something declared in
one file and never applied by the file that actually mattered.

  * sovereign.packages (mirror)      vs  pkgsel/include (install)  -> 37 pkgs missing
  * installed-system.sh              vs  the d-i preseed           -> 33 pkgs missing
  * SOVEREIGN_OS_KERNEL_CMDLINE      vs  grub.cfg                  -> no nomodeset, dark screen
  * sovereign.preseed                vs  default.preseed           -> fix landed in dead code
  * offline initramfs site           vs  online initramfs site     -> one initrd unguarded

The three paths are:
  1. debian-installer  -> profiles/*.preseed pkgsel/include
  2. direct, online    -> install-sovereign-root.sh (debootstrap + apt)
  3. direct, offline   -> build-target-rootfs.sh (squashfs), installed by (2)

This lint asserts each one reads scripts/install/lib/installed-system.sh rather
than carrying its own copy.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB = REPO_ROOT / "scripts" / "install" / "lib" / "installed-system.sh"
ROOTFS = REPO_ROOT / "scripts" / "build" / "build-target-rootfs.sh"
ROOT_INSTALL = REPO_ROOT / "scripts" / "install" / "install-sovereign-root.sh"


def test_the_squashfs_builder_reads_the_shared_definition():
    text = ROOTFS.read_text(encoding="utf-8")
    assert "installed-system.sh" in text, (
        "build-target-rootfs.sh must source the shared definition, not keep its "
        "own package list — that is a fourth list waiting to drift"
    )
    assert "sovereign_os_installed_packages" in text, (
        "it must call the shared accessor so a rename cannot silently leave the "
        "squashfs with an empty package set"
    )


def test_the_shared_accessor_exists_and_is_not_empty():
    """build-target-rootfs.sh interpolates this into `apt-get install`.

    If the function were renamed or removed, the command substitution yields an
    empty string and `apt-get install -y` installs NOTHING — while still
    exiting 0.
    """
    out = subprocess.run(
        ["bash", "-c",
         ". scripts/install/lib/installed-system.sh && sovereign_os_installed_packages"],
        capture_output=True, text=True, cwd=REPO_ROOT)
    assert out.returncode == 0, f"accessor failed: {out.stderr}"
    pkgs = out.stdout.split()
    assert len(pkgs) > 30, f"suspiciously small package set ({len(pkgs)})"
    for needed in ("xserver-xorg-video-fbdev", "firmware-amd-graphics"):
        assert needed in pkgs, f"{needed} missing from the shared definition"


def test_the_direct_installer_reads_it_too():
    assert "installed-system.sh" in ROOT_INSTALL.read_text(encoding="utf-8"), (
        "install-sovereign-root.sh must source the shared definition"
    )


def test_the_definition_declares_both_cmdline_and_blacklist():
    """Packages alone are not a working system.

    The install that failed had every package and still showed a dark screen,
    because the boot options that make those packages usable were not applied.
    """
    text = LIB.read_text(encoding="utf-8")
    for var in ("SOVEREIGN_OS_KERNEL_CMDLINE", "SOVEREIGN_OS_MODULE_BLACKLIST"):
        assert var in text, f"{var} must live in the ONE definition"


def test_the_installer_path_verifies_itself():
    """The d-i path had no verification at all.

    install-sovereign-root.sh refuses to call an install good without checking
    it (sovereign_verify_install). The debian-installer path just finished:
    every package installed, sddm registered, zero failed units, dark screen.
    It now writes evidence to /var/log/sovereign-os/install-verify.log, which
    `sovereign-osctl install logs --from` reads off the unmounted disk.
    """
    verifier = REPO_ROOT / "scripts" / "install" / "verify-installed-system.sh"
    assert verifier.exists(), "the d-i path needs a self-check script"
    assert verifier.stat().st_mode & 0o111, (
        "must be executable — a missing exec bit silently skipped the whole "
        "desktop stage once already"
    )
    body = verifier.read_text(encoding="utf-8")
    assert "nomodeset" in body, "it must name the option that decides display/no display"
    assert body.rstrip().endswith("exit 0"), (
        "it must NEVER fail the install — d-i has already partitioned by then; "
        "aborting leaves a half-installed disk and explains nothing"
    )
    for name in ("default.preseed", "sovereign.preseed"):
        text = (REPO_ROOT / "scripts" / "build" / "installer-cdd" / "profiles" / name).read_text(encoding="utf-8")
        assert "verify-installed-system.sh" in text, f"{name} must run the self-check"
