"""Each install path must have exactly one thing owning the interface.

2026-07-27. The two paths use different stacks, each internally consistent:

  * direct     -> writes /etc/systemd/network/20-wired.network and enables
                  systemd-networkd + systemd-resolved; does NOT install
                  network-manager.
  * installer  -> installs network-manager (pkgsel/include); d-i's netcfg may
                  also write an /etc/network/interfaces stanza.

Nothing enforces that. Adding network-manager to the shared definition — an
obvious "the desktop needs Wi-Fi" change — would put NetworkManager and
systemd-networkd on the same interface on the direct path. Two managers is not
twice the networking; it is a race, and the loser's config is silently ignored.

DNS has already gone wrong here once: systemd-resolved was disabled with no
/etc/resolv.conf, and three separate "downloads are broken" symptoms turned out
to be one missing resolver.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DIRECT = REPO_ROOT / "scripts" / "install" / "install-sovereign-root.sh"


def shared_packages() -> set[str]:
    out = subprocess.run(
        ["bash", "-c", ". scripts/install/lib/installed-system.sh; "
                       "sovereign_os_installed_packages"],
        capture_output=True, text=True, check=True, cwd=REPO_ROOT).stdout
    return set(out.split())


def test_the_direct_path_does_not_run_two_managers():
    body = DIRECT.read_text(encoding="utf-8")
    enables_networkd = "systemctl enable systemd-networkd" in body
    if not enables_networkd:
        return
    assert "network-manager" not in shared_packages(), (
        "the direct path enables systemd-networkd, and network-manager is in "
        "the shared package set — both would claim the same interface. Pick "
        "one: either drop network-manager here, or stop enabling networkd and "
        "let NM own it."
    )


def test_the_direct_path_configures_dns_alongside_the_network():
    """networkd alone leaves glibc with no resolver.

    That exact gap produced three unrelated-looking download failures
    (2026-07-26).
    """
    body = DIRECT.read_text(encoding="utf-8")
    if "systemctl enable systemd-networkd" in body:
        assert "systemd-resolved" in body, (
            "enabling networkd without resolved leaves the system with no DNS"
        )


def test_the_selfcheck_reports_who_owns_the_interface():
    body = (REPO_ROOT / "scripts" / "install" / "verify-installed-system.sh").read_text(encoding="utf-8")
    assert "/etc/network/interfaces" in body and "NetworkManager" in body, (
        "the install report must say which stack owns the interface — an "
        "ifupdown stanza makes NetworkManager mark the device unmanaged, so "
        "the desktop cannot switch networks or join Wi-Fi"
    )
