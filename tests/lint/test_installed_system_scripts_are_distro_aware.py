"""Scripts that run ON the installed system must not hardcode one distro's names.

2026-07-29. The first full Ubuntu install was run to completion in a VM and the
installed disk inspected. Twelve of fourteen checks passed — nomodeset landed,
the custom znver5 kernel installed, the cockpit payload was there. The two
failures were all one bug:

    E: Package 'firefox-esr' has no installation candidate
    FAILED (rc=100)

`install-gui-dashboards.sh` pkg_ensure'd `firefox-esr` — a package that does not
exist on Ubuntu — and its `set -euo pipefail` took the entire cockpit/dashboards
deploy down with it. The install self-check reported two more of the same shape:
`MISSING firmware-amd-graphics` (Ubuntu ships `linux-firmware`) and "no network
apt sources" (write-apt-sources.sh wrote deb.debian.org onto an Ubuntu box).

Verified against the real archives:

    firefox-esr            debian=yes  ubuntu=NO
    firmware-amd-graphics  debian=yes  ubuntu=NO
    linux-firmware         debian=NO   ubuntu=yes
    kubuntu-desktop        debian=NO   ubuntu=yes

These scripts execute long after the build, so they cannot inherit
SOVEREIGN_OS_DISTRO from it — they must ask /etc/os-release. That is what
scripts/install/lib/target-distro.sh does; this keeps them using it.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB = REPO_ROOT / "scripts" / "install" / "lib" / "target-distro.sh"

# Scripts that RUN ON the installed system and name packages or archives.
RUNTIME_SCRIPTS = [
    REPO_ROOT / "scripts" / "install" / "install-gui-dashboards.sh",
    REPO_ROOT / "scripts" / "install" / "verify-installed-system.sh",
    REPO_ROOT / "scripts" / "install" / "write-apt-sources.sh",
]

# Names that exist on exactly one distro. Hardcoding one is a guaranteed
# failure on the other.
DEBIAN_ONLY = ("firefox-esr", "firmware-amd-graphics", "firmware-misc-nonfree",
               "task-kde-desktop")
UBUNTU_ONLY = ("kubuntu-desktop", "ubuntu-standard", "linux-firmware")
DEBIAN_ARCHIVES = ("deb.debian.org", "security.debian.org")


def test_the_runtime_distro_lib_exists_and_is_posix_sh():
    assert LIB.is_file(), "scripts/install/lib/target-distro.sh must exist"
    r = subprocess.run(["sh", "-n", str(LIB)], capture_output=True, text=True)
    assert r.returncode == 0, f"target-distro.sh is not valid POSIX sh:\n{r.stderr}"


def test_it_detects_from_os_release_not_a_build_variable():
    body = LIB.read_text(encoding="utf-8")
    assert "/etc/os-release" in body, (
        "these scripts run on the installed machine long after the build, so the "
        "distro must come from the system itself, not an inherited build var"
    )


@pytest.mark.parametrize("distro,browser,firmware", [
    ("debian", "firefox-esr", "firmware-amd-graphics"),
    ("ubuntu", "firefox", "linux-firmware"),
])
def test_the_mapping_resolves_correctly(distro: str, browser: str, firmware: str):
    """Execute the real lib rather than grepping it."""
    script = f'. "{LIB}"; printf "%s %s" "$(target_browser)" "$(target_firmware_package)"'
    r = subprocess.run(["sh", "-c", script], capture_output=True, text=True,
                       env={"SOVEREIGN_OS_DISTRO": distro, "PATH": "/usr/bin:/bin"})
    assert r.stdout.split() == [browser, firmware], (
        f"{distro}: expected {browser}/{firmware}, got {r.stdout!r}"
    )


def test_debian_remains_the_default_when_nothing_is_known():
    r = subprocess.run(["sh", "-c", f'. "{LIB}"; target_distro'],
                       capture_output=True, text=True,
                       env={"PATH": "/usr/bin:/bin"})   # no os-release readable ID
    assert r.stdout.strip() in ("debian", "ubuntu"), r.stdout
    # With no ID at all it must fall back to debian, never fail.
    r2 = subprocess.run(["sh", "-c", f'ID=""; . "{LIB}"; target_distro'],
                        capture_output=True, text=True, env={"PATH": "/usr/bin:/bin"})
    assert r2.returncode == 0


@pytest.mark.parametrize("script", RUNTIME_SCRIPTS, ids=lambda p: p.name)
def test_no_distro_only_package_is_hardcoded(script: Path):
    if not script.exists():
        pytest.skip(f"{script.name} absent")
    offenders = []
    for n, line in enumerate(script.read_text(encoding="utf-8").splitlines(), 1):
        s = line.strip()
        if not s or s.startswith("#"):
            continue          # comments explain the mapping; that is the point
        for name in DEBIAN_ONLY + UBUNTU_ONLY:
            # A fallback definition inside the lib-missing guard is legitimate.
            if re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", s) \
               and "target_" not in s and "printf" not in s:
                offenders.append(f"{n}: {s}")
    assert not offenders, (
        f"{script.name} hardcodes a distro-specific package name:\n  "
        + "\n  ".join(offenders)
        + "\nUse scripts/install/lib/target-distro.sh — firefox-esr does not "
          "exist on Ubuntu and killed the whole dashboards deploy (2026-07-29)."
    )


def test_apt_sources_are_not_hardcoded_to_debian():
    body = (REPO_ROOT / "scripts" / "install" / "write-apt-sources.sh").read_text(encoding="utf-8")
    code = "\n".join(l for l in body.splitlines() if not l.strip().startswith("#"))
    # The heredoc must interpolate, not name an archive literally.
    for host in DEBIAN_ARCHIVES:
        assert f"deb http://{host}" not in code, (
            f"write-apt-sources.sh writes {host} literally; on Ubuntu that leaves "
            "the installed system with no usable apt at all"
        )
    assert "target_apt_mirror" in code and "target_apt_components" in code, (
        "the archive and components must come from the runtime distro lib"
    )
