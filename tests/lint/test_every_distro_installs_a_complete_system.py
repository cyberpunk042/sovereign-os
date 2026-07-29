"""Every distro must install a COMPLETE system — standard utilities and the AI tier.

Operator directive, 2026-07-28:

  "its important in all versions / distros too that we install 'standard system
   utilities' too."
  "lets not minimize the kernel work too and the preparation in general for
   Ubuntu 26, we want the best AI experience"

Two gaps this locks shut, both found on the same day:

1. STANDARD SYSTEM UTILITIES. The preseed selected only `kde-desktop`, while a
   stock Debian install also selects `standard`. The installed box was missing
   30 Priority:standard packages — dbus, openssh-client, perl, xz-utils, bzip2,
   systemd-timesyncd, ncurses-term, traceroute, manpages. Several arrive
   transitively through the KDE task; depending on that is luck. Subiquity has
   no tasksel, so Ubuntu's analogue is the `ubuntu-standard` seed metapackage.

2. THE AI TIER COULD NOT BUILD ITS DRIVER. nvidia-driver-install.sh runs the
   NVIDIA .run installer with `--dkms`, which needs dkms + a compiler + the
   running kernel's headers ON THE TARGET. Neither distro installed dkms or
   build-essential — and the install is OFFLINE, so first boot could not apt
   them either. The module build would fail and the Oracle/inference tier would
   never come up. Same for python3-pip/venv and the model toolchain.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

REPO_ROOT = Path(__file__).resolve().parents[2]
PRESEEDS = sorted((REPO_ROOT / "scripts" / "build" / "installer-cdd" / "profiles").glob("*.preseed"))
MIRROR = REPO_ROOT / "scripts" / "build" / "installer-cdd" / "profiles" / "sovereign.packages"
UBUNTU = REPO_ROOT / "scripts" / "build" / "ubuntu-autoinstall" / "autoinstall" / "user-data"
KCONFIG = REPO_ROOT / "scripts" / "build" / "03-kernel-config.sh"

# Needed on the TARGET for the AI tier to come up on an offline first boot.
AI_TIER = ("dkms", "build-essential", "python3-pip", "python3-venv")


def debian_install_list() -> set[str]:
    text = (REPO_ROOT / "scripts" / "build" / "installer-cdd" / "profiles" / "default.preseed").read_text(encoding="utf-8")
    m = re.search(r"d-i pkgsel/include string (.+?)(?=\nd-i |\n###|\npopularity)", text, re.S)
    assert m, "could not read pkgsel/include"
    return set(m.group(1).replace("\\\n", " ").split())


def ubuntu_install_list() -> set[str]:
    return set(yaml.safe_load(UBUNTU.read_text(encoding="utf-8"))["autoinstall"]["packages"])


@pytest.mark.parametrize("preseed", PRESEEDS, ids=lambda p: p.name)
def test_debian_selects_the_standard_task_not_just_the_desktop(preseed: Path):
    m = re.search(r"^tasksel tasksel/first multiselect (.+)$",
                  preseed.read_text(encoding="utf-8"), re.M)
    assert m, f"{preseed.name} has no tasksel selection"
    tasks = {t.strip() for t in m.group(1).split(",")}
    assert "standard" in tasks, (
        f"{preseed.name} selects {sorted(tasks)} but not 'standard'. A stock "
        "Debian install selects \"standard system utilities\" by default; without "
        "it the box lacks dbus, openssh-client, perl, xz-utils, bzip2, "
        "systemd-timesyncd and ~25 more that every ordinary Debian has."
    )


def test_ubuntu_installs_the_standard_seed():
    """Subiquity has no tasksel — ubuntu-standard is the equivalent."""
    assert "ubuntu-standard" in ubuntu_install_list(), (
        "the Ubuntu autoinstall must install ubuntu-standard, the analogue of "
        "Debian's 'standard system utilities' task; without it autoinstall "
        "lands a minimal system"
    )


def test_the_cd_pool_carries_the_standard_packages():
    """tasksel can only install what an OFFLINE CD actually holds."""
    pool = {l.strip() for l in MIRROR.read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.strip().startswith("#")}
    # A representative slice of Priority:standard — if these are absent the pool
    # was not refreshed and the task will fail to resolve offline.
    for p in ("openssh-client", "xz-utils", "bzip2", "dbus", "perl"):
        assert p in pool, (
            f"{p} (Priority: standard) is not mirrored onto the CD, so selecting "
            "the standard task cannot succeed on an offline install"
        )


@pytest.mark.parametrize("pkg", AI_TIER)
def test_both_distros_can_build_the_gpu_driver_and_run_the_model_toolchain(pkg: str):
    for name, have in (("debian", debian_install_list()), ("ubuntu", ubuntu_install_list())):
        assert pkg in have, (
            f"{name} does not install {pkg!r}. nvidia-driver-install.sh builds the "
            "module with --dkms on first boot, offline — without dkms and a "
            "compiler the build fails and the inference tier never starts."
        )


def test_the_kernel_seed_is_distro_aware():
    """Seeding an Ubuntu kernel from a Debian host config must not pass silently.

    The seed decides thousands of symbols the profile never names. Debian and
    Ubuntu differ on LSM/apparmor/module-signing defaults, so a cross-distro
    seed yields a kernel matching neither stock config.
    """
    body = KCONFIG.read_text(encoding="utf-8")
    assert "SOVEREIGN_OS_KERNEL_SEED_CONFIG" in body, (
        "step 03 must let the operator choose the seed config explicitly"
    )
    assert "CROSS-DISTRO KERNEL SEED" in body, (
        "step 03 must WARN when the build host's distro differs from the target's"
    )
    assert "SOVEREIGN_OS_DISTRO" in body, (
        "step 03 must compare against the TARGET distro, not assume the host's"
    )


def test_the_custom_kernel_is_not_debian_only():
    """'Do not minimize the kernel work' — it must build for either target.

    kernel.source=kernel.org-stable + bindeb-pkg is distro-agnostic by design;
    a distro-specific fork of the kernel path would be a regression.
    """
    prof = yaml.safe_load((REPO_ROOT / "profiles" / "sain-01.yaml").read_text(encoding="utf-8"))
    k = prof["kernel"]
    assert k["source"] == "kernel.org-stable", (
        "the custom kernel must come from kernel.org so it is identical on both "
        "distros; a distro kernel would fork the AI stack's ABI per distro"
    )
    assert "znver5" in k["compile_flags"]["KCFLAGS"], (
        "the Zen 5 tuning is hardware-derived and must apply on every distro"
    )
    assert "ubuntu 26.04" in " ".join(prof["lifecycle"]["supported_distro"]).lower()
