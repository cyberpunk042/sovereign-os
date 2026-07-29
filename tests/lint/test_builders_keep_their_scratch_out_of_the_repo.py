"""An ISO builder's scratch directory must live OUTSIDE the checkout.

2026-07-29, the first real Ubuntu build. `ubuntu-autoinstall/build.sh` set

    WORK="${HERE}/tmp"          # = <repo>/scripts/build/ubuntu-autoinstall/tmp

and `build_cockpit_deb` copies `${REPO}/scripts` into
`${WORK}/cockpit-pkg/opt/sovereign-os/`. That destination is INSIDE the source,
so cp refused outright:

    cp: cannot copy a directory, '.../scripts', into itself,
        '.../scripts/build/ubuntu-autoinstall/tmp/cockpit-pkg/opt/sovereign-os/scripts'

installer-cdd already had this right — `WORK="${SOVEREIGN_OS_CDD_WORK:-/var/tmp/sovereign-cdd}"`
— and its comments even explain that simple-cdd's own scratch landing inside the
repo caused reprepro collisions. The Ubuntu builder copied the comment's shape
and not its conclusion.

Two independent reasons this rule holds:
  * the cockpit .deb packages the repo, so scratch inside the repo is a
    directory copied into itself — a hard failure, not a slowdown;
  * a 6 GB ISO remaster plus a multi-GB package pool has no business in a git
    working tree (the cockpit builder already guards its payload at 200 MB).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
BUILDERS = sorted(
    p for p in REPO_ROOT.glob("scripts/build/*/build.sh") if p.is_file()
)


def test_builders_were_found():
    assert BUILDERS, "no scripts/build/*/build.sh found — has the layout changed?"


@pytest.mark.parametrize("builder", BUILDERS, ids=lambda p: p.parent.name)
def test_scratch_dir_is_outside_the_repo(builder: Path):
    body = builder.read_text(encoding="utf-8")
    m = re.search(r'^WORK="([^"]+)"', body, re.M)
    assert m, f"{builder.parent.name}/build.sh must define WORK="
    work = m.group(1)
    # Accept an env override with an absolute default: ${VAR:-/abs/path}
    default = re.sub(r"^\$\{[A-Z_]+:-(.*)\}$", r"\1", work)
    assert not default.startswith("${HERE}"), (
        f"{builder.parent.name}/build.sh puts its scratch at {work!r}, inside the "
        "checkout. build_cockpit_deb copies ${REPO}/scripts into "
        "${WORK}/cockpit-pkg/... — a directory copied into itself, which cp "
        "refuses. Use an absolute path outside the repo, as installer-cdd does."
    )
    assert default.startswith("/"), (
        f"{builder.parent.name}/build.sh scratch {work!r} must resolve to an "
        "absolute path outside the repo"
    )


@pytest.mark.parametrize("builder", BUILDERS, ids=lambda p: p.parent.name)
def test_scratch_is_operator_overridable(builder: Path):
    """Different hosts have different roomy filesystems; let them choose."""
    body = builder.read_text(encoding="utf-8")
    m = re.search(r'^WORK="([^"]+)"', body, re.M)
    assert m and m.group(1).startswith("${SOVEREIGN_OS_"), (
        f"{builder.parent.name}/build.sh must let the operator relocate scratch "
        "via a SOVEREIGN_OS_* env var with an absolute default"
    )


def test_the_cockpit_payload_is_still_size_guarded():
    """The reason scratch-in-repo was survivable elsewhere: this guard.

    build_cockpit_deb refuses a payload over 200 MB, which is what stopped a
    multi-GB mirror from being packaged into the .deb when installer-cdd's
    scratch did briefly live in the tree.
    """
    lib = (REPO_ROOT / "scripts" / "build" / "lib" / "cockpit-deb.sh").read_text(encoding="utf-8")
    assert re.search(r"_cksz.*-lt 200|200.*cockpit payload", lib), (
        "the cockpit .deb builder must keep its payload-size guard"
    )


# ── simple-cdd's scratch specifically (2026-07-29) ──────────────────────────

CDD_BUILD = REPO_ROOT / "scripts/build/installer-cdd/build.sh"


def test_simple_cdd_temp_is_pointed_out_of_the_checkout():
    """simple_cdd_temp defaults to ${simple_cdd_dir}/tmp — inside the repo.

    simple_cdd_dir must stay ${HERE}, because that is where find_profile_files()
    looks for profiles/*.{preseed,packages,conf}. But simple_cdd_temp is an
    INDEPENDENT variable (simple_cdd/variables.py:9), and simple_cdd_mirror,
    simple_cdd_logs and simple_cdd_basedir all derive from it — so setting it
    moves the whole scratch tree.

    A completed build left 4.0 GB in 10,081 files under
    scripts/build/installer-cdd/tmp/. Gitignored, so `git status` stayed clean
    and nothing complained — but every repo-walking lint traverses it and the
    lint sweep slowed to roughly triple its usual time. Editors and greps pay
    the same tax.
    """
    body = CDD_BUILD.read_text(encoding="utf-8")
    code = "\n".join(l for l in body.splitlines() if not l.lstrip().startswith("#"))
    assert "simple_cdd_temp=" in code, (
        "installer-cdd/build.sh must set simple_cdd_temp, or simple-cdd writes "
        "multi-GB scratch into the git checkout"
    )
    line = next(l for l in code.splitlines() if l.strip().startswith("simple_cdd_temp="))
    assert "${HERE}" not in line, (
        f"simple_cdd_temp still resolves inside the checkout: {line.strip()!r}"
    )
    assert "CDD_TMP" in line or "/var/tmp" in line or "${WORK}" in line, (
        f"simple_cdd_temp must point outside the repo, got {line.strip()!r}"
    )


def test_the_legacy_in_repo_scratch_is_cleaned_up():
    """A tree built before the fix still has the old directory.

    Leaving it means the slowdown persists for anyone who built once with the
    old layout, and they would have no reason to suspect it.
    """
    body = CDD_BUILD.read_text(encoding="utf-8")
    assert 'rm -rf "${HERE}/tmp"' in body, (
        "build.sh should remove a pre-2026-07-29 in-repo scratch tree if it "
        "finds one, so an existing checkout heals itself on the next build"
    )
