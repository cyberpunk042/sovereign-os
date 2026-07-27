"""An install can produce Debian + KDE and no sovereign-os at all.

2026-07-26. install-gui-dashboards.sh deploys the app tree to
/usr/local/lib/sovereign-os and enables the dashboard services that serve the
hub. On the installer path the cockpit postinst runs it behind `|| true`, so a
total failure there is invisible: the install still succeeds, the desktop comes
up, and none of sovereign-os is present.

That matters more than it sounds: 68 units ExecStart from that path and 67 of
them carry Restart=. A missing app tree is not "no cockpit" — it is dozens of
services failing and restarting forever.

Both paths must therefore REPORT whether sovereign-os itself landed:
  * direct    -> sovereign_verify_install (fails the install)
  * installer -> verify-installed-system.sh (writes evidence; never fails)
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DIRECT = REPO_ROOT / "scripts" / "install" / "install-sovereign-root.sh"
INSTALLER = REPO_ROOT / "scripts" / "install" / "verify-installed-system.sh"
LIB = "/usr/local/lib/sovereign-os"


def test_the_direct_verifier_checks_the_app_tree():
    body = DIRECT.read_text(encoding="utf-8")
    verifier = body[body.index("sovereign_verify_install()"):body.index("\n}\n", body.index("sovereign_verify_install()"))]
    assert LIB in verifier, (
        f"the verifier must check {LIB}; without it an install passes with a "
        "desktop and no sovereign-os on the disk"
    )
    assert "/lib/systemd/system/" in verifier, (
        "it must also confirm the units are where systemd can find them"
    )


def test_the_installer_selfcheck_reports_the_app_tree():
    body = INSTALLER.read_text(encoding="utf-8")
    assert LIB in body, f"the installer self-check must report on {LIB}"
    assert "units present" in body and "units enabled" in body, (
        "it must distinguish PRESENT from ENABLED — presence is not activation, "
        "and enabling the wrong set is what hung a boot"
    )


def test_the_selfcheck_still_never_fails_the_install():
    """d-i has already partitioned by the time this runs."""
    assert INSTALLER.read_text(encoding="utf-8").rstrip().endswith("exit 0")


def test_the_verifier_checks_are_numbered_in_order():
    """Checks are read as a sequence by whoever debugs an install.

    An inserted block landed out of order once (2026-07-26).
    """
    import re
    nums = [int(m.group(1)) for m in
            re.finditer(r"^  # (\d+)\. ", DIRECT.read_text(encoding="utf-8"), re.M)]
    assert nums == sorted(nums), f"verifier checks are out of order: {nums}"
