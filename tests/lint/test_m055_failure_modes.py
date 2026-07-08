"""M055 failure-modes contract lint.

Locks `config/observability/m055-failure-modes.yaml` to the M055 spec: the 10
failure-mode taxonomies (E0529-E0533), the System-Wide Recovery Pattern (E0534),
and the Architectural Law (E0535/E0536). Each failure mode carries its exact
type list + mitigation steps + doctrine. No minimization.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "observability" / "m055-failure-modes.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M055-failure-modes-10-taxonomies.md"

# (failure-mode-id, name, #types, #mitigation-steps, doctrine) — the spec's exact counts.
EXPECTED = [
    (1, "Model Failure", 9, 6, "A model failure should become training/eval material, not just an error"),
    (2, "Router Failure", 6, 5, "Router decisions must be explainable"),
    (3, "Policy Failure", 6, 5, "Policy must never be only prompt-based"),
    (4, "Tool Failure", 8, 7, "Tool output is observation, not truth until interpreted"),
    (5, "Sandbox Failure", 7, 7, "The 4090 VFIO VM is the hard boundary profile"),
    (6, "Memory Failure", 7, 7, "Summaries are derived artifacts, not authority"),
    (7, "Eval Failure", 6, 6, "Evals are instruments, not gods"),
    (8, "Hardware Failure", 9, 8, "Hardware is part of the runtime state"),
    (9, "Continuity Failure", 6, 6, "Continuity must be explicit"),
    (10, "Human Interface Failure", 6, 6, "Sovereignty fails if the user is overwhelmed"),
]


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def _fm(fid: int) -> dict:
    return next(x for x in _c()["failure_modes"] if x["id"] == fid)


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M055"


def test_ten_failure_modes_present_and_ordered():
    ids = [x["id"] for x in _c()["failure_modes"]]
    assert ids == list(range(1, 11)), f"failure-mode id drift: {ids}"


def test_each_failure_mode_counts_and_doctrine():
    for fid, name, n_types, n_mit, doctrine in EXPECTED:
        fm = _fm(fid)
        assert fm["name"] == name, f"name drift for {fid}: {fm['name']}"
        assert len(fm["types"]) == n_types, f"{name}: expected {n_types} types, got {len(fm['types'])}"
        assert len(fm["mitigation"]) == n_mit, f"{name}: expected {n_mit} mitigations"
        assert fm["doctrine"] == doctrine, f"{name}: doctrine drift"


def test_model_failure_nine_types_verbatim():
    t = _fm(1)["types"]
    assert "hallucinated fact" in t and "looping" in t and "context loss" in t


def test_hardware_failure_nine_types_verbatim():
    t = _fm(8)["types"]
    assert "GPU OOM" in t and "ZFS degraded pool" in t and "PCIe lane surprise" in t


def test_tool_failure_eight_types_and_sandbox_first():
    fm = _fm(4)
    assert "permission denied" in fm["types"] and "command timeout" in fm["types"]
    assert fm["mitigation"][0] == "sandbox first"


def test_recovery_pattern_five_steps_and_example():
    rp = _c()["recovery_pattern"]
    assert rp["steps"] == ["detect", "contain", "explain", "recover", "learn"]
    assert len(rp["worked_example"]) == 7
    assert rp["worked_example"][0] == "Tool command fails"
    assert rp["worked_example"][-1] == "resume workflow"


def test_architectural_law():
    al = _c()["architectural_law"]
    assert al["law"] == "Failures are not exceptions. Failures are training signals and control signals"
    assert "metabolize failure into intelligence" in al["cloud_vs_station"]


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M00919", "M00922", "M00923", "M00926", "M00928", "M00929", "M00931"):
        assert mod in body, f"{mod} not in the M055 milestone (must trace to spec)"
