"""R409 (E10.M53) — image-build (step 07) + image-verify (step 09) lint.

Extends R387-R408 operational-artifact pinning to:
  scripts/build/07-image-build.sh
  scripts/build/09-image-verify.sh

These are the operator-named substrate-dispatch + image-validation
endpoints in the build pipeline.

Step 07 (image-build) operator-verbatim invariants:
  - Dispatches by SOVEREIGN_OS_SUBSTRATE: mkosi / live-build / Stage-2+
  - mkosi: 'mkosi build' (operator-named substrate command verbatim)
  - live-build: 'lb build' (operator-named substrate command verbatim)
  - Staging: compiled kernel .debs land in substrate-specific cache
    (mkosi.extra/var/cache/local-debs or config/packages.chroot)
  - Output discovery per substrate (mkosi: output/ subdir; lb: same dir)
  - Image extensions: .raw / .img / .iso / .qcow2 (operator-named)
  - Stage-2+ substrates (rpm-ostree / nixos) MUST fail with operator-
    discoverable reason (drift to silent-skip stalls Stage-2+ migration)

Step 09 (image-verify) operator-verbatim invariants:
  - QEMU boot smoke test (SDD-019 + Q-014 verbatim)
  - SOVEREIGN_OS_SKIP_QEMU honored (CI without KVM)
  - QEMU timeout default 300s (5 min — operator's "5 minute" verbatim)
  - SDD-019 verbatim: sha256sums.txt emission for reproducibility
  - SDD-019 verbatim: in-toto / SLSA build-provenance manifest
  - Userspace marker check (boot reached systemd[1])
  - Provenance references buildType / externalParameters /
    SOURCE_DATE_EPOCH + DEBIAN_SNAPSHOT (SDD-019 reproducibility inputs)
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
STEP_07 = REPO_ROOT / "scripts" / "build" / "07-image-build.sh"
STEP_09 = REPO_ROOT / "scripts" / "build" / "09-image-verify.sh"


def _read(p: Path) -> str:
    assert p.is_file(), f"missing {p}"
    return p.read_text(encoding="utf-8")


def test_both_steps_exist():
    for p in (STEP_07, STEP_09):
        assert p.is_file(), f"build step missing: {p}"


# --- Step 07: image-build substrate dispatcher ---


def test_step_07_dispatches_on_substrate():
    """Step 07 MUST switch on SOVEREIGN_OS_SUBSTRATE (operator-named
    dispatcher env var)."""
    body = _read(STEP_07)
    assert "SOVEREIGN_OS_SUBSTRATE" in body, (
        "07-image-build.sh missing SOVEREIGN_OS_SUBSTRATE dispatch "
        "(operator-named substrate selector)"
    )


def test_step_07_mkosi_build_command_verbatim():
    """Operator-verbatim mkosi command: 'mkosi build'. Drift to
    'mkosi-build' or 'mkosi --build' silently breaks the substrate path."""
    body = _read(STEP_07)
    assert "mkosi build" in body, (
        "07-image-build.sh missing 'mkosi build' command verbatim "
        "(operator-named substrate command; drift breaks mkosi path)"
    )


def test_step_07_lb_build_command_verbatim():
    """Operator-verbatim live-build command: 'lb build'. Drift to
    'live-build' or 'lb-build' silently breaks the substrate path."""
    body = _read(STEP_07)
    assert "lb build" in body, (
        "07-image-build.sh missing 'lb build' command verbatim "
        "(operator-named substrate command; drift breaks live-build path)"
    )


def test_step_07_stages_kernel_debs():
    """Compiled kernel .debs MUST land in substrate-specific cache.
    Drift = substrate falls back to Debian-archive kernel (silently
    discards step 04's compiled kernel)."""
    body = _read(STEP_07)
    has_staging = (
        "stage_kernel_debs" in body
        or "KERNEL_DEBS" in body
        or "*.deb" in body
    )
    assert has_staging, (
        "07-image-build.sh missing kernel .deb staging "
        "(drift = substrate silently uses Debian-archive kernel)"
    )


def test_step_07_mkosi_extra_local_debs_path():
    """mkosi-specific kernel-deb cache: mkosi.extra/var/cache/local-debs
    (operator-verbatim — drift breaks the apt local-cache resolution)."""
    body = _read(STEP_07)
    assert "mkosi.extra" in body, (
        "07-image-build.sh missing mkosi.extra/... kernel deb cache "
        "(operator-verbatim — drift breaks local-deb apt resolution)"
    )


def test_step_07_lb_packages_chroot_path():
    """live-build-specific kernel-deb cache: config/packages.chroot/
    (operator-verbatim live-build local-packages convention)."""
    body = _read(STEP_07)
    assert "packages.chroot" in body, (
        "07-image-build.sh missing config/packages.chroot kernel deb "
        "cache (operator-verbatim live-build convention)"
    )


def test_step_07_stage_2_substrates_fail_with_reason():
    """rpm-ostree / nixos MUST fail with state_step_fail reason
    "substrate-image-build-not-implemented". Drift to silent-skip
    stalls Stage-2+ migration."""
    body = _read(STEP_07)
    has_explicit = "substrate-image-build-not-implemented" in body
    assert has_explicit, (
        "07-image-build.sh Stage-2+ substrates missing explicit "
        "state_step_fail 'substrate-image-build-not-implemented' "
        "(drift = silent skip stalls migration)"
    )


def test_step_07_unknown_substrate_fails():
    """Unknown SOVEREIGN_OS_SUBSTRATE MUST fail (drift = typo silently
    skips image build, exits 0)."""
    body = _read(STEP_07)
    has_unknown = "unknown-substrate" in body
    assert has_unknown, (
        "07-image-build.sh missing 'unknown-substrate' fail path "
        "(drift = typo silently exits 0 without producing image)"
    )


def test_step_07_image_artifact_extensions():
    """Output image extensions MUST cover .raw / .img / .iso / .qcow2
    (operator-named bootable artifact types)."""
    body = _read(STEP_07)
    expected_exts = [".raw", ".img", ".iso", ".qcow2"]
    for ext in expected_exts:
        assert ext in body, (
            f"07-image-build.sh missing {ext!r} output extension "
            f"(operator-named bootable image artifact type)"
        )


def test_step_07_emits_env_image_handoff():
    """Step 07 MUST emit env-image.sh with SOVEREIGN_OS_IMAGE_DIR
    (handoff to step 08 image-sign + step 09 image-verify)."""
    body = _read(STEP_07)
    has_handoff = (
        "env-image.sh" in body
        and "SOVEREIGN_OS_IMAGE_DIR" in body
    )
    assert has_handoff, (
        "07-image-build.sh missing env-image.sh handoff to step 08/09 "
        "(drift = downstream steps can't find image artifacts)"
    )


# --- Step 09: image-verify QEMU smoke + SDD-019 reproducibility ---


def test_step_09_uses_qemu_system_x86_64():
    """Step 09 MUST invoke qemu-system-x86_64 (operator-named QEMU
    architecture binary; drift to qemu-system-i386 = wrong arch)."""
    body = _read(STEP_09)
    assert "qemu-system-x86_64" in body, (
        "09-image-verify.sh missing qemu-system-x86_64 "
        "(operator-named QEMU x86_64 binary; sain-01 is amd64)"
    )


def test_step_09_skip_qemu_env_var():
    """Operator-verbatim CI escape hatch: SOVEREIGN_OS_SKIP_QEMU
    skips the boot test (CI without KVM)."""
    body = _read(STEP_09)
    assert "SOVEREIGN_OS_SKIP_QEMU" in body, (
        "09-image-verify.sh missing SOVEREIGN_OS_SKIP_QEMU honor "
        "(operator-verbatim CI/KVM-less escape hatch)"
    )


def test_step_09_qemu_timeout_default_300():
    """Operator-verbatim 'Timeout: 5 minutes' for QEMU smoke test
    = 300 seconds default."""
    body = _read(STEP_09)
    has_timeout = (
        "QEMU_TIMEOUT:=300" in body
        or "SOVEREIGN_OS_QEMU_TIMEOUT:=300" in body
    )
    assert has_timeout, (
        "09-image-verify.sh missing 300s QEMU timeout default "
        "(operator-verbatim '5 minutes' smoke test ceiling)"
    )


def test_step_09_no_reboot_flag():
    """QEMU smoke MUST use -no-reboot (else infinite reboot loop
    on kernel panic = CI hangs at timeout)."""
    body = _read(STEP_09)
    assert "-no-reboot" in body, (
        "09-image-verify.sh missing -no-reboot QEMU flag "
        "(drift = kernel panic loops indefinitely; CI hangs)"
    )


def test_step_09_nographic_flag():
    """QEMU smoke MUST use -nographic (no display; serial console
    output goes to stdout for log capture)."""
    body = _read(STEP_09)
    assert "-nographic" in body, (
        "09-image-verify.sh missing -nographic QEMU flag "
        "(drift = QEMU tries to open GUI on headless CI host)"
    )


def test_step_09_readonly_drive():
    """QEMU smoke MUST mount image readonly=on (drift = QEMU writes
    to operator's image, corrupting the artifact)."""
    body = _read(STEP_09)
    assert "readonly=on" in body, (
        "09-image-verify.sh missing readonly=on drive flag "
        "(drift = QEMU corrupts operator's image artifact)"
    )


def test_step_09_emits_sha256sums_txt():
    """SDD-019 verbatim: sha256sums.txt for every image artifact
    (operator-discovery reproducibility verification)."""
    body = _read(STEP_09)
    assert "sha256sums.txt" in body, (
        "09-image-verify.sh missing sha256sums.txt emission "
        "(SDD-019 verbatim — reproducibility verification)"
    )


def test_step_09_emits_in_toto_provenance():
    """SDD-019 verbatim: in-toto / SLSA build-provenance manifest
    (operator-named supply-chain artifact format)."""
    body = _read(STEP_09)
    has_intoto = (
        "in-toto" in body
        or "slsa.dev" in body
        or "build-provenance" in body
    )
    assert has_intoto, (
        "09-image-verify.sh missing in-toto/SLSA provenance manifest "
        "(SDD-019 verbatim — supply-chain artifact format)"
    )


def test_step_09_provenance_includes_reproducibility_inputs():
    """SDD-019 verbatim: provenance manifest MUST include
    SOURCE_DATE_EPOCH + DEBIAN_SNAPSHOT (the reproducibility-input
    knobs). Drift loses operator's verifiable build-input record."""
    body = _read(STEP_09)
    assert "source_date_epoch" in body.lower(), (
        "09-image-verify.sh provenance missing SOURCE_DATE_EPOCH "
        "input (SDD-019 — reproducibility verification record)"
    )
    assert "debian_snapshot" in body.lower(), (
        "09-image-verify.sh provenance missing DEBIAN_SNAPSHOT input "
        "(SDD-019 — reproducibility verification record)"
    )


def test_step_09_userspace_marker_check():
    """Step 09 SHOULD check the boot log for userspace markers
    (systemd[1] or 'Welcome to') — confirms the image actually booted
    past kernel init. Drift = booting halt-at-initrd images would pass."""
    body = _read(STEP_09)
    has_check = (
        "systemd\\[1\\]" in body
        or "Welcome to" in body
        or "userspace markers" in body.lower()
    )
    assert has_check, (
        "09-image-verify.sh missing userspace-marker check in QEMU log "
        "(drift = halt-at-initrd images silently pass smoke test)"
    )


def test_step_09_in_toto_statement_v1():
    """SDD-019 + operator-named SLSA v1 schema: provenance MUST use
    https://in-toto.io/Statement/v1 + https://slsa.dev/provenance/v1
    URLs verbatim. Drift to v0/v2 breaks supply-chain verifier tools."""
    body = _read(STEP_09)
    assert "in-toto.io/Statement/v1" in body, (
        "09-image-verify.sh provenance missing in-toto Statement/v1 "
        "URL verbatim (SDD-019 — schema-version pinning)"
    )
    assert "slsa.dev/provenance/v1" in body, (
        "09-image-verify.sh provenance missing SLSA provenance/v1 "
        "URL verbatim (SDD-019 — schema-version pinning)"
    )


def test_step_09_qemu_timeout_exit_124():
    """When QEMU hits the timeout, exit code is 124 (operator-verbatim
    GNU coreutils 'timeout' convention). Drift breaks the per-rc
    classification (timeout-vs-panic-vs-success)."""
    body = _read(STEP_09)
    assert "124" in body, (
        "09-image-verify.sh missing 124 (GNU 'timeout' exit code) "
        "in rc classification (drift conflates timeout with actual fail)"
    )
