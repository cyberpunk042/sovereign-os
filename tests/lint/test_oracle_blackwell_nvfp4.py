"""R455 (E11.M4 — Nemotron 3 NVFP4 finish) — Blackwell-aware default
quantization for Oracle Core start script.

Per operator §1g verbatim:
  "Nvidia Nemotron 3, Nano Omni... all the best selection of models
   adapted for various size and at various quantization or for various
   specific purpose"

R446 added the NVFP4 catalog entry (partial completion of E11.M4).
R455 finishes by wiring NVFP4 as the Blackwell-detected default in
the Oracle Core start script + VRAM verification on every start.
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ORACLE_SH = REPO_ROOT / "scripts" / "inference" / "start-oracle-core.sh"
CATALOG = REPO_ROOT / "models" / "catalog.yaml"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _dry_run_env(**overrides) -> dict:
    """A DRY-RUN env isolated from the operator's ACTIVE runtime profile.

    start-oracle-core.sh's `runtime_profile_override ORACLE_MODEL` reads the
    active runtime profile from three sources, in this precedence order (see
    `runtime_profile_active_file` in scripts/build/lib/runtime-profile.sh):
      1. `$SOVEREIGN_OS_RUNTIME_PROFILE`
      2. `/etc/sovereign-os/active-runtime-profile`
      3. `~/.sovereign-os/active-runtime-profile`
    and, if the active profile names an oracle model, fills an empty
    ORACLE_MODEL from it — which on a developer box (where a profile like
    `high-concurrency-burst` is active and pins a specific oracle model)
    DEFEATS these quantization->model default tests and makes them fail only
    there, not on a clean CI box.

    Deleting the env var + repointing $HOME is NOT enough: source 2 (`/etc/…`)
    is a system path that cannot be redirected without root, so a box that has
    `/etc/sovereign-os/active-runtime-profile` still leaks its profile in.
    Because source 1 takes precedence and, when set, short-circuits BOTH file
    sources, we pin `$SOVEREIGN_OS_RUNTIME_PROFILE` to a deliberately ABSENT
    sentinel id: `runtime_profile_active_file` resolves it to
    `profiles/runtime/<sentinel>.yaml`, finds no such file, and reports "none
    active" — so no ambient profile (env, /etc, or $HOME) can leak, and the
    test hermetically exercises the script's OWN default selection logic.
    ($HOME is still repointed as defence-in-depth.)"""
    env = dict(os.environ)
    # Source 1 wins and, being non-empty, skips the /etc + $HOME file lookups;
    # the sentinel names no real profiles/runtime/*.yaml -> "none active".
    env["SOVEREIGN_OS_RUNTIME_PROFILE"] = "__hermetic_test_no_profile__"
    env["HOME"] = "/nonexistent"      # no ~/.sovereign-os/active-runtime-profile
    env["SOVEREIGN_OS_DRY_RUN"] = "1"
    env.update(overrides)
    return env


# --- Structural ---


def test_oracle_start_script_exists():
    assert ORACLE_SH.is_file(), f"missing {ORACLE_SH}"


def test_oracle_start_script_executable():
    assert os.access(ORACLE_SH, os.X_OK), f"{ORACLE_SH} not executable"


def test_documents_r455_origin():
    body = _read(ORACLE_SH)
    assert "R455" in body and "E11.M4" in body


def test_quotes_operator_1g_quantization_phrase():
    """§1g verbatim quantization phrase MUST appear in script."""
    body = _read(ORACLE_SH)
    flat = re.sub(r"\s+", " ", body)
    assert "various size and at various quantization" in flat, (
        "missing operator §1g verbatim quantization phrase"
    )


# --- Blackwell detection ---


def test_blackwell_detector_function_present():
    body = _read(ORACLE_SH)
    assert "oracle_is_blackwell()" in body, (
        "missing oracle_is_blackwell() function"
    )


def test_blackwell_detector_uses_compute_cap():
    """Detector MUST probe nvidia-smi compute_cap (≥10.0 = Blackwell SM_100)."""
    body = _read(ORACLE_SH)
    assert "compute_cap" in body or "compute-cap" in body, (
        "Blackwell detector should probe compute_cap"
    )


def test_vram_probe_function_present():
    body = _read(ORACLE_SH)
    assert "oracle_max_vram_gib()" in body, (
        "missing oracle_max_vram_gib() function"
    )


def test_vram_probe_uses_nvidia_smi():
    body = _read(ORACLE_SH)
    assert "memory.total" in body, (
        "VRAM probe should query nvidia-smi memory.total"
    )


# --- Quantization-aware defaults ---


def test_quantization_env_var_defined():
    body = _read(ORACLE_SH)
    assert "ORACLE_QUANTIZATION" in body, (
        "missing ORACLE_QUANTIZATION env var"
    )


def test_quantization_default_is_nvfp4_on_blackwell():
    """When Blackwell detected, default MUST be nvfp4."""
    body = _read(ORACLE_SH)
    flat = re.sub(r"\s+", " ", body)
    # Look for the conditional assignment
    assert re.search(
        r'oracle_is_blackwell.*?ORACLE_QUANTIZATION\s*=\s*"nvfp4"',
        flat,
    ), (
        "Blackwell→nvfp4 default not wired"
    )


def test_quantization_default_is_bf16_off_blackwell():
    """When Blackwell NOT detected, default MUST be bf16."""
    body = _read(ORACLE_SH)
    flat = re.sub(r"\s+", " ", body)
    assert re.search(
        r'ORACLE_QUANTIZATION\s*=\s*"bf16"',
        flat,
    ), (
        "bf16 fallback default not wired"
    )


def test_quantization_path_selection_for_three_variants():
    """Each of nvfp4/fp8/bf16 MUST select a distinct catalog path."""
    body = _read(ORACLE_SH)
    for variant in ("nvfp4", "fp8", "bf16"):
        assert variant in body, f"missing variant {variant!r} case"
    # All 3 model paths
    for path_marker in (
        "Reasoning-NVFP4",
        "Reasoning-FP8",
        "Reasoning-BF16",
    ):
        assert path_marker in body, (
            f"missing model path marker {path_marker!r}"
        )


def test_quantization_overrideable_via_env():
    """ORACLE_QUANTIZATION must be respected when set explicitly."""
    body = _read(ORACLE_SH)
    # The conditional default must check `-z "${ORACLE_QUANTIZATION:-}"`
    # so that an explicit override is preserved.
    flat = re.sub(r"\s+", " ", body)
    assert re.search(
        r'-z\s+"\${ORACLE_QUANTIZATION',
        flat,
    ), (
        "ORACLE_QUANTIZATION default-check should test for empty before "
        "overriding, so operator env var wins"
    )


# --- VRAM verification ---


def test_vram_required_per_variant():
    body = _read(ORACLE_SH)
    assert "ORACLE_VRAM_REQUIRED_GIB" in body
    # Each variant sets its own VRAM minimum
    assert ":=22" in body, "nvfp4 should default 22 GiB"
    assert ":=32" in body, "fp8 should default 32 GiB"
    assert ":=64" in body, "bf16 should default 64 GiB"


def test_vram_check_warns_below_required():
    """Below-required VRAM MUST trigger a warning (operator-discoverable)."""
    body = _read(ORACLE_SH)
    flat = re.sub(r"\s+", " ", body)
    assert "OOM risk" in flat or "OOM" in body, (
        "VRAM check should warn about OOM risk"
    )
    assert "log_warn" in body, (
        "VRAM warning should use log_warn"
    )


# --- Catalog cross-ref ---


def test_catalog_has_nvfp4_variant():
    body = _read(CATALOG)
    assert "Nemotron-3-Nano-Omni-30B-Reasoning-NVFP4" in body, (
        "catalog missing NVFP4 entry (R446)"
    )


def test_catalog_has_fp8_variant():
    body = _read(CATALOG)
    assert "Nemotron-3-Nano-Omni-30B-Reasoning-FP8" in body


def test_catalog_has_bf16_variant():
    body = _read(CATALOG)
    assert "Nemotron-3-Nano-Omni-30B-Reasoning-BF16" in body


# --- Logging surface ---


def test_logs_chosen_quantization():
    """Operator-discovery: every start MUST log the chosen quant."""
    body = _read(ORACLE_SH)
    assert "quantization:" in body, (
        "start should log chosen quantization line"
    )


def test_logs_vram_required():
    body = _read(ORACLE_SH)
    assert "vram required:" in body, (
        "start should log VRAM-required + detected"
    )


# --- Smoke test ---


def test_dry_run_smoke():
    """DRY-RUN must complete + log Blackwell-detection + quant + VRAM."""
    result = subprocess.run(
        ["bash", str(ORACLE_SH)],
        capture_output=True, text=True, timeout=15,
        # Force a clean env so detector branches don't surprise us
        env=_dry_run_env(ORACLE_QUANTIZATION=""),
    )
    assert result.returncode == 0, (
        f"DRY_RUN failed: stderr={result.stderr[:500]}, "
        f"stdout={result.stdout[:500]}"
    )
    combined = result.stdout + result.stderr
    assert "R455" in combined, "R455 anchor not logged"
    assert "quantization:" in combined, "quantization not logged"
    assert "vram required:" in combined, "VRAM-required not logged"


def test_dry_run_explicit_nvfp4_selects_nvfp4_path():
    result = subprocess.run(
        ["bash", str(ORACLE_SH)],
        capture_output=True, text=True, timeout=15,
        env=_dry_run_env(ORACLE_QUANTIZATION="nvfp4", ORACLE_MODEL=""),
    )
    assert result.returncode == 0
    combined = result.stdout + result.stderr
    assert "NVFP4" in combined, (
        "nvfp4 override should select the NVFP4 model path"
    )


def test_dry_run_explicit_bf16_selects_bf16_path():
    result = subprocess.run(
        ["bash", str(ORACLE_SH)],
        capture_output=True, text=True, timeout=15,
        env=_dry_run_env(ORACLE_QUANTIZATION="bf16", ORACLE_MODEL=""),
    )
    assert result.returncode == 0
    combined = result.stdout + result.stderr
    assert "BF16" in combined, (
        "bf16 override should select the BF16 model path"
    )
