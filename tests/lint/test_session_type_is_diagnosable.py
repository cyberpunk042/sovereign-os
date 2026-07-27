"""A Wayland session under nomodeset loops at the greeter — say so, don't guess.

2026-07-27. KWin's Wayland session requires a DRM device. nomodeset removes
exactly that, so a Wayland login cannot start: the greeter accepts the password
and returns to the greeter. X11 on fbdev works, which is what the operator's
machine runs.

Deliberately NOT fixed by writing sddm configuration. The proven machine — same
hardware, same nomodeset, working desktop — carries NO sddm config at all and
lands on X11. Adding config would deviate from the only setup known to work
here, on a guess about sddm's default-session semantics. That is the shape of
mistake that cost a day already.

So this records the facts instead: which sessions are offered, whether nomodeset
is on, what sddm config exists, and what it last chose. A login loop then takes
one look rather than another round of bisecting.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VERIFY = REPO_ROOT / "scripts" / "install" / "verify-installed-system.sh"
DASH = REPO_ROOT / "scripts" / "install" / "install-gui-dashboards.sh"


def test_the_selfcheck_reports_both_session_types():
    body = VERIFY.read_text(encoding="utf-8")
    assert "xsessions" in body and "wayland-sessions" in body, (
        "the report must list both session types; which one the greeter picks "
        "decides whether the login works at all under nomodeset"
    )


def test_it_warns_about_the_wayland_nomodeset_combination():
    body = VERIFY.read_text(encoding="utf-8")
    assert "nomodeset" in body and "Wayland" in body, (
        "a Wayland session offered alongside nomodeset must be called out — the "
        "symptom (greeter loops back) looks nothing like the cause"
    )


def test_nothing_pins_the_session_behind_the_operators_back():
    """The proven configuration is 'no sddm config'. Keep it that way.

    If a future change DOES pin the session, it should be a deliberate,
    evidence-backed decision — not something that drifts in.
    """
    for rel in (DASH, REPO_ROOT / "scripts" / "install" / "install-sovereign-root.sh"):
        code = "\n".join(l for l in rel.read_text(encoding="utf-8").splitlines()
                         if not l.lstrip().startswith("#"))
        assert "sddm.conf" not in code, (
            f"{rel.name} writes sddm configuration; the machine that works has "
            "none, so this needs verifying on hardware before it ships"
        )
