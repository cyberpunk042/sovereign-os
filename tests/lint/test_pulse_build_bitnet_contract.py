"""R428 (E10.M72) — Pulse runtime build script (bitnet.cpp) operator-
verbatim § 15-16 + § 17.1 contract + 17th bidirectional-consistency
lint (build script model_repo ↔ model catalog hf_repo_id ↔ backend
adapter DEFAULT_MODEL).

Extends R387-R427 + R394/R404/R427 operational-artifact pinning to:
  scripts/pulse/build-bitnet.sh  (Stage-2 operator-named Pulse build)

R394 covered pulse-bitnet-build verbatim earlier (header content);
R404 covered BitnetBackend DEFAULT_MODEL; R427 covered model catalog.
R428 closes the 4-way ring:

  build-bitnet.sh BITNET_MODEL_REPO default
    ↔ model catalog hf_repo_id for the Pulse default model
    ↔ scripts/inference/backends/bitnet.py DEFAULT_MODEL
    ↔ scripts/inference/start-pulse.sh PULSE_MODEL default

Master spec § 15-16 + § 17.1 verbatim:
  - 1-Bit Paradigm (BitNet ternary)
  - 512-bit AVX-512 Fusion (znver5 + VNNI + bf16)
  - The Pulse Module 1

17th bidirectional-consistency lint:
  build-bitnet.sh BITNET_MODEL_REPO default MUST match the model
  catalog's verified-real BitNet entry hf_repo_id AND match
  bitnet.py DEFAULT_MODEL. Drift between any pair = silent download
  of one model + start of another = mismatch.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
BUILD_SH = REPO_ROOT / "scripts" / "pulse" / "build-bitnet.sh"
CATALOG = REPO_ROOT / "models" / "catalog.yaml"
BITNET_PY = REPO_ROOT / "scripts" / "inference" / "backends" / "bitnet.py"
START_PULSE = REPO_ROOT / "scripts" / "inference" / "start-pulse.sh"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# --- Structural ---


def test_build_bitnet_sh_exists():
    assert BUILD_SH.is_file(), f"missing {BUILD_SH}"


def test_build_bitnet_is_executable():
    """Operator-runnable script MUST be executable."""
    import os
    assert os.access(BUILD_SH, os.X_OK), (
        f"{BUILD_SH} not executable (operator can't run it directly)"
    )


def test_set_euo_pipefail():
    body = _read(BUILD_SH)
    assert "set -euo pipefail" in body, (
        "build-bitnet.sh missing 'set -euo pipefail' (SDD-001 strict)"
    )


# --- Master spec § 15-16 + § 17.1 verbatim ---


def test_documents_section_15_16():
    body = _read(BUILD_SH)
    has_ref = (
        ("§ 15" in body or "§15" in body or "section 15" in body.lower())
        and ("§ 16" in body or "§16" in body or "section 16" in body.lower())
    )
    assert has_ref, (
        "build-bitnet.sh missing master spec § 15-16 reference "
        "(operator-discovery — drift loses 1-Bit Paradigm + AVX-512 "
        "Fusion binding)"
    )


def test_documents_section_17_pulse_module():
    body = _read(BUILD_SH)
    has_pulse = (
        "§ 17" in body or "section 17" in body.lower()
    )
    has_module = "Module 1" in body or "Pulse" in body
    assert has_pulse and has_module, (
        "build-bitnet.sh missing § 17 Pulse Module 1 reference"
    )


def test_uses_znver5_march_flag():
    """§ 16 verbatim: -march=znver5 (operator-named Zen 5 architecture).
    Drift to znver4 or generic = lost CPU-specific optimization."""
    body = _read(BUILD_SH)
    assert "-march=znver5" in body, (
        "build-bitnet.sh missing -march=znver5 CFLAG "
        "(§ 16 verbatim — operator-named Zen 5 microarch)"
    )


def test_uses_avx512_flags():
    """§ 16 verbatim: AVX-512 family (f + dq + bw + vl + bf16 + fp16)."""
    body = _read(BUILD_SH)
    expected_flags = [
        "-mavx512f",
        "-mavx512dq",
        "-mavx512bw",
        "-mavx512vl",
        "-mavx512bf16",
        "-mavx512fp16",
    ]
    for flag in expected_flags:
        assert flag in body, (
            f"build-bitnet.sh missing {flag} (§ 16 AVX-512 Fusion)"
        )


def test_warns_when_avx512_vnni_missing():
    """§ 16 verbatim: avx512_vnni is required for master-spec perf.
    Operator-discoverable warning when CPU lacks it (drift = silent
    degradation)."""
    body = _read(BUILD_SH)
    has_vnni_check = "avx512_vnni" in body
    assert has_vnni_check, (
        "build-bitnet.sh missing avx512_vnni runtime check "
        "(§ 16 verbatim performance gate — drift = silent degradation)"
    )


# --- Operator-discoverable env-var contract ---


def test_supports_dry_run():
    body = _read(BUILD_SH)
    assert "SOVEREIGN_OS_DRY_RUN" in body, (
        "build-bitnet.sh missing SOVEREIGN_OS_DRY_RUN handling"
    )


def test_supports_skip_model_env():
    """Operator-discoverable: BITNET_SKIP_MODEL=1 skips model fetch
    (useful when model is provisioned out-of-band)."""
    body = _read(BUILD_SH)
    assert "BITNET_SKIP_MODEL" in body, (
        "build-bitnet.sh missing BITNET_SKIP_MODEL env var "
        "(operator can't decouple build from model fetch)"
    )


def test_supports_skip_build_env():
    """Operator-discoverable: BITNET_SKIP_BUILD=1 only fetches model
    (when binary is pre-built / pre-packaged)."""
    body = _read(BUILD_SH)
    assert "BITNET_SKIP_BUILD" in body, (
        "build-bitnet.sh missing BITNET_SKIP_BUILD env var"
    )


def test_install_dir_default_usr_local():
    """Default install prefix = /usr/local (operator-discoverable
    standard FHS location)."""
    body = _read(BUILD_SH)
    assert "/usr/local" in body, (
        "build-bitnet.sh missing /usr/local default install prefix "
        "(operator-discoverable FHS location)"
    )


def test_emits_pulse_build_metric():
    """SDD-016: sovereign_os_pulse_build_total counter."""
    body = _read(BUILD_SH)
    assert "sovereign_os_pulse_build_total" in body, (
        "build-bitnet.sh missing sovereign_os_pulse_build_total metric"
    )


def test_emits_last_run_timestamp():
    """SDD-016: last_run_timestamp gauge (staleness detection)."""
    body = _read(BUILD_SH)
    assert "sovereign_os_pulse_build_last_run_timestamp" in body, (
        "build-bitnet.sh missing last_run_timestamp gauge"
    )


def test_idempotency_check_present():
    """Operator-named: re-runs are idempotent. Script MUST detect
    already-installed state + skip."""
    body = _read(BUILD_SH)
    has_idempotent = (
        "already installed" in body
        or "skipping build" in body
        or "command -v bitnet-cli" in body
    )
    assert has_idempotent, (
        "build-bitnet.sh missing idempotency check (operator-named)"
    )


# --- 17th bidirectional-consistency lint ---


def test_bidirectional_default_model_with_backend_adapter():
    """17th bidirectional-consistency lint (part 1):
      build-bitnet.sh BITNET_MODEL_REPO default
        ↔ bitnet.py DEFAULT_MODEL

    Drift = build fetches one model, start serves another."""
    build_body = _read(BUILD_SH)
    bitnet_body = _read(BITNET_PY)

    # Extract BITNET_MODEL_REPO default from build script
    m = re.search(r"BITNET_MODEL_REPO:=(\S+?)\}", build_body)
    assert m, (
        "build-bitnet.sh missing BITNET_MODEL_REPO default value"
    )
    build_default = m.group(1)

    # bitnet.py MUST have the same model id in DEFAULT_MODEL
    assert build_default in bitnet_body, (
        f"build-bitnet.sh defaults to BITNET_MODEL_REPO={build_default!r} "
        f"but bitnet.py DEFAULT_MODEL doesn't include it "
        f"(BIDIRECTIONAL CONSISTENCY VIOLATION: build fetches one "
        f"model, runtime serves another)"
    )


def test_bidirectional_default_model_with_catalog():
    """17th bidirectional consistency (part 2):
      build-bitnet.sh BITNET_MODEL_REPO default
        ↔ models/catalog.yaml hf_repo_id for some Pulse model

    Drift = build fetches a model that isn't in the catalog."""
    build_body = _read(BUILD_SH)
    catalog_data = yaml.safe_load(_read(CATALOG)) or {}
    models = ((catalog_data.get("catalog") or {}).get("models") or [])

    m = re.search(r"BITNET_MODEL_REPO:=(\S+?)\}", build_body)
    assert m
    build_default = m.group(1)

    # At least one Pulse model in catalog SHOULD have hf_repo_id
    # matching the build default
    pulse_hf_repos = {
        model.get("hf_repo_id", "")
        for model in models
        if model.get("tier") == "pulse"
    }
    assert any(build_default == r for r in pulse_hf_repos), (
        f"build-bitnet.sh BITNET_MODEL_REPO={build_default!r} but no "
        f"Pulse model in catalog has matching hf_repo_id "
        f"(catalog Pulse hf_repo_id set: {pulse_hf_repos})"
    )


