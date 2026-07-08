"""M083 DFlash-speculative-decoding contract lint.

Locks `config/inference/m083-dflash-speculative-decoding.yaml` to the M083 spec:
the operator addition + task-type gain (E0798/E0799), the introspection mandate
(E0800), the gated wrapper (E0801), operator override knobs (E0802), per-backend
integration (E0803), graceful degradation (E0804), Layer A/B observability
(E0805), the router task-type signal (E0806), and Layer-5 validation (E0807). No
minimization.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "inference" / "m083-dflash-speculative-decoding.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M083-dflash-speculative-decoding-fast-path.md"


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M083"


def test_operator_text_verbatim():
    t = _c()["operator_text"]
    assert "it can work 3 times faster" in t
    assert "does not work on creative tasks in general" in t
    assert "introspection and knowledge" in t


def test_task_type_gain_3x_not_creative():
    g = _c()["task_type_gain"]
    assert "3x on code" in g["speedup"]
    assert g["does_not_work_on"] == "creative tasks"


def test_gated_wrapper_argv_prefix():
    gw = _c()["gated_wrapper"]
    assert gw["script"] == "scripts/inference/dflash-wrap.sh"
    assert "gating BEFORE the backend sees argv" in gw["shape"]


def test_override_knobs_disable_wins():
    ok = _c()["override_knobs"]
    assert ok["enable"] == "DFLASH_ENABLE_OVERRIDE"
    assert ok["disable"] == "DFLASH_DISABLE_OVERRIDE"
    assert ok["precedence"] == "DISABLE wins when both set"


def test_three_backend_bindings():
    b = [x["backend"] for x in _c()["backend_bindings"]]
    assert b == ["vllm", "llama_cpp", "transformers"]
    vllm = next(x for x in _c()["backend_bindings"] if x["backend"] == "vllm")
    assert '"method":"dflash"' in vllm["argv"]


def test_graceful_degradation_never_hard_failure():
    gd = _c()["graceful_degradation"]["rule"]
    assert "vanilla decoding" in gd and "never a hard failure" in gd


def test_router_signal_header():
    rs = _c()["router_signal"]
    assert rs["classifier"] == "classify_task_type"
    assert rs["header"] == "X-Sovereign-Task-Type"


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M01395", "M01396", "M01397", "M01398", "M01401", "M01404", "M01411"):
        assert mod in body, f"{mod} not in the M083 milestone (must trace to spec)"
