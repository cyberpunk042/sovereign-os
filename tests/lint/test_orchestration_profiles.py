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
KNOWN_TIERS = {"pulse", "logic", "oracle", "router", "embed", "rerank"}
KNOWN_ENGINES = {"bitnet.cpp", "vllm", "vllm-vulkan", "llama.cpp"}
# The 5 named seed intents + `custom` (operator-composed profiles, D-21 composer).
KNOWN_INTENTS = {"full-orchestration", "coding", "thinking", "hybrid", "full-hybrid", "custom"}


def _all_stems() -> list[str]:
    return sorted(p.stem for p in ORCH_DIR.glob("*.yaml"))


def _catalog_ids() -> set[str]:
    spec = importlib.util.spec_from_file_location(
        "_mh_core", REPO_ROOT / "scripts" / "inference" / "model-health.py")
    mh = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mh)
    rows = mh.load_catalog()
    assert all("id" in row for row in rows), "catalog parser emitted a non-model row"
    return {m["id"] for m in rows}


def _load(pid: str) -> dict:
    p = ORCH_DIR / f"{pid}.yaml"
    assert p.is_file(), f"missing orchestration profile: {p}"
    return yaml.safe_load(p.read_text())


def test_schema_present():
    assert SCHEMA.is_file(), f"missing {SCHEMA}"


def test_the_five_named_profiles_are_a_floor():
    """The operator-named 5 orchestration-intent profiles must ALWAYS exist —
    they are a floor, not a ceiling. The family is now growable (D-21 composer
    writes operator-composed profiles here), so EXTRA profiles are allowed as
    long as every file schema-validates (test_each_profile_conforms below +
    tests/schema/test_orchestration_profile_schema_conformance.py). Removing or
    renaming one of the 5 requires updating EXPECTED_PROFILES in the same commit."""
    on_disk = set(_all_stems())
    missing = set(EXPECTED_PROFILES) - on_disk
    assert not missing, f"the 5 named orchestration profiles must exist; missing: {missing}"


def test_qwythos_profile_is_catalogued_and_applyable():
    """The operator-requested Qwythos GGUF profile remains a first-class D-21 choice."""
    profile = _load("qwythos-local-agent")["orchestration_profile"]
    assert any(a.get("model") == "Qwythos-9B-Claude-Mythos-5-1M-GGUF"
               and a.get("active") is True for a in profile["allocations"])


def test_qwythos_deep_context_profile_is_pro_6000_sized_and_gated():
    """Deep-context Qwythos stays a single PRO 6000 Oracle allocation until benchmarked."""
    profile = _load("qwythos-deep-context")["orchestration_profile"]
    alloc = next(a for a in profile["allocations"]
                 if a.get("model") == "Qwythos-9B-Claude-Mythos-5-1M-GGUF")
    assert alloc["target_hardware"] == "cuda:1"
    assert alloc["vram_limit_bytes"] == 80 * 1024**3
    assert "--ctx-size 65536" in alloc["runtime_invocation"]
    assert profile["context_budget"]["initial_tokens"] == 65536
    assert profile["benchmark_gate"]["required"] is True


def test_qwythos_three_card_profile_places_one_instance_on_each_gpu():
    """The explicit all-GPU Qwythos pool remains a D-21 applyable choice."""
    profile = _load("qwythos-three-card")["orchestration_profile"]
    qwythos = [a for a in profile["allocations"]
               if a.get("model") == "Qwythos-9B-Claude-Mythos-5-1M-GGUF"]
    assert {a["target_hardware"] for a in qwythos} == {"cuda:0", "cuda:1", "cuda:2"}
    assert {a["port"] for a in qwythos} == {8082, 8083, 8086}
    assert all(a["engine"] == "llama.cpp" and a["active"] for a in qwythos)


