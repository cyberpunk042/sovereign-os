"""Tetragon daemon INSTALL contract (2026-07-17 gap closure).

The sain-01 profile removed `tetragon` from the package list ("not in
the Debian archive; installs at first boot from Cilium's release
tarball") — but no code ever performed that install: on a fresh image
tetragon-policy-load.sh hard-failed with "tetragon binary not found"
and the kernel fence could not come up without an undocumented manual
step. This contract pins the closure:

  scripts/hooks/post-install/tetragon-install.sh   (the installer)
  systemd/system/sovereign-tetragon-install.service (first-boot unit)
  profiles/sain-01.yaml                            (hook registration)
  scripts/build/provision-bake.sh                  (unit baked + enabled)

Supply-chain invariants (operator-owned doctrine, same family as the
mkosi SecureBoot keys + MS003):
  - daemon version PINNED (env-overridable, never floating "latest")
  - tarball sha256 VERIFIED (operator pin or published .sha256sum);
    no checksum source → hard refusal, never an unverified install
  - fail-loud with remediation text (security boundary, no silent skip)
  - installer ordered BEFORE tetragon-policy-load in first boot
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALL_HOOK = REPO_ROOT / "scripts" / "hooks" / "post-install" / "tetragon-install.sh"
LOAD_HOOK = REPO_ROOT / "scripts" / "hooks" / "post-install" / "tetragon-policy-load.sh"
INSTALL_UNIT = REPO_ROOT / "systemd" / "system" / "sovereign-tetragon-install.service"
TARGET = REPO_ROOT / "systemd" / "system" / "sovereign-firstboot.target"
PROFILE = REPO_ROOT / "profiles" / "sain-01.yaml"
BAKE = REPO_ROOT / "scripts" / "build" / "provision-bake.sh"


def _read(p: Path) -> str:
    assert p.is_file(), f"missing {p}"
    return p.read_text(encoding="utf-8")


def test_installer_hook_exists_and_executable():
    body = _read(INSTALL_HOOK)
    assert body.startswith("#!/usr/bin/env bash"), "installer missing bash shebang"
    assert INSTALL_HOOK.stat().st_mode & 0o111, (
        "tetragon-install.sh not executable (first-boot unit ExecStart "
        "invokes it directly)"
    )


def test_installer_version_is_pinned_not_latest():
    """Daemon version MUST be pinned (env-overridable default), never a
    floating 'latest' — a silent major bump is a supply-chain surface."""
    body = _read(INSTALL_HOOK)
    assert "SOVEREIGN_OS_TETRAGON_VERSION:=" in body, (
        "tetragon-install.sh missing pinned SOVEREIGN_OS_TETRAGON_VERSION "
        "default (operator-owned version pin)"
    )
    assert "releases/latest" not in body, (
        "tetragon-install.sh must not follow releases/latest "
        "(floating version = unpinned supply chain)"
    )


def test_installer_verifies_checksum_and_refuses_unverified():
    """Tarball sha256 MUST be verified — operator-pinned env or the
    release's published .sha256sum. No checksum source available →
    hard refusal (exit 1), never an unverified install."""
    body = _read(INSTALL_HOOK)
    assert "sha256sum" in body, "tetragon-install.sh missing sha256 verification"
    assert "SOVEREIGN_OS_TETRAGON_SHA256" in body, (
        "tetragon-install.sh missing operator-pinnable "
        "SOVEREIGN_OS_TETRAGON_SHA256 override"
    )
    assert "refusing unverified install" in body, (
        "tetragon-install.sh missing the no-checksum-source hard refusal "
        "(drift = silent unverified binary on the security boundary)"
    )


def test_installer_is_idempotent_on_present_daemon():
    body = _read(INSTALL_HOOK)
    assert "command -v tetragon" in body and "no-op" in body, (
        "tetragon-install.sh missing already-present no-op "
        "(idempotency contract for first-boot hooks)"
    )


def test_installer_emits_layer_b_metric():
    body = _read(INSTALL_HOOK)
    assert "sovereign_os_post_install_tetragon_install_total" in body, (
        "tetragon-install.sh missing per-result metric (SDD-016 Layer B)"
    )


def test_installer_uses_cilium_release_url():
    """The profile's verbatim claim is 'installs at first boot from
    Cilium's release tarball' — the URL must be Cilium's GitHub release,
    asset shape tetragon-v<VER>-amd64.tar.gz (vendor-documented flow)."""
    body = _read(INSTALL_HOOK)
    assert "github.com/cilium/tetragon/releases/download" in body, (
        "tetragon-install.sh not fetching from Cilium's release URL "
        "(profile-verbatim source claim)"
    )
    assert "-amd64.tar.gz" in body, (
        "tetragon-install.sh missing the vendor tarball asset shape"
    )


def test_install_unit_exists_and_ordered_before_policy_load():
    body = _read(INSTALL_UNIT)
    assert "ConditionFirstBoot=yes" in body, (
        "sovereign-tetragon-install.service missing ConditionFirstBoot"
    )
    assert "Before=sovereign-tetragon-policy-load.service" in body, (
        "installer unit not ordered Before= policy-load — the load hook "
        "hard-fails when the daemon binary is absent"
    )
    assert "network-online.target" in body, (
        "installer unit missing network-online ordering (release fetch "
        "needs the network up)"
    )
    assert "WantedBy=sovereign-firstboot.target" in body, (
        "installer unit not a first-boot target member"
    )


def test_firstboot_target_wants_install_unit():
    """G1/SDD-998: target MUST Wants= each member explicitly."""
    body = _read(TARGET)
    assert "sovereign-tetragon-install.service" in body, (
        "sovereign-firstboot.target missing Wants= for the tetragon "
        "installer (member would never start — G1 failure shape)"
    )


def test_profile_registers_installer_before_policy_load():
    body = _read(PROFILE)
    assert "tetragon-install" in body, (
        "sain-01.yaml missing tetragon-install hook registration"
    )
    assert body.index("tetragon-install") < body.index("tetragon-policy-load"), (
        "sain-01.yaml orders tetragon-install AFTER tetragon-policy-load "
        "(load would fail on missing daemon)"
    )


def test_provision_bake_installs_the_unit():
    body = _read(BAKE)
    assert "sovereign-tetragon-install.service" in body, (
        "provision-bake.sh FB_UNITS missing sovereign-tetragon-install"
        ".service (unit never lands on the flashed image)"
    )


def test_load_hook_points_at_installer_for_remediation():
    """The load hook's binary-missing error must name the installer
    (block-with-reason-and-remediation doctrine)."""
    body = _read(LOAD_HOOK)
    assert "tetragon-install.sh" in body, (
        "tetragon-policy-load.sh missing-binary error must point at "
        "tetragon-install.sh as remediation"
    )
