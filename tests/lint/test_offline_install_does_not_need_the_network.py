"""The ISO installs offline — so nothing in the install may require a network.

2026-07-27. The d-i profile installs every package from the CD and deliberately
configures NO network mirror (apt-setup/use_mirror=false). That is the whole
point of a 1.2 GB installer image.

pkg_ensure tried apt FIRST and only fell back to dpkg when apt-get was absent:

    if command -v apt-get; then apt-get install -y "$@"; return $?; fi

On an offline machine that fails to locate packages that are ALREADY INSTALLED
by pkgsel — and the failure takes the whole dashboards deploy with it, so the
cockpit never lands on precisely the offline install this ISO exists for.

Asking dpkg first makes the common case a no-op needing no network. apt is
called only for genuinely missing packages, where needing a network is honest.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DASH = REPO_ROOT / "scripts" / "install" / "install-gui-dashboards.sh"
PRESEED = (REPO_ROOT / "scripts" / "build" / "installer-cdd"
           / "profiles" / "default.preseed")


def pkg_ensure_body() -> str:
    body = DASH.read_text(encoding="utf-8")
    start = body.index("pkg_ensure() {")
    return body[start:body.index("\n}\n", start)]


def test_dpkg_is_consulted_before_apt():
    code = "\n".join(l for l in pkg_ensure_body().splitlines()
                     if not l.lstrip().startswith("#"))
    dpkg = code.index("dpkg-query")
    apt = code.index("apt-get install")
    assert dpkg < apt, (
        "pkg_ensure must ask dpkg what is missing BEFORE calling apt; on an "
        "offline install apt cannot locate already-installed packages and the "
        "whole deploy fails"
    )


def test_apt_is_called_only_with_the_missing_set():
    code = pkg_ensure_body()
    assert 'apt-get install -y --no-install-recommends "${missing[@]}"' in code, (
        'apt must receive only "${missing[@]}", not "$@" — re-requesting '
        "installed packages is what needs a mirror that is not there"
    )


def test_the_profile_really_is_offline():
    """Guard the premise: if a mirror is ever configured, revisit this."""
    text = PRESEED.read_text(encoding="utf-8")
    assert re.search(r"^d-i apt-setup/use_mirror boolean false", text, re.M), (
        "this lint assumes an offline install; the preseed no longer says so"
    )
