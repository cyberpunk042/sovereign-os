"""The three operator panels must handle Ubuntu, not just Debian.

Operator, 2026-07-30: "The build-configurator/ doesn't seem to be ready to build
ubuntu, i asked to prepare the three panels including emulator and Flash to
Device."

The three are Build Configurator (composes and RUNS the build), Emulate (boots
the result in QEMU) and Flash (writes it to a disk). A distro axis that stops at
the CLI is not an axis the operator has.

What was actually missing, panel by panel:

  * BUILD CONFIGURATOR — the secure-boot selector offered `disabled`, but the
    choice reached only the PRINTED command. The real build kept the profile's
    `signed` posture, so an operator who picked `disabled` still hit
    "profile posture secure_boot=signed needs an operator signing key" and had
    no way out of the panel at all. Cosmetic controls are worse than absent
    ones: they read as a decision that was taken.

  * FLASH — both installer ISOs end in `-installer.iso`, so both rendered as an
    identical "🖴 INSTALLER" row, and the panel default-selects the NEWEST
    installer — Ubuntu after a Ubuntu build, even if the operator had just built
    Debian. Writing the wrong distro to an internal disk is not recoverable.

  * EMULATE — mkosi emitted `<profile>.raw` for BOTH distros, so the row could
    be either and the second build had silently overwritten the first.

The posture forwarding is DOWNGRADE-ONLY on purpose: an HTTP POST must not be
able to claim a stronger security posture than the profile declares in git.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIGURATOR = REPO_ROOT / "webapp/build-configurator/index.html"
CONFIG_API = REPO_ROOT / "scripts/operator/build-configurator-api.py"
FLASH_PANEL = REPO_ROOT / "webapp/flash/index.html"
EMULATE_PANEL = REPO_ROOT / "webapp/emulate/index.html"

PANELS = {
    "build-configurator": CONFIGURATOR,
    "flash": FLASH_PANEL,
    "emulate": EMULATE_PANEL,
}


# ── build configurator: can it actually START an Ubuntu build? ──────────────

def test_the_configurator_offers_ubuntu():
    body = CONFIGURATOR.read_text(encoding="utf-8")
    assert 'value="ubuntu"' in body, "the panel must offer Ubuntu as a distro"
    assert 'id="distro"' in body, "there must be a distro control to read"


def test_the_configurator_sends_the_distro_to_the_build():
    """A control that does not reach the build is decoration."""
    body = CONFIGURATOR.read_text(encoding="utf-8")
    assert re.search(r"distro:\s*state\.distro", body), (
        "the build POST must carry the chosen distro, or the panel claims "
        "Ubuntu while the build runs Debian"
    )


def test_the_api_validates_and_forwards_the_distro():
    src = CONFIG_API.read_text(encoding="utf-8")
    assert 'bake_env["SOVEREIGN_OS_DISTRO"]' in src, (
        "the API must export SOVEREIGN_OS_DISTRO — it selects the substrate"
    )
    assert '("debian", "ubuntu")' in src, (
        "the distro must be validated against a whitelist, not trusted: an "
        "unknown value would resolve to the Debian installer while the panel "
        "claimed Ubuntu"
    )


def test_the_installer_hint_tracks_the_distro():
    """"Debian 13 installer" while Ubuntu is selected is a mislabel.

    The two are genuinely different mechanisms — d-i + preseed vs Subiquity +
    autoinstall — and that class of mislabel got a TUI ISO flashed twice.
    """
    body = CONFIGURATOR.read_text(encoding="utf-8")
    assert "syncInstallerHint" in body, (
        "the INSTALLER checkbox builds a different thing per distro; the hint "
        "must follow the selection"
    )
    seg = body[body.index("function syncInstallerHint"):]
    seg = seg[: seg.index("}")]
    assert "Ubuntu" in seg and "Subiquity" in seg, (
        "the Ubuntu hint must say Subiquity, not d-i — Ubuntu has had no "
        "debian-installer since 20.04"
    )


# ── the two blockers, from the panel ───────────────────────────────────────

def test_the_panel_can_supply_a_bootstrap_root_password():
    body = CONFIGURATOR.read_text(encoding="utf-8")
    assert 'id="root-password"' in body, (
        "mkosi hard-fails without a root password (a locked-root image boots "
        "to a prompt nobody can satisfy) — the panel must be able to supply one"
    )
    assert "root_password:" in body, "and it must reach the build POST"


def test_the_password_is_hashed_before_it_reaches_an_env():
    """pkexec env K=V argv is world-readable in `ps`."""
    src = CONFIG_API.read_text(encoding="utf-8")
    seg = src[src.index("root_pw = body.get"):]
    seg = seg[: seg.index("argv_fn, needs_root")]
    assert "openssl" in seg and "passwd" in seg, (
        "the plaintext root password must be hashed in the API; elevation "
        "passes env through argv, which is world-readable in ps"
    )


def test_the_secure_boot_choice_actually_reaches_the_build():
    """It offered `disabled` and changed only the printed command."""
    body = CONFIGURATOR.read_text(encoding="utf-8")
    assert re.search(r"secure_boot:\s*state\.secureboot", body), (
        "the panel's secure-boot selector must reach the build POST. Offering "
        "`disabled` while the build keeps the profile's `signed` posture leaves "
        "the operator stuck on 'needs an operator signing key' with no way out."
    )
    src = CONFIG_API.read_text(encoding="utf-8")
    assert 'bake_env["SOVEREIGN_OS_SECURE_BOOT"]' in src, (
        "the API must forward the downgrade to the build"
    )


def test_the_posture_forwarding_is_downgrade_only():
    """A POST must not claim a stronger posture than the profile declares.

    Requiring `signed` is a profile decision — reviewable in git — not
    something an HTTP body should be able to assert.
    """
    src = CONFIG_API.read_text(encoding="utf-8")
    seg = src[src.index("_sb = str(body.get"):]
    seg = seg[: seg.index("argv_fn, needs_root")]
    assert '("disabled", "none")' in seg, (
        "only disabled/none may be forwarded; signed and setup must be ignored"
    )
    assert '"signed"' not in seg.replace("STRONGER", ""), (
        "the API must not forward a 'signed' posture from the request body"
    )


# ── the other two panels ───────────────────────────────────────────────────

@pytest.mark.parametrize("name", ["flash", "emulate"])
def test_the_artifact_panels_name_the_distro(name):
    body = PANELS[name].read_text(encoding="utf-8")
    assert "distro_label" in body, (
        f"the {name} panel must name the distro on every artifact row. Both "
        "installer ISOs end in -installer.iso, and mkosi emitted <profile>.raw "
        "for both distros — the rows were indistinguishable."
    )


def test_flash_warns_when_more_than_one_distro_is_present():
    """That is exactly when a mis-pick is possible.

    The list default-selects the NEWEST installer, which need not be the distro
    the operator just built.
    """
    body = FLASH_PANEL.read_text(encoding="utf-8")
    assert "distros are present" in body, (
        "the flash panel must warn when artifacts for more than one distro "
        "exist — writing the wrong one to an internal disk is not recoverable"
    )


# ── emulate must be able to rehearse what you are about to flash ───────────

EMULATE_API = REPO_ROOT / "scripts/operator/emulate-api.py"


def test_emulate_lists_installer_isos_not_only_appliances():
    """The ISO is the artifact actually flashed today, for both distros.

    The panel's stated purpose is "boot a built image in a throwaway QEMU VM
    before flashing". Listing only *.raw meant the main path could not be
    rehearsed at all — and for Ubuntu, where no appliance has ever been built,
    the panel had nothing to show whatsoever (2026-07-30).
    """
    src = EMULATE_API.read_text(encoding="utf-8")
    assert 'output/*.iso' in src, (
        "emulate must list installer ISOs alongside appliance .raw images"
    )


def test_emulate_boots_an_iso_from_the_optical_drive():
    """An ISO attached as a raw virtio disk boots nothing.

    qemu finds no bootable disk and the operator sees a UEFI shell, which reads
    like a broken image rather than a wrong attachment.
    """
    src = EMULATE_API.read_text(encoding="utf-8")
    seg = src[src.index("AN ISO IS NOT A DISK"):]
    seg = seg[: seg.index("vars_file")]
    assert '"-cdrom"' in seg and '"-boot", "d"' in seg, (
        "an .iso must be attached with -cdrom and booted with -boot d"
    )
    assert "if=virtio" in seg, (
        "a .raw appliance must still be attached as a virtio disk"
    )
    assert 'endswith(".iso")' in seg, "the choice must be driven by the extension"
