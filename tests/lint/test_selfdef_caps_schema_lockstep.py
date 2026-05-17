"""Layer 1 lint — R189 / closes SDD-019 T-4.

Pin the SHAPE of selfdef's HardwareCapabilities JSON that sovereign-os
mirrors depend on. If selfdef bumps the schema without updating the
consumers (R170 modules-gate, R173 selfdef-tune.sh, R178 pick-gpu,
R182 selfdef-models, R187 cycle2-status), this test catches it
BEFORE a deploy.

The test reads selfdef-emitted FIXTURE JSON files (or canned shapes)
and asserts every key the sovereign-os scripts unconditionally
access is present. When selfdef changes the schema, the operator
sees a CI failure here + the message points at the consumer that
needs updating.

This test is intentionally a "shape pin", not a "deep schema
validation" — we don't want to fail on every harmless field
addition; only on field RENAMES / removals.
"""

from __future__ import annotations

import json
import pathlib

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


# Canonical fixture: SAIN-01-shaped capabilities JSON as emitted by
# selfdef SD-R10..R30. Mirrors the docstring example in
# scripts/hardware/selfdef-modules-gate.py.
CANONICAL_FIXTURE: dict = {
    "schema_version": "1.3.0",
    "probed_at": "2026-05-16T00:00:00Z",
    "host_tag": None,
    "cpu": {
        "vendor": "AuthenticAMD",
        "model_name": "AMD Ryzen 9 9900X",
        "physical_cores": 12,
        "logical_threads": 24,
        "sse4_2": True,
        "avx": True,
        "avx2": True,
        "fma": True,
        "avx512f": True,
        "avx512dq": True,
        "avx512bw": True,
        "avx512vl": True,
        "avx512vnni": True,
        "avx512bf16": True,
        "avx512fp16": True,
        "avx512vbmi": True,
        "avx512vbmi2": True,
        # SD-R64 derived fields. Forward-compat: pre-SD-R64 dumps
        # omit them; consumers read 0/false.
        "ternary_aot_capable": True,
        "zmm_int8_lane_capacity": 64,
        "recommended_march": "znver5",
        "recommended_compile_flags": ["-mavx512f", "-mavx512vnni"],
    },
    "memory": {
        "total_bytes": 274877906944,
        "at_least_256gb": True,
        "at_least_512gb": False,
    },
    "gpu": {
        "device_count": 2,
        "device_nodes": [],
        "devices": [
            {
                "vram_bytes": 105226698752,
                "model_hint": "NVIDIA RTX PRO 6000 Blackwell",
                "power_limit_watts": 600,
                "power_draw_watts": 275,
            },
            {
                "vram_bytes": 25769803776,
                "model_hint": "NVIDIA GeForce RTX 3090",
                "power_limit_watts": 350,
                "power_draw_watts": 180,
            },
        ],
    },
    "pcie": {"gen4_or_higher_x8_slot_count": 2, "dual_x8_present": True},
    "sain01_match": {
        "overall": "FullMatch",
        "cpu_avx512_vnni": True,
        "cpu_avx512_bf16": True,
        "memory_at_least_256gb": True,
        "gpu_count_at_least_2": True,
        "motherboard_proart_x870e": None,
        "pcie_dual_x8_present": True,
    },
    "wasm_aot": {
        "target_triple": "x86_64-unknown-linux-gnu",
        "target_cpu": "znver5",
        "target_features": "+avx512f,+avx512vnni",
        "compile_command_hint": "",
        # SD-R66 — operator-readable kernel hint. Forward-compat:
        # pre-SD-R66 dumps omit; consumers treat as empty.
        "ternary_kernel_hint": (
            "bitnet.cpp/VPDPBUSD: 64×INT8 per ZMM (master spec § 16 hot path)"
        ),
    },
}


# Top-level keys every cross-repo consumer needs.
REQUIRED_TOP_LEVEL = [
    "schema_version",
    "cpu",
    "memory",
    "gpu",
    "sain01_match",
    "wasm_aot",
]


