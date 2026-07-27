"""One machine's GPU workarounds must not be welded into every ISO.

2026-07-27, operator: "would it install even if I wasn't on SAIN? I think I will
test with my other computer."

nomodeset and the amdgpu/nouveau blacklist were chosen for the sain-01 box,
where no GPU driver binds at all and they cost nothing. On different hardware
they are NOT neutral: nomodeset disables KMS, and blacklisting a driver that
would have bound turns a working accelerated desktop into a framebuffer one.
The machine still boots — it just looks broken for no reason.

installed-system.sh is the ONE definition of both, and both are overridable by
environment. build.sh now renders them into the WORK copy of the preseed, so a
different profile or machine produces a correct ISO without hand-editing a
preseed. The repo files keep the sain-01 values so they stay valid and
lint-checkable.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BUILD = REPO_ROOT / "scripts" / "build" / "installer-cdd" / "build.sh"
LIB = REPO_ROOT / "scripts" / "install" / "lib" / "installed-system.sh"
PROFILES = REPO_ROOT / "scripts" / "build" / "installer-cdd" / "profiles"


def test_the_build_renders_rather_than_ships_the_repo_values():
    body = BUILD.read_text(encoding="utf-8")
    assert "installed-system.sh" in body, (
        "build.sh must read the shared definition, not ship whatever the repo "
        "preseed happens to contain"
    )
    assert "add-kernel-opts" in body and "for m in" in body, (
        "both the kernel cmdline and the module blacklist must be rendered"
    )


def test_both_preseeds_are_rendered_not_just_the_profile_one():
    """default.preseed is the file d-i actually loads.

    sovereign.preseed is inert — it depends on the simple-cdd-profiles udeb that
    silently no-ops. Rendering only the profile preseed would change nothing at
    all on the path that runs.
    """
    body = BUILD.read_text(encoding="utf-8")
    assert "default.preseed" in body, (
        "default.preseed is the live file; rendering only ${PROFILE}.preseed "
        "leaves the actual install untouched"
    )


def test_the_repo_defaults_still_match_the_shared_definition():
    """The repo values are the fallback when rendering cannot run."""
    out = subprocess.run(
        ["bash", "-c", ". scripts/install/lib/installed-system.sh; "
                       'echo "${SOVEREIGN_OS_KERNEL_CMDLINE}|${SOVEREIGN_OS_MODULE_BLACKLIST}"'],
        capture_output=True, text=True, check=True, cwd=REPO_ROOT).stdout.strip()
    cmdline, blacklist = out.split("|")
    text = (PROFILES / "default.preseed").read_text(encoding="utf-8")
    m = re.search(r"^d-i debian-installer/add-kernel-opts string (.+)$", text, re.M)
    assert m and m.group(1).strip() == cmdline.strip(), (
        f"repo preseed says {m.group(1)!r}, shared definition says {cmdline!r}"
    )
    loop = re.search(r"for m in ([a-z0-9 _-]+); do echo blacklist", text)
    assert loop and loop.group(1).strip() == blacklist.strip(), (
        f"repo preseed blacklists {loop.group(1)!r}, definition says {blacklist!r}"
    )


def test_rendering_keeps_the_preseed_valid():
    """A sed that produces an unparseable preseed is worse than no rendering."""
    import shutil, tempfile
    if shutil.which("debconf-set-selections") is None:
        return
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d) / "t.preseed"
        tmp.write_text((PROFILES / "default.preseed").read_text(encoding="utf-8"),
                       encoding="utf-8")
        subprocess.run(
            ["sed", "-i",
             "-e", "s|^d-i debian-installer/add-kernel-opts string .*|"
                   "d-i debian-installer/add-kernel-opts string quiet splash|",
             "-e", "s|for m in [a-z0-9 _-]*; do echo blacklist|"
                   "for m in i915; do echo blacklist|",
             str(tmp)], check=True)
        out = subprocess.run(["debconf-set-selections", "--checkonly", str(tmp)],
                             capture_output=True, text=True)
        assert out.returncode == 0, f"rendered preseed is invalid:\n{out.stderr}"
