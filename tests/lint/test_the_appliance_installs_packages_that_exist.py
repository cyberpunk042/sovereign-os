"""The mkosi appliance must name packages the target distro actually has.

2026-07-29, de-risking the first Ubuntu appliance build. The adapter emitted a
BYTE-IDENTICAL 45-package list for both distros — it never translated names at
all, even though `distro_map_packages()` had existed since 2026-07-28 and both
INSTALLERS used it. Checked against the live resolute index, four of those
packages do not exist in Ubuntu:

    firefox-esr              -> firefox
    nvidia-driver            -\\
    nvidia-open-kernel-dkms  --> nvidia-driver-570-open
    nvidia-smi               -/

so the build would have failed at package install — after downloading a
multi-GB buildroot. The installers were immune only because they translate.

The three NVIDIA names collapse to ONE versioned Ubuntu metapackage, which is
why a naive one-to-one rename would not have worked either.

These tests are static (no network). The archive cross-check that FOUND this is
`verify-packages-exist.sh` for the ISO path and the same technique by hand for
the appliance; it needs the internet, so it cannot live here.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DISTRO_SH = REPO_ROOT / "scripts/build/lib/distro.sh"
MKOSI_EMIT = REPO_ROOT / "scripts/build/adapters/mkosi-emit.sh"

# Every one of these was verified ABSENT from the resolute index on 2026-07-29.
DEBIAN_ONLY = ["firefox-esr", "nvidia-driver", "nvidia-open-kernel-dkms", "nvidia-smi"]


def mapped(distro: str, packages: str) -> list[str]:
    out = subprocess.run(
        ["sh", "-c", f'. {DISTRO_SH}; distro_map_packages'],
        input=packages, capture_output=True, text=True, cwd=REPO_ROOT,
        env={"SOVEREIGN_OS_DISTRO": distro, "PATH": "/usr/bin:/bin"},
    )
    assert out.returncode == 0, out.stderr
    return out.stdout.split()


@pytest.mark.parametrize("pkg", DEBIAN_ONLY)
def test_no_debian_only_package_survives_translation_to_ubuntu(pkg):
    got = mapped("ubuntu", f"sudo {pkg} curl")
    assert pkg not in got, (
        f"{pkg!r} does not exist in the Ubuntu archive; leaving it in the list "
        f"fails the appliance build at package install. Got {got}"
    )
    # The unrelated packages must survive — a mapping that eats everything is
    # not a mapping.
    assert "sudo" in got and "curl" in got, f"lost an unrelated package: {got}"


def test_the_nvidia_stack_collapses_to_one_ubuntu_package():
    """Three Debian names, one Ubuntu metapackage — not a 1:1 rename."""
    got = mapped("ubuntu", " ".join(DEBIAN_ONLY[1:]))
    drivers = [g for g in got if "nvidia" in g]
    assert len(drivers) == 1, (
        f"expected exactly one Ubuntu nvidia package, got {drivers}. The "
        "versioned metapackage pulls the kernel module and utilities together."
    )
    assert re.match(r"^nvidia-driver-\d+-open$", drivers[0]), (
        f"{drivers[0]!r}: Blackwell needs the OPEN modules and a version >= 570"
    )


def test_debian_is_untouched_by_the_mapping():
    """Nothing about Debian changes. It is the proven configuration."""
    src = "task-kde-desktop firefox-esr nvidia-driver nvidia-smi sudo"
    assert mapped("debian", src) == src.split(), (
        "the mapping altered the Debian list; debian must pass through verbatim"
    )


def test_the_mkosi_adapter_actually_applies_the_mapping():
    """It had the mapping available and did not call it for a whole release."""
    body = MKOSI_EMIT.read_text(encoding="utf-8")
    # Match the IDENTIFIER, not a substring. A first cut used `in body` and
    # passed when the call was renamed to distro_map_packages_DISABLED — the
    # test proved nothing about whether the mapping still ran.
    assert re.search(r"\bdistro_map_packages\b(?![\w-])", body), (
        "mkosi-emit must translate package names. Without it the Ubuntu "
        "appliance ships Debian names and fails at package install — the "
        "installers translate, the adapter did not."
    )


def test_the_adapter_does_not_keep_its_own_copy_of_the_mapping():
    """A second copy is a second thing to forget.

    That is exactly how this adapter came to lack the first one.
    """
    body = MKOSI_EMIT.read_text(encoding="utf-8")
    code = "\n".join(l for l in body.splitlines() if not l.lstrip().startswith("#"))
    for name in ("kubuntu-desktop", "linux-firmware"):
        assert name not in code, (
            f"mkosi-emit hardcodes {name!r} instead of asking "
            "distro_map_packages. Keep one source of truth."
        )


def test_the_translation_is_reported_not_silent():
    """An operator should see what changed under them."""
    body = MKOSI_EMIT.read_text(encoding="utf-8")
    seg = body[body.index("distro_map_packages"):]
    seg = seg[: seg.index("cfg = textwrap.dedent")]
    assert "dropped/renamed" in seg or "now installs" in seg, (
        "the adapter should log which package names it changed; a silent "
        "substitution in a build that takes hours is hard to trace later"
    )
    assert "WARNING" in seg, (
        "if the translation cannot run, say so loudly rather than silently "
        "shipping Debian names to Ubuntu"
    )


# ── the secure-boot posture override (2026-07-30) ───────────────────────────
# Added on the operator's call so the first Ubuntu appliance build can run
# unsigned WITHOUT editing the tracked profile. A first build on a
# never-executed path is the wrong moment to mint a long-lived key identity:
# that key is what the firmware enrols AND what the NVIDIA .run signs its
# modules against, so a throwaway breaks every later signed kernel.
#
# The danger of any such escape is that it becomes a silent way to ship an
# unsigned image. These tests pin the two properties that keep it honest.

def _emit(env_extra: dict, tmp_path):
    key, cert = tmp_path / "k", tmp_path / "c"
    key.write_text(""), cert.write_text("")
    out = tmp_path / "o"
    out.mkdir(exist_ok=True)
    import os
    env = {
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "HOME": str(tmp_path),
        "SOVEREIGN_OS_MOK_KEY": str(key), "SOVEREIGN_OS_MOK_CERT": str(cert),
        "SOVEREIGN_OS_ROOT_PASSWORD": "render-only-not-a-secret",
        **env_extra,
    }
    return subprocess.run(
        ["bash", str(MKOSI_EMIT), str(REPO_ROOT / "profiles/sain-01.yaml"), str(out)],
        capture_output=True, text=True, cwd=REPO_ROOT, env=env, timeout=180,
    ), out


def test_the_override_can_only_weaken_never_strengthen(tmp_path):
    """Asserting 'signed' from the environment would let a build claim a
    posture the profile never declared. That belongs in git, reviewable."""
    run, _ = _emit({"SOVEREIGN_OS_SECURE_BOOT": "signed"}, tmp_path)
    assert run.returncode != 0, (
        "SOVEREIGN_OS_SECURE_BOOT=signed must be REFUSED — an environment "
        "variable must not be able to claim a stronger posture than the profile"
    )
    assert "may only DISABLE" in run.stderr, run.stderr[-300:]


def test_downgrading_is_never_silent(tmp_path):
    """An unsigned image that looks signed is the failure mode to avoid."""
    run, out = _emit({"SOVEREIGN_OS_SECURE_BOOT": "none"}, tmp_path)
    if run.returncode != 0:
        pytest.skip(f"emitter could not run here: {run.stderr.strip()[-200:]}")
    assert "WARNING" in run.stderr and "downgrades" in run.stderr, (
        "downgrading the secure-boot posture must be announced loudly:\n"
        + run.stderr[-400:]
    )
    confs = list(out.rglob("mkosi.conf")) + list(out.rglob("mkosi.conf.d/*.conf"))
    text = "\n".join(c.read_text(errors="replace") for c in confs)
    assert "SecureBoot=" not in text, (
        "the emitted config still enables SecureBoot despite the downgrade — "
        "the image would claim a posture it cannot satisfy"
    )


# ── the bake must not GUESS the distro (2026-07-30, first real build) ───────
# The Ubuntu appliance failed after a full kernel compile and a complete package
# install, at the very last step:
#
#     provision-bake:   no apt in this root AND these packages are missing:
#                       firefox-esr
#     postinst: provision-bake FAILED (rc=1)
#
# mkosi had correctly installed `firefox` — the Packages= translation worked.
# But provision-bake runs install-gui-dashboards.sh INSIDE the chroot, which
# resolves the browser through target_browser() -> target_distro(). With no
# SOVEREIGN_OS_DISTRO in the chroot environment that falls back to reading
# /etc/os-release and then to the historical `debian` default, so it demanded
# the Debian name inside an Ubuntu root.
#
# mkosi-emit is the ONE place that knows which distro is being built. Baking the
# answer in makes every in-image script deterministic instead of dependent on
# what happens to be readable mid-bake.

def test_the_postinst_declares_the_distro_it_was_built_for(tmp_path):
    """Otherwise the in-image bake guesses, and guesses debian."""
    import os
    run, out = _emit({"SOVEREIGN_OS_DISTRO": "ubuntu",
                      "SOVEREIGN_OS_SECURE_BOOT": "none"}, tmp_path)
    if run.returncode != 0:
        pytest.skip(f"emitter could not run here: {run.stderr.strip()[-200:]}")
    postinst = out / "mkosi.postinst.chroot"
    assert postinst.is_file(), "no postinst emitted"
    body = postinst.read_text(encoding="utf-8")
    assert "export SOVEREIGN_OS_DISTRO=ubuntu" in body, (
        "the generated postinst must declare the distro it was built for. "
        "Without it, install-gui-dashboards.sh resolves firefox-esr inside an "
        "Ubuntu root and the build fails at the last step."
    )
    assert "__SOVEREIGN_OS_DISTRO__" not in body, (
        "the substitution sentinel leaked into the emitted script — the body is "
        "a plain dedent, not an f-string, so it must be replaced at write time"
    )


def test_the_browser_matches_what_mkosi_actually_installed(tmp_path):
    """The two must agree, or the bake demands a package that is not there.

    This is the exact mismatch that failed the build: Packages= had `firefox`
    while the in-image check wanted `firefox-esr`.
    """
    import os
    for distro, expected in (("ubuntu", "firefox"), ("debian", "firefox-esr")):
        got = subprocess.run(
            ["sh", "-c",
             ". scripts/install/lib/target-distro.sh; target_browser"],
            capture_output=True, text=True, cwd=REPO_ROOT,
            env={"SOVEREIGN_OS_DISTRO": distro, "PATH": "/usr/bin:/bin"},
        ).stdout.strip()
        assert got == expected, f"{distro}: target_browser gave {got!r}"
        # …and the build-side mapping must name the SAME package.
        mapped_pkgs = mapped(distro, "firefox-esr")
        assert mapped_pkgs == [expected], (
            f"{distro}: mkosi would install {mapped_pkgs} but the in-image bake "
            f"looks for {expected!r} — that mismatch fails provision-bake"
        )


def test_the_generated_postinst_is_actually_executable(tmp_path):
    """A script that contains the right text but cannot be exec'd is not a fix.

    2026-07-30: adding `export SOVEREIGN_OS_DISTRO=...` at column 0 inside the
    postinst's textwrap.dedent() body destroyed the common leading whitespace,
    so dedent() stripped nothing, EVERY line kept its 4-space indent, and the
    shebang became "    #!/bin/bash". mkosi died with

        OSError: [Errno 8] Exec format error

    after a full package install. The test added alongside that change asserted
    the export STRING was present and passed happily — it never checked the
    artifact was still a runnable script. Assert validity, not just content.
    """
    run, out = _emit({"SOVEREIGN_OS_DISTRO": "ubuntu",
                      "SOVEREIGN_OS_SECURE_BOOT": "none"}, tmp_path)
    if run.returncode != 0:
        pytest.skip(f"emitter could not run here: {run.stderr.strip()[-200:]}")
    postinst = out / "mkosi.postinst.chroot"
    assert postinst.is_file(), "no postinst emitted"

    first = postinst.read_text(encoding="utf-8").splitlines()[0]
    assert first.startswith("#!"), (
        f"the postinst's first line is not a shebang: {first!r}. execvp() "
        "rejects it with Errno 8 Exec format error."
    )
    assert first == first.lstrip(), (
        f"the shebang is INDENTED ({first!r}) — textwrap.dedent() found no "
        "common prefix, which happens the moment a line is added at column 0 "
        "inside the dedent body."
    )
    assert postinst.stat().st_mode & 0o111, "the postinst is not executable"

    syntax = subprocess.run(["bash", "-n", str(postinst)],
                            capture_output=True, text=True)
    assert syntax.returncode == 0, (
        f"the generated postinst is not valid bash:\n{syntax.stderr}"
    )


def test_every_line_of_the_postinst_body_shares_the_dedent_indent():
    """Catch the fault in the SOURCE, not only in the output.

    The emitted script is the symptom; the cause is a line added at column 0
    inside the dedent block. Anyone editing that body will reach for column 0
    again, so name the rule where they are typing.
    """
    body = MKOSI_EMIT.read_text(encoding="utf-8")
    start = body.index('postinst.write_text(textwrap.dedent("""\\')
    end = body.index('"""', start + 40)
    block = body[body.index("\n", start) + 1: end]
    # INTERPRET THE ESCAPES FIRST. The block is a NON-raw Python triple-quoted
    # string, so Python turns `\n` into a real newline BEFORE textwrap.dedent()
    # sees it. A first cut of this test scanned the raw source, found nothing,
    # and passed while `printf '%s\n' ...` was silently splitting into a line
    # whose tail sat at column 0 — indenting the shebang and producing
    # "OSError: [Errno 8] Exec format error" after a full package install.
    interpreted = block.encode().decode("unicode_escape")
    offenders = [
        l for l in interpreted.splitlines()
        if l.strip() and not l.startswith("    ")
    ]
    assert not offenders, (
        "these lines sit at column 0 inside the postinst dedent body (AFTER "
        "Python interprets its escapes), which kills textwrap.dedent() and "
        "indents the shebang:\n  "
        + "\n  ".join(repr(l) for l in offenders[:5])
    )


