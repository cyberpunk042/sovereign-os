"""A unit whose ExecStart does not exist fails instantly — and then loops.

2026-07-26. The sovereign units and the installed payload disagreed on where
the code lives:

    68 units ExecStart from  /usr/local/lib/sovereign-os
    the cockpit .deb installs to  /opt/sovereign-os

67 of those 68 carry Restart=, so enabling them yields dozens of services
failing with "executable not found" and restarting forever — the ~130 services
in restart loops seen on the appliance.

/usr/local/lib/sovereign-os is the correct home: install-gui-dashboards.sh
deploys the app tree there (SOVEREIGN_OS_LIB). The .deb is the odd one out, so
the postinst guarantees that path exists — via the dashboards deployment, or a
compatibility symlink when that deployment fails.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BUILD = REPO_ROOT / "scripts" / "build" / "installer-cdd" / "build.sh"
UNITS = REPO_ROOT / "systemd" / "system"
LIB = "/usr/local/lib/sovereign-os"


def postinst() -> str:
    text = BUILD.read_text(encoding="utf-8")
    start = text.index("DEBIAN/postinst")
    return text[start:text.index("\nPOSTINST", start)]


def test_units_really_do_reference_the_lib_path():
    """Guard the premise — if the layout changes, this lint must be revisited."""
    hits = [p for p in UNITS.glob("*.service") if LIB in p.read_text(encoding="utf-8")]
    assert hits, f"no unit references {LIB}; the layout changed, re-check this lint"


def test_the_install_guarantees_that_path_exists():
    body = postinst()
    code = "\n".join(l for l in body.splitlines() if not l.lstrip().startswith("#"))
    assert LIB in code, (
        f"nothing in the postinst guarantees {LIB} exists. Every unit that "
        "ExecStarts from there fails with 'executable not found', and most of "
        "them restart forever."
    )
    assert "ln -sfn" in code or "install-gui-dashboards" in code, (
        "the path must be produced either by deploying the app tree or by a "
        "compatibility symlink"
    )


def test_the_symlink_never_clobbers_a_real_deployment():
    """install-gui-dashboards.sh deploys the real tree there and runs FIRST.

    The symlink is a fallback for when that deployment fails — if it ran
    unconditionally it would replace a good tree with a link to a partial one.
    """
    code = [l for l in postinst().splitlines() if not l.lstrip().startswith("#")]
    ln = next((i for i, l in enumerate(code) if "ln -sfn" in l), None)
    if ln is None:
        return  # no symlink strategy in use
    guard = next((i for i, l in enumerate(code) if re.search(r"if \[ ! -e .*sovereign-os", l)), None)
    assert guard is not None and guard < ln, (
        "the symlink must be guarded by an existence check, or it overwrites a "
        "real deployment of the app tree"
    )
    deploy = next((i for i, l in enumerate(code) if "install-gui-dashboards" in l), None)
    if deploy is not None:
        assert deploy < ln, (
            "the dashboards deployment must run BEFORE the fallback symlink, "
            "or the guard sees an empty path and links over the real tree"
        )