def test_bidirectional_default_model_with_start_pulse():
    """17th bidirectional consistency (part 3):
      build-bitnet.sh BITNET_MODEL_REPO default
        ↔ start-pulse.sh PULSE_MODEL default

    Drift = build fetches model to one path, start-pulse reads
    from another."""
    build_body = _read(BUILD_SH)
    start_body = _read(START_PULSE)

    # Extract the model path from start-pulse.sh (PULSE_MODEL default)
    # The defaults in both should reference the same model id slug
    # (e.g., 'microsoft__bitnet-b1.58-2B-4T' in start-pulse.sh paths
    # and 'microsoft/bitnet-b1.58-2B-4T' in build script repo URL)
    has_bitnet_id = (
        "bitnet-b1.58-2B-4T" in build_body
        and "bitnet-b1.58-2B-4T" in start_body
    )
    assert has_bitnet_id, (
        "build-bitnet.sh and start-pulse.sh disagree on default "
        "model id (bitnet-b1.58-2B-4T should appear in both)"
    )


# --- Build tooling prerequisites ---


def test_checks_for_required_build_tools():
    """build-bitnet.sh MUST verify git + cmake + make + g++ are present
    (operator-discoverable preflight error vs cryptic build failure)."""
    body = _read(BUILD_SH)
    expected_tools = ["git", "cmake", "make", "g++"]
    for tool in expected_tools:
        assert tool in body, (
            f"build-bitnet.sh missing {tool!r} prerequisite check"
        )


def test_uses_shallow_clone():
    """Shallow clone (--depth 1) speeds the initial download. Drift
    to full clone = wasted bandwidth + disk."""
    body = _read(BUILD_SH)
    assert "--depth 1" in body, (
        "build-bitnet.sh missing --depth 1 shallow clone "
        "(operator-discoverable wasted-bandwidth drift)"
    )
