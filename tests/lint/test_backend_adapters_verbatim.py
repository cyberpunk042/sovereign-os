"""R404 (E10.M48) — inference backend adapters operator-verbatim §17.1 lint.

Extends R387-R403 operational-artifact pinning to the 3 backend
adapter modules that construct argv for the §17.1 Trinity runtime:
  scripts/inference/backends/bitnet.py      (Pulse / TL2 kernel / CCD 0)
  scripts/inference/backends/vllm.py        (Logic Engine + Oracle Core)
  scripts/inference/backends/llama_cpp.py   (fallback path)

These adapters encode the operator-named §17.1 + E109 (DFlash)
runtime invariants at the ARGV construction layer — the layer where
'--kv-cache-dtype fp8' actually becomes a process argument, and
'taskset -c 0-5' actually pins the bitnet CPU mask.

Master spec §17.1 + E109 + SDD-005 verbatim:
  - Pulse: bitnet.cpp + TL2 x86 kernel default + CCD 0 cores 0-5 +
           model microsoft/bitnet-b1.58-2B-4T
  - Logic Engine: vLLM in podman wrapper (VFIO 4090 isolation) +
                  port 8082 + tensor-parallel-size 1
  - Oracle Core: vLLM native (Blackwell host-resident) + port 8083 +
                 fp8 KV cache default + DFlash speculative decoding
                 via --speculative-config (E109)

If a future agent silently:
  - changes DEFAULT_KERNEL from TL2 (Pulse loses x86 optimization)
  - drops `taskset -c` from bitnet argv (CCD 0 pinning lost = §17.1 SRP)
  - changes vLLM podman flag for Logic Engine (4090 isolation breaks)
  - changes Oracle Core fp8 default (halves effective context length)
  - removes --speculative-config from DFlash path (E109 spec-decode lost)
…the §17.1 + E109 contract silently breaks at argv-construction layer.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BITNET = REPO_ROOT / "scripts" / "inference" / "backends" / "bitnet.py"
VLLM = REPO_ROOT / "scripts" / "inference" / "backends" / "vllm.py"
LLAMA = REPO_ROOT / "scripts" / "inference" / "backends" / "llama_cpp.py"


def _read(p: Path) -> str:
    assert p.is_file(), f"missing {p}"
    return p.read_text(encoding="utf-8")


def test_all_three_adapter_files_exist():
    for p in (BITNET, VLLM, LLAMA):
        assert p.is_file(), f"§17.1 backend adapter missing: {p}"


# --- BitnetBackend (Pulse tier) ---


def test_bitnet_default_model_verbatim():
    """SDD-005 verbatim: 'microsoft/bitnet-b1.58-2B-4T'.
    Drift to a different bitnet variant breaks the operator-named
    Pulse reference model (operator-discovered weights path)."""
    body = _read(BITNET)
    assert "microsoft/bitnet-b1.58-2B-4T" in body, (
        "bitnet.py missing DEFAULT_MODEL='microsoft/bitnet-b1.58-2B-4T' "
        "(SDD-005 verbatim — operator-named Pulse reference model)"
    )


def test_bitnet_tl2_kernel_default():
    """SDD-005 verbatim: TL2 x86 kernel default (alternative: I2_S
    lossless). Drift to non-TL2 default silently loses x86 optimization
    on Zen 5."""
    body = _read(BITNET)
    assert 'DEFAULT_KERNEL = "TL2"' in body or "DEFAULT_KERNEL='TL2'" in body, (
        "bitnet.py missing DEFAULT_KERNEL='TL2' (SDD-005 verbatim — "
        "operator-named x86 kernel default for Pulse)"
    )


def test_bitnet_ccd_0_default_affinity():
    """SDD-005 verbatim: Pulse pinned to CCD 0 cores 0-5.
    The default affinity '0-5' MUST appear (drift to '6-11' or '0-11'
    silently bleeds Pulse onto CCD 1 = §17.1 dual-CCD SRP violation)."""
    body = _read(BITNET)
    assert '"0-5"' in body, (
        "bitnet.py missing default affinity '0-5' (operator-named "
        "§17.1 — Pulse pinned to CCD 0 cores 0-5; drift = SRP violation)"
    )


def test_bitnet_uses_taskset_in_argv():
    """The bitnet argv MUST start with 'taskset -c <mask>' for OS-level
    CPU pinning. Drift losing taskset = bitnet's internal pinning may
    not survive systemd-managed restarts = silent CCD bleed."""
    body = _read(BITNET)
    assert '"taskset"' in body, (
        "bitnet.py argv missing taskset -c affinity enforcement "
        "(operator-named §17.1 CCD 0 defense-in-depth pinning)"
    )


def test_bitnet_tier_pulse_attribute():
    """Class-level tier attribute MUST be 'pulse' verbatim
    (SDD-016 metric label binding)."""
    body = _read(BITNET)
    assert 'tier = "pulse"' in body, (
        "bitnet.py BitnetBackend.tier MUST be 'pulse' verbatim "
        "(SDD-016 — Layer B metric label binding)"
    )


def test_bitnet_default_port_8081():
    """default_config() MUST bind to port 8081 (Pulse tier port —
    must match TIER_ENDPOINTS in router.py)."""
    body = _read(BITNET)
    assert "port=8081" in body, (
        "bitnet.py default_config() MUST use port=8081 "
        "(operator-named §17.1 Pulse port — matches router.py + start-pulse.sh)"
    )


# --- VllmBackend (Logic Engine + Oracle Core) ---


def test_vllm_min_version_pinned():
    """E109 verbatim: vLLM v0.20.1+ pinned (required for DFlash
    speculative decoding). Drift below 0.20.1 silently loses DFlash
    integration on Oracle Core."""
    body = _read(VLLM)
    assert "0.20.1" in body, (
        "vllm.py missing MIN_VERSION = '0.20.1' (E109 verbatim — "
        "required for DFlash speculative decoding on Oracle Core)"
    )


def test_vllm_logic_engine_uses_podman():
    """SDD-011 + §17.1: Logic Engine on VFIO-bound 4090 MUST use podman
    container wrapping (process isolation from host's Blackwell driver).
    Drift to native breaks 4090 VFIO isolation contract."""
    body = _read(VLLM)
    # for_logic_engine() MUST set podman=True
    assert ("podman=True" in body or 'podman = True' in body), (
        "vllm.py for_logic_engine() MUST use podman=True "
        "(SDD-011 + §17.1 — 4090 VFIO isolation requires container wrapping)"
    )


def test_vllm_oracle_core_native_not_podman():
    """Oracle Core (Blackwell, host-resident) MUST run vLLM natively
    (NOT podman) — operator-named §17.1 + L0 Profile 3. Native gives
    full Blackwell driver access; podman wrapping would lose Blackwell
    optimizations."""
    body = _read(VLLM)
    # for_oracle_core() MUST set podman=False
    assert ("podman=False" in body or "podman = False" in body), (
        "vllm.py for_oracle_core() MUST use podman=False "
        "(§17.1 — Oracle Core is host-resident on Blackwell)"
    )


def test_vllm_oracle_core_fp8_default():
    """L0 Profile 3 verbatim: Oracle Core defaults to fp8 KV cache
    (deep-context-friendly). Drift to 'auto' or fp16 silently halves
    effective context length on Blackwell."""
    body = _read(VLLM)
    # for_oracle_core has kv_cache_dtype: str = "fp8" default
    assert 'kv_cache_dtype: str = "fp8"' in body or "kv_cache_dtype='fp8'" in body, (
        "vllm.py for_oracle_core() MUST default kv_cache_dtype='fp8' "
        "(L0 Profile 3 verbatim — Blackwell deep-context tuning)"
    )


def test_vllm_dflash_speculative_config_present():
    """E109 verbatim: DFlash integration via vLLM --speculative-config
    flag. Drift losing this flag silently disables E109 spec-decode."""
    body = _read(VLLM)
    assert "--speculative-config" in body, (
        "vllm.py missing --speculative-config flag (E109 verbatim — "
        "DFlash speculative decoding integration on Oracle Core)"
    )


def test_vllm_dflash_method_label_verbatim():
    """E109 verbatim: speculative-config JSON includes 'method': 'dflash'.
    Drift to 'method': 'eagle' or other speculative method breaks the
    operator-named DFlash binding."""
    body = _read(VLLM)
    assert '"method": "dflash"' in body, (
        'vllm.py missing \'"method": "dflash"\' in --speculative-config '
        "(E109 verbatim — operator-named DFlash spec-decode method)"
    )


def test_vllm_openai_api_server_entrypoint():
    """vLLM MUST be started via vllm.entrypoints.openai.api_server
    (OpenAI-compatible API surface — operator-discovery: same wire
    protocol as Pulse + llama.cpp). Drift to a custom entrypoint
    breaks the unified OpenAI-API surface."""
    body = _read(VLLM)
    assert "vllm.entrypoints.openai.api_server" in body, (
        "vllm.py missing vllm.entrypoints.openai.api_server entrypoint "
        "(operator-discovery — OpenAI-compatible API surface)"
    )


def test_vllm_logic_engine_port_8082():
    body = _read(VLLM)
    assert "port=8082" in body, (
        "vllm.py for_logic_engine() MUST use port=8082 "
        "(§17.1 — must match router.py TIER_ENDPOINTS + start-logic-engine.sh)"
    )


def test_vllm_oracle_core_port_8083():
    body = _read(VLLM)
    assert "port=8083" in body, (
        "vllm.py for_oracle_core() MUST use port=8083 "
        "(§17.1 — must match router.py TIER_ENDPOINTS + start-oracle-core.sh)"
    )


# --- LlamaCppBackend (fallback) ---


def test_llama_cpp_old_workstation_port_8084():
    """Fallback port: 8084 for old-workstation primary (matches
    TIER_ENDPOINTS llama_old binding in router.py)."""
    body = _read(LLAMA)
    assert "port=8084" in body, (
        "llama_cpp.py for_old_workstation() MUST use port=8084 "
        "(matches router.py TIER_ENDPOINTS['llama_old'])"
    )


def test_llama_cpp_sain01_fallback_port_8085():
    """Fallback port: 8085 for sain-01 fallback (matches
    TIER_ENDPOINTS llama_fb binding)."""
    body = _read(LLAMA)
    assert "port=8085" in body, (
        "llama_cpp.py for_sain01_fallback() MUST use port=8085 "
        "(matches router.py TIER_ENDPOINTS['llama_fb'])"
    )


def test_llama_cpp_offloads_all_layers_to_gpu():
    """When GPU is present, MUST offload all layers (-ngl 999 sentinel).
    Drift to a lower default silently leaves layers on CPU = perf loss."""
    body = _read(LLAMA)
    assert "DEFAULT_N_GPU_LAYERS = 999" in body or "n_gpu_layers=999" in body, (
        "llama_cpp.py missing -ngl 999 GPU-offload-all default "
        "(operator-discovery: GPU presence MUST offload all layers)"
    )


# --- Cross-adapter invariants ---


def test_all_three_inherit_from_backend_base():
    """All three adapters MUST inherit from Backend base class
    (SDD-011 polymorphic-backend contract)."""
    for path in (BITNET, VLLM, LLAMA):
        body = _read(path)
        assert "from lib.backend import Backend" in body, (
            f"{path.name} missing 'from lib.backend import Backend' "
            f"(SDD-011 — polymorphic-backend base class)"
        )
        # MUST extend Backend in class definition
        assert "(Backend)" in body, (
            f"{path.name} class doesn't extend Backend (SDD-011)"
        )


def test_all_three_emit_v1_models_health_url():
    """All three adapters MUST expose /v1/models health endpoint
    (operator-discovery: same health-check surface across Trinity)."""
    for path in (BITNET, VLLM, LLAMA):
        body = _read(path)
        assert "/v1/models" in body, (
            f"{path.name} missing /v1/models health URL "
            f"(SDD-011 + operator-discovery uniformity)"
        )


def test_all_three_define_start_command_method():
    """All three adapters MUST define start_command() returning argv list
    (SDD-011 polymorphic-backend contract)."""
    for path in (BITNET, VLLM, LLAMA):
        body = _read(path)
        assert "def start_command(self)" in body, (
            f"{path.name} missing start_command() method "
            f"(SDD-011 — argv-construction contract)"
        )


def test_loopback_only_in_classmethods():
    """All factory classmethods MUST use 127.0.0.1 loopback in their
    default BackendConfig (matches router.py §8 Zero-Trust invariant —
    backends MUST NOT bind externally)."""
    for path in (BITNET, VLLM, LLAMA):
        body = _read(path)
        # Either explicit 127.0.0.1 or host="127.0.0.1" appears
        assert "127.0.0.1" in body, (
            f"{path.name} factory classmethods missing 127.0.0.1 "
            f"loopback host (§8 Zero-Trust — backends MUST NOT "
            f"bind externally; only router is network-reachable)"
        )
