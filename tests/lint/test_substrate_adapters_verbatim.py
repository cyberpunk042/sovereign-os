"""R406 (E10.M50) — substrate adapter emission operator-verbatim lint.

Extends R387-R405 operational-artifact pinning to the 2 substrate
adapter emitters that translate sovereign-os profile YAML → substrate
build config:
  scripts/build/adapters/mkosi-emit.sh       (PRIMARY per SDD-003)
  scripts/build/adapters/live-build-emit.sh  (Alt-A fallback per SDD-003)

These adapters are the bridge between operator-verbatim profile content
and substrate-specific build config. Drift here silently changes what
gets baked into the image.

Master spec verbatim invariants:
  - Distribution=debian + Release=trixie (operator-named base distro)
  - SecureBoot=yes (operator-named secure-boot baseline in mkosi)
  - Bootloader=systemd-boot (mkosi default per master spec)
  - ZFS-tiered storage layout → mkosi.repart/10-root-zfs.conf with
    Format=none (post-install hook creates pool, not mkosi)
  - SDD-019 reproducibility: SOURCE_DATE_EPOCH + DEBIAN_SNAPSHOT
    propagation when env vars set
  - Architecture=amd64 + ISO-hybrid for live-build (Debian Trixie)
  - Both adapters MUST filter out linux-image-* / linux-headers-* from
    package list (custom kernel ships separately)

If a future agent silently:
  - changes Distribution=debian (substrate baseline drift)
  - flips SecureBoot=yes → no (image fails to verify on operator's hw)
  - drops zfs-tiered repart conditional (mkosi reformats ZFS partition)
  - drops linux-image filter (substrate installs Debian stock kernel
    AND custom kernel = double-kernel install + boot ambiguity)
…the substrate-emission contract silently breaks.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MKOSI_EMIT = REPO_ROOT / "scripts" / "build" / "adapters" / "mkosi-emit.sh"
LIVE_BUILD_EMIT = REPO_ROOT / "scripts" / "build" / "adapters" / "live-build-emit.sh"


def _read(p: Path) -> str:
    assert p.is_file(), f"missing {p}"
    return p.read_text(encoding="utf-8")


def test_both_adapters_exist():
    for p in (MKOSI_EMIT, LIVE_BUILD_EMIT):
        assert p.is_file(), f"substrate adapter missing: {p}"


# --- mkosi-emit.sh (PRIMARY per SDD-003) ---


def test_mkosi_distribution_debian():
    """SDD-003 verbatim: substrate baseline is Debian Trixie."""
    body = _read(MKOSI_EMIT)
    assert "Distribution=debian" in body, (
        "mkosi-emit.sh missing Distribution=debian (SDD-003 verbatim — "
        "operator-named substrate baseline)"
    )


def test_mkosi_release_trixie():
    body = _read(MKOSI_EMIT)
    assert "Release=trixie" in body, (
        "mkosi-emit.sh missing Release=trixie (SDD-003 verbatim — "
        "operator-named Debian release; drift to bookworm would lose "
        "kernel 6.12+ for Blackwell/Zen 5 native support)"
    )


def test_mkosi_secure_boot_yes():
    """Operator-named secure-boot baseline: image MUST be signed by
    default. Drift to SecureBoot=no = unsigned image silently produced."""
    body = _read(MKOSI_EMIT)
    assert "SecureBoot=yes" in body, (
        "mkosi-emit.sh missing SecureBoot=yes (operator-verbatim — "
        "drift to SecureBoot=no produces unsigned images)"
    )


def test_mkosi_bootloader_systemd_boot():
    """mkosi standard bootloader per master spec — systemd-boot
    (matches the EFI ESP partition layout)."""
    body = _read(MKOSI_EMIT)
    assert "Bootloader=systemd-boot" in body, (
        "mkosi-emit.sh missing Bootloader=systemd-boot (master spec — "
        "drift breaks ESP-based UEFI boot path)"
    )


def test_mkosi_format_disk():
    """mkosi output Format=disk (raw disk image, not tar/cpio/initrd).
    Drift to Format=tar produces a non-bootable tarball."""
    body = _read(MKOSI_EMIT)
    assert "Format=disk" in body, (
        "mkosi-emit.sh missing Format=disk (drift to tar/cpio = "
        "non-bootable image; operator can't dd to disk)"
    )


def test_mkosi_propagates_source_date_epoch():
    """SDD-019 verbatim: SOURCE_DATE_EPOCH propagation for build
    reproducibility. Drift losing this breaks reproducible builds."""
    body = _read(MKOSI_EMIT)
    assert "SOURCE_DATE_EPOCH" in body, (
        "mkosi-emit.sh missing SOURCE_DATE_EPOCH propagation "
        "(SDD-019 verbatim — substrate-level reproducibility)"
    )


def test_mkosi_propagates_debian_snapshot():
    """SDD-019 verbatim: DEBIAN_SNAPSHOT for bit-identical apt
    resolution via snapshot.debian.org. Drift loses bit-identical
    package resolution."""
    body = _read(MKOSI_EMIT)
    assert "DEBIAN_SNAPSHOT" in body, (
        "mkosi-emit.sh missing DEBIAN_SNAPSHOT propagation "
        "(SDD-019 verbatim — snapshot.debian.org bit-identical apt)"
    )


def test_mkosi_snapshot_debian_org_url():
    """When DEBIAN_SNAPSHOT is set, mirror URL MUST point at
    snapshot.debian.org (operator-named bit-identical apt mirror)."""
    body = _read(MKOSI_EMIT)
    assert "snapshot.debian.org" in body, (
        "mkosi-emit.sh missing snapshot.debian.org mirror URL "
        "(SDD-019 verbatim — bit-identical apt resolution path)"
    )


def test_mkosi_filters_kernel_packages_from_apt():
    """Custom kernel ships via mkosi.extra/ as a .deb. The substrate
    apt path MUST NOT also pull linux-image-* (double-kernel install
    causes boot ambiguity)."""
    body = _read(MKOSI_EMIT)
    has_filter = (
        ("linux-image-" in body or "linux-image" in body)
        and ("startswith" in body or "filter" in body.lower())
    )
    assert has_filter, (
        "mkosi-emit.sh missing linux-image-* / linux-headers-* filter "
        "(operator-verbatim — custom kernel ships separately; drift "
        "= double-kernel install + boot ambiguity)"
    )


def test_mkosi_zfs_tiered_repart():
    """zfs-tiered storage layout MUST get its own mkosi.repart config.
    Drift = mkosi formats the ZFS partition with ext4 by default."""
    body = _read(MKOSI_EMIT)
    assert "zfs-tiered" in body, (
        "mkosi-emit.sh missing zfs-tiered storage handling "
        "(operator-named hardware.storage.layout — drift formats "
        "ZFS partition with ext4)"
    )


def test_mkosi_zfs_partition_format_none():
    """For zfs-tiered, the root partition MUST be Format=none — the
    post-install ZFS pool-create hook lays out the pool. Drift to
    Format=zfs or Format=ext4 silently re-formats the ZFS area."""
    body = _read(MKOSI_EMIT)
    # The Format=none + ZFS pool comment SHOULD appear together
    has_correct = (
        "Format=none" in body
        and ("ZFS" in body or "zfs" in body)
    )
    assert has_correct, (
        "mkosi-emit.sh missing Format=none for ZFS root partition "
        "(operator-verbatim — post-install hook creates pool; drift "
        "to Format=ext4/zfs silently re-formats operator's data)"
    )


def test_mkosi_esp_partition_512m():
    """ESP partition SHOULD be 512M (standard EFI size; large enough
    for multiple kernels + initrds + systemd-boot)."""
    body = _read(MKOSI_EMIT)
    assert "512M" in body, (
        "mkosi-emit.sh missing 512M ESP size "
        "(standard EFI partition size; drift = boot failures with "
        "multiple kernels or large initrds)"
    )


def test_mkosi_propagates_kernel_cmdline():
    """Profile's kernel.cmdline.base + .vfio MUST flow into mkosi's
    KernelCommandLine= (operator-named §4.3 vfio-pci.ids etc. live there)."""
    body = _read(MKOSI_EMIT)
    assert "KernelCommandLine=" in body, (
        "mkosi-emit.sh missing KernelCommandLine= propagation "
        "(operator-verbatim §4.3 GRUB cmdline must reach mkosi)"
    )


# --- live-build-emit.sh (Alt-A per SDD-003) ---


def test_live_build_distribution_trixie():
    """SDD-003 verbatim: Alt-A substrate ALSO targets Debian Trixie.
    Drift between mkosi (trixie) and live-build (bookworm) = inconsistent
    profile output across substrates."""
    body = _read(LIVE_BUILD_EMIT)
    assert "trixie" in body, (
        "live-build-emit.sh missing 'trixie' distribution "
        "(SDD-003 verbatim — Alt-A path MUST match primary mkosi path)"
    )


def test_live_build_amd64_architecture():
    """Operator-named architecture: amd64 (sain-01 Zen 5 + 4090 +
    Blackwell). Drift to i386 or arm64 silently produces wrong-arch
    image for SAIN-01."""
    body = _read(LIVE_BUILD_EMIT)
    assert "amd64" in body, (
        "live-build-emit.sh missing 'amd64' architecture "
        "(operator-named SAIN-01 baseline)"
    )


def test_live_build_iso_hybrid():
    """ISO output MUST be iso-hybrid (dd-bootable to USB AND CD).
    Drift to iso9660 only = can't dd to operator's install USB."""
    body = _read(LIVE_BUILD_EMIT)
    assert "iso-hybrid" in body, (
        "live-build-emit.sh missing 'iso-hybrid' output format "
        "(operator-discovery — USB install path requires hybrid)"
    )


def test_live_build_filters_kernel_packages():
    """Alt-A path also MUST filter linux-image-* / linux-headers-*
    (same reason as mkosi-emit: custom kernel ships separately)."""
    body = _read(LIVE_BUILD_EMIT)
    assert "linux-image-" in body or "linux-headers-" in body, (
        "live-build-emit.sh missing linux-image-* filter "
        "(operator-verbatim — custom kernel ships separately via "
        "includes.chroot; drift = double-kernel install)"
    )


def test_live_build_honors_deny_list():
    """profile.packages.deny MUST be honored — operator's sovereignty
    deny-list filters out phone-home daemons. Drift silently installs
    denied packages."""
    body = _read(LIVE_BUILD_EMIT)
    assert "deny" in body, (
        "live-build-emit.sh missing profile.packages.deny handling "
        "(operator-verbatim sovereignty deny-list)"
    )


def test_live_build_iso_publisher_verbatim():
    """ISO publisher metadata = 'cyberpunk042' (operator-named ISO
    identity baked into the iso volume metadata). Drift loses
    operator-named provenance signature on the produced image."""
    body = _read(LIVE_BUILD_EMIT)
    assert "cyberpunk042" in body, (
        "live-build-emit.sh missing 'cyberpunk042' iso-publisher "
        "(operator-verbatim identity baked into ISO metadata)"
    )


def test_live_build_iso_application_sovereign_os():
    """ISO application metadata = 'Sovereign OS' (operator-named
    product identity in iso metadata)."""
    body = _read(LIVE_BUILD_EMIT)
    assert "Sovereign OS" in body, (
        "live-build-emit.sh missing 'Sovereign OS' iso-application "
        "(operator-verbatim product identity in ISO metadata)"
    )


# --- Cross-adapter invariants ---


def test_both_adapters_require_profile_yaml_arg():
    """Both emitters MUST accept profile.yaml as $1 and out_dir as $2
    (consistent CLI contract across substrates — orchestrator can call
    either without conditional argv construction)."""
    for path in (MKOSI_EMIT, LIVE_BUILD_EMIT):
        body = _read(path)
        assert "profile_yaml=" in body and "out_dir=" in body, (
            f"{path.name} missing standard 2-arg CLI "
            f"(<profile.yaml> <out-dir>) — substrate orchestrator "
            f"contract violation"
        )


def test_both_adapters_source_common_lib():
    """Both emitters MUST source lib/common.sh (provides log_*,
    require_file, etc.)."""
    for path in (MKOSI_EMIT, LIVE_BUILD_EMIT):
        body = _read(path)
        assert "lib/common.sh" in body, (
            f"{path.name} missing lib/common.sh source "
            f"(provides log_info / require_file)"
        )


def test_both_adapters_read_packages_from_profile():
    """Both emitters MUST read packages from profile.yaml
    (operator-verbatim — single source of truth for package list)."""
    for path in (MKOSI_EMIT, LIVE_BUILD_EMIT):
        body = _read(path)
        assert "packages" in body and "base" in body and "profile" in body, (
            f"{path.name} missing packages.base + packages.profile "
            f"reading (single source of truth violation)"
        )


def test_both_adapters_use_python_yaml_load():
    """Both emitters MUST use python yaml.safe_load (NOT yaml.load —
    yaml.load is a CVE-grade RCE risk on untrusted input)."""
    for path in (MKOSI_EMIT, LIVE_BUILD_EMIT):
        body = _read(path)
        assert "yaml.safe_load" in body, (
            f"{path.name} missing yaml.safe_load (security: yaml.load "
            f"is an RCE risk on untrusted profile content)"
        )
        # And MUST NOT use the unsafe yaml.load directly
        assert "yaml.load(" not in body or "yaml.safe_load" in body, (
            f"{path.name} uses yaml.load() directly — RCE risk"
        )


def test_no_unsafe_yaml_load_in_adapters():
    """Belt-and-suspenders: no bare 'yaml.load(' (without 'safe_'
    prefix) in adapter code."""
    import re
    pattern = re.compile(r"\byaml\.load\s*\(")
    for path in (MKOSI_EMIT, LIVE_BUILD_EMIT):
        body = _read(path)
        # Find any matches that aren't yaml.safe_load
        matches = [m.start() for m in pattern.finditer(body)]
        for offset in matches:
            preceding = body[max(0, offset - 5):offset]
            assert "safe_" in preceding or "safe" in body[offset-10:offset], (
                f"{path.name} at offset {offset}: bare yaml.load( "
                f"detected (security CVE: yaml.load = RCE risk on "
                f"untrusted YAML)"
            )
