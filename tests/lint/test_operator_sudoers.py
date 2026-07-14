"""operator-sudoers: a SCOPED, RISK-TIERED NOPASSWD drop-in — reproducible,
reviewable, and never a blanket-root grant OR a privilege-escalation footgun.

The operator asked to unlock the specific privileged commands sovereign-os
workflows need (read-only diagnostics + image loop-mount verification + panel
port-reclaim) for the panels + the agent, without password prompts — but scoped
and reproducible via a script/make target.

The OPS surface used to be one opaque `SOVEREIGN_OS_OPS` alias with NO coverage
lint: nothing kept its command set the reviewed one, and — the real hole —
nothing stopped a privilege-escalating binary (`dd`, `bash`, `systemctl`, `tee`,
`chmod`…) from being added to a NOPASSWD grant, which would silently turn the
scoped drop-in into root-equivalent. This lint closes that (SDD-700): the
command set of each risk tier (DIAG / IMAGE / PROC) is **locked** to the reviewed
set, and a privesc denylist can **never** appear in any NOPASSWD bucket — the
same lockstep discipline `test_cockpit_action_exec_sudoers.py` already applies to
the per-verb cockpit alias.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "operator" / "operator-sudoers.sh"

# The reviewed command set of each risk tier — locked so a new grant is a
# deliberate, reviewed change (edit the script AND this set together, in a PR).
EXPECTED_DIAG = {
    "dmidecode", "lshw", "lspci", "lsusb", "lsblk", "nvme",
    "smartctl", "sensors", "nvidia-smi", "zpool", "zfs", "journalctl",
}
EXPECTED_IMAGE = {"losetup", "mount", "umount"}   # HIGH-RISK: loop-mount an image to verify it
EXPECTED_PROC = {"kill"}                          # reclaim a prior root-owned panel port

# Binaries that must NEVER be granted NOPASSWD — each is a trivial root shell /
# arbitrary-write / service-control escape. A defense-in-depth denylist on top of
# the locked sets above: even if someone edits both the script and the EXPECTED_*
# sets, adding one of these still fails CI. (mount/umount/losetup are deliberately
# NOT here — they are the reviewed HIGH-RISK image-verify grants.)
PRIVESC_DENYLIST = {
    "dd", "bash", "sh", "zsh", "csh", "ksh", "dash", "env",
    "python", "python2", "python3", "perl", "ruby", "node", "lua", "php",
    "tee", "cp", "mv", "install", "ln", "chmod", "chown", "chgrp",
    "chroot", "mknod", "nsenter", "unshare", "capsh",
    "systemctl", "service", "init", "telinit",
    "apt", "apt-get", "aptitude", "dpkg", "pip", "pip3", "snap", "flatpak",
    "vi", "vim", "nano", "ed", "emacs", "less", "more", "man", "pager",
    "find", "tar", "rsync", "cpio", "zip", "unzip", "gzip",
    "gdb", "strace", "ltrace", "nmap", "socat", "ncat", "nc",
    "crontab", "at", "visudo", "passwd", "useradd", "usermod", "su", "sudo",
}


def _array(name: str) -> set[str]:
    """Parse a `NAME=(a b c)` bash array from the script into a set of names."""
    body = SCRIPT.read_text(encoding="utf-8")
    m = re.search(rf"^{name}=\(([^)]*)\)", body, re.MULTILINE)
    assert m, f"{name}=(...) array not found in {SCRIPT}"
    return {tok for tok in m.group(1).split() if tok}


def test_script_present_and_executable():
    assert SCRIPT.is_file(), f"missing {SCRIPT}"
    assert os.access(SCRIPT, os.X_OK), f"{SCRIPT} not executable"


def test_bash_syntax_ok():
    r = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_reviewed_command_set_is_locked():
    """Each risk tier's command set == the reviewed set — a new grant can't drift
    in without a deliberate change to this lint (the lockstep drift-lock)."""
    assert _array("DIAG") == EXPECTED_DIAG, (
        "DIAG bucket drifted from the reviewed set — update EXPECTED_DIAG in this "
        "lint deliberately (a new NOPASSWD grant is a security change)"
    )
    assert _array("IMAGE") == EXPECTED_IMAGE, "IMAGE bucket drifted from the reviewed set"
    assert _array("PROC") == EXPECTED_PROC, "PROC bucket drifted from the reviewed set"


def test_no_privilege_escalating_binary_in_any_bucket():
    """No NOPASSWD grant may be a trivial root-shell / arbitrary-write escape."""
    for name in ("DIAG", "IMAGE", "PROC"):
        bad = _array(name) & PRIVESC_DENYLIST
        assert not bad, (
            f"{name} bucket grants privilege-escalating binaries NOPASSWD: "
            f"{sorted(bad)} — a scoped drop-in must never include a root-shell escape"
        )


def test_generated_spec_is_scoped_not_blanket_all():
    r = subprocess.run(
        [str(SCRIPT), "--print"], capture_output=True, text=True,
        env={**os.environ, "SOVEREIGN_OS_OPERATOR_USER": "testop"},
    )
    out = r.stdout
    # Never a blanket root grant, under any circumstance.
    assert "NOPASSWD: ALL" not in out, "must never grant NOPASSWD: ALL"
    # When commands resolve, the spec grants only the scoped risk-tier aliases
    # (+ the per-verb cockpit alias), never a raw command on the grant line.
    if "Cmnd_Alias" in out:
        grant = next(ln for ln in out.splitlines() if " ALL=(root) NOPASSWD:" in ln)
        granted = grant.split("NOPASSWD:", 1)[1]
        for tok in (x.strip() for x in granted.split(",")):
            assert re.fullmatch(r"SOVEREIGN_OS_[A-Z]+", tok), (
                f"grant line lists a non-alias token {tok!r} — only scoped aliases allowed"
            )
        # every member of the three command-path tiers is an absolute path (the
        # per-verb SOVEREIGN_OS_COCKPIT alias is a `sovereign-osctl <verb> *` list,
        # guarded by test_cockpit_action_exec_sudoers.py — not checked here).
        for ln in out.splitlines():
            if re.match(r"Cmnd_Alias SOVEREIGN_OS_(DIAG|IMAGE|PROC) =", ln):
                for c in (x.strip() for x in ln.split("=", 1)[1].split(",")):
                    assert c.startswith("/"), f"granted command is not an absolute path: {c!r}"


def test_risk_tiers_are_separate_aliases():
    """The drop-in self-documents danger: read-only diagnostics, HIGH-RISK image
    mount, and process control are distinct aliases (not one opaque bucket)."""
    body = SCRIPT.read_text(encoding="utf-8")
    for alias in ("SOVEREIGN_OS_DIAG", "SOVEREIGN_OS_IMAGE", "SOVEREIGN_OS_PROC"):
        assert alias in body, f"{alias} risk-tier alias missing from the generator"


def test_install_is_self_validating_and_locked_down():
    body = SCRIPT.read_text(encoding="utf-8")
    assert "VISUDO" in body and "-cf" in body, "must visudo-validate before writing the drop-in"
    assert "install -m 0440" in body, "the drop-in must be installed mode 0440"
    assert "--uninstall" in body, "must offer an uninstall path"


def test_make_targets_present():
    mk = (REPO / "Makefile").read_text(encoding="utf-8")
    assert "operator-sudo:" in mk and "operator-sudo-uninstall:" in mk, (
        "Makefile must expose operator-sudo + operator-sudo-uninstall"
    )
