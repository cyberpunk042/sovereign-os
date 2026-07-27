"""SDD-013 must not describe an installer the project no longer builds.

2026-07-27. SDD-013's 2026-07-25 amendment specified the bootable installer as a
"live-build ISO ... guided TUI (scripts/install/installer-tui.sh)". The operator
booted that, rejected it outright, and the code was repointed to a genuine
debian-installer ISO — but the SDD still said TUI.

Design canon that contradicts the code is the most expensive kind of stale doc:
the next session reads it, rebuilds the rejected thing, and repeats the day.
This asserts the SDD names the substrate that actually ships.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SDD = REPO_ROOT / "docs" / "sdd" / "013-installer-experience.md"
ORCHESTRATE = REPO_ROOT / "scripts" / "build" / "orchestrate.sh"


def installer_substrate() -> str:
    """What SOVEREIGN_OS_ARTIFACT=installer actually selects."""
    text = ORCHESTRATE.read_text(encoding="utf-8")
    m = re.search(r"^\s*installer\)\s*SOVEREIGN_OS_SUBSTRATE=([a-z0-9-]+)", text, re.M)
    assert m, "could not read the installer substrate from orchestrate.sh"
    return m.group(1)


def test_the_sdd_names_the_substrate_that_ships():
    sub = installer_substrate()
    body = SDD.read_text(encoding="utf-8")
    assert sub in body, (
        f"ARTIFACT=installer builds `{sub}`, but SDD-013 never mentions it — a "
        "reader would build the superseded artifact"
    )


def test_the_superseded_tui_delivery_is_marked_superseded():
    body = SDD.read_text(encoding="utf-8")
    if "installer-tui.sh" not in body:
        return  # no stale claim to guard
    # Wherever the TUI is described as the installer, a later amendment must
    # explicitly supersede it.
    assert "SUPERSEDED" in body and "2026-07-26" in body, (
        "SDD-013 still presents the whiptail TUI as the bootable installer with "
        "nothing marking it superseded"
    )


def test_it_points_at_the_directive():
    body = SDD.read_text(encoding="utf-8")
    assert "2026-07-26-the-normal-debian-13-installer" in body, (
        "the amendment must cite the operator directive it derives from, so the "
        "verbatim requirement is one click away"
    )
