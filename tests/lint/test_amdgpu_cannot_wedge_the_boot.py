"""amdgpu must not be allowed to fatally probe the iGPU on this hardware.

2026-07-26. A freshly installed system halted at boot with:

    unknown chipset
    [drm:amdgpu_device_init [amdgpu]] *ERROR* early_init of ...
    amdgpu: Fatal error during GPU init

A Ryzen 9 9900X carries a Granite Ridge iGPU [1002:13c0]. This kernel's amdgpu
does not recognise that ASIC, so the probe fails fatally. Installing
firmware-amd-graphics did NOT fix it — "unknown chipset" is missing chipset
support, not missing firmware.

The operator's working Debian 13 on this same machine binds NO kernel driver to
ANY of its three GPUs and runs the desktop on the EFI framebuffer. Both install
paths must keep amdgpu out of the way, and the blacklist has to reach the
INITRD — amdgpu probes from there, long before /etc/modprobe.d is consulted.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLED = REPO_ROOT / "scripts" / "install" / "lib" / "installed-system.sh"
ROOT_INSTALL = REPO_ROOT / "scripts" / "install" / "install-sovereign-root.sh"
PRESEED = (REPO_ROOT / "scripts" / "build" / "installer-cdd"
           / "profiles" / "sovereign.preseed")


def test_the_shared_definition_blacklists_amdgpu():
    text = INSTALLED.read_text(encoding="utf-8")
    assert "SOVEREIGN_OS_MODULE_BLACKLIST" in text, (
        "the ONE definition of an installed system must say which modules are "
        "kept out, or the two install paths will disagree again"
    )
    assert "amdgpu" in text


def test_the_direct_install_path_writes_it_before_the_initramfs():
    text = ROOT_INSTALL.read_text(encoding="utf-8")
    assert "SOVEREIGN_OS_MODULE_BLACKLIST" in text, "must use the shared list"
    where = text.index("SOVEREIGN_OS_MODULE_BLACKLIST")
    initramfs = text.index("update-initramfs")
    assert where < initramfs, (
        "the blacklist must be written BEFORE update-initramfs; amdgpu probes "
        "from the initrd, where a later /etc/modprobe.d file is never seen"
    )


def test_the_installer_writes_it_before_the_initramfs():
    text = PRESEED.read_text(encoding="utf-8")
    assert "blacklist amdgpu" in text, (
        "the d-i late_command must blacklist amdgpu — this is the path the "
        "operator actually installs from"
    )
    assert text.index("blacklist amdgpu") < text.index("update-initramfs"), (
        "same ordering requirement as the direct path: the initrd must carry it"
    )
