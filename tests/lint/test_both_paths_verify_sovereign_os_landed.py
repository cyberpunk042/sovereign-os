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


def test_the_dashboards_outcome_is_recorded_not_swallowed():
    """It cannot abort the install — so it must leave evidence.

    Three failure modes were silent: the script absent, the script not
    executable ([ -x ] false -> skipped, which killed this whole stage once
    before), and the script failing behind `|| true`. Each produced an install
    that "succeeded" with no sovereign-os on it (2026-07-27).
    """
    build = (REPO_ROOT / "scripts" / "build" / "installer-cdd" / "build.sh").read_text(encoding="utf-8")
    post = build[build.index("DEBIAN/postinst"):build.index("\nPOSTINST")]
    assert "dashboards-install.status" in post, (
        "the postinst must record whether the dashboards deploy succeeded"
    )
    for mode in ("MISSING", "NOT EXECUTABLE", "FAILED"):
        assert mode in post, f"the {mode} case is still silent"


def test_the_postinst_cannot_abort_the_install():
    """A failing postinst makes dpkg fail the package and d-i abort the run.

    An unguarded `mkdir -p /var/log/sovereign-os` under `set -e` did exactly
    that — caught by the execution test before it shipped.
    """
    build = (REPO_ROOT / "scripts" / "build" / "installer-cdd" / "build.sh").read_text(encoding="utf-8")
    post = build[build.index("DEBIAN/postinst"):build.index("\nPOSTINST")]
    for line in post.splitlines():
        s = line.strip()
        writes = s.startswith("mkdir ") or (s.startswith("echo ") and ">" in s)
        if writes:
            assert "|| true" in s or "2>/dev/null" in s, (
                f"unguarded write in the postinst would abort the install: {s!r}"
            )


def test_the_report_tells_the_operator_how_to_fix_it():
    """First-time success matters more than a diagnosis nobody can act on."""
    body = (REPO_ROOT / "scripts" / "install" / "verify-installed-system.sh").read_text(encoding="utf-8")
    assert "install-gui-dashboards.sh" in body and "fix:" in body, (
        "when the deploy failed, the report must give the exact command to "
        "re-run rather than leave the operator to reconstruct it"
    )
