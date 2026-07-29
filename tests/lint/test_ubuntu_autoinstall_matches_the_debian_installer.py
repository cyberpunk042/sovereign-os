"""The two installers must install the SAME system.

2026-07-28. Ubuntu 26.04 became a build option beside Debian 13. Because Ubuntu
dropped debian-installer at 20.04 and Subiquity does not read preseeds, the two
paths cannot share an answer file: there is a `pkgsel/include` line in
default.preseed and a `packages:` list in autoinstall/user-data, and nothing
structural stops them drifting apart.

This repo has already paid for that exact shape twice:

  * `sovereign.packages` drives what gets MIRRORED onto the CD while
    `pkgsel/include` drives what gets INSTALLED. 37 packages were added to the
    first and never the second, so a clean install booted with no firmware and
    no X driver — zero failed units, dark screen (2026-07-26).

  * bootstrap-host.sh kept calling operator-deps.py with a syntax provision.sh
    had already fixed, and operator-deps.py never picked up the PEP 668 handling
    warp-setup.sh already had (both found 2026-07-28).

So: every package the Debian installer installs must also be installed by the
Ubuntu one, after the documented name mapping in scripts/build/lib/distro.sh —
or appear in EXPECTED_ABSENT below with a reason.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

REPO_ROOT = Path(__file__).resolve().parents[2]
PRESEED = REPO_ROOT / "scripts" / "build" / "installer-cdd" / "profiles" / "default.preseed"
USER_DATA = REPO_ROOT / "scripts" / "build" / "ubuntu-autoinstall" / "autoinstall" / "user-data"
DISTRO_LIB = REPO_ROOT / "scripts" / "build" / "lib" / "distro.sh"

# Packages the Debian installer lists that the Ubuntu one deliberately does not,
# each with the reason it is safe. Anything NOT here is drift.
EXPECTED_ABSENT = {
    # Local .debs, not archive packages. Ubuntu installs them in late-commands
    # with `dpkg -i` from /cdrom/sovereign/pool; Subiquity's `packages:` resolves
    # against the archive and would fail on a name it cannot find.
    "linux-image-6.12.0",
    "linux-headers-6.12.0",
    "sovereign-os-cockpit",
    # Ubuntu 26.04 has no isc-dhcp-client; DHCP is netplan + NetworkManager /
    # systemd-networkd. Listing it would abort an offline install.
    "isc-dhcp-client",
}


def debian_packages() -> set[str]:
    text = PRESEED.read_text(encoding="utf-8")
    m = re.search(r"d-i pkgsel/include string (.+?)(?=\nd-i |\n###|\npopularity)",
                  text, re.S)
    assert m, "could not read pkgsel/include from default.preseed"
    return set(m.group(1).replace("\\\n", " ").split())


def ubuntu_packages() -> set[str]:
    data = yaml.safe_load(USER_DATA.read_text(encoding="utf-8"))
    return set(data["autoinstall"]["packages"])


def map_to_ubuntu(pkgs: set[str]) -> set[str]:
    """Run the real mapping from lib/distro.sh — not a copy of it."""
    r = subprocess.run(
        ["bash", "-c",
         f'export SOVEREIGN_OS_DISTRO=ubuntu; . "{DISTRO_LIB}"; '
         f'echo "{" ".join(sorted(pkgs))}" | distro_map_packages'],
        capture_output=True, text=True, check=True)
    return set(r.stdout.split())


def test_the_ubuntu_installer_installs_everything_the_debian_one_does():
    missing = map_to_ubuntu(debian_packages()) - ubuntu_packages() - EXPECTED_ABSENT
    assert not missing, (
        f"the Ubuntu autoinstall omits {sorted(missing)}, which the Debian "
        "installer installs. Add them to autoinstall/user-data's `packages:`, "
        "or to EXPECTED_ABSENT with the reason they are safe to skip. A silently "
        "shorter list is how an install ends up with no firmware and a dark screen."
    )


def test_no_debian_only_package_names_leak_into_the_ubuntu_list():
    """A Debian name in the Ubuntu list is a hard failure at install time.

    Subiquity resolves `packages:` against the archive; an unknown name aborts
    the run — after partitioning, which is the worst moment to find out.
    """
    debian_only = {"task-kde-desktop", "firefox-esr", "isc-dhcp-client",
                   "firmware-amd-graphics", "firmware-nvidia-graphics",
                   "firmware-linux-free", "firmware-misc-nonfree"}
    leaked = debian_only & ubuntu_packages()
    assert not leaked, (
        f"{sorted(leaked)} are Debian package names with no Ubuntu equivalent; "
        "map them in scripts/build/lib/distro.sh instead"
    )


def test_the_mapping_is_declared_in_the_distro_lib_not_inline():
    """The translation must live in ONE place both installers can read."""
    lib = DISTRO_LIB.read_text(encoding="utf-8")
    for fn in ("distro_desktop_task", "distro_browser",
               "distro_firmware_packages", "distro_map_packages"):
        assert f"{fn}()" in lib, f"lib/distro.sh must define {fn}()"


def test_the_ubuntu_installer_keeps_the_desktop_and_the_firmware():
    """The two packages whose absence produced the 2026-07-26 dark screen."""
    ubu = ubuntu_packages()
    assert "kubuntu-desktop" in ubu, "the KDE desktop must be installed"
    assert "linux-firmware" in ubu, (
        "firmware must be installed — a desktop with no firmware is the "
        "2026-07-26 dark screen"
    )
