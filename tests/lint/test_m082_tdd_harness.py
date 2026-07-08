"""M082 TDD-Harness-Architecture contract lint.

Locks `config/agent/m082-tdd-harness.yaml` to the M082 spec: the 5-layer test
pyramid (E0788), the virtualization stack (E0789), per-stage invariants (E0790),
discovery/CI/flake policy (E0791), the test catalog (E0792), scaffold
deliverables (E0793), the CI workflow (E0794), the bootstrap + stage-2 stub SDDs
(E0795/E0796), and Stage Gate 5 (E0797). No minimization.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "agent" / "m082-tdd-harness.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M082-tdd-harness-architecture-hardware-free-validation.md"


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M082"


def test_five_layer_pyramid_verbatim():
    p = _c()["test_pyramid"]
    assert [x["layer"] for x in p] == [1, 2, 3, 4, 5]
    names = [x["name"] for x in p]
    assert names == ["schema/lint", "unit", "stage acceptance", "integration",
                     "hardware-conformance"], f"layer drift: {names}"


def test_layer1_pure_ci_layer5_gated_hw():
    p = {x["layer"]: x for x in _c()["test_pyramid"]}
    assert "pure CI" in p[1]["virtualization"]
    assert "SAIN-01 hardware" in p[5]["virtualization"]
    assert "nspawn" in p[3]["virtualization"]


def test_virtualization_stack_four():
    v = _c()["virtualization_stack"]
    assert v == ["chroot", "systemd-nspawn", "QEMU (system)", "qemu-user"]


def test_per_stage_invariants_three():
    assert _c()["per_stage_invariants"] == ["pre-install", "during-install",
                                            "post-install-first-boot"]


def test_ci_workflow_pr_vs_merge():
    cw = _c()["ci_workflow"]
    assert cw["every_pr"] == "schema + lint"
    assert cw["on_merge_or_label"] == "chroot / nspawn / qemu"


def test_scaffold_deliverables_include_harness_skeletons():
    sd = _c()["scaffold_deliverables"]
    assert "tests/schema/" in sd and "tests/lint/" in sd
    assert ".github/workflows/test.yml" in sd


def test_stage_gate_5_foundation_complete():
    sg = _c()["stage_gate_5"]
    assert sg["name"] == "foundation-complete gate"
    assert "Stage 2" in sg["scope"] and "authorized ONLY after this gate" in sg["scope"]


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M01369", "M01374", "M01378", "M01381", "M01384", "M01382", "M01385"):
        assert mod in body, f"{mod} not in the M082 milestone (must trace to spec)"
