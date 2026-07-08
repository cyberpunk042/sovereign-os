"""M066 Trinity-Framework-Genesis contract lint.

Locks `config/agent/m066-trinity-framework.yaml` to the M066 spec: the genesis
narrative + SRP anchor (E0638/E0639), the 3 trinity modules Pulse/Weaver/Auditor
with software->hardware manifestation (E0640-E0643), the chronological synthesis
5 phases (E0644), the project boundary (E0645), and the cohesive lineage
(E0646/E0647). No minimization.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
Project boundary (R10212): the Auditor's IPS implementation lives in selfdef MS044.
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "agent" / "m066-trinity-framework.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M066-trinity-framework-genesis-pulse-weaver-auditor.md"


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def _t(name: str) -> dict:
    return next(x for x in _c()["trinity"] if x["name"] == name)


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M066"


def test_genesis_srp_anchor():
    g = _c()["genesis"]
    assert "pure, decoupled software trinity" in g["narrative"]
    assert "Single Responsibility Principle" in g["srp_anchor"]
    assert "Zero to Hero" in g["srp_anchor"]


def test_three_trinity_modules_verbatim():
    names = [x["name"] for x in _c()["trinity"]]
    assert names == ["The Pulse", "The Weaver", "The Auditor"]
    subs = [x["subtitle"] for x in _c()["trinity"]]
    assert subs == ["Vector Core", "Sandboxed Fabric", "Immutable Gatekeeper"]


def test_pulse_physical_manifestation():
    p = _t("The Pulse")
    assert "-march=znver5" in p["physical_manifestation"]
    assert "AVX-512" in p["physical_manifestation"]
    assert "bitnet.cpp" in p["physical_manifestation"]


def test_weaver_podman_vfio():
    w = _t("The Weaver")
    assert "Podman" in w["physical_manifestation"] and "VFIO" in w["physical_manifestation"]
    assert "multi-agent orchestration" in w["original_concept"]


def test_auditor_selfdef_boundary():
    a = _t("The Auditor")
    assert "Tetragon eBPF" in a["physical_manifestation"]
    assert "MS044" in a["implementation_home"]


def test_project_boundary_pulse_weaver_local_auditor_selfdef():
    pb = _c()["project_boundary"]
    assert pb["sovereign_os_owns"] == ["The Pulse", "The Weaver"]
    assert "MS044" in pb["selfdef_owns"]


def test_chronological_synthesis_five_phases():
    ph = _c()["chronological_synthesis"]["phases"]
    assert ph == ["Basic Automation", "Deep Logic", "Contextual Sandboxing",
                  "Total System Defense", "Sovereign Synthesis"]


def test_cohesive_lineage_and_completed_node():
    cl = _c()["cohesive_lineage"]
    assert "specialized hardware topology" in cl["statement"]
    assert cl["vibe_managing_platform"] == "9900X + 96GB Blackwell + Isolated 4090"


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M01105", "M01108", "M01112", "M01116", "M01118", "M01119", "M01121"):
        assert mod in body, f"{mod} not in the M066 milestone (must trace to spec)"
