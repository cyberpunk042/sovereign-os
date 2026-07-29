"""Whatever the dashboards deploy needs, the installer must already have put there.

2026-07-28, recovered from the failed disk's own log. The cockpit/dashboards
deploy died on a clean install:

    ━━━ 1/5 frontend stacks (install: kde-plasma · default: kde-plasma)
      stage: kde plasma desktop
      installing 1 missing package(s): xdg-utils
    E: Package 'xdg-utils' has no installation candidate
    FAILED (rc=100)

`install-gui-dashboards.sh` pkg_ensure's `xdg-utils` for EVERY frontend. It was
in neither `sovereign.packages` (what gets MIRRORED onto the CD) nor
`pkgsel/include` (what gets INSTALLED), and the install is deliberately offline
with no network mirror — so apt had no candidate, `set -euo pipefail` aborted,
and `late_command`'s `|| true` swallowed the whole thing. The operator got no
cockpit, no dashboards, and no message.

This is the third instance of one shape in this repo: two lists that must agree
and nothing making them. The mirror-vs-install split already shipped 37 packages
to one and not the other (2026-07-26). Here a package was in NEITHER, while a
script that runs during the install needed it.

Rule: every package the ACTIVE frontend's deploy would install must already be
installable offline — i.e. named in the installer's own package list.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

REPO_ROOT = Path(__file__).resolve().parents[2]
DASH = REPO_ROOT / "scripts" / "install" / "install-gui-dashboards.sh"
PRESEED = REPO_ROOT / "scripts" / "build" / "installer-cdd" / "profiles" / "default.preseed"
MIRROR = REPO_ROOT / "scripts" / "build" / "installer-cdd" / "profiles" / "sovereign.packages"
UBUNTU = REPO_ROOT / "scripts" / "build" / "ubuntu-autoinstall" / "autoinstall" / "user-data"

# The frontend sain-01 actually ships (SOVEREIGN_OS_FRONTEND=kde-plasma).
ACTIVE_FRONTEND_PACKAGES = {"kde-plasma-desktop", "sddm", "firefox-esr", "xdg-utils"}

# A metapackage in the installer list that pulls a package the deploy asks for.
# Keep this SHORT and justified — every entry is a place the check stops being
# literal and starts trusting a dependency chain.
PROVIDED_BY = {
    "kde-plasma-desktop": "task-kde-desktop",   # the Debian KDE task pulls it
}

# Ubuntu spellings, per scripts/build/lib/distro.sh.
UBUNTU_RENAMES = {
    "task-kde-desktop": "kubuntu-desktop",
    "kde-plasma-desktop": "kubuntu-desktop",
    "firefox-esr": "firefox",
}


def pkg_ensure_calls() -> dict[int, set[str]]:
    """Every `pkg_ensure a b c` in the deploy, by line number."""
    out = {}
    for i, line in enumerate(DASH.read_text(encoding="utf-8").splitlines(), 1):
        m = re.match(r"\s*pkg_ensure\s+([a-z0-9 ._+-]+)", line)
        if m:
            out[i] = {p for p in m.group(1).split() if not p.startswith("-")}
    return out


def debian_install_list() -> set[str]:
    text = PRESEED.read_text(encoding="utf-8")
    m = re.search(r"d-i pkgsel/include string (.+?)(?=\nd-i |\n###|\npopularity)", text, re.S)
    assert m, "could not read pkgsel/include from default.preseed"
    return set(m.group(1).replace("\\\n", " ").split())


def debian_mirror_list() -> set[str]:
    return {l.strip() for l in MIRROR.read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.strip().startswith("#")}


def ubuntu_install_list() -> set[str]:
    return set(yaml.safe_load(UBUNTU.read_text(encoding="utf-8"))["autoinstall"]["packages"])


def _satisfied(pkg: str, have: set[str]) -> bool:
    return pkg in have or PROVIDED_BY.get(pkg, "\0") in have


def test_the_active_frontend_can_be_deployed_offline_on_debian():
    missing = {p for p in ACTIVE_FRONTEND_PACKAGES
               if not _satisfied(p, debian_install_list())}
    assert not missing, (
        f"install-gui-dashboards.sh will pkg_ensure {sorted(missing)}, but the "
        f"Debian installer does not install {'it' if len(missing) == 1 else 'them'}. "
        "The install is offline with no mirror, so apt has no candidate, the "
        "deploy exits non-zero and late_command swallows it — no cockpit, no "
        "message. Exactly how xdg-utils killed the 2026-07-28 install."
    )


def test_the_active_frontend_is_also_on_the_cd_mirror():
    """pkgsel/include only works if the package is ON the disc.

    The mirror list and the install list are different files and have drifted
    before (37 packages, 2026-07-26).
    """
    have = debian_mirror_list()
    missing = {p for p in ACTIVE_FRONTEND_PACKAGES
               if not (p in have or PROVIDED_BY.get(p, "\0") in have)}
    assert not missing, (
        f"{sorted(missing)} must be MIRRORED onto the CD (sovereign.packages) or "
        "the offline install cannot install them no matter what pkgsel says"
    )


def test_the_active_frontend_can_be_deployed_offline_on_ubuntu():
    have = ubuntu_install_list()
    missing = set()
    for p in ACTIVE_FRONTEND_PACKAGES:
        cands = {p, UBUNTU_RENAMES.get(p, p),
                 UBUNTU_RENAMES.get(PROVIDED_BY.get(p, "\0"), "\0"),
                 PROVIDED_BY.get(p, "\0")}
        if not (cands & have):
            missing.add(p)
    assert not missing, (
        f"the Ubuntu autoinstall does not install {sorted(missing)}, which the "
        "dashboards deploy will pkg_ensure — the same offline dead-end as Debian"
    )


def test_xdg_utils_specifically_is_never_dropped_again():
    """Named, because it is needed by EVERY frontend and cost a whole install."""
    for name, have in (("debian pkgsel/include", debian_install_list()),
                       ("debian CD mirror", debian_mirror_list()),
                       ("ubuntu autoinstall", ubuntu_install_list())):
        assert "xdg-utils" in have, (
            f"xdg-utils missing from {name}. Every frontend in "
            "install-gui-dashboards.sh pkg_ensure's it; without it the dashboards "
            "deploy fails offline with 'no installation candidate' (2026-07-28)."
        )


def test_every_frontend_shares_the_same_universal_packages():
    """A package needed by ALL frontends must be treated as a base requirement.

    xdg-utils and firefox-esr appear in every pkg_ensure call. Anything with
    that property belongs in the installer list regardless of which frontend a
    build selects, because the frontend is switchable at runtime (SDD-704).
    """
    calls = pkg_ensure_calls()
    assert calls, "no pkg_ensure calls found — has the deploy been restructured?"
    universal = set.intersection(*calls.values())
    have = debian_install_list()
    missing = {p for p in universal if not _satisfied(p, have)}
    assert not missing, (
        f"{sorted(missing)} are required by EVERY frontend "
        f"({len(calls)} pkg_ensure sites) but the installer does not install them. "
        "A switchable frontend (SDD-704) means any of these can be selected later."
    )
