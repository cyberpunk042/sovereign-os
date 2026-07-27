"""The installed system must boot with nomodeset, or it has no display at all.

2026-07-26. A clean install: every package present, sddm registered as
display-manager, /opt/sovereign-os in place, zero failed units, boot completed
in 1m47 — and a dark screen with no Xorg log.

    working system:  root=UUID=... ro nomodeset   -> /dev/fb0 = "EFI VGA"
    installed system: root=UUID=... ro quiet      -> no framebuffer at all

Without nomodeset, nouveau attempts KMS on the two Blackwell cards, fails with
"unknown chipset (1b2000a1)", and no EFI framebuffer is established. No
/dev/fb0 means the X server has no device to open, so sddm never starts a
session and never writes a log. The absence of an Xorg log was read for several
rounds as "X failed"; it actually meant "X was never able to begin".

installed-system.sh has defaulted SOVEREIGN_OS_KERNEL_CMDLINE to nomodeset all
along. The debian-installer path simply never applied it — d-i needs
`debian-installer/add-kernel-opts` to put options on the installed system's
kernel line; nothing else in a preseed does that.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PROFILES = REPO_ROOT / "scripts" / "build" / "installer-cdd" / "profiles"
INSTALLED = REPO_ROOT / "scripts" / "install" / "lib" / "installed-system.sh"
PRESEEDS = ("default.preseed", "sovereign.preseed")


def shared_cmdline() -> str:
    text = INSTALLED.read_text(encoding="utf-8")
    # `:?-` so this matches BOTH ${VAR:-d} and ${VAR-d}. installed-system.sh
    # moved to the colon-less form so an explicitly EMPTY value survives
    # (blacklist nothing / no extra cmdline); three lints parsed the old
    # spelling and broke (2026-07-27).
    m = re.search(r'SOVEREIGN_OS_KERNEL_CMDLINE="\$\{SOVEREIGN_OS_KERNEL_CMDLINE:?-([^}]*)\}"', text)
    assert m, "installed-system.sh must define the installed kernel cmdline"
    return m.group(1)


def test_the_shared_definition_still_asks_for_nomodeset():
    assert "nomodeset" in shared_cmdline(), (
        "no GPU driver binds on this hardware; without nomodeset there is no "
        "EFI framebuffer and therefore no display at all"
    )


@pytest.mark.parametrize("name", PRESEEDS)
def test_the_installer_applies_it_to_the_installed_system(name: str):
    text = (PROFILES / name).read_text(encoding="utf-8")
    m = re.search(r'^d-i debian-installer/add-kernel-opts string (.+)$', text, re.M)
    assert m, (
        f"{name}: no add-kernel-opts. A preseed cannot set the installed "
        "system's kernel cmdline any other way, so the system boots with "
        "d-i's defaults and loses its framebuffer."
    )
    for opt in shared_cmdline().split():
        assert opt in m.group(1), (
            f"{name}: add-kernel-opts is missing {opt!r}, which "
            "installed-system.sh requires for the installed system"
        )


def test_the_direct_path_verifies_the_cmdline_reached_grub_cfg():
    """Declaring the cmdline is not applying it.

    The installed system had every package, a registered display-manager and
    zero failed units — and booted without nomodeset, so it had no framebuffer
    and X could never start. The verifier checked the X DRIVER but not whether
    the option that makes that driver usable ever reached grub.cfg
    (2026-07-26).
    """
    text = (REPO_ROOT / "scripts" / "install" / "install-sovereign-root.sh").read_text(encoding="utf-8")
    assert "boot/grub/grub.cfg" in text, (
        "the verifier must read the GENERATED grub.cfg — /etc/default/grub only "
        "says what was requested, not what a kernel will actually receive"
    )
    v = text[text.index("sovereign_verify_install()"):]
    assert "SOVEREIGN_OS_KERNEL_CMDLINE" in v, (
        "the verifier must confirm every declared cmdline option is present"
    )
    assert "SOVEREIGN_OS_MODULE_BLACKLIST" in v, (
        "the verifier must confirm the blacklist reached the target"
    )
