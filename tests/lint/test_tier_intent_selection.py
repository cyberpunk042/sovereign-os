"""SDD-043 Phase 2 — tier_intent VRAM-aware selection lockstep.

Locks the mechanism authored in scripts/models/select-by-intent.py +
the runtime-profile schema's model-XOR-tier_intent rule:
  - the selector NEVER picks a model over the VRAM budget,
  - it SPENDS the budget (a bigger budget yields a model at least as
    large — the more-capable variant),
  - it is deterministic,
  - the schema accepts a tier_intent allocation and rejects one that has
    both model AND tier_intent (or neither),
  - every runtime profile that uses tier_intent resolves to a real model.

This is what makes "declare a tier by intent" trustworthy enough to scale
to 20+ profiles: the resolution is honest (fits the hardware) and stable.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SELECTOR = REPO_ROOT / "scripts" / "models" / "select-by-intent.py"
SCHEMA_FILE = REPO_ROOT / "schemas" / "runtime-profile.schema.yaml"
RUNTIME_DIR = REPO_ROOT / "profiles" / "runtime"


def _sel():
    spec = importlib.util.spec_from_file_location("select_by_intent", SELECTOR)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _catalog():
    return _sel().load_catalog()


def test_selector_present_and_executable():
    assert SELECTOR.is_file()
    assert SELECTOR.stat().st_mode & 0o111


def test_never_exceeds_budget():
    """For a sweep of budgets/classes, the chosen model's vram_gib_min is
    always ≤ the budget (or nothing is chosen)."""
    m = _sel()
    models = _catalog()
    for klass in ("rlm", "llm", "ternary-lm", "code", "slm"):
        for budget in (2, 8, 24, 48, 96, 200):
            chosen = m.select(models, {"class": [klass], "vram_budget_gib": budget})
            if chosen is not None:
                assert float(chosen["vram_gib_min"]) <= budget, (
                    f"{klass}@{budget}GiB picked {chosen['id']} "
                    f"({chosen['vram_gib_min']} GiB) — over budget"
                )


def test_bigger_budget_is_at_least_as_capable():
    """Raising the budget never yields a SMALLER model (spend-the-budget)."""
    m = _sel()
    models = _catalog()
    prev = 0.0
    for budget in (24, 48, 96, 200):
        chosen = m.select(models, {"class": ["rlm"], "vram_budget_gib": budget},
                          tier="oracle")
        if chosen:
            assert float(chosen["vram_gib_min"]) >= prev, "bigger budget picked smaller model"
            prev = float(chosen["vram_gib_min"])


def test_known_resolution_is_stable_and_correct():
    """oracle/rlm/≤48 GiB deterministically resolves to the Q4 70B (42 GiB),
    not the 140 GiB FP16 — the canonical VRAM-aware example."""
    m = _sel()
    models = _catalog()
    picks = {m.select(models, {"class": ["rlm"], "vram_budget_gib": 48}, tier="oracle")["id"]
             for _ in range(5)}
    assert picks == {"DeepSeek-R1-Distill-Llama-70B-Q4_K_M"}, picks


def test_no_fit_returns_none():
    m = _sel()
    assert m.select(_catalog(), {"class": ["rlm"], "vram_budget_gib": 8}, tier="oracle") is None


# ---- schema: model XOR tier_intent ----

def _schema():
    return yaml.safe_load(SCHEMA_FILE.read_text())


def _minimal_profile(alloc: dict) -> dict:
    return {
        "schema_version": "1.0.0",
        "runtime_profile": {
            "id": "test-intent", "name": "t",
            "description": "x" * 40, "hardware_profile_compat": ["sain-01"],
            "allocations": [alloc],
        },
    }


def test_schema_accepts_tier_intent_allocation():
    jsonschema = pytest.importorskip("jsonschema")
    inst = _minimal_profile({
        "agent_id": "oracle_01", "target_hardware": "cuda:0", "engine": "vllm",
        "tier": "oracle",
        "tier_intent": {"class": ["rlm"], "vram_budget_gib": 48},
    })
    jsonschema.Draft202012Validator(_schema()).validate(inst)


def test_schema_rejects_both_model_and_tier_intent():
    jsonschema = pytest.importorskip("jsonschema")
    inst = _minimal_profile({
        "agent_id": "oracle_01", "target_hardware": "cuda:0", "engine": "vllm",
        "model": "DeepSeek-R1-Distill-Llama-70B-Q4_K_M",
        "tier_intent": {"class": ["rlm"], "vram_budget_gib": 48},
    })
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(_schema()).validate(inst)


def test_schema_rejects_neither_model_nor_tier_intent():
    jsonschema = pytest.importorskip("jsonschema")
    inst = _minimal_profile({
        "agent_id": "oracle_01", "target_hardware": "cuda:0", "engine": "vllm",
    })
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(_schema()).validate(inst)


def test_shipped_profiles_with_intent_resolve():
    """Any runtime profile that uses tier_intent must resolve every one to
    a real catalog model (guards future intent-driven profiles)."""
    m = _sel()
    models = _catalog()
    for p in sorted(RUNTIME_DIR.glob("*.yaml")):
        prof = yaml.safe_load(p.read_text())
        for r in m.resolve_profile(prof, models):
            assert r["chosen"] is not None, (
                f"{p.name}: tier_intent for {r['agent_id']} "
                f"({r['intent']}) resolves to NO catalog model"
            )
