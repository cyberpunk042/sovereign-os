"""Two distros must never write the same artifact filename.

Operator question, 2026-07-29: "make sure we won't confuse which is which at
the Emulator or Flash to Device panel select, they should not collide."

They did collide, and two of the four substrates collided SILENTLY:

    installer-cdd       sain-01-installer.iso          (debian)
    ubuntu-autoinstall  sain-01-ubuntu-installer.iso   (ubuntu)
    live-build          sain-01-installer.iso          <- EITHER distro
    mkosi               sain-01.raw                    <- EITHER distro

So a Ubuntu live-build overwrote the Debian d-i ISO, and a Ubuntu appliance
overwrote the Debian appliance, with no error and nothing on disk afterwards to
say which distro the file was. The two installer ISOs only avoided collision
because the Ubuntu builder happened to insert "-ubuntu-" — a coincidence, not a
rule.

Panel labelling cannot fix a file that was overwritten, so the NAME carries the
distro. And a name alone is not enough for a destructive action, so the panels
must SAY which distro they are about to write: both installer ISOs ended in
`-installer.iso` and rendered as an identical "🖴 INSTALLER" row, while the
flash panel default-selects the NEWEST installer — Ubuntu, after a Ubuntu
build, even if the operator had just built Debian.

It had already caused a real misreport: step 07 matched a bare `*.iso` and
announced "the .iso is UNCHANGED" while naming the OTHER distro's image.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DISTRO_SH = REPO_ROOT / "scripts/build/lib/distro.sh"
FLASH_API = REPO_ROOT / "scripts/operator/flash-api.py"
EMULATE_API = REPO_ROOT / "scripts/operator/emulate-api.py"
FLASH_PANEL = REPO_ROOT / "webapp/flash/index.html"
EMULATE_PANEL = REPO_ROOT / "webapp/emulate/index.html"

DISTROS = ("debian", "ubuntu")
ARTIFACTS = ("image", "installer")


def basename(distro: str, artifact: str, profile: str = "sain-01") -> str:
    out = subprocess.run(
        ["sh", "-c", f'. {DISTRO_SH}; distro_artifact_basename {profile} {artifact}'],
        capture_output=True, text=True, cwd=REPO_ROOT,
        env={"SOVEREIGN_OS_DISTRO": distro, "PATH": "/usr/bin:/bin"},
    )
    assert out.returncode == 0, out.stderr
    return out.stdout.strip()


# ── the property that matters ───────────────────────────────────────────────

def test_no_two_distros_produce_the_same_artifact_name():
    """The whole point. Every (distro, artifact) pair must be unique."""
    seen: dict[str, tuple[str, str]] = {}
    for artifact in ARTIFACTS:
        for distro in DISTROS:
            name = basename(distro, artifact)
            assert name, f"empty basename for {distro}/{artifact}"
            if name in seen:
                other = seen[name]
                pytest.fail(
                    f"{distro}/{artifact} and {other[0]}/{other[1]} both produce "
                    f"{name!r}. One build silently overwrites the other and "
                    f"nothing on disk says which distro it was."
                )
            seen[name] = (distro, artifact)


@pytest.mark.parametrize("distro", DISTROS)
@pytest.mark.parametrize("artifact", ARTIFACTS)
def test_the_distro_is_in_every_artifact_name(distro, artifact):
    name = basename(distro, artifact)
    assert distro in name, (
        f"{distro}/{artifact} produces {name!r}, which does not name the "
        "distro. A reader — human or glob — cannot tell what it is."
    )


@pytest.mark.parametrize("distro", DISTROS)
@pytest.mark.parametrize("artifact", ARTIFACTS)
def test_the_name_round_trips_back_to_its_distro(distro, artifact):
    ext = "iso" if artifact == "installer" else "raw"
    name = f"{basename(distro, artifact)}.{ext}"
    out = subprocess.run(
        ["sh", "-c", f'. {DISTRO_SH}; artifact_distro_of {name}'],
        capture_output=True, text=True, cwd=REPO_ROOT,
        env={"PATH": "/usr/bin:/bin"},
    )
    assert out.stdout.strip() == distro, (
        f"{name!r} parsed back as {out.stdout.strip()!r}, not {distro!r}"
    )


def test_the_profile_is_honoured_not_hardcoded():
    """installer-cdd hardcoded `sain-01-installer.iso`, ignoring the profile.

    Building profile `test-02` wrote into sain-01's name — the same bug class
    the builder's own comment says was fixed for the output DIRECTORY in
    2026-07-26, still live in the FILENAME.
    """
    assert basename("debian", "installer", profile="test-02").startswith("test-02"), (
        "the artifact name must start with the profile that was built"
    )
    body = (REPO_ROOT / "scripts/build/installer-cdd/build.sh").read_text(encoding="utf-8")
    code = "\n".join(l for l in body.splitlines() if not l.lstrip().startswith("#"))
    assert "sain-01-installer.iso" not in code, (
        "installer-cdd/build.sh still hardcodes sain-01-installer.iso; use "
        "distro_artifact_basename with the real profile"
    )


# ── the panels must SAY which one it is ─────────────────────────────────────

@pytest.mark.parametrize("api", [FLASH_API, EMULATE_API], ids=lambda p: p.name)
def test_the_apis_report_the_distro(api):
    body = api.read_text(encoding="utf-8")
    assert '"distro"' in body and "distro_label" in body, (
        f"{api.name} must report which distro each artifact is. Without it the "
        "panel can only show a filename, and both installer ISOs end in "
        "-installer.iso."
    )


@pytest.mark.parametrize("panel", [FLASH_PANEL, EMULATE_PANEL], ids=lambda p: p.parent.name)
def test_the_panels_render_the_distro(panel):
    body = panel.read_text(encoding="utf-8")
    assert "distro_label" in body, (
        f"the {panel.parent.name} panel must render the distro in the artifact "
        "row. Flashing the wrong distro to an internal disk is not recoverable, "
        "and the row for both used to read an identical '🖴 INSTALLER'."
    )


def test_the_flash_panel_warns_when_both_distros_are_present():
    """That is precisely when a mis-pick is possible."""
    body = FLASH_PANEL.read_text(encoding="utf-8")
    assert re.search(r"distros are present", body), (
        "the flash panel should warn when artifacts for more than one distro "
        "exist — the default selection is the NEWEST installer, which need not "
        "be the distro the operator just built"
    )


# ── discovery must not match the other distro's file ────────────────────────

@pytest.mark.parametrize("step,anchor", [
    ("scripts/build/07-image-build.sh", "distro_artifact_basename"),
    ("scripts/build/09-image-verify.sh", "distro_artifact_basename"),
])
def test_the_build_steps_scope_discovery_to_this_distro(step, anchor):
    body = (REPO_ROOT / step).read_text(encoding="utf-8")
    assert anchor in body, (
        f"{step} must derive its artifact glob from the naming rule. A bare "
        "'*.iso' matches the OTHER distro's image — step 07 already reported "
        "'the .iso is UNCHANGED' while naming the wrong file, and step 09 "
        "would 'verify' an artifact this build never produced."
    )


def test_no_build_step_uses_a_bare_iso_glob_in_the_output_dir():
    """The specific shape of the bug."""
    offenders = []
    for step in ("07-image-build.sh", "09-image-verify.sh"):
        for line in (REPO_ROOT / "scripts/build" / step).read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if s.startswith("#"):
                continue
            # a bare *.iso glob rooted at the shared output dir
            if re.search(r"(IMAGE_DIR|_out|output)\S*/?\s*[\"']?\*\.iso", s):
                offenders.append(f"{step}: {s}")
    assert not offenders, (
        "bare '*.iso' glob over the shared output dir — it matches the other "
        "distro's artifact:\n  " + "\n  ".join(offenders)
    )
