"""operator-sudoers: a SCOPED NOPASSWD drop-in — reproducible, reviewable, and
never a blanket-root grant.

The operator asked to unlock the specific privileged commands sovereign-os
workflows need (read-only diagnostics + image loop-mount verification) for the
panels + the agent, without password prompts — but scoped and reproducible via
a script/make target. These locks keep it from drifting into `NOPASSWD: ALL`,
keep every granted command an absolute path (auditable + visudo-required), and
keep the install self-validating.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "operator" / "operator-sudoers.sh"


def test_script_present_and_executable():
    assert SCRIPT.is_file(), f"missing {SCRIPT}"
    assert os.access(SCRIPT, os.X_OK), f"{SCRIPT} not executable"


def test_bash_syntax_ok():
    r = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_generated_spec_is_scoped_not_blanket_all():
    r = subprocess.run(
        [str(SCRIPT), "--print"], capture_output=True, text=True,
        env={**os.environ, "SOVEREIGN_OS_OPERATOR_USER": "testop"},
    )
    out = r.stdout
    # Never a blanket root grant, under any circumstance.
    assert "NOPASSWD: ALL" not in out, "must never grant NOPASSWD: ALL"
    # When commands resolve, the spec is a scoped Cmnd_Alias of absolute paths.
    if "Cmnd_Alias" in out:
        assert "NOPASSWD: SOVEREIGN_OS_OPS" in out, "must grant only the scoped alias"
        alias_line = next(l for l in out.splitlines() if l.startswith("Cmnd_Alias"))
        cmds = alias_line.split("=", 1)[1]
        for c in (x.strip() for x in cmds.split(",")):
            assert c.startswith("/"), f"granted command is not an absolute path: {c!r}"


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
