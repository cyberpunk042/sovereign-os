"""/etc/skel reaches nobody who already exists.

2026-07-27. install-gui-dashboards.sh installed the hub launcher into
/etc/skel/.config/autostart and /etc/skel/Desktop only. skel is copied into a
home at CREATION time — so on the debian-installer path, where d-i creates the
operator's account during pkgsel and this script runs afterwards from
late_command, the account received neither. The hub ran on 127.0.0.1:8100 and
nothing on the desktop opened it or pointed at it.

An OS whose cockpit is running but invisible has not worked on the first try.

The seeding loop must skip root, `nobody`, and service accounts with a nologin
shell — writing a desktop autostart entry into /root or /nonexistent is at best
noise and at worst a permissions mess.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DASH = REPO_ROOT / "scripts" / "install" / "install-gui-dashboards.sh"


def test_existing_accounts_are_seeded_not_only_skel():
    body = DASH.read_text(encoding="utf-8")
    code = "\n".join(l for l in body.splitlines() if not l.lstrip().startswith("#"))
    assert "/etc/passwd" in code, (
        "the launcher must reach accounts that ALREADY exist; /etc/skel only "
        "covers users created afterwards, and d-i creates the operator's "
        "account before this script runs"
    )
    assert "autostart" in code and "Desktop" in code


def test_it_skips_root_and_service_accounts():
    code = "\n".join(l for l in DASH.read_text(encoding="utf-8").splitlines()
                     if not l.lstrip().startswith("#"))
    assert "-ge 1000" in code, "must skip system accounts (uid < 1000)"
    assert "65534" in code, "must skip `nobody`"
    assert "nologin" in code, "must skip accounts that cannot log in"


def test_the_seeding_loop_actually_selects_the_right_users(tmp_path: Path):
    """Run the real loop against a synthetic passwd."""
    home = tmp_path / "home"
    for u in ("alice", "bob"):
        (home / u).mkdir(parents=True)
    passwd = tmp_path / "passwd"
    passwd.write_text(
        "root:x:0:0:root:/root:/bin/bash\n"
        "nobody:x:65534:65534:nobody:/nonexistent:/usr/sbin/nologin\n"
        f"svc:x:998:998:svc:{home}/svc:/usr/sbin/nologin\n"
        f"alice:x:1000:1000:alice:{home}/alice:/bin/bash\n"
        f"bob:x:1001:1001:bob:{home}/bob:/bin/bash\n", encoding="utf-8")
    launcher = tmp_path / "l.desktop"
    launcher.write_text("launcher\n", encoding="utf-8")

    script = f'''
    LAUNCHER="{launcher}"; _seeded=0
    while IFS=: read -r _u _x _uid _gid _gecos _home _shell; do
      [ "${{_uid}}" -ge 1000 ] 2>/dev/null || continue
      [ "${{_uid}}" -lt 65534 ] 2>/dev/null || continue
      case "${{_shell}}" in */nologin|*/false) continue ;; esac
      [ -d "${{_home}}" ] || continue
      install -Dm644 "${{LAUNCHER}}" "${{_home}}/.config/autostart/x.desktop" || continue
      _seeded=$((_seeded + 1)); echo "${{_u}}"
    done < "{passwd}"
    '''
    out = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    seeded = out.stdout.split()
    assert seeded == ["alice", "bob"], (
        f"expected only the human accounts with real homes, got {seeded}"
    )
