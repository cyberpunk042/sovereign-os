"""Orchestration-intent profile family lint.

Pins the SEPARATE orchestration-profile family (profiles/orchestration/) that
the D-21 LM Orchestration panel surfaces. This is DISTINCT from the §18 runtime
load-balancing profiles (profiles/runtime/, verbatim-locked to exactly 3 by
test_runtime_profiles_verbatim.py — which this lint does NOT touch).

Enforces: the 5 operator-named intent profiles exist, conform to the
orchestration-profile schema shape, id == filename stem, engine ∈ known
backends, model ∈ models/catalog.yaml, and the top-level key is
`orchestration_profile` (guaranteeing no collision with the runtime-profile
reader/lint).

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
ORCH_DIR = REPO_ROOT / "profiles" / "orchestration"
SCHEMA = REPO_ROOT / "schemas" / "orchestration-profile.schema.yaml"

EXPECTED_PROFILES = [
    "full-orchestration",
    "coding-focus",
    "thinking-focus",
    "hybrid-coding-thinking",
    "full-hybrid",
]
KNOWN_TIERS = {"pulse", "logic", "oracle", "router"}
KNOWN_ENGINES = {"bitnet.cpp", "vllm", "vllm-vulkan", "llama.cpp"}
KNOWN_INTENTS = {"full-orchestration", "coding", "thinking", "hybrid", "full-hybrid"}


def _catalog_ids() -> set[str]:
    spec = importlib.util.spec_from_file_location(
        "_mh_core", REPO_ROOT / "scripts" / "inference" / "model-health.py")
    mh = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mh)
    return {m["id"] for m in mh.load_catalog()}


def _load(pid: str) -> dict:
    p = ORCH_DIR / f"{pid}.yaml"
    assert p.is_file(), f"missing orchestration profile: {p}"
    return yaml.safe_load(p.read_text())


def test_schema_present():
    assert SCHEMA.is_file(), f"missing {SCHEMA}"


def test_exactly_the_five_profiles_present():
    """The operator-named 5 orchestration-intent profiles must exist —
    no more, no fewer (add/rename requires updating EXPECTED_PROFILES in
    the same commit)."""
    on_disk = sorted(p.stem for p in ORCH_DIR.glob("*.yaml"))
    assert on_disk == sorted(EXPECTED_PROFILES), (
        f"orchestration profile set drift: on-disk {on_disk} vs "
        f"expected {sorted(EXPECTED_PROFILES)}"
    )


def test_top_level_key_is_orchestration_profile():
    """The distinct top-level key guarantees no collision with the
    verbatim-locked runtime-profile family."""
    for pid in EXPECTED_PROFILES:
        d = _load(pid)
        assert "orchestration_profile" in d, f"{pid}: missing orchestration_profile key"
        assert "runtime_profile" not in d, (
            f"{pid}: must NOT carry runtime_profile (that's the locked §18 family)"
        )


def test_each_profile_conforms():
    catalog = _catalog_ids()
    for pid in EXPECTED_PROFILES:
        d = _load(pid)
        assert d.get("schema_version"), f"{pid}: missing schema_version"
        op = d["orchestration_profile"]
        assert op["id"] == pid, f"{pid}: id {op['id']} != filename stem"
        assert op.get("name"), f"{pid}: missing name"
        assert len(op.get("description", "")) >= 30, f"{pid}: description too short"
        assert op.get("intent") in KNOWN_INTENTS, f"{pid}: bad intent {op.get('intent')}"
        assert "sain-01" in op.get("hardware_profile_compat", []), f"{pid}: not sain-01-compat"
        allocs = op.get("allocations", [])
        assert allocs, f"{pid}: no allocations"
        for a in allocs:
            assert a.get("tier") in KNOWN_TIERS, f"{pid}: bad tier {a.get('tier')}"
            assert a.get("engine") in KNOWN_ENGINES, f"{pid}: bad engine {a.get('engine')}"
            assert a.get("model") in catalog, (
                f"{pid}: model {a.get('model')!r} not in models/catalog.yaml"
            )


def test_runtime_profile_family_untouched():
    """Guard: the verbatim-locked §18 runtime family still has exactly 3
    profiles — the new orchestration family must not have leaked into it."""
    runtime = sorted(p.stem for p in (REPO_ROOT / "profiles" / "runtime").glob("*.yaml"))
    assert len(runtime) == 3, (
        f"runtime profile family must stay at 3 (verbatim §18); got {runtime}"
    )
