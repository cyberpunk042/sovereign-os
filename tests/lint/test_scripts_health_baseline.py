"""Scripts health-baseline contract (F-2026-020 / SDD-969).

The audit found the operator-script surface at an exemplary baseline — every
shell script parses, every Python script byte-compiles, and every verb
`sovereign-osctl` dispatches resolves to a defined handler — and asked to
protect it so the bar can't silently drop as scripts churn. This is the
scripts-surface parallel to the crate-hygiene contract (SDD-974), recomputed
from the tree each run:

  1. every `scripts/**/*.sh` passes `bash -n` (parse-only, no execution);
  2. every `scripts/**/*.py` passes `py_compile` (byte-compile, no import);
  3. `scripts/sovereign-osctl` — every `cmd_*` it *calls* is *defined*, so a
     dispatch to a non-existent handler is caught in CI, not at the operator's
     terminal.

Read-only: `bash -n` and `py_compile` parse/compile, they never run the script.
The port-map / systemd-pairing baselines are already held by
`test_dashboard_port_and_reference_integrity.py`; this covers the
parse/compile/dispatch axis that was unguarded.
"""
from __future__ import annotations

import py_compile
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "scripts"
OSCTL = SCRIPTS / "sovereign-osctl"


def _sh_files() -> list[Path]:
    return sorted(SCRIPTS.rglob("*.sh"))


def _py_files() -> list[Path]:
    return sorted(p for p in SCRIPTS.rglob("*.py") if "__pycache__" not in p.parts)


def test_all_shell_scripts_parse():
    assert _sh_files(), "no shell scripts found under scripts/"
    broken = []
    for f in _sh_files():
        r = subprocess.run(
            ["bash", "-n", str(f)],
            capture_output=True,
            text=True,
        )
        if r.returncode != 0:
            broken.append(f"{f.relative_to(REPO_ROOT)}: {r.stderr.strip().splitlines()[-1] if r.stderr.strip() else 'parse error'}")
    assert not broken, f"{len(broken)} shell script(s) fail `bash -n`:\n" + "\n".join(broken[:10])


def test_all_python_scripts_byte_compile():
    assert _py_files(), "no python scripts found under scripts/"
    broken = []
    for f in _py_files():
        try:
            py_compile.compile(str(f), doraise=True)
        except py_compile.PyCompileError as e:
            broken.append(f"{f.relative_to(REPO_ROOT)}: {e.msg}")
    assert not broken, f"{len(broken)} python script(s) fail py_compile:\n" + "\n".join(broken[:10])


def test_osctl_dispatch_targets_resolve():
    """Every `cmd_*` sovereign-osctl calls must be defined — a dispatch verb
    routed to a missing handler is a runtime break at the operator's terminal."""
    body = OSCTL.read_text(encoding="utf-8")
    modules = REPO_ROOT / "scripts" / "osctl.d"
    body += "\n" + "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(modules.glob("*.sh"))
    )
    defined = set(re.findall(r"^(cmd_[a-z0-9_]+)\(\)", body, re.MULTILINE))
    called = set(re.findall(r"\b(cmd_[a-z0-9_]+)\b", body))
    assert defined, "no cmd_* functions defined in sovereign-osctl"
    dangling = sorted(called - defined)
    assert not dangling, (
        f"sovereign-osctl calls cmd_* handler(s) that are not defined: "
        f"{dangling} — a dispatch verb routes to a missing function"
    )
