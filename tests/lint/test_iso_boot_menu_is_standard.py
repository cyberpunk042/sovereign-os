"""The ISO must present Debian's own boot menu, and its default must exist.

2026-07-27, per the standing directive: "it should be the normal debian 13
installer". The build appends to the ISO's grub.cfg:

    set timeout=10
    set default='Install'

That is a NAME reference. GRUB resolves it against the menu entries Debian
shipped; if the entry is ever renamed, `set default` silently resolves to
nothing and GRUB falls back to entry 0 — a different installer than intended,
with no error anywhere. Today the entries are:

    'Graphical install'  'Install'  'Install with speech synthesis'

so the reference holds, and the menu is Debian's own — which is the point.

Text `Install` is chosen over `Graphical install` deliberately: no GPU driver
binds on this hardware, and the text installer cannot be affected by that.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
BUILD = REPO_ROOT / "scripts" / "build" / "installer-cdd" / "build.sh"
ISO = REPO_ROOT / "build" / "sain-01" / "output" / "sain-01-installer.iso"


def default_entry() -> str:
    m = re.search(r"set default='([^']+)'", BUILD.read_text(encoding="utf-8"))
    assert m, "the build no longer sets a default menu entry"
    return m.group(1)


def test_the_build_does_not_replace_debians_menu():
    """It must APPEND to grub.cfg, not author its own menu."""
    body = BUILD.read_text(encoding="utf-8")
    assert "grub.cfg.orig" in body and "cat " in body, (
        "the boot menu must be Debian's own with settings appended; authoring a "
        "replacement menu is how 'standard installer' stops being standard"
    )


@pytest.mark.skipif(not ISO.exists(), reason="no ISO built yet")
@pytest.mark.skipif(shutil.which("xorriso") is None, reason="xorriso not installed")
def test_the_default_entry_exists_on_the_iso(tmp_path: Path):
    cfg = tmp_path / "grub.cfg"
    subprocess.run(["xorriso", "-osirrox", "on", "-indev", str(ISO),
                    "-cpx", "/boot/grub/grub.cfg", str(cfg)],
                   capture_output=True, check=False)
    if not cfg.exists():
        pytest.skip("could not extract grub.cfg from the ISO")
    entries = re.findall(r"^menuentry\s+(?:--\S+\s+)*'([^']+)'", cfg.read_text(encoding="utf-8"), re.M)
    assert entries, "no menu entries found on the ISO"
    want = default_entry()
    assert want in entries, (
        f"the build sets default={want!r} but the ISO's entries are {entries}. "
        "GRUB would silently fall back to entry 0 — a different installer than "
        "intended, with no error."
    )


@pytest.mark.skipif(not ISO.exists(), reason="no ISO built yet")
@pytest.mark.skipif(shutil.which("xorriso") is None, reason="xorriso not installed")
def test_the_menu_is_recognisably_debians(tmp_path: Path):
    cfg = tmp_path / "grub.cfg"
    subprocess.run(["xorriso", "-osirrox", "on", "-indev", str(ISO),
                    "-cpx", "/boot/grub/grub.cfg", str(cfg)],
                   capture_output=True, check=False)
    if not cfg.exists():
        pytest.skip("could not extract grub.cfg from the ISO")
    text = cfg.read_text(encoding="utf-8")
    for expected in ("Graphical install", "Install"):
        assert expected in text, (
            f"{expected!r} missing — this is no longer Debian's installer menu"
        )
