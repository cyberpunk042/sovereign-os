"""R402 (E10.M46) — inference Trinity start-script operator-verbatim content lint.

Extends R387-R401 operational-artifact pinning to the three §17.1
Trinity-side runtime start scripts:
  scripts/inference/start-pulse.sh         (Pulse / bitnet.cpp / CCD 0)
  scripts/inference/start-logic-engine.sh  (Logic Engine / RTX 3090 / VFIO)
  scripts/inference/start-oracle-core.sh   (Oracle Core / Blackwell / vLLM)

These scripts encode the operator-named SRP Trinity. R397 pinned the
.service unit Description= strings — but the runtime invariants
(tier names in metric labels, port assignments, CCD pinning, idempotent
no-op-on-listen, DRY_RUN honor, taskset affinity for Pulse) are encoded
in the START SCRIPTS, not in the units.

Master spec §17.1 verbatim Trinity binding (operator-named):
  - Pulse        → bitnet.cpp, ternary, CCD 0 cores 0-5, port 8081
  - Logic Engine → RTX 3090 (VFIO-bound), vLLM / llama_cpp, port 8082
  - Oracle Core  → RTX PRO 6000 Blackwell, vLLM, fp8 KV, port 8083

Layer B metric label invariants (SDD-016):
  tier="pulse" | tier="logic_engine" | tier="oracle_core"

If a future agent silently:
  - renames tier= label (breaks Grafana queries downstream)
  - reassigns ports (router config in router.py points to 8081/8082/8083)
  - drops Pulse taskset affinity (CCD 0 pinning lost → workload bleeds
    onto CCD 1 = §17.1 dual-CCD SRP violation)
  - drops idempotent-on-listen guard (double-start = port conflict)
  - drops DRY_RUN honor (CI runs the actual workload)
…the §17.1 Trinity runtime contract silently breaks.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PULSE = REPO_ROOT / "scripts" / "inference" / "start-pulse.sh"
LOGIC = REPO_ROOT / "scripts" / "inference" / "start-logic-engine.sh"
ORACLE = REPO_ROOT / "scripts" / "inference" / "start-oracle-core.sh"


def _read(path: Path) -> str:
    assert path.is_file(), f"missing {path}"
    return path.read_text(encoding="utf-8")


def test_all_three_start_scripts_exist():
    for p in (PULSE, LOGIC, ORACLE):
        assert p.is_file(), f"§17.1 Trinity start script missing: {p}"


# --- Port allocation invariants (operator-named §17.1) ---


def test_pulse_port_8081():
    body = _read(PULSE)
    assert "8081" in body, (
        "start-pulse.sh missing port 8081 (operator-named §17.1 + "
        "router.py pulse backend port — drift breaks router routing)"
    )


def test_logic_engine_port_8082():
    body = _read(LOGIC)
    assert "8082" in body, (
        "start-logic-engine.sh missing port 8082 (operator-named §17.1 + "
        "router.py logic_engine backend port — drift breaks router routing)"
    )


def test_oracle_core_port_8083():
    body = _read(ORACLE)
    assert "8083" in body, (
        "start-oracle-core.sh missing port 8083 (operator-named §17.1 + "
        "router.py oracle_core backend port — drift breaks router routing)"
    )


def test_ports_unique_across_trinity():
    """8081 / 8082 / 8083 MUST stay distinct — port collision would
    silently make one tier shadow another at the router level."""
    p_body, l_body, o_body = _read(PULSE), _read(LOGIC), _read(ORACLE)
    # Each script must contain its own port AND must not contain the
    # other two as the default value (defense-in-depth against drift).
    assert "8081" in p_body and "8082" not in p_body.split("8081")[0][-30:], (
        "start-pulse.sh: 8082 appears too close to PULSE_PORT default "
        "(drift risk — Pulse silently bound to Logic Engine port)"
    )
    assert "8082" in l_body and "8081" not in l_body.split("8082")[0][-30:], (
        "start-logic-engine.sh: missing 8082, or 8081 appears too close to "
        "LOGIC_PORT default (drift risk — Logic Engine silently bound to "
        "Pulse port)"
    )
    assert "8083" in o_body and "8082" not in o_body.split("8083")[0][-30:], (
        "start-oracle-core.sh: missing 8083, or 8082 appears too close to "
        "ORACLE_PORT default (drift risk — Oracle Core silently bound to "
        "Logic Engine port)"
    )


# --- Layer B metric tier= label invariants (SDD-016) ---


def test_pulse_metric_tier_label_verbatim():
    """Pulse start script MUST encode tier='pulse' identifier (literal
    or via TIER variable). Drift to tier='bitnet' / tier='cpu' silently
    breaks SDD-016 Grafana queries aggregating across Trinity tiers."""
    body = _read(PULSE)
    has_label = (
        'tier="pulse"' in body
        or 'TIER="pulse"' in body
        or 'TIER=pulse' in body
    )
    assert has_label, (
        "start-pulse.sh missing tier=\"pulse\" Layer B metric label / "
        "TIER variable (SDD-016 verbatim — Grafana inference dashboards "
        "filter on this; drift breaks downstream aggregation)"
    )


def test_logic_engine_metric_tier_label_verbatim():
    """Logic Engine start script MUST encode tier='logic_engine' identifier
    (either literal in metric label OR via TIER=\"logic_engine\" variable
    that's then interpolated into tier=\"${TIER}\")."""
    body = _read(LOGIC)
    has_label = (
        'tier="logic_engine"' in body
        or 'TIER="logic_engine"' in body
        or 'TIER=logic_engine' in body
    )
    assert has_label, (
        "start-logic-engine.sh missing tier=\"logic_engine\" Layer B "
        "metric label / TIER variable (SDD-016 verbatim — operator-named "
        "tier identifier; drift breaks Grafana inference dashboard filters)"
    )


def test_oracle_core_metric_tier_label_verbatim():
    body = _read(ORACLE)
    has_label = (
        'tier="oracle_core"' in body
        or 'TIER="oracle_core"' in body
        or 'TIER=oracle_core' in body
    )
    assert has_label, (
        "start-oracle-core.sh missing tier=\"oracle_core\" Layer B "
        "metric label / TIER variable (SDD-016 verbatim — operator-named "
        "tier identifier; drift breaks Grafana inference dashboard filters)"
    )


def test_all_three_emit_start_total_metric():
    """SDD-016 verbatim metric name: sovereign_os_inference_backend_start_total"""
    metric = "sovereign_os_inference_backend_start_total"
    for path in (PULSE, LOGIC, ORACLE):
        body = _read(path)
        assert metric in body, (
            f"{path.name} missing {metric} metric emission "
            f"(SDD-016 verbatim — start-up observability surface)"
        )


# --- Pulse-specific: CCD 0 + bitnet.cpp + taskset ---


def test_pulse_references_bitnet():
    body = _read(PULSE)
    assert "bitnet" in body.lower(), (
        "start-pulse.sh missing bitnet.cpp reference (operator-named "
        "§17.1 — Pulse IS bitnet.cpp ternary inference)"
    )


def test_pulse_ccd_0_affinity():
    """Pulse MUST pin to CCD 0 (operator-named §17.1 dual-CCD SRP).
    Default affinity 0-5 = 6 cores on CCD 0 of Ryzen 9 9900X."""
    body = _read(PULSE)
    has_ccd0 = (
        "CCD 0" in body
        or "ccd 0" in body.lower()
        or "PULSE_AFFINITY:=0-5" in body
        or "core 0-5" in body.lower()
    )
    assert has_ccd0, (
        "start-pulse.sh missing CCD 0 affinity (operator-named §17.1 — "
        "Pulse pinned to first CCD; drift to CCD 1 violates dual-CCD SRP)"
    )


def test_pulse_uses_taskset_for_pinning():
    """Pulse MUST exec via taskset to enforce CPU affinity at OS level
    (defense-in-depth — bitnet.cpp's own pinning may not survive
    systemd-managed restarts). Drift here silently loses CCD pinning."""
    body = _read(PULSE)
    assert "taskset" in body, (
        "start-pulse.sh missing taskset affinity enforcement "
        "(operator-named §17.1 CCD pinning defense-in-depth)"
    )


# --- Logic Engine specific: RTX 3090 + VFIO + vLLM ---


def test_logic_engine_references_rtx_3090_or_vfio():
    body = _read(LOGIC)
    has_3090 = (
        "RTX 3090" in body or "3090" in body or "VFIO" in body
        or "vfio" in body
    )
    assert has_3090, (
        "start-logic-engine.sh missing RTX 3090 / VFIO reference "
        "(operator-named §17.1 — Logic Engine on VFIO-bound 3090)"
    )


def test_logic_engine_supports_vllm_backend():
    body = _read(LOGIC)
    assert "vllm" in body.lower(), (
        "start-logic-engine.sh missing vllm backend "
        "(SDD-011 routing rule 4 — Logic Engine default backend)"
    )


def test_logic_engine_supports_llama_cpp_fallback():
    """Operator-named fallback: llama_cpp when vLLM unavailable on 3090.
    Drift losing this fallback silently strands Logic Engine on debug
    hardware."""
    body = _read(LOGIC)
    assert "llama_cpp" in body, (
        "start-logic-engine.sh missing llama_cpp fallback backend "
        "(operator-named §17.1 — hardware-constraint fallback path)"
    )


# --- Oracle Core specific: Blackwell + vLLM + fp8 KV ---


def test_oracle_core_references_blackwell_or_pro_6000():
    body = _read(ORACLE)
    has_blackwell = (
        "Blackwell" in body or "blackwell" in body
        or "RTX PRO 6000" in body or "PRO 6000" in body
    )
    assert has_blackwell, (
        "start-oracle-core.sh missing Blackwell / RTX PRO 6000 reference "
        "(operator-named §17.1 — Oracle Core on host-resident Blackwell)"
    )


def test_oracle_core_uses_vllm():
    body = _read(ORACLE)
    assert "vllm" in body.lower() or "VllmBackend" in body, (
        "start-oracle-core.sh missing vLLM reference "
        "(operator-named §17.1 — Oracle Core uses vLLM native)"
    )


def test_oracle_core_fp8_kv_cache_default():
    """Operator-named §17.1: Oracle Core defaults to fp8 KV cache
    (deep-context-friendly). Drift to auto/fp16 silently halves
    effective context length."""
    body = _read(ORACLE)
    has_fp8 = "fp8" in body
    assert has_fp8, (
        "start-oracle-core.sh missing fp8 KV cache default "
        "(operator-named §17.1 — deep-context-friendly KV dtype; "
        "drift to fp16/auto halves effective context length)"
    )


# --- Cross-script invariants (defense-in-depth) ---


def test_all_three_honor_dry_run():
    """All Trinity start scripts MUST honor SOVEREIGN_OS_DRY_RUN
    (otherwise CI invocations actually exec the inference workload)."""
    for path in (PULSE, LOGIC, ORACLE):
        body = _read(path)
        assert "SOVEREIGN_OS_DRY_RUN" in body, (
            f"{path.name} missing SOVEREIGN_OS_DRY_RUN honor "
            f"(SDD-016 verbatim — CI / dry-run path)"
        )


def test_all_three_are_idempotent_on_port_listen():
    """All Trinity start scripts MUST exit 0 with skip when their
    port is already bound (otherwise double-start = port conflict)."""
    for path in (PULSE, LOGIC, ORACLE):
        body = _read(path)
        has_idempotent = (
            "already listening" in body
            or ("ss -lnt" in body and "grep -q LISTEN" in body)
        )
        assert has_idempotent, (
            f"{path.name} missing already-listening idempotency guard "
            f"(double-start would conflict on port)"
        )


def test_all_three_use_set_euo_pipefail():
    """All Trinity start scripts MUST use 'set -euo pipefail' (bash
    strict mode — drift to set -e only loses unset-var safety)."""
    for path in (PULSE, LOGIC, ORACLE):
        body = _read(path)
        assert "set -euo pipefail" in body, (
            f"{path.name} missing 'set -euo pipefail' bash strict mode "
            f"(SDD-001 verbatim shell-discipline)"
        )


def test_all_three_emit_backend_pid_metric():
    """SDD-016 verbatim: sovereign_os_inference_backend_pid emitted
    by all three (operator-discovery — which PID is serving which tier)."""
    metric = "sovereign_os_inference_backend_pid"
    for path in (PULSE, LOGIC, ORACLE):
        body = _read(path)
        assert metric in body, (
            f"{path.name} missing {metric} (SDD-016 verbatim — "
            f"operator-discovery PID-to-tier mapping)"
        )
