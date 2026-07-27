"""An explicitly empty setting must survive, not be replaced by the default.

2026-07-27. installed-system.sh used the colon form:

    SOVEREIGN_OS_KERNEL_CMDLINE="${SOVEREIGN_OS_KERNEL_CMDLINE:-nomodeset}"
    SOVEREIGN_OS_MODULE_BLACKLIST="${SOVEREIGN_OS_MODULE_BLACKLIST:-amdgpu nouveau}"

`${VAR:-default}` substitutes when VAR is unset OR EMPTY. So "blacklist
nothing" and "no extra kernel cmdline" were inexpressible — and those are
exactly the two choices the build panel offers for hardware whose GPU driver
binds. The panel sent them, the API forwarded them, and this line silently
overrode both: an operator could set blacklist=none, see success, and get an
ISO that still blacklists amdgpu and nouveau.

Found by running the build prologue end to end with the values set, rather than
by reading the code.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB = REPO_ROOT / "scripts" / "install" / "lib" / "installed-system.sh"

# Settings an operator may legitimately want to blank out.
BLANKABLE = ("SOVEREIGN_OS_KERNEL_CMDLINE", "SOVEREIGN_OS_MODULE_BLACKLIST")


@pytest.mark.parametrize("var", BLANKABLE)
def test_the_definition_uses_the_unset_only_form(var: str):
    text = LIB.read_text(encoding="utf-8")
    assert f'${{{var}:-' not in text, (
        f"{var} uses ${{VAR:-default}}, which replaces an EXPLICITLY EMPTY "
        "value with the default — making 'none' impossible to express"
    )
    assert f'${{{var}-' in text, f"{var} must use the ${{VAR-default}} form"


@pytest.mark.parametrize("var", BLANKABLE)
def test_empty_survives_sourcing(var: str):
    """Execute it: unset gives the default, empty stays empty, set is honoured."""
    def value(env: dict | None) -> str:
        return subprocess.run(
            ["bash", "-c", f'. scripts/install/lib/installed-system.sh; printf "%s" "${{{var}}}"'],
            capture_output=True, text=True, cwd=REPO_ROOT,
            env={"PATH": "/usr/bin:/bin", **(env or {})}).stdout

    assert value(None) != "", f"{var} unset should yield the built-in default"
    assert value({var: ""}) == "", (
        f"{var} explicitly empty was replaced by the default — 'none' cannot be "
        "expressed and the panel silently lies"
    )
    assert value({var: "sentinel"}) == "sentinel", f"{var} ignores an explicit value"


def test_the_empty_rendering_is_still_valid_shell():
    """Rendering an empty blacklist yields `for m in ; do` in the late_command."""
    out = subprocess.run(["sh", "-c", "for m in ; do echo x; done"],
                         capture_output=True, text=True)
    assert out.returncode == 0, (
        "an empty for-list must be valid, or clearing the blacklist breaks the "
        "late_command step"
    )
