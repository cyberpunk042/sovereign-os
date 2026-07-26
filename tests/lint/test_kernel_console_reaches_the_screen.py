"""A profile that sets console= must give /dev/console to the SCREEN.

Operator, 2026-07-26: the flashed NVMe booted to "a blinking underscore with a
black screen, stuck there into infinity" — three times, across three rebuilds.

The box was booting perfectly the entire time. sain-01's kernel cmdline carried
`console=ttyS0` and nothing else. The kernel hands /dev/console to the LAST
console= listed, so every kernel message, the boot splash, and every getty went
to a serial port with no cable attached. The monitor kept the bootloader's
leftover cursor forever.

Why it survived so long: step 09's QEMU smoke test runs `-serial mon:stdio`, and
so did the diagnostic boots — i.e. the verification watched the ONE output path
this flag redirects to, and reported a healthy boot to a login prompt every time.
A test that reads only the redirected console can never see this class of bug.

The rule: `console=` is fine (a serial console is genuinely useful on hardware),
but tty0 must be listed LAST so the physical display owns /dev/console. Every
console= listed still receives kernel messages, so nothing is lost.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
PROFILES = sorted((REPO_ROOT / "profiles").glob("*.yaml"))


def _console_args(profile: Path) -> list[str]:
    try:
        data = yaml.safe_load(profile.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return []
    cmdline = (data.get("kernel") or {}).get("cmdline") or {}
    args: list[str] = []
    for key in ("base", "vfio", "extra"):
        for item in (cmdline.get(key) or []):
            args.append(str(item))
    return [a for a in args if a.startswith("console=")]


def test_there_are_profiles_to_check():
    assert PROFILES, "no profiles found — this lint would silently pass"


@pytest.mark.parametrize("profile", PROFILES, ids=lambda p: p.name)
def test_last_console_is_the_screen(profile: Path):
    consoles = _console_args(profile)
    if not consoles:
        return  # no console= at all → kernel defaults to tty0. Correct.
    last = consoles[-1]
    assert last == "console=tty0", (
        f"{profile.name}: the LAST console= is {last!r}, so /dev/console — the "
        "login prompt and every kernel message — goes there instead of the "
        "physical display. On hardware with no serial cable that is a black "
        "screen with a frozen cursor and no way to tell the box is running. "
        f"Order them {consoles[:-1] + ['console=tty0']} instead."
    )


@pytest.mark.parametrize("profile", PROFILES, ids=lambda p: p.name)
def test_serial_console_is_not_silently_dropped(profile: Path):
    """Fixing the screen must not cost the serial console.

    The serial getty is what gives the QEMU smoke test a real userspace marker,
    and what gives an operator a console on headless hardware. Both consoles
    receive kernel messages, so keeping ttyS0 alongside tty0 is free.
    """
    consoles = _console_args(profile)
    if "console=tty0" in consoles and len(consoles) == 1:
        pytest.skip(f"{profile.name} has no serial console to preserve")
    if consoles:
        assert any(c.startswith("console=ttyS") for c in consoles), (
            f"{profile.name}: the serial console was dropped rather than reordered"
        )
