"""The d-i installer must install what installed-system.sh says a system IS.

2026-07-26. scripts/install/lib/installed-system.sh was created as the ONE
definition of an installed sovereign-os. The debian-installer path kept its own
list in profiles/sovereign.packages, and the two drifted 33 packages apart:

  * xserver-xorg-video-fbdev / -vesa — the only X configuration proven on this
    hardware (no kernel driver binds to any of its three GPUs; the desktop runs
    on the EFI framebuffer). Without them X cannot start at all.
  * systemd-resolved — the installed system had no working DNS.
  * tmux, vim, xterm, htop, lshw, nvme-cli, pciutils, … — "there was not even a
    console tool installed and a lot was missing".

The firmware bug that halted a boot at "amdgpu: Fatal error during GPU init"
hid inside this same drift. Two lists mean two chances to be wrong, so this
lint asserts the installer is a SUPERSET of the shared definition.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CDD_PACKAGES = (REPO_ROOT / "scripts" / "build" / "installer-cdd"
                / "profiles" / "sovereign.packages")


def shared_definition() -> set[str]:
    out = subprocess.run(
        ["bash", "-c",
         '. scripts/install/lib/installed-system.sh; '
         'echo "${SOVEREIGN_OS_BASE_PACKAGES} ${SOVEREIGN_OS_WORKSTATION_PACKAGES}"'],
        capture_output=True, text=True, check=True, cwd=REPO_ROOT).stdout
    return {p for p in out.split() if p}


def installer_packages() -> set[str]:
    out: set[str] = set()
    for line in CDD_PACKAGES.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            out.update(line.split())
    return out


def test_the_installer_installs_the_whole_shared_definition():
    missing = sorted(shared_definition() - installer_packages())
    assert not missing, (
        "the debian-installer package list has drifted from "
        "scripts/install/lib/installed-system.sh — it would install a system "
        f"missing {len(missing)} package(s): {missing}"
    )


def test_the_installer_has_an_x_driver_that_works_on_this_hardware():
    """No kernel driver binds to any GPU here; X needs fbdev/vesa or nothing."""
    pkgs = installer_packages()
    assert "xserver-xorg-video-fbdev" in pkgs or "xserver-xorg-video-all" in pkgs, (
        "without an fbdev/vesa X driver the desktop is a black screen on healthy "
        "hardware — nouveau does not bind on Blackwell and there is no nvidia driver"
    )
