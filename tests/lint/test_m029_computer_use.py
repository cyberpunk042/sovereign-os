"""M029 computer-use-plane contract lint.

Locks `config/agent/m029-computer-use.yaml` to the M029 spec: the 3 layers +
perceive-once doctrine (E0270), the GUI-state + typed-action JSON + 6 runtime
gate predicates (E0272), the state-machine memory (E0273), and the 5 autonomy
profiles (E0274). No minimization of the spec.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "agent" / "m029-computer-use.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M029-computer-use-plane-perception-planning-execution.md"


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M029"


def test_three_layers_perception_planning_execution():
    layers = [x["layer"] for x in _c()["layers"]]
    assert layers == ["Perception", "Planning", "Execution"], f"layer drift: {layers}"


def test_typed_action_json_four_fields():
    f = _c()["typed_action_json"]["fields"]
    assert f == ["action", "target_id", "reason", "requires_confirmation"], (
        f"typed-action drift: {f}")


def test_gui_state_element_six_fields():
    e = _c()["gui_state_json"]["element_fields"]
    assert e == ["id", "type", "text", "bbox", "interactable", "risk"], (
        f"GUI-state element drift: {e}")


def test_six_runtime_gate_predicates_verbatim():
    p = _c()["runtime_gate_predicates"]["predicates"]
    assert p == ["target-exists", "target-interactable", "action-allowed",
                 "risk-acceptable", "credential-payment-destructive-state",
                 "human-gate-needed"], f"gate-predicate drift: {p}"
    assert len(p) == 6


def test_five_autonomy_profiles_verbatim():
    prof = [x["profile"] for x in _c()["autonomy_profiles"]]
    assert prof == ["observe_only", "assistive", "supervised", "sandbox",
                    "autonomous_low_risk"], f"autonomy-profile drift: {prof}"


def test_perceive_once_doctrine_re_query_on_change():
    r = _c()["perceive_once_doctrine"]["rule"]
    assert "act programmatically" in r and "state change" in r


def test_state_attributes_five():
    a = _c()["state_attributes"]["attributes"]
    assert len(a) == 5 and "failure-handlers" in a


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M00476", "M00479", "M00480", "M00481", "M00482", "M00485", "M00489"):
        assert mod in body, f"{mod} not in the M029 milestone (must trace to spec)"