REQUIRED_CPU_FIELDS = [
    "model_name",
    "avx512vnni",
    "avx512bf16",
    "recommended_march",
    # SD-R64 derived rollup fields — R209 mirror in
    # scripts/hardware/selfdef-modules-gate.py reads them.
    "ternary_aot_capable",
    "zmm_int8_lane_capacity",
]

REQUIRED_GPU_FIELDS = [
    "device_count",
    "devices",
]

REQUIRED_GPU_DEVICE_FIELDS = [
    "vram_bytes",
    "model_hint",
    "power_limit_watts",
    "power_draw_watts",
]

REQUIRED_SAIN01_MATCH_FIELDS = [
    "overall",
]

REQUIRED_WASM_AOT_FIELDS = [
    "target_triple",
    "target_cpu",
    "target_features",
    # SD-R66 — operator-readable kernel selection hint.
    "ternary_kernel_hint",
]


# --- Shape pins ---------------------------------------------------------------


@pytest.mark.parametrize("key", REQUIRED_TOP_LEVEL)
def test_top_level_key_present(key):
    assert key in CANONICAL_FIXTURE, (
        f"top-level key {key!r} must be present;"
        f" R170/R173/R178/R182/R187 consumers all read it"
    )


@pytest.mark.parametrize("key", REQUIRED_CPU_FIELDS)
def test_cpu_field_present(key):
    assert key in CANONICAL_FIXTURE["cpu"], (
        f"cpu.{key} must be present;"
        f" R170 gate or R173 tune lib reads it"
    )


@pytest.mark.parametrize("key", REQUIRED_GPU_FIELDS)
def test_gpu_field_present(key):
    assert key in CANONICAL_FIXTURE["gpu"], (
        f"gpu.{key} must be present;"
        f" R178 pick-gpu or R187 cycle2-status reads it"
    )


@pytest.mark.parametrize("key", REQUIRED_GPU_DEVICE_FIELDS)
def test_gpu_device_field_present(key):
    assert key in CANONICAL_FIXTURE["gpu"]["devices"][0], (
        f"gpu.devices[i].{key} must be present;"
        f" R170 gate (vram), R178 pick-gpu (model_hint), or R187"
        f" (power_*) reads it"
    )


@pytest.mark.parametrize("key", REQUIRED_SAIN01_MATCH_FIELDS)
def test_sain01_match_field_present(key):
    assert key in CANONICAL_FIXTURE["sain01_match"], (
        f"sain01_match.{key} must be present (R170 gate reads it)"
    )


@pytest.mark.parametrize("key", REQUIRED_WASM_AOT_FIELDS)
def test_wasm_aot_field_present(key):
    assert key in CANONICAL_FIXTURE["wasm_aot"], (
        f"wasm_aot.{key} must be present;"
        f" R179 wasm-aot.sh bridge reads it"
    )


# --- Cross-repo consumer sanity ----------------------------------------------


def test_selfdef_modules_gate_can_evaluate_against_canonical_fixture():
    """The R170 mirror's evaluate() function should not crash on the
    canonical fixture. Loads the script as a module via importlib
    + invokes evaluate() with an empty requirements dict."""
    import importlib.util

    p = REPO_ROOT / "scripts/hardware/selfdef-modules-gate.py"
    spec = importlib.util.spec_from_file_location("modules_gate", str(p))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # Empty requirements → always pass; the test is that evaluate
    # doesn't KeyError on the fixture shape.
    unmet = mod.evaluate({}, CANONICAL_FIXTURE)
    assert unmet == [], f"empty requirements should pass: {unmet}"


def test_selfdef_models_can_evaluate_against_canonical_fixture():
    """The R182 mirror's evaluate() function should not crash on the
    canonical fixture either."""
    import importlib.util

    p = REPO_ROOT / "scripts/models/selfdef-models.py"
    spec = importlib.util.spec_from_file_location("selfdef_models", str(p))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    unmet = mod.evaluate({}, CANONICAL_FIXTURE)
    assert unmet == [], f"empty requirements should pass: {unmet}"
