"""Test-tier harness honesty contract (F-2026-052, 2026-07-17).

SDD-008 + ARCHITECTURE.md advertise a multi-tier test harness. F-2026-052 found
the qemu/chroot tiers were effectively one bare scaffold each, so the docs
over-claimed. This lint keeps the claim honest:

  * the Layer-3 chroot harness (tests/chroot/run.sh) and the Layer-4 qemu harness
    (tests/qemu/scaffold.sh) both EXIST, are executable, PROBE their preconditions
    (a chroot mechanism / a rootfs / KVM / qemu / a built image), and SKIP-CLEAN
    when a precondition is absent — never a false green, never a hard fail;
  * the nspawn tier carries the real cross-daemon integration test (F-2026-066);
  * SDD-008 carries the "Tier status" reconciliation section so the honest state
    is documented and can't silently regress.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CHROOT = REPO / "tests" / "chroot" / "run.sh"
QEMU = REPO / "tests" / "qemu" / "scaffold.sh"
XDAEMON = REPO / "tests" / "nspawn" / "test_cross_daemon_integration.sh"
SDD008 = REPO / "docs" / "sdd" / "008-test-harness.md"


def _exec_ok(p: Path) -> bool:
    return p.is_file() and os.access(p, os.X_OK)


def test_tier_harnesses_exist_and_are_executable():
    for p in (CHROOT, QEMU, XDAEMON):
        assert _exec_ok(p), f"tier harness missing or not executable: {p}"


def test_harnesses_pass_bash_syntax():
    for p in (CHROOT, QEMU, XDAEMON):
        r = subprocess.run(["bash", "-n", str(p)], capture_output=True, text=True)
        assert r.returncode == 0, f"{p} bash syntax error: {r.stderr}"


def test_chroot_harness_probes_and_skip_cleans():
    body = CHROOT.read_text(encoding="utf-8")
    # probes a chroot mechanism + a rootfs, and has a SKIP path (skip-clean).
    assert "unshare" in body and "chroot" in body, "chroot harness must probe a mechanism"
    assert "SOVEREIGN_OS_CHROOT_ROOT" in body, "chroot harness must accept a rootfs override"
    assert "SKIP" in body or "sk " in body, "chroot harness must skip-clean"
    # real filesystem assertion (not just the friction-audit smoke it used to be).
    assert "os-release" in body, "chroot harness must assert os-release branding"


def test_chroot_harness_skip_cleans_with_exit_0():
    """No rootfs present here ⇒ the harness must exit 0 (skip-clean), not fail."""
    r = subprocess.run(
        ["bash", str(CHROOT), "sain-01"],
        capture_output=True, text=True, timeout=60,
        env={**os.environ, "SOVEREIGN_OS_CHROOT_ROOT": ""},
    )
    assert r.returncode == 0, f"chroot harness must skip-clean (exit 0), got {r.returncode}:\n{r.stdout}\n{r.stderr}"
    assert "SKIP" in r.stdout, "chroot harness should report a SKIP when no rootfs"


def test_qemu_harness_probes_preconditions_and_bridges_driver():
    body = QEMU.read_text(encoding="utf-8")
    assert "/dev/kvm" in body, "qemu harness must probe KVM"
    assert "qemu-system-x86_64" in body, "qemu harness must probe the qemu binary"
    assert "09-image-verify.sh" in body, "qemu harness must bridge to the real boot driver"
    assert "SKIP" in body or "sk " in body, "qemu harness must skip-clean"


def test_cross_daemon_test_boots_both_daemons():
    body = XDAEMON.read_text(encoding="utf-8")
    assert "sovereign-gatewayd" in body, "cross-daemon test must boot gatewayd"
    assert "brain-api.py" in body, "cross-daemon test must boot brain-api"
    assert "gateway_up" in body or "/brain/chat" in body, "must round-trip the cross-daemon path"
    assert "SKIP" in body or "sk " in body, "must skip-clean when the daemon is unavailable"


def test_sdd008_carries_honest_tier_status():
    body = SDD008.read_text(encoding="utf-8")
    assert "Tier status" in body, "SDD-008 must carry the F-2026-052 tier-status reconciliation"
    assert "skip clean" in body.lower(), "SDD-008 must state the skip-clean discipline"
    # the stale 'scaffold ships at PR 10' status must be gone.
    assert "harness scaffold ships at PR 10" not in body, "SDD-008 status still stale"
