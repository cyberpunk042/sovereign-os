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

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLED = REPO_ROOT / "scripts" / "install" / "lib" / "installed-system.sh"
ROOT_INSTALL = REPO_ROOT / "scripts" / "install" / "install-sovereign-root.sh"
PROFILES = REPO_ROOT / "scripts" / "build" / "installer-cdd" / "profiles"
# BOTH preseeds. default.preseed is the one that actually runs -- it is loaded
# directly via preseed/file=, while sovereign.preseed depends on the
# simple-cdd-profiles udeb that "silently no-op'd". Proof: sovereign.preseed's
# partman/early_command explicitly REFUSES nvme0n1, yet the operator's install
# landed on nvme0n1. A fix applied only to sovereign.preseed is dead code --
# which is exactly where the amdgpu blacklist first went (2026-07-26).
PRESEEDS = ("default.preseed", "sovereign.preseed")


def test_the_shared_definition_blacklists_amdgpu():
    text = INSTALLED.read_text(encoding="utf-8")
    assert "SOVEREIGN_OS_MODULE_BLACKLIST" in text, (
        "the ONE definition of an installed system must say which modules are "
        "kept out, or the two install paths will disagree again"
    )
    assert "amdgpu" in text


def test_every_initramfs_site_is_preceded_by_the_blacklist():
    """There are TWO writers: the offline (squashfs) and online (debootstrap)
    paths. Checking only the first one passed while the second shipped an
    initrd with no blacklist at all — the same two-writers drift that had the
    d-i preseed and installed-system.sh disagreeing all session (2026-07-26).
    """
    lines = ROOT_INSTALL.read_text(encoding="utf-8").splitlines()
    initramfs_lines = [n for n, l in enumerate(lines) if "update-initramfs" in l]
    blacklist_lines = [n for n, l in enumerate(lines)
                       if "SOVEREIGN_OS_MODULE_BLACKLIST" in l and "for " in l]
    assert initramfs_lines, "no update-initramfs call found"
    assert len(blacklist_lines) >= len(initramfs_lines), (
        f"{len(initramfs_lines)} update-initramfs site(s) but only "
        f"{len(blacklist_lines)} blacklist writer(s) — at least one path builds "
        "an initrd that still lets amdgpu/nouveau probe"
    )
    for n in initramfs_lines:
        assert any(b < n for b in blacklist_lines), (
            f"update-initramfs at line {n + 1} has no blacklist written before "
            "it; the initrd probes before /etc/modprobe.d is ever consulted"
        )


@pytest.mark.parametrize("name", PRESEEDS)
def test_the_installer_writes_it_before_the_initramfs(name: str):
    text = (PROFILES / name).read_text(encoding="utf-8")
    # DERIVE the expected modules from the shared definition. Hardcoding
    # "amdgpu nouveau" here would let a third module be added to
    # SOVEREIGN_OS_MODULE_BLACKLIST and silently never reach the installer —
    # the same declared-but-not-applied bug as everything else this session.
    import subprocess
    mods = subprocess.run(
        ["bash", "-c", '. scripts/install/lib/installed-system.sh; '
                       'echo "${SOVEREIGN_OS_MODULE_BLACKLIST}"'],
        capture_output=True, text=True, check=True, cwd=REPO_ROOT).stdout.split()
    assert mods, "the shared definition declares no modules to blacklist"
    loop = next((l for l in text.splitlines() if "for m in" in l), "")
    for m in mods:
        assert m in loop, (
            f"{name}: {m!r} is in SOVEREIGN_OS_MODULE_BLACKLIST but not in the "
            f"late_command blacklist loop: {loop.strip()!r}"
        )
    assert text.index("for m in") < text.index("update-initramfs"), (
        "same ordering requirement as the direct path: the initrd must carry it"
    )
