"""Shared root-elevation resolver for the operator panel APIs.

WHY THIS EXISTS (the 2026-07-25 operator-reported bug): a panel API is an HTTP
server with no controlling terminal. It can never prompt for a sudo password
itself — the browser has nowhere to render one. So a privileged run (a real
build, a real flash) has to be handed to an elevation helper. Two exist, tried
in order:

  1. pkexec  — polkit pops the system password dialog on the operator's desktop
               session; the command then runs as root. The default on a GUI
               host. Needs the `pkexec` package (Debian 13 split it out of
               policykit-1, so a stock trixie install lacks it) AND a running
               polkit agent (KDE/GNOME ship one).
  2. sudo -n — for an operator who installed a NOPASSWD grant covering the
               command (`make operator-sudo` installs a SCOPED drop-in; a
               broader grant is the operator's call). Probed non-interactively
               with `sudo -n -l -- <cmd>` so we NEVER hang an HTTP request on a
               password prompt.

Neither available → the caller returns 403 with a payload that names the exact
missing package and the ONE self-elevating command that installs it
(`scripts/install/bootstrap-host.sh`). The old message told the operator to
demote the entire panel server to root, which is the worse posture and hid the
real cause: bootstrap under-declared its dependency.

Contract locked by tests/lint/test_panel_elevation_contract.py.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

# The bootstrap that installs the missing piece; quoted in every 403 so the
# operator never has to hand-run apt.
BOOTSTRAP_CMD = "scripts/install/bootstrap-host.sh"
ELEVATION_PACKAGE = "pkexec"

# `sudo -n -l -- <cmd>` probe timeout. sudo with -n never prompts, so this is a
# guard against a wedged sudoers/LDAP lookup, not against an interactive hang.
_SUDO_PROBE_TIMEOUT = 5


def _sudo_can_run(command: str) -> bool:
    """True iff a NOPASSWD grant lets this user run `command` right now.

    `sudo -n -l -- <cmd>` exits 0 only when the command is permitted WITHOUT a
    password. Any prompt-required or denied case exits non-zero rather than
    blocking, because -n forbids prompting.
    """
    sudo = shutil.which("sudo")
    if not sudo:
        return False
    try:
        return subprocess.run(
            [sudo, "-n", "-l", "--", command],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=_SUDO_PROBE_TIMEOUT,
        ).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def status() -> dict:
    """Machine-readable elevation posture, for panel /status endpoints."""
    return {
        "is_root": os.geteuid() == 0,
        "pkexec": bool(shutil.which("pkexec")),
        "polkit_agent": bool(os.environ.get("DISPLAY") or
                             os.environ.get("WAYLAND_DISPLAY")),
    }


def unavailable_payload(what: str, unprivileged_hint: str) -> dict:
    """The 403 body when no elevation path exists.

    `what` names the blocked action ("a real build", "flashing");
    `unprivileged_hint` names what still works without root (dry-run, plan).
    """
    return {
        "error": f"{what} needs root and no elevation path is available",
        "cause": (
            f"`{ELEVATION_PACKAGE}` is not installed — Debian 13 ships it as its "
            "own package, split out of policykit-1, so a stock trixie host lacks "
            "it — and no passwordless sudo grant covers this command."
        ),
        "fix": (
            f"run the host bootstrap; it self-elevates and installs {ELEVATION_PACKAGE} "
            f"(plus the rest of the build-host toolchain):  {BOOTSTRAP_CMD}"
        ),
        "package": ELEVATION_PACKAGE,
        "bootstrap": BOOTSTRAP_CMD,
        "alternatives": [
            f"sudo -E scripts/operator/panel.sh   — run the panel itself as root "
            f"(coarser: the whole server is privileged, not just {what})",
            f"{unprivileged_hint} works right now without root",
        ],
    }


class ElevationUnavailable(Exception):
    """No elevation path. Carries the ready-to-send 403 body in `.payload`."""

    def __init__(self, payload: dict):
        super().__init__(payload["error"])
        self.payload = payload


def wrap(argv: list[str], env: dict[str, str], *, what: str,
         unprivileged_hint: str, extra_path: str = "") -> tuple[list[str], str]:
    """Return (argv-to-run, operator-facing note) for a privileged command.

    Already root → argv is returned untouched with an empty note. Otherwise the
    command is wrapped in pkexec (preferred) or `sudo -n`, with `env` re-injected
    because both helpers sanitize the environment.

    Raises ElevationUnavailable when neither path exists.
    """
    if os.geteuid() == 0:
        return list(argv), ""

    # A root run needs the sbin dirs (debootstrap / lb / sgdisk live in
    # /usr/sbin) but the panel runs as the operator, whose login PATH usually
    # omits them — the installer's live-build → debootstrap failed exactly here.
    path = os.environ.get("PATH", "/usr/bin:/bin")
    if extra_path:
        path = f"{extra_path}:{path}"
    env_args = [f"{k}={v}" for k, v in env.items()] + [f"PATH={path}"]

    pkexec = shutil.which("pkexec")
    if pkexec:
        return ([pkexec, "env", *env_args, *argv],
                "  (look for the system password prompt on your desktop — polkit/pkexec)\n")

    if _sudo_can_run(str(argv[0])):
        sudo = shutil.which("sudo") or "sudo"
        return ([sudo, "-n", "env", *env_args, *argv],
                "  (elevated via your passwordless sudo grant)\n")

    raise ElevationUnavailable(unavailable_payload(what, unprivileged_hint))


def repo_root() -> Path:
    """Repo root, for callers that resolve script paths against it."""
    return Path(__file__).resolve().parents[3]
