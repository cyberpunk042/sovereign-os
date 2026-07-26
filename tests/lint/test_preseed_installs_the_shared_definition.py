"""pkgsel/include is what INSTALLS. sovereign.packages only MIRRORS.

2026-07-26. A clean install booted with zero failed units, a completed boot
(1m49), and a dark screen. `install logs --from` showed no Xorg log at all —
X was never even started — and no first-boot markers.

The cause was a FOURTH package list. sovereign.packages drives what lands in
the CD's mirror; profiles/*.preseed's `pkgsel/include` drives what d-i actually
installs. 37 packages had been added to the mirror list and never installed:
no firmware-*, no xserver-xorg-video-fbdev/vesa, no console tools. The mirror
was perfect and the installed system had none of it.

The earlier lint checked sovereign.packages, so it passed while the installed
system stayed broken. This one checks the file that installs.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PROFILES = REPO_ROOT / "scripts" / "build" / "installer-cdd" / "profiles"
PRESEEDS = ("default.preseed", "sovereign.preseed")


def shared_definition() -> set[str]:
    out = subprocess.run(
        ["bash", "-c",
         '. scripts/install/lib/installed-system.sh; '
         'echo "${SOVEREIGN_OS_BASE_PACKAGES} ${SOVEREIGN_OS_WORKSTATION_PACKAGES}"'],
        capture_output=True, text=True, check=True, cwd=REPO_ROOT).stdout
    return {p for p in out.split() if p}


def pkgsel_include(name: str) -> list[str]:
    text = (PROFILES / name).read_text(encoding="utf-8")
    m = re.search(r'^d-i pkgsel/include string ((?:.*\\\n)*.*)$', text, re.M)
    assert m, f"{name} has no pkgsel/include — nothing would be installed"
    return m.group(1).replace("\\\n", " ").split()


@pytest.mark.parametrize("name", PRESEEDS)
def test_the_install_list_covers_the_shared_definition(name: str):
    missing = sorted(shared_definition() - set(pkgsel_include(name)))
    assert not missing, (
        f"{name}'s pkgsel/include omits {len(missing)} package(s) from "
        f"installed-system.sh: {missing}. These are MIRRORED but never "
        "INSTALLED — the installed system silently lacks them."
    )


@pytest.mark.parametrize("name", PRESEEDS)
def test_every_entry_is_a_valid_package_name(name: str):
    """Line-wrapping this list once split 'prometheus-node-exporter' in two.

    A hyphen is legal in a package name, so a naive wrap produces 'prometheus-'
    and 'node-exporter' — two packages that do not exist. d-i would fail to
    install them (caught pre-flight, 2026-07-26).
    """
    bad = [p for p in pkgsel_include(name)
           if not re.fullmatch(r"[a-z0-9][a-z0-9.+-]*", p)]
    assert not bad, f"{name}: malformed package name(s) {bad}"


@pytest.mark.parametrize("name", PRESEEDS)
def test_the_x_driver_and_firmware_are_installed_not_just_mirrored(name: str):
    pkgs = set(pkgsel_include(name))
    for needed in ("xserver-xorg-video-fbdev", "firmware-amd-graphics"):
        assert needed in pkgs, (
            f"{name}: {needed} is not in pkgsel/include. Being in the CD mirror "
            "does not install it; this is exactly how the dark-screen install "
            "passed every earlier check."
        )
