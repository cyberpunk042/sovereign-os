"""A long phase that prints nothing is indistinguishable from a hang.

2026-07-27, from the operator: "make sure we are not just stuck at work
happening behind the scene that could take a long time, or a loop".

Two places were silent:

  * build.sh piped build-simple-cdd through `| tail -60`. tail BUFFERS the whole
    run and prints only the tail at the end, so the mirror download — the
    longest phase of the build, ~25 minutes — showed nothing at all.
  * the cockpit postinst redirected install-gui-dashboards.sh (468 lines, doing
    apt work) into a log file, turning the longest phase of the INSTALL silent.
    That one was self-inflicted earlier the same day.

Buffering is the trap: `tail`, `sort`, and a plain `sed` all wait. `sed -u` and
`grep --line-buffered` do not.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CDD_BUILD = REPO_ROOT / "scripts" / "build" / "installer-cdd" / "build.sh"
# The cockpit .deb + its postinst moved to the shared builder on
# 2026-07-28 (the Ubuntu autoinstall substrate ships the identical
# package); read the postinst where it now lives.
COCKPIT_DEB = REPO_ROOT / "scripts" / "build" / "lib" / "cockpit-deb.sh"
PROFILES = REPO_ROOT / "scripts" / "build" / "installer-cdd" / "profiles"


def test_the_mirror_build_is_not_piped_into_a_buffering_filter():
    body = CDD_BUILD.read_text(encoding="utf-8")
    code = "\n".join(l for l in body.splitlines() if not l.lstrip().startswith("#"))
    # Anchor on the real INVOCATION (--dvd), not the `command -v` availability
    # check that also mentions the binary. Line-based, because a regex with a
    # greedy [^\n]* consumes the trailing backslash and never matches the
    # continuation lines — so it "found" only the first line and reported a
    # false failure (2026-07-27, my own lint, twice).
    lines = code.splitlines()
    start = next((i for i, l in enumerate(lines) if "build-simple-cdd --dvd" in l), None)
    assert start is not None, "build-simple-cdd --dvd invocation not found"
    chunk, i = [], start
    while True:
        chunk.append(lines[i])
        if not lines[i].rstrip().endswith("\\"):
            break
        i += 1
    invocation = "\n".join(chunk)
    for buffering in ("| tail", "| sort", "| head"):
        assert buffering not in invocation, (
            f"build-simple-cdd is piped through {buffering!r}, which buffers the "
            "entire run — the operator sees nothing for ~25 minutes"
        )
    assert "sed -u" in invocation or "--line-buffered" in invocation, (
        "stream the output unbuffered so a long phase is visibly progressing"
    )


def test_the_mirror_build_reports_how_long_it_took():
    body = CDD_BUILD.read_text(encoding="utf-8")
    assert "finished in" in body, (
        "report elapsed time — it is the difference between 'slow' and 'hung' "
        "the next time someone waits on it"
    )


def test_the_dashboards_deploy_streams_during_install():
    """It moved out of the postinst — apt under dpkg deadlocks on the dpkg lock,
    which Debian Policy forbids — into late_command via deploy-dashboards.sh."""
    deploy = REPO_ROOT / "scripts" / "install" / "deploy-dashboards.sh"
    assert deploy.exists() and deploy.stat().st_mode & 0o111
    body = deploy.read_text(encoding="utf-8")
    assert "/dev/tty4" in body, (
        "the deploy must stream to d-i's log console; redirecting it into a "
        "file makes the longest phase of the install look like a hang"
    )
    assert "tee" in body, "keep the log AND show it live"


def test_apt_is_never_called_from_a_maintainer_script():
    """dpkg holds its lock while running maintainer scripts.

    install-gui-dashboards.sh calls apt-get. Running it from the cockpit
    postinst meant its first pkg_ensure would fail on the dpkg lock, so the
    cockpit never landed — silently, because the deploy was best-effort
    (2026-07-27).
    """
    body = COCKPIT_DEB.read_text(encoding="utf-8")
    post = body[body.index("DEBIAN/postinst"):body.index("\nPOSTINST")]
    code = "\n".join(l for l in post.splitlines() if not l.lstrip().startswith("#"))
    assert "install-gui-dashboards.sh" not in code, (
        "the postinst must not run a script that calls apt-get; dpkg holds the "
        "lock while maintainer scripts run"
    )
    for direct in ("apt-get ", "apt-cache ", "aptitude "):
        assert direct not in code, f"postinst calls {direct.strip()!r} under dpkg"


def test_the_install_announces_each_step():
    """d-i shows one progress bar for the whole late_command."""
    text = (PROFILES / "default.preseed").read_text(encoding="utf-8")
    labels = re.findall(r'echo "sovereign: ([^"]+)"', text)
    assert len(labels) >= 5, (
        f"only {len(labels)} step(s) announce themselves; a multi-minute "
        "late_command should say what it is doing"
    )
    assert len(labels) == len(set(labels)), f"duplicate labels: {labels}"


def test_no_unbounded_device_walk_can_hang():
    """The disk-resolution walkers loop until no parent remains."""
    for rel in ("scripts/operator/flash-api.py",):
        body = (REPO_ROOT / rel).read_text(encoding="utf-8")
        fn = body[body.index("def _parent_disk"):body.index("def protected_disks")]
        assert "range(" in fn, f"{rel}: the device walk must be bounded"


WALKERS = ("scripts/install/install-sovereign-root.sh",
           "scripts/install/setup-lvm-dualboot.sh",
           "scripts/hooks/decommission/secure-wipe.sh",
           "scripts/hooks/during-install/rootfs-format-ext4.sh")


@pytest.mark.parametrize("rel", WALKERS)
def test_the_shell_device_walkers_are_bounded(rel: str):
    """`while :; do` with no counter can spin forever, as root, mid-install.

    The Python twin in flash-api.py was capped at 16 hops and had a lint saying
    so; the four SHELL copies were written as unbounded loops. A device whose
    PKNAME resolves to itself — or any cycle — never terminates (2026-07-27).
    """
    body = (REPO_ROOT / rel).read_text(encoding="utf-8")
    if "_parent_disk_of" not in body:
        return
    fn = body[body.index("_parent_disk_of() {"):]
    fn = fn[:fn.index("\n}\n") + 3]
    # Read CODE, not comments. The fix's own comment quotes the `while :; do`
    # it removed — five lints this session tripped on their own prose, so
    # stripping comments is the default now, not an afterthought.
    fn = "\n".join(l for l in fn.splitlines() if not l.lstrip().startswith("#"))
    assert "while :;" not in fn, (
        f"{rel}: the device walk is unbounded; a cyclic device tree hangs the "
        "installer with no output at all"
    )
    assert "_hops" in fn and "-lt" in fn, f"{rel}: no hop counter found"


@pytest.mark.parametrize("rel", (
    "scripts/hooks/post-install/openclaw-install.sh",
    "scripts/hooks/post-install/open-computer-install.sh",
))
def test_package_installs_at_first_boot_are_not_silenced(rel: str):
    """These fetch node/qemu — minutes of download with nothing on screen.

    `apt-get install ... >/dev/null 2>&1` at first boot is indistinguishable
    from a hung service.
    """
    for line in (REPO_ROOT / rel).read_text(encoding="utf-8").splitlines():
        if "apt-get install" in line and not line.lstrip().startswith("#"):
            assert ">/dev/null" not in line, (
                f"{rel}: silenced package install: {line.strip()!r}"
            )
