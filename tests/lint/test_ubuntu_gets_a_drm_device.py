"""nomodeset is DEBIAN-ONLY. On Ubuntu it is fatal, and silently so.

Operator decision, 2026-07-29: Ubuntu gets its DRM device from the NVIDIA
proprietary driver (nvidia-drm.modeset=1), NOT from nomodeset.

THE EVIDENCE. A complete Ubuntu 26.04 install, verified 14/15 on disk
(nomodeset present, sddm selected, custom kernel installed, cockpit deployed),
booted to a blinking cursor on black. The same disk with `nomodeset` stripped
from /boot/grub/grub.cfg and NOTHING else changed boots to the Kubuntu Plasma
greeter. Screen luminance 1e-05 -> 0.076.

WHY. Ubuntu 26.04's Plasma is WAYLAND-ONLY:

    /usr/share/wayland-sessions/  ->  plasma.desktop, ubuntu.desktop
    /usr/share/xsessions/         ->  EMPTY

Debian's plasma-workspace DOES ship /usr/share/xsessions/plasmax11.desktop,
which is why X11-on-fbdev works there and why nomodeset was adopted at all.
Wayland needs a DRM device; nomodeset is precisely what prevents one. So on
Ubuntu the flag guarantees there is NO session the display manager can start.

The two options are MUTUALLY EXCLUSIVE — nomodeset stops the NVIDIA driver
binding, so shipping both looks like a failed driver install rather than a
cmdline conflict.

This file makes the wrong route unshippable in both directions.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
USER_DATA = REPO_ROOT / "scripts/build/ubuntu-autoinstall/autoinstall/user-data"
PRESEED = REPO_ROOT / "scripts/build/installer-cdd/profiles/default.preseed"
DISTRO_SH = REPO_ROOT / "scripts/build/lib/distro.sh"
TARGET_SH = REPO_ROOT / "scripts/install/lib/target-distro.sh"
VERIFY = REPO_ROOT / "scripts/install/verify-installed-system.sh"
PROFILE = REPO_ROOT / "profiles/sain-01.yaml"

DRM_OPT = "nvidia-drm.modeset=1"


def autoinstall() -> dict:
    return yaml.safe_load(USER_DATA.read_text(encoding="utf-8"))["autoinstall"]


def late_commands() -> list[str]:
    cmds = autoinstall()["late-commands"]
    bad = [c for c in cmds if not isinstance(c, str)]
    assert not bad, (
        f"late-command parsed as a non-string {bad!r}. A bare `WORD: word` in an "
        "unquoted YAML scalar makes the whole entry a MAPPING — valid YAML, "
        "silently wrong, and Subiquity gets a dict where it expects a command."
    )
    return cmds


# ── the answer file ─────────────────────────────────────────────────────────

def test_ubuntu_never_sets_nomodeset_on_the_installed_system():
    """The single most important assertion in this file."""
    setters = [
        c for c in late_commands()
        if re.search(r"GRUB_CMDLINE_LINUX=\\?\"[^\"]*nomodeset", c)
    ]
    assert not setters, (
        "the Ubuntu autoinstall writes nomodeset into GRUB_CMDLINE_LINUX. That "
        "is FATAL here: Plasma on 26.04 is Wayland-only (/usr/share/xsessions "
        "is empty) and Wayland needs the DRM device nomodeset removes. The "
        f"install boots to a blinking cursor on black.\nOffending: {setters!r}"
    )


def test_ubuntu_sets_the_drm_option_instead():
    setters = [
        c for c in late_commands()
        if re.search(rf"GRUB_CMDLINE_LINUX=\\?\"[^\"]*{re.escape(DRM_OPT)}", c)
    ]
    assert setters, (
        f"the Ubuntu autoinstall must put {DRM_OPT} on the installed kernel "
        "command line — it is what registers a DRM node so udev rule 35 can tag "
        "card0 master-of-seat and logind reports CanGraphical=yes"
    )


def test_ubuntu_installs_the_driver_that_provides_the_drm_device():
    """The cmdline option is inert without the module.

    nvidia-drm.modeset=1 with no nvidia driver installed produces exactly the
    same black screen, by a different route — and is harder to diagnose because
    the cmdline looks right.
    """
    pkgs = autoinstall()["packages"]
    drivers = [p for p in pkgs if re.match(r"^nvidia-driver-\d+", str(p))]
    assert drivers, (
        f"the autoinstall sets {DRM_OPT} but installs no nvidia-driver-* "
        "package. The option is inert without the module: no DRM device, no "
        "Wayland session, blinking cursor."
    )
    assert all(d.endswith("-open") for d in drivers), (
        f"Blackwell (GB202) requires NVIDIA's OPEN kernel modules; the "
        f"proprietary module does not support it. Got {drivers!r} — use the "
        "-open variant."
    )
    for d in drivers:
        ver = int(re.search(r"(\d+)", d).group(1))
        assert ver >= 570, (
            f"{d} predates Blackwell. The RTX 5090 needs >= 570."
        )


def test_the_driver_version_matches_the_profile():
    """One version, decided once. Drift here is invisible until the GPU is dead."""
    prof = PROFILE.read_text(encoding="utf-8")
    want = re.findall(r"driver:\s*nvidia-(\d+)-open", prof)
    assert want, "profiles/sain-01.yaml should pin a `driver: nvidia-<ver>-open`"
    pkgs = [str(p) for p in autoinstall()["packages"]]
    drivers = [p for p in pkgs if re.match(r"^nvidia-driver-\d+", p)]
    for d in drivers:
        got = re.search(r"(\d+)", d).group(1)
        assert got in want, (
            f"the autoinstall installs {d} but the profile pins "
            f"nvidia-{want[0]}-open. Keep them in step."
        )


def test_debian_still_uses_nomodeset():
    """Nothing about Debian changes. It is the PROVEN config on this hardware."""
    text = PRESEED.read_text(encoding="utf-8")
    assert "nomodeset" in text, (
        "the Debian preseed must keep nomodeset — Debian's Plasma ships an X11 "
        "session and runs on the EFI framebuffer, which is the configuration "
        "proven on the operator's machine. This is not symmetric with Ubuntu."
    )


def test_the_two_options_are_never_emitted_together():
    """Mutually exclusive: nomodeset stops the driver binding."""
    for path in (USER_DATA, PRESEED):
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            if line.lstrip().startswith("#"):
                continue
            if "nomodeset" in line and DRM_OPT in line:
                pytest.fail(
                    f"{path.name} emits nomodeset and {DRM_OPT} on the same "
                    f"line. They are mutually exclusive — nomodeset prevents "
                    f"the driver binding, so the box falls back to framebuffer "
                    f"graphics and looks like the driver failed.\n  {line!r}"
                )


# ── the shared definitions ──────────────────────────────────────────────────

@pytest.mark.parametrize("distro,expect_in,expect_out", [
    ("debian", "nomodeset", DRM_OPT),
    ("ubuntu", DRM_OPT, "nomodeset"),
])
def test_the_build_side_cmdline_translation_is_real(distro, expect_in, expect_out):
    """Run the real shell function, do not merely grep for it."""
    out = subprocess.run(
        ["sh", "-c",
         f'. {DISTRO_SH}; distro_kernel_cmdline "nomodeset quiet"'],
        capture_output=True, text=True, cwd=REPO_ROOT,
        env={"SOVEREIGN_OS_DISTRO": distro, "PATH": "/usr/bin:/bin"},
    )
    assert out.returncode == 0, out.stderr
    got = out.stdout.strip()
    assert expect_in in got, f"{distro}: expected {expect_in!r} in {got!r}"
    assert expect_out not in got, (
        f"{distro}: {expect_out!r} must NOT survive translation, got {got!r}"
    )
    assert "quiet" in got, f"{distro}: unrelated options must be preserved: {got!r}"


@pytest.mark.parametrize("distro,route,opt", [
    ("debian", "nomodeset", "nomodeset"),
    ("ubuntu", "drm", DRM_OPT),
])
def test_the_runtime_seat_route_is_real(distro, route, opt):
    out = subprocess.run(
        ["sh", "-c",
         f'. {TARGET_SH}; printf "%s %s" "$(target_seat_route)" "$(target_seat_cmdline_option)"'],
        capture_output=True, text=True, cwd=REPO_ROOT,
        env={"SOVEREIGN_OS_DISTRO": distro, "PATH": "/usr/bin:/bin"},
    )
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == f"{route} {opt}", (
        f"{distro}: expected {route!r}/{opt!r}, got {out.stdout.strip()!r}"
    )


def test_the_self_check_is_route_aware_not_debian_only():
    """Reporting 'nomodeset ABSENT' on Ubuntu is worse than useless.

    It is the CORRECT state there, and telling the operator to add it sends
    them to the one change that guarantees the machine stays dark.
    """
    body = VERIFY.read_text(encoding="utf-8")
    assert "target_seat_route" in body, (
        "verify-installed-system.sh must ask target_seat_route which route this "
        "distro takes, not assume nomodeset"
    )
    assert DRM_OPT in body, (
        f"the report must know about {DRM_OPT} — on Ubuntu that, not nomodeset, "
        "is the thing whose absence explains a dark screen"
    )
    assert "FATAL" in body, (
        "the report must flag nomodeset-on-Ubuntu as fatal, not merely note it"
    )
