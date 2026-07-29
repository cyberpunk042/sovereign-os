"""Every substrate builder must resolve the custom kernel .debs identically.

2026-07-29. The two installer builders each hardcoded a fallback, and the two
fallbacks DISAGREED:

    installer-cdd/build.sh       /mnt/kernel_forge/kernel-debs
    ubuntu-autoinstall/build.sh  /mnt/kernel_forge          <- missing suffix

Neither path exists on the operator's machine. The Debian build worked only
because step 07 sources step 04's state file before invoking it; running either
builder DIRECTLY failed — and the Ubuntu one failed with a path that was wrong
in a second, independent way, so the two failures did not even look alike.

A default that is only ever correct because some caller overrides it is not a
default, it is a trap. The authority is step 04, which writes
${SOVEREIGN_OS_STATE_DIR}/env-kernel-debs.sh; lib/kernel-debs.sh is the one
resolver that consults it.
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
RESOLVER = REPO_ROOT / "scripts/build/lib/kernel-debs.sh"
BUILDERS = {
    "installer-cdd": REPO_ROOT / "scripts/build/installer-cdd/build.sh",
    "ubuntu-autoinstall": REPO_ROOT / "scripts/build/ubuntu-autoinstall/build.sh",
    # build-readiness REPORTS on the kernel .debs, so it must look in the
    # same place. It had its own `${SOVEREIGN_OS_FORGE_DIR}` default and
    # announced "no custom kernel .debs in /mnt/kernel_forge" on a machine
    # that had them — sending the operator off to rebuild a kernel that was
    # already there (2026-07-29). A reporter that lies is worse than none.
    "build-readiness": REPO_ROOT / "scripts/build/build-readiness.sh",
}


def test_the_resolver_exists():
    assert RESOLVER.is_file(), (
        "scripts/build/lib/kernel-debs.sh must exist — it is the single "
        "resolution order for the custom kernel .debs"
    )


@pytest.mark.parametrize("name", sorted(BUILDERS))
def test_each_builder_uses_the_shared_resolver(name):
    body = BUILDERS[name].read_text(encoding="utf-8")
    assert "kernel-debs.sh" in body and "kernel_debs_dir" in body, (
        f"{name}/build.sh must resolve the kernel .debs through "
        "lib/kernel-debs.sh, not with its own fallback path"
    )


@pytest.mark.parametrize("name", sorted(BUILDERS))
def test_no_builder_hardcodes_a_kernel_debs_fallback(name):
    """The specific shape of the bug: a `${VAR:-/some/path}` default."""
    body = BUILDERS[name].read_text(encoding="utf-8")
    code = "\n".join(
        l for l in body.splitlines() if not l.lstrip().startswith("#")
    )
    m = re.search(r"SOVEREIGN_OS_KERNEL_DEBS_DIR:-([^}]+)\}", code)
    assert not m, (
        f"{name}/build.sh hardcodes a kernel-debs fallback ({m.group(1)!r}). "
        "That is how the two builders came to disagree, and how both came to "
        "point at a directory that does not exist. Use kernel_debs_dir()."
    )


def test_the_resolver_prefers_the_state_file_written_by_step_04(tmp_path):
    """Step 04 is the authority; a stale default must never outrank it."""
    state = tmp_path / "state"
    state.mkdir()
    (state / "env-kernel-debs.sh").write_text(
        'export SOVEREIGN_OS_KERNEL_DEBS_DIR="/proof/from/state-file"\n'
    )
    env = {
        "PATH": "/usr/bin:/bin", "HOME": str(tmp_path),
        "SOVEREIGN_OS_STATE_DIR": str(state),
    }
    out = subprocess.run(
        ["sh", "-c", f'. {RESOLVER}; kernel_debs_dir'],
        capture_output=True, text=True, env=env, cwd=REPO_ROOT,
    )
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "/proof/from/state-file", (
        f"the resolver ignored step 04's state file, got {out.stdout.strip()!r}"
    )


def test_an_explicit_environment_override_still_wins(tmp_path):
    """The operator's own value outranks everything, including the state file."""
    state = tmp_path / "state"
    state.mkdir()
    (state / "env-kernel-debs.sh").write_text(
        'export SOVEREIGN_OS_KERNEL_DEBS_DIR="/from/state"\n'
    )
    out = subprocess.run(
        ["sh", "-c", f'. {RESOLVER}; kernel_debs_dir'],
        capture_output=True, text=True, cwd=REPO_ROOT,
        env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path),
             "SOVEREIGN_OS_STATE_DIR": str(state),
             "SOVEREIGN_OS_KERNEL_DEBS_DIR": "/operator/said/so"},
    )
    assert out.stdout.strip() == "/operator/said/so", out.stdout


def test_it_names_a_real_location_when_nothing_is_found(tmp_path):
    """The error message must send the operator somewhere that makes sense.

    Returning /mnt/kernel_forge on a machine that has never had such a mount
    tells them nothing about where the forge actually puts its output.
    """
    out = subprocess.run(
        ["sh", "-c", f'. {RESOLVER}; kernel_debs_dir'],
        capture_output=True, text=True, cwd=REPO_ROOT,
        env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path),
             "SOVEREIGN_OS_STATE_DIR": str(tmp_path / "nope")},
    )
    got = out.stdout.strip()
    assert got.endswith("/kernel-forge/kernel-debs"), (
        f"with nothing found the resolver should name the canonical forge "
        f"output dir, got {got!r}"
    )
    assert str(tmp_path) in got, (
        "it should be under the invoking user's home, not a /mnt path they "
        f"have never had, got {got!r}"
    )


# build-readiness only REPORTS; refusing is the builders' job, and a readiness
# check that exits non-zero on a warning would be useless.
ACTUAL_BUILDERS = [n for n in BUILDERS if n != "build-readiness"]


@pytest.mark.parametrize("name", sorted(ACTUAL_BUILDERS))
def test_each_builder_still_refuses_without_the_debs(name):
    """Resolving a path is not the same as finding the files.

    Both builders must FAIL EARLY. The Debian one once warned "the install will
    use the stock kernel" and continued — but linux-image-6.12.0 is a REQUIRED
    entry, so it downloaded a whole mirror and then died anyway (2026-07-27).
    """
    body = BUILDERS[name].read_text(encoding="utf-8")
    assert "Refusing now rather than after" in body, (
        f"{name}/build.sh must refuse before the expensive step when the "
        "kernel .debs are absent"
    )
    assert re.search(r"linux-image-6\.12\.0.*\.deb", body), (
        f"{name}/build.sh must check for the actual .deb, not just the dir"
    )


def test_the_readiness_reporter_warns_rather_than_blocking():
    """A missing kernel is a WARNING for the appliance, a blocker for neither.

    The installers require the .debs and refuse; the mkosi appliance can fall
    back to the substrate's stock kernel. Reporting it as a hard blocker would
    stop a build that would have succeeded.
    """
    body = BUILDERS["build-readiness"].read_text(encoding="utf-8")
    start = body.index("check_kernel() {")
    seg = body[start: body.index("\n}\n", start)]
    assert "warn " in seg, (
        "check_kernel must be able to WARN — the appliance survives without "
        "the custom kernel"
    )
