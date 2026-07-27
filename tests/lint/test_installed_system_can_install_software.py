"""An offline install must not produce a permanently offline system.

2026-07-27. The d-i profile installs entirely from the CD mirror, so the
preseed sets:

    apt-setup/use_mirror        false
    apt-setup/cdrom/set-first   false
    apt-setup/services-select   (empty)

That is right DURING the install — every package is on the disc and there is no
network guarantee. But it leaves the installed system with no usable apt
sources: `apt install` fails and no security update ever arrives. The operator
hit "a lot was missing" and then could not install the missing pieces either.

write-apt-sources.sh runs at the end of the install and writes network sources
for afterwards. It does NOT run `apt-get update` — that would require the
network the install was built not to need.
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
WRITER = REPO_ROOT / "scripts" / "install" / "write-apt-sources.sh"
PROFILES = REPO_ROOT / "scripts" / "build" / "installer-cdd" / "profiles"
PRESEEDS = ("default.preseed", "sovereign.preseed")


def test_the_writer_exists_and_is_executable():
    assert WRITER.exists()
    assert WRITER.stat().st_mode & 0o111, (
        "a missing exec bit silently skipped a whole install stage once already"
    )


@pytest.mark.parametrize("name", PRESEEDS)
def test_the_installer_runs_it(name: str):
    text = (PROFILES / name).read_text(encoding="utf-8")
    assert "write-apt-sources.sh" in text, (
        f"{name} leaves the installed system unable to install software"
    )


def test_it_does_not_require_network_during_the_install():
    # Read CODE, not comments — the rationale below the shebang names the very
    # command it explains not running. Four lints this session tripped on their
    # own prose.
    body = "\n".join(l for l in WRITER.read_text(encoding="utf-8").splitlines()
                      if not l.lstrip().startswith("#"))
    assert "apt-get update" not in body and "apt update" not in body, (
        "the install is deliberately offline; refreshing indexes here would "
        "make it depend on a network it was built not to need"
    )


def test_it_never_clobbers_existing_sources():
    body = WRITER.read_text(encoding="utf-8")
    assert "already has network sources" in body, (
        "it must leave an operator's own sources.list alone"
    )


def test_non_free_firmware_is_among_the_components():
    """firmware-amd-graphics lives there; without it a firmware fix is unreachable."""
    assert "non-free-firmware" in WRITER.read_text(encoding="utf-8")


def test_the_selfcheck_reports_whether_apt_works():
    body = (REPO_ROOT / "scripts" / "install" / "verify-installed-system.sh").read_text(encoding="utf-8")
    assert "apt sources" in body, (
        "the install report must say whether the system can install software"
    )
