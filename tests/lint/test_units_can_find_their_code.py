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
    # The guarantee moved OUT of the postinst: a symlink created before the
    # deploy makes install-gui-dashboards.sh copy a directory into itself, and
    # its own code leaves a symlink alone by design (2026-07-27). It is now a
    # FALLBACK created after the deploy, in deploy-dashboards.sh.
    body = (REPO_ROOT / "scripts" / "install" / "deploy-dashboards.sh").read_text(encoding="utf-8")
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
    """The deploy writes the real tree there and runs FIRST.

    The symlink is a fallback for when that deployment fails. If it ran
    unconditionally it would replace a good tree with a link to a partial one;
    if it ran BEFORE the deploy, install-gui-dashboards.sh (which leaves a
    symlink alone by design) would copy a directory into itself.

    Checks the SEMANTICS, not one syntax: an early-return guard
    (`[ -e X ] && return 0`) is as valid as `if [ ! -e X ]` — matching only the
    latter failed on correct code (2026-07-27, my own lint).
    """
    body = (REPO_ROOT / "scripts" / "install" / "deploy-dashboards.sh").read_text(encoding="utf-8")
    code = [l for l in body.splitlines() if not l.lstrip().startswith("#")]
    ln = next((i for i, l in enumerate(code) if "ln -sfn" in l), None)
    assert ln is not None, "no fallback symlink found"

    # Some existence check on that path must precede the link, in either form.
    guard = next((i for i, l in enumerate(code[:ln])
                  if "sovereign-os" in l and ("-e " in l or "-L " in l)), None)
    assert guard is not None, (
        "the symlink must be guarded by an existence check, or it overwrites a "
        f"real deployment; lines before it: {code[max(0, ln-4):ln]}"
    )

    # On the path that RUNS the deploy, the fallback must come after it. Calls
    # on the early-exit paths legitimately appear earlier in the file — the
    # deploy never runs there. Requiring ALL calls to follow the deploy flagged
    # correct code (2026-07-27, my own lint, again).
    deploy = next((i for i, l in enumerate(code) if 'bash "${DASH}"' in l), None)
    calls = [i for i, l in enumerate(code)
             if "_fallback_link" in l and "()" not in l]
    if deploy is not None:
        assert any(c > deploy for c in calls), (
            "no fallback call follows the deploy; on the path where the deploy "
            "runs and produces nothing, the units would have no code path"
        )


def test_the_fallback_runs_on_every_exit_path():
    """It was placed after the early returns, so it was skipped in exactly the
    cases that need it — script missing or not executable, where no tree exists
    at all (caught by testing, 2026-07-27)."""
    body = (REPO_ROOT / "scripts" / "install" / "deploy-dashboards.sh").read_text(encoding="utf-8")
    code = [l for l in body.splitlines() if not l.lstrip().startswith("#")]
    exits = [i for i, l in enumerate(code) if "exit 0" in l and "_fallback_link" not in l]
    calls = [i for i, l in enumerate(code) if "_fallback_link" in l and "()" not in l]
    inline = [i for i, l in enumerate(code) if "_fallback_link" in l and "exit 0" in l]
    assert calls, "the fallback is never invoked"
    for e in exits:
        assert any(c <= e for c in calls) or e in inline, (
            f"exit at line {e} is reachable without the fallback having run"
        )


def test_the_direct_install_path_installs_the_units_too():
    """Both install paths, one behaviour.

    install-gui-dashboards.sh stages exactly ONE unit (the kiosk); the other
    ~113 stayed in the source tree where systemd never looks. The installer
    path was fixed first — leaving the two paths disagreeing is how the amdgpu
    fix ended up in a preseed that never runs (2026-07-26).
    """
    text = (REPO_ROOT / "scripts" / "install" / "install-sovereign-root.sh").read_text(encoding="utf-8")
    code = [l for l in text.splitlines() if not l.lstrip().startswith("#")]
    body = "\n".join(code)
    assert "/lib/systemd/system" in body, (
        "the direct path must install the sovereign units where systemd looks"
    )
    # ...and must not switch any of them on.
    import re
    for l in code:
        if "systemctl" in l and "sovereign-" in l:
            assert not re.search(r"systemctl\s+(enable|start)\s+sovereign-", l), (
                f"the direct path activates a sovereign unit: {l.strip()!r}"
            )


def test_units_are_installed_outside_the_gui_branch():
    """A headless install needs them discoverable too.

    STAGE=/opt/sovereign-os-src only exists when SOVEREIGN_OS_INSTALL_GUI=1, so
    anything that reads from it silently does nothing on a headless install.
    """
    text = (REPO_ROOT / "scripts" / "install" / "install-sovereign-root.sh").read_text(encoding="utf-8")
    # Anchor on the INSTALL step, not the first mention of the path — the
    # verifier also references /lib/systemd/system, and adding that check made
    # this test read the wrong block entirely (2026-07-26, my own test).
    i = text.index("installing sovereign units")
    block = text[i:i + 800]
    assert "REPO_SRC" in block, (
        "the unit install must read from REPO_SRC, not the GUI-only STAGE "
        "directory — STAGE exists only when SOVEREIGN_OS_INSTALL_GUI=1, so a "
        "headless install would silently get no units"
    )
    assert "STAGE" not in block, (
        f"the unit install references STAGE: {block[:200]!r}"
    )
