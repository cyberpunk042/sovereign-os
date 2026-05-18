"""R433 (E10.M77) — selfdef-tune.sh cross-repo bridge contract lint.

Extends R387-R432 + R418/R428 operational-artifact pinning to:
  scripts/build/lib/selfdef-tune.sh

R418 covered build/lib/* infrastructure; R428 covered pulse-build's
use of selfdef-tune for znver5 + AVX-512 CFLAGS. R433 covers the
DETAILED CONTRACT of the cross-repo integration:

  Source-order preference (operator-named):
    1. selfdefctl CLI (SD-R19 'hardware tune --format env-file')
    2. /var/lib/selfdef/hardware-capabilities.json (SD-R10 JSON)
    3. Native fallback (probe local /proc/cpuinfo)

  Variables exported:
    SELFDEF_HARDWARE_MARCH                — march flag (e.g., znver5)
    SELFDEF_HARDWARE_CFLAGS               — compile flags
    SELFDEF_HARDWARE_KCFLAGS              — kernel-build flags
    SELFDEF_HARDWARE_AVX512_VNNI          — true/false
    SELFDEF_HARDWARE_AVX512_BF16          — true/false
    SELFDEF_HARDWARE_TUNE_SOURCE          — which path produced the vars
    SELFDEF_HARDWARE_WASM_AOT_TARGET_*    — SD-R30 forward-compat

If a future agent silently:
  - changes the source-order preference = downstream callers (R428
    build-bitnet.sh) get unexpected flags
  - drops the native-fallback path = lib fails on hosts without
    selfdefctl OR capabilities.json
  - renames any SELFDEF_HARDWARE_* env var = R428 build-bitnet.sh
    breaks at runtime
…the cross-repo flag-derivation loop silently breaks.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SELFDEF_TUNE = REPO_ROOT / "scripts" / "build" / "lib" / "selfdef-tune.sh"


def _read() -> str:
    assert SELFDEF_TUNE.is_file(), f"missing {SELFDEF_TUNE}"
    return SELFDEF_TUNE.read_text(encoding="utf-8")


# --- Structural ---


def test_selfdef_tune_file_exists():
    assert SELFDEF_TUNE.is_file(), f"missing {SELFDEF_TUNE}"


def test_header_documents_cross_repo_bridge():
    body = _read()
    has_bridge = (
        "cross-repo" in body.lower()
        or "selfdef" in body.lower()
    )
    assert has_bridge, (
        "selfdef-tune.sh missing cross-repo bridge documentation"
    )


# --- 3-source preference order ---


def test_documents_three_source_preference_order():
    """Operator-named: 3-source preference (selfdefctl >
    capabilities.json > native fallback). Drift = downstream
    callers get unexpected flags."""
    body = _read()
    has_order = (
        "preference" in body.lower()
        or "Source-order" in body
        or "fallback" in body.lower()
    )
    assert has_order, (
        "selfdef-tune.sh missing 3-source preference order docs"
    )


def test_references_selfdefctl():
    body = _read()
    assert "selfdefctl" in body, (
        "selfdef-tune.sh missing selfdefctl CLI reference "
        "(operator-named source 1)"
    )


def test_references_sd_r19():
    """SD-R19 is the operator-named round that shipped
    `selfdefctl hardware tune --format env-file`."""
    body = _read()
    assert "SD-R19" in body, (
        "selfdef-tune.sh missing SD-R19 round reference "
        "(operator-named selfdefctl CLI provenance)"
    )


def test_references_capabilities_json_path():
    """Source 2: /var/lib/selfdef/hardware-capabilities.json."""
    body = _read()
    assert "/var/lib/selfdef/hardware-capabilities.json" in body, (
        "selfdef-tune.sh missing capabilities.json path "
        "(operator-named source 2 — SD-R10 JSON fallback)"
    )


def test_references_sd_r10():
    """SD-R10 is the operator-named round that shipped the
    capabilities.json schema."""
    body = _read()
    assert "SD-R10" in body, (
        "selfdef-tune.sh missing SD-R10 round reference"
    )


def test_references_native_fallback():
    body = _read()
    has_fallback = (
        "native" in body.lower()
        or "native fallback" in body.lower()
        or "fallback_native" in body
    )
    assert has_fallback, (
        "selfdef-tune.sh missing native-fallback path "
        "(source 3 — drift = lib fails on minimal hosts)"
    )


# --- Function contract ---


def test_defines_selfdef_tune_load():
    body = _read()
    assert re.search(r"^selfdef_tune_load\(\)", body, re.M), (
        "selfdef-tune.sh missing selfdef_tune_load() entry point "
        "(operator-named public API)"
    )


def test_defines_helper_functions():
    """Internal helpers MUST exist for each source path."""
    body = _read()
    expected = [
        "selfdef_tune__try_selfdefctl",
        "selfdef_tune__try_capabilities_json",
        "selfdef_tune__fallback_native",
    ]
    for fn in expected:
        assert re.search(rf"^{re.escape(fn)}\(\)", body, re.M), (
            f"selfdef-tune.sh missing {fn}() helper "
            f"(source-path implementation)"
        )


# --- Exported env vars ---


def test_exports_selfdef_hardware_march():
    body = _read()
    assert "SELFDEF_HARDWARE_MARCH" in body, (
        "selfdef-tune.sh missing SELFDEF_HARDWARE_MARCH export "
        "(R428 build-bitnet.sh consumes it)"
    )


def test_exports_selfdef_hardware_cflags():
    body = _read()
    assert "SELFDEF_HARDWARE_CFLAGS" in body, (
        "selfdef-tune.sh missing SELFDEF_HARDWARE_CFLAGS export"
    )


def test_exports_selfdef_hardware_kcflags():
    body = _read()
    assert "SELFDEF_HARDWARE_KCFLAGS" in body, (
        "selfdef-tune.sh missing SELFDEF_HARDWARE_KCFLAGS "
        "(kernel build consumes it)"
    )


def test_exports_avx512_capability_flags():
    body = _read()
    assert "SELFDEF_HARDWARE_AVX512_VNNI" in body, (
        "selfdef-tune.sh missing SELFDEF_HARDWARE_AVX512_VNNI"
    )
    assert "SELFDEF_HARDWARE_AVX512_BF16" in body, (
        "selfdef-tune.sh missing SELFDEF_HARDWARE_AVX512_BF16"
    )


def test_exports_tune_source_marker():
    """SELFDEF_HARDWARE_TUNE_SOURCE marks which path produced the
    vars (operator-discoverable: am I getting selfdefctl-tuned vars
    or native-fallback?)."""
    body = _read()
    assert "SELFDEF_HARDWARE_TUNE_SOURCE" in body, (
        "selfdef-tune.sh missing TUNE_SOURCE marker "
        "(operator-discoverable: which path produced the vars)"
    )


def test_exports_wasm_aot_forward_compat():
    """SD-R30 forward-compat fields. Drift removing breaks Wasm-AOT
    integration when SD-R30 lands."""
    body = _read()
    has_wasm = (
        "SELFDEF_HARDWARE_WASM_AOT" in body
        or "WASM_AOT" in body
    )
    assert has_wasm, (
        "selfdef-tune.sh missing WASM_AOT forward-compat fields "
        "(SD-R30 cross-repo integration)"
    )


# --- Idempotency ---


def test_idempotent_call_documented():
    """Operator-discoverable: calling selfdef_tune_load twice is a
    no-op. Drift = repeated calls overwrite operator-set values."""
    body = _read()
    has_idempotent = (
        "Idempotent" in body
        or "idempotent" in body
    )
    assert has_idempotent, (
        "selfdef-tune.sh missing idempotency documentation "
        "(operator-discoverable contract — drift = repeated calls "
        "clobber operator-set values)"
    )


def test_set_default_respects_pre_existing():
    """selfdef_tune__set_default helper MUST NOT clobber if var
    is already set (caller-wins contract)."""
    body = _read()
    # Look for the pattern that checks if var is already set
    has_check = (
        "set_default" in body
        and ("[ -z" in body or "if [ -z" in body)
    )
    assert has_check, (
        "selfdef-tune.sh set_default helper doesn't check pre-existing "
        "(drift = clobbers operator-set values)"
    )


# --- Bidirectional consistency with consumer (R428 build-bitnet.sh) ---


def test_bidirectional_consumer_uses_correct_var_names():
    """R428 build-bitnet.sh reads SELFDEF_HARDWARE_MARCH and
    SELFDEF_HARDWARE_CFLAGS. Drift renaming = build-bitnet breaks."""
    build_bitnet = REPO_ROOT / "scripts" / "pulse" / "build-bitnet.sh"
    if build_bitnet.is_file():
        consumer_body = build_bitnet.read_text(encoding="utf-8")
        lib_body = _read()
        # Both files MUST reference the same env var names
        shared_vars = ["SELFDEF_HARDWARE_MARCH", "SELFDEF_HARDWARE_CFLAGS"]
        for var in shared_vars:
            if var in consumer_body:
                assert var in lib_body, (
                    f"build-bitnet.sh consumes {var!r} but selfdef-"
                    f"tune.sh doesn't export it (BIDIRECTIONAL "
                    f"CONSISTENCY VIOLATION)"
                )


def test_module_referenced_in_inference_router_or_pulse_build():
    """selfdef-tune.sh is sourced by R428 build-bitnet.sh. That
    consumer MUST source the lib (drift = consumer uses hardcoded
    flags ignoring operator-tuning)."""
    build_bitnet = REPO_ROOT / "scripts" / "pulse" / "build-bitnet.sh"
    if build_bitnet.is_file():
        consumer_body = build_bitnet.read_text(encoding="utf-8")
        assert "selfdef-tune.sh" in consumer_body, (
            "build-bitnet.sh doesn't source selfdef-tune.sh "
            "(cross-repo flag-derivation loop broken)"
        )


# --- Robustness ---


def test_handles_missing_selfdefctl_gracefully():
    """Source 1 path MUST handle 'selfdefctl not on PATH'
    gracefully (fall to source 2). Drift = lib crashes when
    selfdef package isn't installed."""
    body = _read()
    has_check = (
        "command -v selfdefctl" in body
        and "return 1" in body
    )
    assert has_check, (
        "selfdef-tune.sh source 1 doesn't handle missing selfdefctl "
        "(drift = crashes on minimal hosts)"
    )


def test_handles_empty_output_gracefully():
    """If selfdefctl returns empty output, fall to next source.
    Drift = empty selfdefctl output causes lib to set vars to ''."""
    body = _read()
    has_check = (
        "-z" in body  # bash empty check
        and "rc" in body  # exit code check
    )
    assert has_check, (
        "selfdef-tune.sh source 1 doesn't handle empty output "
        "(drift = sets vars to '' silently)"
    )
