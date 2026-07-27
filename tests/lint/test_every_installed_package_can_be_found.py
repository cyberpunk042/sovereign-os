"""A package name that resolves to nothing fails the build 25 minutes in.

2026-07-27. The install list grew from 21 to 59 packages in one day. simple-cdd
does not fail fast on a bad name — it builds the mirror, then dies with

    ERROR missing required packages from profile sovereign: ...

after the long download. Every name must therefore resolve to either Debian's
archive or a package this build produces itself.

The locally-produced ones are expected NOT to resolve upstream:
  linux-image-6.12.0 / linux-headers-6.12.0  — the custom znver5 kernel .debs
  sovereign-os-cockpit                        — built by installer-cdd/build.sh
simple-cdd picks these up through local_packages.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PROFILES = REPO_ROOT / "scripts" / "build" / "installer-cdd" / "profiles"
BUILD = REPO_ROOT / "scripts" / "build" / "installer-cdd" / "build.sh"


def install_list(name: str) -> list[str]:
    text = (PROFILES / name).read_text(encoding="utf-8")
    m = re.search(r'^d-i pkgsel/include string ((?:.*\\\n)*.*)$', text, re.M)
    assert m, f"{name} has no pkgsel/include"
    return m.group(1).replace("\\\n", " ").split()


def locally_built() -> set[str]:
    """Names this build stages into simple-cdd's local_packages."""
    body = BUILD.read_text(encoding="utf-8")
    names = set()
    if "sovereign-os-cockpit" in body:
        names.add("sovereign-os-cockpit")
    # the kernel .debs are globbed by version, e.g. linux-image-6.12.0_*.deb
    for m in re.finditer(r"linux-(image|headers)-([0-9][0-9.]*)", body):
        names.add(f"linux-{m.group(1)}-{m.group(2)}")
    return names


@pytest.mark.skipif(shutil.which("apt-cache") is None, reason="no apt-cache")
@pytest.mark.parametrize("name", ("default.preseed", "sovereign.preseed"))
def test_every_package_resolves_somewhere(name: str):
    local = locally_built()
    unresolved = []
    for pkg in install_list(name):
        if pkg in local:
            continue
        if subprocess.run(["apt-cache", "show", pkg],
                          capture_output=True).returncode != 0:
            unresolved.append(pkg)
    assert not unresolved, (
        f"{name}: {unresolved} resolve to no Debian package and are not built "
        "locally. simple-cdd will download the whole mirror before failing."
    )


def test_the_locally_built_names_are_actually_produced():
    """Guard the exemption: if the build stops producing these, the exemption
    would silently hide three genuinely missing packages."""
    local = locally_built()
    assert "sovereign-os-cockpit" in local
    assert any(n.startswith("linux-image-") for n in local), (
        "no custom kernel image name found in build.sh — the exemption list "
        "would be wrong"
    )


@pytest.mark.skipif(shutil.which("apt-cache") is None, reason="no apt-cache")
def test_the_mirror_list_resolves_too():
    """sovereign.packages drives what is MIRRORED; a bad name there fails the
    same way, just earlier."""
    local = locally_built()
    pkgs = set()
    for line in (PROFILES / "sovereign.packages").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            pkgs.update(line.split())
    unresolved = [p for p in sorted(pkgs)
                  if p not in local
                  and subprocess.run(["apt-cache", "show", p],
                                     capture_output=True).returncode != 0]
    assert not unresolved, f"unresolvable in the mirror list: {unresolved}"
