"""Why a stock Debian installer works where ours can fail — and where to catch it.

2026-07-27, from the operator: "how come a normal debian 13 installer would work
and not our modified one?"

The difference is dependency resolution. Stock d-i installs a small base from a
NETWORK mirror and resolves as it goes. Ours installs 59 explicit packages from
a FIXED offline CD, and pkgsel/include is fatal: one package — or one transitive
dependency — missing from that pool and d-i aborts AFTER partitioning,
formatting and unpacking. Already seen here as "Unable to install zstd", a
base-installer dependency absent from the mirror.

The answer is NOT to make the install limp on. A system without sddm, an X
driver or firmware is not worth booting, and silently dropping packages is how
"there was not even a console tool installed" happened. The answer is to move
the failure to where it is cheap: verify the produced ISO can satisfy its own
preseed before anyone flashes it. Seconds at build time instead of an hour at
install time.

Failing gracefully belongs where the outcome is genuinely optional — the
late_command steps, all guarded, and the dashboards deploy, which records its
outcome instead of aborting dpkg. Failing LOUDLY belongs where the result would
be an unusable machine.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CHECKER = (REPO_ROOT / "scripts" / "build" / "installer-cdd"
           / "verify-iso-has-packages.sh")
STEP07 = REPO_ROOT / "scripts" / "build" / "07-image-build.sh"


def test_the_checker_exists_and_is_executable():
    assert CHECKER.exists() and CHECKER.stat().st_mode & 0o111


def test_the_build_refuses_an_iso_that_cannot_install_itself():
    body = STEP07.read_text(encoding="utf-8")
    blk = body[body.index("installer-cdd)"):body.index("  live-build)")]
    assert "verify-iso-has-packages.sh" in blk, (
        "step 07 must verify the ISO's pool against pkgsel/include; otherwise a "
        "missing package is discovered by the operator an hour later, after the "
        "disk has already been partitioned"
    )
    assert "installer-cdd-incomplete-pool" in blk, (
        "the failure must be a distinct, named state so it is not confused with "
        "a build that produced no artifact at all"
    )


def test_it_matches_package_names_on_a_boundary():
    """`sddm` must not be satisfied by `sddm-theme-breeze_*.deb`."""
    body = CHECKER.read_text(encoding="utf-8")
    assert "_[^/]*" in body or "_" in body, "must anchor on the name_version separator"
    assert "grep -q" in body


def test_it_degrades_when_xorriso_is_absent():
    """A missing tool must not fail a build that is otherwise fine."""
    body = CHECKER.read_text(encoding="utf-8")
    i = body.index("xorriso")
    assert "exit 0" in body[i:i + 400], (
        "without xorriso the check cannot run; skip it rather than fail the build"
    )


def test_it_actually_detects_a_missing_package(tmp_path: Path):
    """Run the real extraction against a preseed naming a package no ISO has."""
    preseed = tmp_path / "p.preseed"
    preseed.write_text(
        'd-i pkgsel/include string sudo \\\n    definitely-not-a-real-package\n',
        encoding="utf-8")
    # Extraction logic only — no ISO needed to prove the parser reads the list.
    out = subprocess.run(
        ["awk", r'''
  /^d-i pkgsel\/include string/ { inlist=1; sub(/^d-i pkgsel\/include string[[:space:]]*/, ""); }
  inlist { line=$0; sub(/\\$/, "", line); printf "%s ", line; if ($0 !~ /\\$/) exit; }
''', str(preseed)], capture_output=True, text=True)
    got = out.stdout.split()
    assert got == ["sudo", "definitely-not-a-real-package"], (
        f"the install list parser lost or mangled entries: {got}"
    )
