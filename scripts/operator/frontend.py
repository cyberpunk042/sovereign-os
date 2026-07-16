#!/usr/bin/env python3
"""scripts/operator/frontend.py — swappable boot-frontend selector (SDD-704).

Materializes the operator's directive (verbatim, 2026-07-14):
  "I might wanna be able to hotswap if possible? … be able to chose at any point
   to start in one or another or even disable both, is that possible?"

The box PRESENTS one of four frontends on the display, independent of which AI
runtimes are installed:

  gnome                the near-stock GNOME desktop + dashboards launcher (default)
  dashboards-kiosk     a fullscreen kiosk (cage + browser) → the :8100 dashboards hub
  open-computer-kiosk  a fullscreen kiosk → the open-computer sandbox UI (SDD-706)
  none                 headless (multi-user.target)

Build-time the profile's provisioning.frontend.default picks the boot frontend and
provisioning.frontend.install stages the stacks. This tool is the RUNTIME switch —
`sovereign-osctl frontend set <value>` flips it live, no reflash: it toggles gdm3 vs
the kiosk unit, rewrites the kiosk target URL, and sets the boot target. The switch is
only as good as what was staged (`install:`); selecting an unstaged frontend hints how
to add it.

Sovereignty: stdlib-only. Read-only by default (status/list); `set` is the operator
mutation (needs root — it drives systemctl). SOVEREIGN_OS_FRONTEND_DRYRUN=1 prints the
plan instead of running systemctl (used by the contract lint + safe rehearsal).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0.0"

KIOSK_UNIT = "sovereign-frontend-kiosk.service"
GDM_UNIT = "gdm3.service"

# The four frontends + one-line descriptions. Order is the presentation order.
FRONTENDS: dict[str, str] = {
    "gnome": "GNOME desktop + dashboards launcher",
    "dashboards-kiosk": "fullscreen kiosk → the :8100 dashboards hub",
    "open-computer-kiosk": "fullscreen kiosk → the open-computer sandbox UI (SDD-706)",
    "none": "headless (multi-user.target)",
}
KIOSK_FRONTENDS = {"dashboards-kiosk", "open-computer-kiosk"}
# Default URL each kiosk targets (the operator can override with --url).
DEFAULT_KIOSK_URL: dict[str, str] = {
    "dashboards-kiosk": "http://127.0.0.1:8100/",
    # open-computer serves its agent UI from base port 9800 (SDD-706, verified).
    "open-computer-kiosk": "http://127.0.0.1:9800/",
}

STATE_FILE = Path(os.environ.get(
    "SOVEREIGN_OS_FRONTEND_STATE", "/etc/sovereign-os/frontend.active"))
KIOSK_ENV_FILE = Path(os.environ.get(
    "SOVEREIGN_OS_FRONTEND_KIOSK_ENV", "/etc/sovereign-os/frontend-kiosk.env"))
# SDD-600: the command to bring the desktop back — surfaced AT THE CONSOLE (a
# login hint), because when the GUI is off the web settings pane is unreachable.
# `set gnome` fixes the default target (next boot); `isolate` brings it up in the
# CURRENT session.
RESTORE_CMD = "sudo sovereign-osctl frontend set gnome && sudo systemctl isolate graphical.target"
# A /etc/profile.d drop-in that self-gates on the boot target, so it prints ONLY
# when the box is headless (multi-user.target) — silent under a GUI. It shows on
# every console/tty login while GUI is off ("after a login").
LOGIN_HINT_FILE = Path(os.environ.get(
    "SOVEREIGN_OS_FRONTEND_LOGIN_HINT", "/etc/profile.d/sovereign-frontend-restore.sh"))
DRYRUN = os.environ.get("SOVEREIGN_OS_FRONTEND_DRYRUN") == "1"


def _have_systemctl() -> bool:
    return shutil.which("systemctl") is not None


def _sc(args: list[str]) -> tuple[int, str]:
    """Run a systemctl command. In dry-run (or when systemctl is absent) it is a
    logged no-op returning success — so the tool imports + rehearses on a CI box
    with no init system."""
    cmd = ["systemctl", *args]
    if DRYRUN or not _have_systemctl():
        # stderr so --json stdout stays pure JSON for machine consumers.
        print(f"  [dry-run] {' '.join(cmd)}", file=sys.stderr)
        return 0, ""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return p.returncode, (p.stdout + p.stderr).strip()
    except (OSError, subprocess.SubprocessError) as e:
        return 1, str(e)


def _unit_present(unit: str) -> bool:
    """True if systemd knows the unit file (installed)."""
    if DRYRUN or not _have_systemctl():
        # Fall back to the on-disk unit file for the kiosk (staged in-repo/-image).
        return unit == KIOSK_UNIT and (
            Path("/etc/systemd/system") / unit).is_file()
    rc, out = _sc(["list-unit-files", "--no-legend", unit])
    return rc == 0 and unit in out


def _default_target() -> str:
    rc, out = _sc(["get-default"])
    return out.strip() if rc == 0 and out.strip() else "unknown"


def _active_frontend() -> str:
    """The operator's last selection (state file), else inferred from what's active."""
    if STATE_FILE.is_file():
        try:
            v = STATE_FILE.read_text(encoding="utf-8").strip()
            if v in FRONTENDS:
                return v
        except OSError:
            pass
    # Infer: kiosk active → a kiosk frontend; gdm active → gnome; else unknown.
    if not DRYRUN and _have_systemctl():
        rc, _ = _sc(["is-active", "--quiet", KIOSK_UNIT])
        if rc == 0:
            return "kiosk (unknown target)"
        rc, _ = _sc(["is-active", "--quiet", GDM_UNIT])
        if rc == 0:
            return "gnome"
    return "unknown"


def _write_state(value: str) -> None:
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(value + "\n", encoding="utf-8")
    except OSError as e:
        print(f"  warning: could not persist state to {STATE_FILE}: {e}", file=sys.stderr)


def _write_kiosk_url(url: str) -> None:
    body = (
        "# /etc/sovereign-os/frontend-kiosk.env — SDD-704 kiosk target "
        "(rewritten by 'sovereign-osctl frontend set').\n"
        f"FRONTEND_KIOSK_URL={url}\n"
    )
    try:
        KIOSK_ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
        KIOSK_ENV_FILE.write_text(body, encoding="utf-8")
    except OSError as e:
        print(f"  warning: could not write {KIOSK_ENV_FILE}: {e}", file=sys.stderr)


def _write_login_hint() -> None:
    """Install the console login hint (idempotent). It self-gates on the boot
    target so it only speaks when the box is headless — telling the operator, at
    the CLI, how to bring the desktop back. Under a GUI it stays silent."""
    body = (
        "# /etc/profile.d/sovereign-frontend-restore.sh — SDD-600.\n"
        "# When the GUI is off (headless boot target), remind the operator AT THE\n"
        "# CONSOLE how to restore the desktop — the web settings pane is unreachable\n"
        "# without a GUI. Self-gating: silent under graphical.target. Managed by\n"
        "# 'sovereign-osctl frontend set'; safe to delete.\n"
        'if [ \"$(systemctl get-default 2>/dev/null)\" = \"multi-user.target\" ]; then\n'
        "  printf '\\n\\033[1msovereign-os\\033[0m \\342\\200\\224 GUI is off. Bring the desktop back:\\n"
        f"  {RESTORE_CMD}\\n\\n'\n"
        "fi\n"
    )
    if DRYRUN:
        print(f"  [dry-run] would write {LOGIN_HINT_FILE}", file=sys.stderr)
        return
    try:
        LOGIN_HINT_FILE.parent.mkdir(parents=True, exist_ok=True)
        LOGIN_HINT_FILE.write_text(body, encoding="utf-8")
        os.chmod(LOGIN_HINT_FILE, 0o644)
    except OSError as e:
        print(f"  warning: could not write {LOGIN_HINT_FILE}: {e}", file=sys.stderr)


def _kiosk_url() -> str:
    if not KIOSK_ENV_FILE.is_file():
        return ""
    try:
        for line in KIOSK_ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("FRONTEND_KIOSK_URL="):
                return line.split("=", 1)[1]
    except OSError:
        pass
    return ""


def _require_root() -> None:
    if not DRYRUN and hasattr(os, "geteuid") and os.geteuid() != 0:
        print("frontend set: must run as root (drives systemctl)", file=sys.stderr)
        raise SystemExit(2)


def status() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "active": _active_frontend(),
        "default_target": _default_target(),
        "gdm_installed": _unit_present(GDM_UNIT),
        "kiosk_unit_installed": _unit_present(KIOSK_UNIT),
        "cage_installed": shutil.which("cage") is not None,
        "kiosk_url": _kiosk_url(),
        "state_file": str(STATE_FILE),
    }


def catalog() -> dict[str, Any]:
    active = _active_frontend()
    rows = []
    for name, desc in FRONTENDS.items():
        if name == "gnome":
            staged = _unit_present(GDM_UNIT) or shutil.which("gnome-shell") is not None
        elif name in KIOSK_FRONTENDS:
            staged = _unit_present(KIOSK_UNIT) and shutil.which("cage") is not None
        else:  # none is always available
            staged = True
        rows.append({"frontend": name, "description": desc,
                     "staged": staged, "active": name == active})
    return {"schema_version": SCHEMA_VERSION, "active": active, "frontends": rows}


def set_frontend(value: str, url: str | None = None) -> dict[str, Any]:
    if value not in FRONTENDS:
        return {"ok": False, "error": f"unknown frontend {value!r}",
                "known": list(FRONTENDS)}
    _require_root()
    notes: list[str] = []

    if value == "gnome":
        _sc(["disable", "--now", KIOSK_UNIT])
        if _unit_present(GDM_UNIT):
            _sc(["enable", GDM_UNIT])
        else:
            notes.append("gdm3 not installed — install a desktop stack (frontend install: gnome)")
        _sc(["set-default", "graphical.target"])

    elif value in KIOSK_FRONTENDS:
        target_url = url or DEFAULT_KIOSK_URL[value]
        _write_kiosk_url(target_url)
        notes.append(f"kiosk target → {target_url}")
        if not _unit_present(KIOSK_UNIT):
            notes.append(f"{KIOSK_UNIT} not installed — stage it (frontend install: {value})")
        if value == "open-computer-kiosk":
            notes.append("open-computer sandbox service lands in SDD-706; until then the "
                         "kiosk shows whatever answers at the URL above")
        _sc(["disable", GDM_UNIT])            # a kiosk owns the seat — no login manager
        _sc(["enable", "--now", KIOSK_UNIT])
        _sc(["set-default", "graphical.target"])

    else:  # none
        _sc(["disable", "--now", KIOSK_UNIT])
        _sc(["disable", GDM_UNIT])
        _sc(["set-default", "multi-user.target"])
        # surface the restore command right when going headless AND at the console
        notes.append(f"headless — restore the desktop with: {RESTORE_CMD}")

    _write_state(value)
    # the console login hint is self-gating (silent under a GUI) — keep it fresh
    # on every switch so a headless login always shows how to get back.
    _write_login_hint()
    return {"ok": True, "frontend": value, "dryrun": DRYRUN, "notes": notes}


def _print(obj: Any) -> None:
    print(json.dumps(obj, indent=2))


def _human_status(s: dict[str, Any]) -> None:
    print("frontend status")
    print("===============")
    print()
    print(f"  active:          {s['active']}")
    print(f"  default target:  {s['default_target']}")
    print(f"  gnome (gdm3):    {'installed' if s['gdm_installed'] else 'absent'}")
    print(f"  kiosk unit:      {'installed' if s['kiosk_unit_installed'] else 'absent'}")
    print(f"  cage compositor: {'installed' if s['cage_installed'] else 'absent'}")
    print(f"  kiosk url:       {s['kiosk_url'] or '(unset)'}")
    print()
    if s.get("default_target") == "multi-user.target" or s.get("active") == "none":
        print(f"  GUI is off — restore the desktop:  {RESTORE_CMD}")
    print("  switch:  sovereign-osctl frontend set {gnome|dashboards-kiosk|open-computer-kiosk|none}")


def _human_list(c: dict[str, Any]) -> None:
    print("frontends (active ▸, staged ✓)")
    print("==============================")
    for r in c["frontends"]:
        mark = "▸" if r["active"] else " "
        staged = "✓" if r["staged"] else "·"
        print(f"  {mark} {staged} {r['frontend']:<20} {r['description']}")
    print()
    print("  staged ✓ = its stack is installed and can be selected now;")
    print("  · = add it to the profile's provisioning.frontend.install and rebuild.")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="swappable boot-frontend selector (SDD-704)")
    sub = p.add_subparsers(dest="cmd")
    sp_st = sub.add_parser("status", help="what's installed / default / active")
    sp_st.add_argument("--json", action="store_true")
    sp_li = sub.add_parser("list", help="the frontends + which are staged/active")
    sp_li.add_argument("--json", action="store_true")
    sp_set = sub.add_parser("set", help="switch the boot frontend live")
    sp_set.add_argument("value", choices=list(FRONTENDS))
    sp_set.add_argument("--url", default=None,
                        help="override the kiosk target URL (kiosk frontends only)")
    sp_set.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    cmd = args.cmd or "status"

    if cmd == "status":
        s = status()
        _print(s) if getattr(args, "json", False) else _human_status(s)
        return 0
    if cmd == "list":
        c = catalog()
        _print(c) if getattr(args, "json", False) else _human_list(c)
        return 0
    if cmd == "set":
        r = set_frontend(args.value, args.url)
        if getattr(args, "json", False):
            _print(r)
        else:
            if r.get("ok"):
                print(f"frontend → {r['frontend']}" + (" (dry-run)" if r.get("dryrun") else ""))
                for n in r.get("notes", []):
                    print(f"  · {n}")
            else:
                print(f"error: {r.get('error')}", file=sys.stderr)
        return 0 if r.get("ok") else 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
