"""Layer-4 in-guest feature-conformance harness contract (F-2026-052).

The QEMU tier (SDD-008 Layer 4) was scaffold-only: `tests/qemu/scaffold.sh`
probes preconditions and bridges to the boot smoke, but nothing ran the shipped
features' live self-tests INSIDE the guest. `tests/qemu/feature-conformance.sh`
closes that: it builds the `sovereign-feature-selftest` payload and, when a
KVM-capable runner + built image are present, runs `--self-check` in-guest and
asserts `all_ok`. This lint pins the harness's structure + the honest gating
(the boot transport is environment-gated; the payload is covered host-side by
`cargo test -p sovereign-feature-selftest`).
"""
from __future__ import annotations

import stat
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HARNESS = REPO / "tests" / "qemu" / "feature-conformance.sh"
SELFTEST = REPO / "crates" / "sovereign-feature-selftest" / "src" / "main.rs"


def test_harness_exists_and_is_executable():
    assert HARNESS.is_file(), "the Layer-4 feature-conformance harness must exist"
    mode = HARNESS.stat().st_mode
    assert mode & stat.S_IXUSR, "the harness must be executable"


def test_harness_runs_the_selftest_payload_in_guest_with_graceful_skip():
    src = HARNESS.read_text(encoding="utf-8")
    # It drives the real feature self-test binary in-guest and asserts all_ok.
    assert "sovereign-feature-selftest --self-check" in src
    assert '"all_ok": true' in src, "must assert the in-guest self-check reports all_ok"
    # Boot transport reuses the existing image-verify driver.
    assert "09-image-verify.sh" in src
    # Graceful, precondition-gated SKIP (KVM + qemu + image) — CI-safe.
    assert "/dev/kvm" in src and "qemu-system-x86_64" in src
    assert "exit 0" in src, "an environment-gated skip must exit 0"
    # It builds the payload so the features are exercised even when the run skips.
    assert "cargo build --release -p sovereign-feature-selftest" in src


def test_selftest_payload_is_covered_host_side():
    # The Layer-4 payload (the feature self-tests) is asserted by a host-side test,
    # so features are verified even where the QEMU boot transport can't run.
    src = SELFTEST.read_text(encoding="utf-8")
    assert "fn every_feature_self_test_passes" in src
    assert "assert!(r.ok" in src, "every registered feature self-test must be asserted to pass"


def test_harness_documents_the_gating_honestly():
    src = HARNESS.read_text(encoding="utf-8")
    low = src.lower()
    assert "environment-gated" in low
    assert "cargo test -p sovereign-feature-selftest" in src, (
        "the harness must point to the host-side payload coverage"
    )