def test_dual_agent_qwen_profile_has_hardware_safe_launch_contract():
    """The Qwen profile must avoid known post-reboot vLLM startup failures.

    Qwen3.6-27B-Coder consumes nearly all 32 GiB of the RTX 5090 before KV
    cache initialization, so CUDAGraph capture is not viable there.  The PRO
    6000 host does not ship nvcc, so FlashInfer JIT must not be selected.
    """
    allocs = _load("dual-agent-autocomplete")["orchestration_profile"]["allocations"]
    logic = next(a for a in allocs if a["tier"] == "logic")
    oracle = next(a for a in allocs if a["tier"] == "oracle")
    assert logic["model"] == "GGML-Qwen3.6-27B-Coder"
    assert logic["target_hardware"] == "cuda:1"
    assert logic["model_path"].endswith("Qwen3.6-27B-Q4_K_M.gguf")
    assert logic["engine"] == "llama.cpp"
    assert logic["max_model_len"] == 32768
    assert "--cache-type-k q8_0" in logic["extra_args"]
    assert oracle["model"] == "Qwen3-Coder-32B-Instruct"
    assert "--served-model-name gpu-oracle" in oracle["extra_args"]
    assert "--attention-backend TRITON_ATTN" in oracle["extra_args"]


def test_top_level_key_is_orchestration_profile():
    """The distinct top-level key guarantees no collision with the
    verbatim-locked runtime-profile family — checked for EVERY profile on disk
    (the 5 named + any operator-composed extras)."""
    for pid in _all_stems():
        d = _load(pid)
        assert "orchestration_profile" in d, f"{pid}: missing orchestration_profile key"
        assert "runtime_profile" not in d, (
            f"{pid}: must NOT carry runtime_profile (that's the locked §18 family)"
        )


def test_each_profile_conforms():
    catalog = _catalog_ids()
    for pid in _all_stems():
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


def test_ports_unique_per_card():
    """SDD-903 Phase 1a (N-per-card): two model instances sharing a
    target_hardware MUST declare distinct serving ports — otherwise the second
    can't bind and the gatewayd tier registration collides. Validated for every
    profile on disk. Allocations without an explicit `port` (single-model tiers)
    are unaffected."""
    for pid in _all_stems():
        d = _load(pid)
        seen: dict[tuple[str, int], str] = {}
        for a in d["orchestration_profile"].get("allocations", []):
            port = a.get("port")
            if port is None:
                continue
            key = (a.get("target_hardware", "?"), port)
            prev = seen.get(key)
            assert prev is None, (
                f"{pid}: port {port} reused on {key[0]} by {a.get('agent_id')!r} "
                f"and {prev!r} — models co-resident on a card need distinct ports "
                f"(SDD-903 Phase 1a)"
            )
            seen[key] = a.get("agent_id")


def test_multiple_models_per_card_is_expressible():
    """SDD-903 Phase 1a acceptance: the schema+lint can express N models on one
    card. At least one on-disk profile must place >1 active allocation on the
    same cuda device, each with its own port — proving the feature is writable
    (dense-4090 is the seed example, mirroring the live 4090 embed+rerank)."""
    found = False
    for pid in _all_stems():
        d = _load(pid)
        by_card: dict[str, int] = {}
        for a in d["orchestration_profile"].get("allocations", []):
            hw = a.get("target_hardware", "")
            if hw.startswith("cuda:") and a.get("port") is not None:
                by_card[hw] = by_card.get(hw, 0) + 1
        if any(n >= 2 for n in by_card.values()):
            found = True
            break
    assert found, (
        "no orchestration profile places >1 ported model on one card — the "
        "N-per-card schema (SDD-903 Phase 1a) has no exercising example"
    )


def test_runtime_profile_family_untouched():
    """Guard: the runtime family holds exactly the 3 master-spec §18 profiles
    plus any tracked operator-additive §18 profiles — and the orchestration
    family must not have leaked into it. The exact allowlist (not a bare count)
    is the real guard; see tests/lint/test_runtime_profiles_verbatim.py."""
    # Master-spec §18 (verbatim-locked) + operator-additive §18 (SDD-714).
    expected = sorted([
        "ultra-sovereign-efficiency",
        "deep-context-synthesis",
        "high-concurrency-burst",
        "dual-turing-serving",  # SDD-714 — operator-additive
    ])
    runtime = sorted(p.stem for p in (REPO_ROOT / "profiles" / "runtime").glob("*.yaml"))
    assert runtime == expected, (
        f"runtime profile family drift: got {runtime} vs expected {expected} "
        f"(§18 master-spec 3 + tracked operator-additive; a new profile must be "
        f"registered here + in test_runtime_profiles_verbatim.py, and an "
        f"orchestration profile must NOT land in profiles/runtime/)"
    )