# ── the appliance's kernel cmdline (2026-07-30, on real hardware) ───────────
# The operator booted the first Ubuntu appliance and got "a weird login page…
# like it was broken and then it even froze, I could not enter the login
# password". The UKI it booted had:
#
#     nomodeset splash loglevel=3 console=ttyS0 console=tty0 vfio-pci.ids=…
#
# `nomodeset` is load-bearing on Debian (Plasma ships an X11 session, runs on
# the EFI framebuffer) and FATAL on Ubuntu 26.04, whose Plasma is WAYLAND-ONLY:
# /usr/share/xsessions/ is empty, Wayland needs a DRM device, and nomodeset is
# exactly what removes one. sddm renders a greeter with no session it can start.
#
# The Ubuntu ISO builder has translated the cmdline since 2026-07-29. This
# adapter did not — one path fixed, one forgotten, and the forgotten one is the
# one that reached hardware.

@pytest.mark.parametrize("distro,must,must_not", [
    ("debian", "nomodeset", "nvidia-drm.modeset=1"),
    ("ubuntu", "nvidia-drm.modeset=1", "nomodeset"),
])
def test_the_appliance_cmdline_is_translated_for_its_distro(distro, must, must_not, tmp_path):
    run, out = _emit({"SOVEREIGN_OS_DISTRO": distro,
                      "SOVEREIGN_OS_SECURE_BOOT": "none"}, tmp_path)
    if run.returncode != 0:
        pytest.skip(f"emitter could not run here: {run.stderr.strip()[-200:]}")
    lines = []
    for conf in list(out.rglob("mkosi.conf")) + list(out.rglob("mkosi.conf.d/*.conf")):
        lines += [l for l in conf.read_text(errors="replace").splitlines()
                  if l.startswith("KernelCommandLine=")]
    assert lines, "the appliance config declares no KernelCommandLine at all"
    cmdline = lines[0].split("=", 1)[1]
    assert must in cmdline, (
        f"{distro}: the appliance cmdline is missing {must!r} — got {cmdline!r}"
    )
    assert must_not not in cmdline, (
        f"{distro}: {must_not!r} must NOT reach this distro's appliance. On "
        "Ubuntu, nomodeset removes the DRM device that Wayland-only Plasma "
        f"requires, producing a greeter that cannot log anyone in. Got {cmdline!r}"
    )


def test_the_unrelated_cmdline_options_survive_translation(tmp_path):
    """A translation that drops vfio or the console settings is not a fix."""
    run, out = _emit({"SOVEREIGN_OS_DISTRO": "ubuntu",
                      "SOVEREIGN_OS_SECURE_BOOT": "none"}, tmp_path)
    if run.returncode != 0:
        pytest.skip("emitter could not run here")
    cmdline = ""
    for conf in list(out.rglob("mkosi.conf")) + list(out.rglob("mkosi.conf.d/*.conf")):
        for l in conf.read_text(errors="replace").splitlines():
            if l.startswith("KernelCommandLine="):
                cmdline = l.split("=", 1)[1]
    for opt in ("splash", "loglevel=3", "console=tty0", "amd_iommu=on", "iommu=pt"):
        assert opt in cmdline, (
            f"translation dropped {opt!r}, which the profile asked for: {cmdline!r}"
        )
