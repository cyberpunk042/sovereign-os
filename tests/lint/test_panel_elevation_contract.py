"""Panel root-elevation contract — the 2026-07-25 operator-reported bug.

WHAT BROKE: `scripts/install/bootstrap-host.sh` promises in its own header
"ONE command to make a fresh Debian host ready to BUILD and RUN sovereign-os.
No manual apt, ever." Its HOST_PACKAGES list was assembled as the union of what
the CLI build path needs — and nobody added `pkexec`. The operator panels are
HTTP servers with no controlling terminal, so they CANNOT prompt for a sudo
password; they hand the privileged run to pkexec. Debian 13 split pkexec out of
policykit-1 into its own package, so a stock trixie host does not have it.

Result: bootstrap reported success on a host where the panel's BUILD and FLASH
buttons were dead, 403-ing with "pkexec is unavailable" and advising the
operator to demote the whole panel server to root — which hid the real cause
(an under-declared dependency) behind a worse security posture.

This locks all three halves of the fix:
  1. every binary the panels shell out to for elevation is in HOST_PACKAGES
  2. both panels resolve elevation through the ONE shared helper, so their
     behaviour + their reported status can never diverge again
  3. the unavailable-payload names the package AND the self-elevating bootstrap
     that installs it — never "go run apt by hand"
"""
from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
BOOTSTRAP = REPO_ROOT / "scripts" / "install" / "bootstrap-host.sh"
ELEVATION = REPO_ROOT / "scripts" / "operator" / "lib" / "elevation.py"
BUILD_API = REPO_ROOT / "scripts" / "operator" / "build-configurator-api.py"
FLASH_API = REPO_ROOT / "scripts" / "operator" / "flash-api.py"

# Every panel API that can run something as root. Add new ones here — the
# import + no-inline-pkexec assertions then apply automatically.
PANEL_APIS = (BUILD_API, FLASH_API)


def _host_packages() -> list[str]:
    """Parse the HOST_PACKAGES bash array out of bootstrap-host.sh."""
    text = BOOTSTRAP.read_text(encoding="utf-8")
    m = re.search(r"^HOST_PACKAGES=\((.*?)^\)", text, re.S | re.M)
    assert m, "HOST_PACKAGES array not found in bootstrap-host.sh"
    pkgs: list[str] = []
    for line in m.group(1).splitlines():
        line = line.split("#", 1)[0].strip()
        pkgs.extend(line.split())
    return pkgs


def test_bootstrap_declares_the_panel_elevation_packages():
    """pkexec (+ its daemon) must be part of the one-command bootstrap.

    This is the exact regression: without pkexec on the host, a panel that
    reports "bootstrap complete" still cannot build or flash.
    """
    pkgs = _host_packages()
    for required in ("pkexec", "polkitd"):
        assert required in pkgs, (
            f"{required!r} missing from HOST_PACKAGES in bootstrap-host.sh — the "
            "panels' BUILD/FLASH buttons elevate via pkexec and will 403 on a "
            "freshly bootstrapped host without it"
        )


def test_bootstrap_explains_why_pkexec_is_there():
    """The entry carries its rationale, so nobody prunes it as 'unused'.

    pkexec is invisible to the CLI build path, which is exactly how it went
    missing the first time.
    """
    text = BOOTSTRAP.read_text(encoding="utf-8")
    block = text[text.index("HOST_PACKAGES=("):]
    block = block[:block.index("\n)")]
    assert "pkexec" in block and "panel" in block.lower(), (
        "the pkexec entry in HOST_PACKAGES must be commented with WHY (the panel "
        "elevation path) — an unexplained package gets pruned"
    )


@pytest.mark.parametrize("api", PANEL_APIS, ids=lambda p: p.name)
def test_panels_use_the_shared_elevation_helper(api: Path):
    """Both panels resolve elevation through lib/elevation.py."""
    text = api.read_text(encoding="utf-8")
    assert "import elevation" in text, (
        f"{api.name} must import the shared elevation resolver; hand-rolled "
        "elevation is how the two panels drifted apart"
    )
    assert "_elevate.wrap(" in text, (
        f"{api.name} must elevate via _elevate.wrap() so the 403 payload, the "
        "PATH fix-up and the sudo fallback stay identical across panels"
    )


@pytest.mark.parametrize("api", PANEL_APIS, ids=lambda p: p.name)
def test_panels_have_no_inline_pkexec_lookup(api: Path):
    """No panel re-implements `shutil.which("pkexec")` inline.

    An inline lookup is what produced a 403 that named no package and no fix.
    """
    text = api.read_text(encoding="utf-8")
    assert 'which("pkexec")' not in text, (
        f"{api.name} still does an inline pkexec lookup — route it through "
        "lib/elevation.py instead"
    )


@pytest.mark.parametrize("api", PANEL_APIS, ids=lambda p: p.name)
def test_panels_parse(api: Path):
    """The edited panels are syntactically valid Python."""
    ast.parse(api.read_text(encoding="utf-8"), filename=str(api))


def test_unavailable_payload_names_package_and_bootstrap():
    """The 403 tells the operator the ONE self-elevating command to run.

    Operator directive that drove this fix (verbatim): "I am not supposed to
    have to run any manual commands." So the payload points at bootstrap-host.sh
    — which self-elevates — and never at a bare `apt install`.
    """
    sys.path.insert(0, str(ELEVATION.parent))
    try:
        import elevation  # noqa: PLC0415
    finally:
        sys.path.pop(0)

    payload = elevation.unavailable_payload("a real build", "dry-run + preflight")

    assert payload["package"] == "pkexec"
    assert payload["bootstrap"] == "scripts/install/bootstrap-host.sh"
    assert "pkexec" in payload["cause"]
    assert "scripts/install/bootstrap-host.sh" in payload["fix"], (
        "the fix line must name the self-elevating bootstrap, not a manual apt"
    )
    assert not re.search(r"\bapt(-get)? install\b", payload["fix"]), (
        "the primary fix must never be a hand-run apt — bootstrap-host.sh owns "
        "package installation"
    )
    # The run-the-panel-as-root workaround stays available, but demoted to an
    # alternative: it was the ONLY advice before, and it hid the real cause.
    assert any("panel.sh" in alt for alt in payload["alternatives"])


def test_elevation_probe_never_prompts():
    """The sudo fallback must be non-interactive.

    A panel request that blocks on a password prompt hangs the HTTP thread
    forever with no way for the operator to answer it.
    """
    text = ELEVATION.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(ELEVATION))
    sudo_calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.List)
        and any(isinstance(e, ast.Constant) and e.value == "-n" for e in node.elts)
    ]
    assert sudo_calls, "the sudo path must pass -n (never prompt)"
    assert "timeout=" in text, "the sudo probe must be timeout-bounded"


@pytest.mark.skipif(not (REPO_ROOT / ".git").exists(), reason="not a git checkout")
def test_bootstrap_is_shellcheck_clean():
    """The edited bootstrap still passes shellcheck (when available)."""
    if subprocess.run(["which", "shellcheck"], capture_output=True).returncode != 0:
        pytest.skip("shellcheck not installed")
    proc = subprocess.run(
        ["shellcheck", "-S", "error", str(BOOTSTRAP)],
        capture_output=True, text=True, env={**os.environ, "LC_ALL": "C"},
    )
    assert proc.returncode == 0, f"shellcheck errors:\n{proc.stdout}{proc.stderr}"
