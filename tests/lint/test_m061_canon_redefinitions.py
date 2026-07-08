"""M061 AVX++ canon-redefinition contract lint.

Locks `config/agent/m061-canon-redefinitions.yaml` to the M061 spec: the 6
backward-sweep redefinitions (E0588-E0593) with their historical->canonical
mapping + severity + affected milestones + canonical home, plus the patch passes
A/B/C (E0594-E0596) and catalog-hygiene closure (E0597). No minimization.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
Operator standing (sacrosanct): "never discarded" — earlier rows preserved.
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "agent" / "m061-canon-redefinitions.yaml"
MILESTONE = (REPO_ROOT / "backlog" / "milestones" /
             "M061-avx-plus-plus-canon-update-backward-sweep-2026-05-19.md")

# (id, subject, severity, canonical_home) — the spec's exact redefinition table.
EXPECTED = [
    (1, "Profiles", "breaking", "M056"),
    (2, "Core Law", "clarifying", "M059"),
    (3, "Authority Levels 0..6", "additive", "M056"),
    (4, "Trust Rings 0..4", "additive", "M056"),
    (5, "Scheduler", "breaking", "M058"),
    (6, "Commit Authority", "breaking", "M056"),
]


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def _r(rid: int) -> dict:
    return next(x for x in _c()["redefinitions"] if x["id"] == rid)


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M061"


def test_preservation_doctrine_never_discarded():
    assert "never discarded" in _c()["preservation_doctrine"]


def test_six_redefinitions_present_and_ordered():
    ids = [x["id"] for x in _c()["redefinitions"]]
    assert ids == [1, 2, 3, 4, 5, 6], f"redefinition id drift: {ids}"


def test_each_redefinition_subject_severity_home():
    for rid, subject, severity, home in EXPECTED:
        r = _r(rid)
        assert r["subject"] == subject, f"subject drift for {rid}: {r['subject']}"
        assert r["severity"] == severity, f"severity drift for {subject}: {r['severity']}"
        assert r["canonical_home"] == home, f"canonical_home drift for {subject}"
        assert r["historical"] and r["canonical"], f"{subject}: both defs must be present"


def test_profiles_redefinition_memory_lens_to_authority_gate():
    r = _r(1)
    assert "memory-lens" in r["historical"] and "authority-gate" in r["canonical"]
    assert "selfdef MS010" in r["affected"]


def test_core_law_redefinition_adds_cpu_enforces():
    r = _r(2)
    assert "missing 'CPU enforces'" in r["historical"]
    assert "CPU enforces" in r["canonical"]


def test_scheduler_redefinition_component_to_policy_layer():
    r = _r(5)
    assert "component" in r["historical"] and "first-class policy layer" in r["canonical"]
    assert "sovereign-os M043" in r["affected"]


def test_commit_authority_deterministic_to_evidence_earned():
    r = _r(6)
    assert r["historical"] == "deterministic substrate"
    assert r["canonical"] == "evidence-earned authority"


def test_three_patch_passes():
    p = [x["pass"] for x in _c()["patch_passes"]]
    assert p == ["A", "B", "C"]
    assert "typed-mirror crate version bumps" in _c()["patch_passes"][1]["name"]


def test_closure_backward_sweep_complete():
    assert _c()["closure"]["statement"] == "backward-sweep complete, prior-dump review next"


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M01020", "M01021", "M01024", "M01025", "M01027", "M01035", "M01036"):
        assert mod in body, f"{mod} not in the M061 milestone (must trace to spec)"
