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
