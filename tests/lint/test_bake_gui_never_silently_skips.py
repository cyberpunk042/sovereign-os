"""A requested desktop must never silently vanish (2026-07-26 root cause).

WHAT HAPPENED: the operator selected everything in the build configurator with
the sain-01 default frontend (kde-plasma). The build reported SUCCESS and the
flashed image booted to a text console with no desktop at all — no sddm, no
xsessions, no display-manager.service.

The cause was a single missing exec bit. `scripts/install/install-gui-dashboards.sh`
was committed 100644 — the ONLY script in scripts/install/ without it — and
provision-bake.sh gated the whole desktop stage on:

    if [ "$SOVEREIGN_OS_BAKE_GUI" = "1" ] && [ -x .../install-gui-dashboards.sh ]

BAKE_GUI was 1; the -x arm was false; a false `if` logs NOTHING. So the stage was
skipped rather than failed: no log line, no /var/lib/sovereign-os/bake-gui-failed
breadcrumb, no non-zero exit. The `exit 1` guard added by the 2026-07-25 directive
lives INSIDE that block and never got the chance to run.

Two more silencers sat on the same path:
  * mkosi-emit's postinst ran provision-bake with `|| echo "…(non-fatal)"`,
    discarding its exit code entirely;
  * (already fixed 2026-07-25) the `| sed` pipe that masked PIPESTATUS.

Three independent mufflers on one signal. This lint keeps all three off.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PROVISION_BAKE = REPO_ROOT / "scripts" / "build" / "provision-bake.sh"
MKOSI_EMIT = REPO_ROOT / "scripts" / "build" / "adapters" / "mkosi-emit.sh"
GUI_INSTALLER = REPO_ROOT / "scripts" / "install" / "install-gui-dashboards.sh"


def _git_mode(path: Path) -> str:
    """The mode git has RECORDED — the one every clone and build gets."""
    out = subprocess.run(
        ["git", "ls-files", "-s", str(path.relative_to(REPO_ROOT))],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True).stdout
    return out.split()[0] if out.strip() else ""


def test_gui_installer_is_committed_executable():
    """The exact file whose missing exec bit cost a whole build+flash cycle."""
    assert GUI_INSTALLER.is_file(), "the GUI installer must exist"
    mode = _git_mode(GUI_INSTALLER)
    assert mode == "100755", (
        f"install-gui-dashboards.sh is committed {mode}, not 100755 — "
        "provision-bake gates the desktop on [ -x ], so a non-executable mode "
        "makes the desktop stage skip SILENTLY and the image ship headless"
    )


def test_every_x_guarded_script_is_committed_executable():
    """Generalise it: any script a shell tests with -x must carry the bit.

    An `[ -x ]` guard that is false is indistinguishable from 'feature not
    requested' — it produces no output at all. So the bit is load-bearing.
    """
    pat = re.compile(r'\[ -x "\$\{[A-Z_]+\}/([a-zA-Z0-9_./-]+\.(?:sh|py))"')
    offenders: list[str] = []
    for sh in REPO_ROOT.joinpath("scripts").rglob("*.sh"):
        for rel in pat.findall(sh.read_text(encoding="utf-8", errors="replace")):
            target = REPO_ROOT / rel
            if target.is_file() and _git_mode(target) != "100755":
                offenders.append(f"{rel} ({_git_mode(target)}) guarded by {sh.name}")
    assert not offenders, (
        "these scripts are -x-guarded but not committed executable, so their "
        f"feature silently no-ops: {sorted(set(offenders))}"
    )


def test_bake_gui_fails_loudly_when_the_installer_is_unusable():
    """BAKE_GUI=1 + a missing/non-executable installer must FAIL, not skip."""
    body = PROVISION_BAKE.read_text(encoding="utf-8")
    assert "NOT EXECUTABLE" in body, (
        "provision-bake must detect and report a non-executable GUI installer"
    )
    assert "is MISSING from the image" in body, (
        "provision-bake must distinguish a missing installer from a "
        "non-executable one — the fixes are different"
    )
    # the precondition check must come BEFORE the block it protects
    assert body.index("NOT EXECUTABLE") < body.index("installing frontend on the image"), (
        "the usability check must run before the install block, or a skipped "
        "block is again indistinguishable from a disabled feature"
    )
    assert "desktop-installer-unusable" in body, (
        "an unusable installer must leave the same breadcrumb a failed install "
        "does, so a headless image is always explainable after the fact"
    )


def test_postinst_propagates_provision_bake_failure():
    """The caller must not discard provision-bake's exit code."""
    emit = MKOSI_EMIT.read_text(encoding="utf-8")
    assert 'provision-bake returned nonzero (non-fatal)' not in emit, (
        "the postinst must not swallow provision-bake's failure — that muffled "
        "even the exit 1 the 2026-07-25 directive added"
    )
    assert "provision-bake FAILED" in emit and "_pb_rc" in emit, (
        "the postinst must capture provision-bake's rc and fail the build with it"
    )


