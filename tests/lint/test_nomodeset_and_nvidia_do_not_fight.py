"""nomodeset and the NVIDIA DRM driver are mutually exclusive — keep them apart.

2026-07-27. Two correct changes collide:

  * the installer bakes `nomodeset` in, because no GPU driver binds on this
    hardware and without it there is no framebuffer and X cannot start;
  * nvidia-blackwell-driver-install.sh deliberately STRIPS nomodeset and adds
    nvidia-drm.modeset=1, because the two cannot coexist.

So the upgrade path is: install with nomodeset → later install the driver,
which removes it. That works — until something re-adds nomodeset afterwards.
persist-kernel-cmdline.sh, added the same day to repair installs missing the
option, would have done exactly that: silently undoing a driver install and
returning the box to the framebuffer, with the symptom looking like the driver
had failed.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PERSIST = REPO_ROOT / "scripts" / "install" / "persist-kernel-cmdline.sh"
VERIFY = REPO_ROOT / "scripts" / "install" / "verify-installed-system.sh"
NVIDIA = REPO_ROOT / "scripts" / "hooks" / "post-install" / "nvidia-blackwell-driver-install.sh"


def test_the_repair_script_refuses_over_an_nvidia_install():
    body = PERSIST.read_text(encoding="utf-8")
    assert "nvidia-drm" in body, (
        "persist-kernel-cmdline.sh must detect an active NVIDIA DRM driver; "
        "re-adding nomodeset there undoes the driver install"
    )
    assert "REFUSING" in body, "it must refuse, not warn and proceed"


def test_the_refusal_names_the_way_past_it():
    body = PERSIST.read_text(encoding="utf-8")
    assert "SOVEREIGN_OS_KERNEL_CMDLINE=''" in body, (
        "a refusal with no escape hatch is a wall; the operator may genuinely "
        "want to go back to the framebuffer"
    )


def test_the_selfcheck_reports_the_conflict():
    body = VERIFY.read_text(encoding="utf-8")
    assert "CONFLICT" in body and "nvidia-drm" in body, (
        "if both options end up on the kernel line the report must say so — "
        "the symptom (no acceleration) looks like a failed driver, not a "
        "cmdline conflict"
    )


def test_the_nvidia_installer_still_strips_nomodeset():
    """Guard the premise: if it stops doing this, the whole interaction changes."""
    body = NVIDIA.read_text(encoding="utf-8")
    assert "nomodeset" in body and "sed -i" in body, (
        "the driver installer is expected to remove nomodeset; if that changed, "
        "revisit the repair script's refusal"
    )
