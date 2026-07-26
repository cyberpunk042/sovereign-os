"""A kernel that loads drivers as modules must ship the firmware they ask for.

2026-07-26. The operator's install completed, rebooted, and halted at:

    amdgpu: Fatal error during GPU init

The machine's real GPUs are NVIDIA (RTX PRO 6000 Blackwell + RTX 5090) — but a
Ryzen 9 9900X also carries a Granite Ridge iGPU [1002:13c0], so amdgpu probes
real hardware. The custom kernel is CONFIG_DRM_AMDGPU=m with
CONFIG_EXTRA_FIRMWARE="", meaning the module loads at runtime and requests its
blobs from the filesystem. Neither install path shipped a single firmware
package, so the probe failed fatally and the boot stopped.

Both paths are checked because they are independent lists that have already
drifted apart once.
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLED = REPO_ROOT / "scripts" / "install" / "lib" / "installed-system.sh"
CDD_PACKAGES = (REPO_ROOT / "scripts" / "build" / "installer-cdd"
                / "profiles" / "sovereign.packages")

# The exact set the operator's working Debian 13 carries on this hardware.
REQUIRED = ("firmware-amd-graphics", "amd64-microcode")


def _cdd_packages() -> set[str]:
    out = set()
    for line in CDD_PACKAGES.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            out.update(line.split())
    return out


@pytest.mark.parametrize("pkg", REQUIRED)
def test_the_di_installer_ships_firmware(pkg: str):
    assert pkg in _cdd_packages(), (
        f"{pkg!r} missing from the d-i package list — an installed system boots "
        "into 'amdgpu: Fatal error during GPU init' and stops"
    )


@pytest.mark.parametrize("pkg", REQUIRED)
def test_the_direct_install_path_ships_firmware(pkg: str):
    assert pkg in INSTALLED.read_text(encoding="utf-8"), (
        f"{pkg!r} missing from installed-system.sh — the other install path has "
        "the identical fatal-probe failure"
    )


def test_firmware_survives_a_headless_install():
    """A fatal driver probe kills a headless boot exactly as it kills a GUI one."""
    text = INSTALLED.read_text(encoding="utf-8")
    body = text[text.index('SOVEREIGN_OS_INSTALL_GUI:-1'):]
    cleared = body[:body.index("SOVEREIGN_OS_WORKSTATION_PACKAGES=")]
    assert "_sovos_ws_firmware=" not in cleared, (
        "the headless branch must not clear the firmware set — amdgpu still "
        "probes and still dies without its blobs"
    )
    assert "${_sovos_ws_firmware}" in text, (
        "the firmware set must be part of the installed package list"
    )