def test_provision_bake_still_checks_pipestatus():
    """The 2026-07-25 fix must stay: `| sed` must not mask the real rc."""
    body = PROVISION_BAKE.read_text(encoding="utf-8")
    assert "PIPESTATUS[0]" in body, (
        "the desktop install runs through `| sed`; without PIPESTATUS the "
        "if-branch tests sed's exit code and the failure arm never fires"
    )


def test_scripts_parse():
    for script in (PROVISION_BAKE, MKOSI_EMIT, GUI_INSTALLER):
        proc = subprocess.run(["bash", "-n", str(script)],
                              capture_output=True, text=True)
        assert proc.returncode == 0, f"{script.name}:\n{proc.stderr}"


def test_bake_gui_puts_the_desktop_in_the_image_package_list():
    """mkosi must install the desktop — the postinst chroot has no apt.

    After the exec-bit fix the installer finally RAN, and died at
    `apt-get: command not found` (rc=127): the appliance image ships no `apt`,
    so shelling apt-get inside the postinst chroot can never work. mkosi
    installs packages from Packages= using the HOST's apt against the
    buildroot, which is the only mechanism available here.
    """
    emit = MKOSI_EMIT.read_text(encoding="utf-8")
    assert "if bake_gui:" in emit, (
        "mkosi-emit must extend the image package list when a desktop is requested"
    )
    block = emit[emit.index("if bake_gui:"):]
    block = block[:block.index("if bake_dev_tools:")]
    for pkg in ("kde-plasma-desktop", "sddm", "gnome-core", "gdm3"):
        assert pkg in block, f"{pkg} must be mapped for its frontend"
    assert "all_packages.append(pkg)" in block, (
        "the frontend packages must be appended to the image package list"
    )


def test_gui_installer_never_bare_apt_gets():
    """Every package install must go through pkg_ensure.

    A bare `apt-get install` is fatal in the postinst chroot (no apt) — that is
    rc=127 and a headless image. pkg_ensure installs where apt exists and
    VERIFIES (via dpkg) where it does not, failing loudly if the packages are
    genuinely absent.
    """
    body = GUI_INSTALLER.read_text(encoding="utf-8")
    assert "pkg_ensure()" in body, "the helper must exist"
    # CODE only — the helper's own comments quote `apt-get install` to explain
    # why it is forbidden, and matching prose would be a false positive.
    code = "\n".join(
        line for line in body.splitlines() if not line.lstrip().startswith("#")
    )
    helper = code[code.index("pkg_ensure() {"):code.index('step "1/5')]
    outside = code.replace(helper, "")
    assert "apt-get install" not in outside, (
        "a bare apt-get install outside pkg_ensure will exit 127 in the image "
        "chroot and ship a headless image"
    )
    assert "dpkg-query" in helper, "the no-apt path must verify with dpkg"
    assert "return 1" in helper, (
        "genuinely missing packages with no installer must be a hard error"
    )
