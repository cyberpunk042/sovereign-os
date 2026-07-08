"""SDD-043 Phase 3 — runtime-profile generation lockstep.

Locks scripts/operator/generate-runtime-profile.py: every
(OS-profile × strategy) combo must generate a profile that (a) conforms
to the runtime-profile schema and (b) resolves every tier_intent to a
real catalog model. This is what makes "generate 20+ combos" trustworthy
— a generated profile is never broken or unresolvable.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
GEN = REPO_ROOT / "scripts" / "operator" / "generate-runtime-profile.py"
SCHEMA_FILE = REPO_ROOT / "schemas" / "runtime-profile.schema.yaml"
PROFILES_DIR = REPO_ROOT / "profiles"

STRATEGIES = ["efficiency", "high-concurrency", "deep-context"]


def _gen_mod():
    spec = importlib.util.spec_from_file_location("gen_runtime", GEN)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _gpu_profiles() -> list[str]:
    """OS profiles that declare at least one GPU (deep-context needs one)."""
    out = []
    for p in sorted(PROFILES_DIR.glob("*.yaml")):
        d = yaml.safe_load(p.read_text()) or {}
        if ((d.get("hardware") or {}).get("gpu")):
            out.append(p.stem)
    return out


def test_generator_present_and_executable():
    assert GEN.is_file()
    assert GEN.stat().st_mode & 0o111


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_sain01_every_strategy_generates_and_validates(strategy):
    """The reference hardware (sain-01) generates a clean profile for
    every strategy — schema-valid AND every tier resolves."""
    m = _gen_mod()
    profile = m.generate("sain-01", strategy)
    problems = m.validate(profile)
    assert not problems, f"sain-01/{strategy}: {problems}"


def test_generated_profiles_conform_to_schema():
    jsonschema = pytest.importorskip("jsonschema")
    m = _gen_mod()
    schema = yaml.safe_load(SCHEMA_FILE.read_text())
    validator = jsonschema.Draft202012Validator(schema)
    for hw in _gpu_profiles():
        for strategy in STRATEGIES:
            profile = m.generate(hw, strategy)
            validator.validate(profile)   # raises on non-conformance


def test_generated_ids_and_budgets_are_sane():
    m = _gen_mod()
    prof = m.generate("sain-01", "high-concurrency")["runtime_profile"]
    assert prof["id"] == "sain-01-high-concurrency"
    # budgets never exceed the declared GPU VRAM (headroom applied)
    for a in prof["allocations"]:
        intent = a.get("tier_intent")
        if intent and a["target_hardware"].startswith("cuda"):
            assert intent["vram_budget_gib"] > 0


def test_high_concurrency_is_three_tiers_on_dual_gpu():
    """On sain-01 (2 GPUs) high-concurrency lays out the full 3-tier plane:
    Pulse on CPU, Logic + Oracle on the two GPUs, largest → Oracle."""
    m = _gen_mod()
    prof = m.generate("sain-01", "high-concurrency")["runtime_profile"]
    tiers = {a["tier"]: a for a in prof["allocations"]}
    assert set(tiers) == {"pulse", "logic", "oracle"}
    assert tiers["pulse"]["target_hardware"] == "cpu"
    # Oracle gets the largest GPU (cuda:0 = 96 GB Blackwell); Logic the 4090.
    assert tiers["oracle"]["tier_intent"]["vram_budget_gib"] > \
        tiers["logic"]["tier_intent"]["vram_budget_gib"]


def test_deep_context_is_tensor_parallel_across_all_gpus():
    m = _gen_mod()
    prof = m.generate("sain-01", "deep-context")["runtime_profile"]
    alloc = prof["allocations"][0]
    assert alloc["target_hardware"] == "cuda:0,cuda:1"
    assert alloc.get("tensor_parallel_size") == 2
