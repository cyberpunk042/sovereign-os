"""The kernel cmdline must actually REACH the installed system.

2026-07-28. A sovereign-os install booted three times (18min, 18min, 1.5min),
with the custom znver5 kernel, 24 CPUs, 261 GB RAM and ZERO failed units — and
showed nothing. The operator power-cycled it each time and eventually
reinstalled Debian over the other NVMe.

Two independent faults combined:

  1. `d-i debian-installer/add-kernel-opts string nomodeset` silently did
     nothing. grub-installer ran 18:49:13-16 and left GRUB_CMDLINE_LINUX=""
     on the installed disk; every generated menuentry read `ro  quiet`.

  2. late_command wrote `blacklist nouveau`, so no KMS driver ever bound.

/usr/lib/udev/rules.d/71-seat.rules grants `master-of-seat` in exactly two ways
on this hardware — rules 23/28 tag fb[0-9] but ONLY under
IMPORT{cmdline}="nomodeset", and rule 35 tags a drm card[0-9]* which needs a
bound driver. Fault 1 closes the first route, fault 2 closes the second. With no
master-of-seat device logind reports CanGraphical=no and sddm waits forever at
"Logind interface found" — no error, no failed unit, no Xorg.0.log.

EITHER fault alone is survivable. This file makes the pair unshippable.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PRESEED = REPO_ROOT / "scripts" / "build" / "installer-cdd" / "profiles" / "default.preseed"
VERIFY = REPO_ROOT / "scripts" / "install" / "verify-installed-system.sh"
PERSIST = REPO_ROOT / "scripts" / "install" / "persist-kernel-cmdline.sh"


def late_command() -> str:
    text = PRESEED.read_text(encoding="utf-8")
    start = text.index("d-i preseed/late_command string")
    # The directive is one logical line continued with trailing backslashes.
    out = []
    for line in text[start:].splitlines():
        out.append(line)
        if not line.rstrip().endswith("\\"):
            break
    return "\n".join(out)


def test_the_cmdline_is_written_explicitly_not_left_to_add_kernel_opts():
    """add-kernel-opts is not sufficient — it demonstrably did nothing.

    Preseeding it is fine as belt-and-braces, but something in late_command must
    write the cmdline itself. Relying on the debconf template alone is what
    shipped GRUB_CMDLINE_LINUX="" to a machine whose whole display config
    depends on that one option.
    """
    lc = late_command()
    assert "persist-kernel-cmdline.sh" in lc, (
        "late_command must write the kernel cmdline EXPLICITLY (call "
        "persist-kernel-cmdline.sh). d-i's add-kernel-opts silently left "
        "GRUB_CMDLINE_LINUX empty on the 2026-07-28 install."
    )


def test_the_cmdline_is_written_before_grub_cfg_is_generated():
    """Order matters: update-grub bakes grub.cfg from /etc/default/grub.

    Writing the cmdline AFTER the update-grub calls would leave the generated
    grub.cfg — the thing that actually boots — without it until some later
    regeneration that may never happen.
    """
    lc = late_command()
    persist_at = lc.index("persist-kernel-cmdline.sh")
    for later in ("update-grub", "set-grub-default-kernel.sh"):
        assert persist_at < lc.index(later), (
            f"persist-kernel-cmdline.sh must run BEFORE {later}, or grub.cfg is "
            "generated from a /etc/default/grub that has no cmdline yet"
        )


def test_blacklisting_every_kms_driver_requires_nomodeset():
    """The invariant. Closing both routes to master-of-seat is the dark screen.

    If the preseed blacklists GPU drivers, it MUST also put nomodeset on the
    cmdline — otherwise nothing can be tagged master-of-seat and sddm hangs.
    """
    text = PRESEED.read_text(encoding="utf-8")
    lc = late_command()
    blacklists = re.findall(r"blacklist \$?m|blacklist (nouveau|amdgpu|i915|radeon)", lc)
    if not blacklists and "sovereign-blacklist-" not in lc:
        return  # nothing blacklisted — rule 35 can still fire
    assert "nomodeset" in text, (
        "this preseed blacklists KMS driver(s) but never sets nomodeset. That "
        "closes BOTH routes to a master-of-seat device (udev 71-seat.rules "
        "23/28 need nomodeset; rule 35 needs a bound DRM driver), so logind "
        "reports CanGraphical=no and sddm never starts X — a fully-booted "
        "machine with a dark screen and zero failed units."
    )


def test_the_efi_removable_fallback_is_our_bootloader():
    """\\EFI\\BOOT\\BOOTX64.EFI must be GRUB, not whatever was there before.

    partman REUSED the target ESP (the recipe's $reusemethod{ }, and the
    filesystem LABEL is "ESP" which d-i never sets and systemd-repart does), so
    a previous mkosi appliance's systemd-boot stayed at the removable path with
    an EMPTY loader/entries/. Any NVRAM reset or "Removable Device" boot pick
    lands in a bootloader with nothing to boot.
    """
    text = PRESEED.read_text(encoding="utf-8")
    assert re.search(r"grub-installer/force-efi-extra-removable\s+boolean\s+true", text), (
        "preseed must set grub-installer/force-efi-extra-removable=true so the "
        "EFI removable-media fallback is GRUB and not a stale bootloader"
    )


def test_stale_boot_furniture_is_cleared_from_the_reused_esp():
    """A reused ESP carries the previous image's UKI + bootloader.

    On the 2026-07-28 disk that was a 154 MB sovereign-6.12.0.efi — 30% of a
    512 MB ESP — plus EFI/systemd/ and an empty loader/.
    """
    lc = late_command()
    assert "/boot/efi/EFI/Linux" in lc and "/boot/efi/EFI/systemd" in lc, (
        "late_command must clear the stale UKI + systemd-boot left on a reused ESP"
    )
    # Never touch another OS's bootloader — the reason we clean rather than reformat.
    assert "EFI/Microsoft" not in lc, (
        "the ESP cleanup must never remove another OS's bootloader"
    )


def test_the_self_check_tests_the_real_invariant_not_just_nomodeset():
    """Checking nomodeset alone misses the combination that shipped."""
    body = VERIFY.read_text(encoding="utf-8")
    assert "master-of-seat" in body, (
        "verify-installed-system.sh must check whether ANY route to a graphical "
        "seat exists, not merely whether nomodeset is present"
    )
    assert "CanGraphical" in body, (
        "the report must name the property the operator can verify on the "
        "booted system: loginctl show-seat seat0 -p CanGraphical"
    )
    assert "blacklist" in body, (
        "the check must read /etc/modprobe.d — a blacklisted KMS driver is half "
        "of the failing pair"
    )


def test_the_self_check_no_longer_claims_the_framebuffer_is_missing():
    """The old explanation was wrong and misled the investigation.

    efifb attaches fine without nomodeset; the failed install's journal shows
    `fb0: EFI VGA frame buffer device` on all three boots. The problem is that
    udev will not TAG it master-of-seat.
    """
    body = VERIFY.read_text(encoding="utf-8")
    assert "no EFI framebuffer, X cannot start" not in body, (
        "this explanation is false — fb0 exists without nomodeset. Describe the "
        "udev master-of-seat tagging instead, or the next reader loses an hour."
    )


def test_the_cmdline_definition_stays_single_sourced():
    """persist-kernel-cmdline.sh must read the shared definition, not hardcode."""
    body = PERSIST.read_text(encoding="utf-8")
    assert "installed-system.sh" in body and "SOVEREIGN_OS_KERNEL_CMDLINE" in body, (
        "persist-kernel-cmdline.sh must read SOVEREIGN_OS_KERNEL_CMDLINE from "
        "lib/installed-system.sh so a fresh install and a repair cannot drift"
    )


# ─────────────────────────────────────────────────────────────────────────────
# The display manager. Added 2026-07-29 after a COMPLETE Ubuntu install, with
# every check above passing, booted to a blinking cursor on black.
# ─────────────────────────────────────────────────────────────────────────────

SELECT_DM = REPO_ROOT / "scripts" / "install" / "select-display-manager.sh"


def test_a_display_manager_is_selected_explicitly():
    """`systemctl enable sddm` does NOT make sddm the display manager.

    The active DM is decided by /etc/X11/default-display-manager and the
    display-manager.service alias symlink; `enable` will not take that alias
    from a package that already owns it. The Ubuntu DESKTOP ISO's base install
    is GNOME, so the alias stayed on gdm3 — which needs a DRM device for its
    Wayland greeter, exactly what nomodeset removes.
    """
    assert SELECT_DM.is_file(), "select-display-manager.sh must exist"
    body = SELECT_DM.read_text(encoding="utf-8")
    assert "/etc/X11/default-display-manager" in body, (
        "the debconf choice file must be written, or a later reconfigure reverts it"
    )
    assert "display-manager.service" in body and "ln -sf" in body, (
        "the alias symlink must be REPLACED — enable cannot steal it"
    )


@pytest.mark.parametrize("installer,anchor", [
    ("scripts/build/installer-cdd/profiles/default.preseed", "late_command"),
    ("scripts/build/ubuntu-autoinstall/autoinstall/user-data", "late-commands"),
])
def test_both_installers_select_the_display_manager(installer: str, anchor: str):
    body = (REPO_ROOT / installer).read_text(encoding="utf-8")
    assert "select-display-manager.sh" in body, (
        f"{installer} must select the display manager explicitly in its {anchor}; "
        "installing sddm is not enough when another DM already owns the alias"
    )


def test_the_self_check_flags_gdm_plus_nomodeset():
    """The on-box report must name the fatal COMBINATION, not just the DM.

    gdm3 alone is fine on a machine with working KMS. gdm3 AND nomodeset is a
    guaranteed black screen, and that pair is what shipped.
    """
    body = VERIFY.read_text(encoding="utf-8")
    assert "gdm" in body and "nomodeset" in body, (
        "verify-installed-system.sh must check the display manager against the "
        "cmdline, not merely print which one is registered"
    )
    assert "select-display-manager.sh" in body, (
        "the report must give the exact fix command, not just the diagnosis"
    )


# ── a display that does not depend on a GPU driver (2026-07-30) ─────────────
# Investigated after EVERY Ubuntu attempt reached a login nobody could use,
# while Debian on the same machine was fine.
#
# THE FACT THAT EXPLAINS BOTH: the operator's working Debian desktop has NO
# /dev/dri at all — it runs X11 straight on the EFI framebuffer. X11 can do
# that; Wayland cannot. Ubuntu 26.04's Plasma is Wayland-ONLY, so it REQUIRES a
# DRM device, and this kernel could produce one only if the NVIDIA driver bound
# to Blackwell. `# CONFIG_DRM_SIMPLEDRM is not set` in the Debian config the
# kernel is seeded from meant there was no fallback whatsoever.
#
# simpledrm turns the firmware framebuffer into a real DRM device with NO GPU
# driver involved. Without it, "the driver did not bind" and "the machine is
# unusable" are the same event.

PROFILE = REPO_ROOT / "profiles" / "sain-01.yaml"


def _kernel_enable() -> list[str]:
    import yaml
    k = yaml.safe_load(PROFILE.read_text(encoding="utf-8"))["kernel"]
    return list((k.get("config") or {}).get("enable") or [])


def test_the_profile_requires_a_driverless_drm_fallback():
    enabled = _kernel_enable()
    for sym in ("DRM_SIMPLEDRM", "SYSFB_SIMPLEFB"):
        assert sym in enabled, (
            f"the profile must enable {sym}. Without it the kernel can only "
            "produce a DRM device when the NVIDIA driver binds, so a Wayland-"
            "only desktop has NO path to a display if the driver fails — which "
            "is exactly what happened on every Ubuntu attempt while Debian "
            "(X11 on the EFI framebuffer, no /dev/dri at all) worked fine."
        )


def test_the_kernel_step_refuses_to_silently_drop_required_symbols():
    """A symbol that olddefconfig drops must be reported, not assumed present.

    These two are only useful if they actually land in the .config; a build
    that quietly resolves them away would recreate the same dead end while
    looking fixed.
    """
    body = (REPO_ROOT / "scripts/build/03-kernel-config.sh").read_text(encoding="utf-8")
    assert "missing_syms" in body, (
        "step 03 must track profile-required symbols that did not survive "
        "olddefconfig"
    )
    assert "sovereign_os_build_step_kernel_config_missing_symbols" in body, (
        "and emit the count, so a silently-dropped symbol is visible"
    )
