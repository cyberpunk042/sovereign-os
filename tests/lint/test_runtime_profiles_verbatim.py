"""R422 (E10.M66) — runtime-profile YAMLs § 18 verbatim 3-mode contract
+ 12th bidirectional-consistency lint (runtime_profile.id↔filename +
engines↔backend-adapters from R404).

Extends R387-R421 + R404 operational-artifact pinning to:
  profiles/runtime/ultra-sovereign-efficiency.yaml
  profiles/runtime/deep-context-synthesis.yaml
  profiles/runtime/high-concurrency-burst.yaml

Master spec § 18 verbatim 3-profile Trinity workload catalog:
  Profile 1: Ultra-Sovereign Efficiency Mode (CPU Focused)
    > "Designed for continuous background state monitoring, log auditing,
    >  and autonomous maintenance tasks with near-zero power draw."
    Tier set: pulse only (CPU)

  Profile 2: Deep-Context Synthesis Mode (Oracle reasoning)
    Tier set: oracle (Blackwell)

  Profile 3: High-Concurrency Burst Mode (full Trinity)
    Tier set: pulse + logic + oracle (all 3 simultaneously)

12th bidirectional-consistency lint:
  - runtime_profile.id MUST match filename stem
  - engine names in allocations MUST be known backend names
    (bitnet.cpp / vllm / vllm-vulkan / llama.cpp) — R404 covered the
    adapter Python classes
  - hardware_profile_compat values MUST be real profiles in profiles/
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_DIR = REPO_ROOT / "profiles" / "runtime"

EXPECTED_PROFILES = [
    "ultra-sovereign-efficiency",
    "deep-context-synthesis",
    "high-concurrency-burst",
]

# Operator-additive § 18 profiles — NOT the master-spec Trinity 3, but § 18
# (and the schema-conformance test) explicitly permit operator-additive
# profiles. Tracked here so drift detection still fails on any UNtracked file.
OPERATOR_ADDITIVE_PROFILES = [
    "dual-turing-serving",  # SDD-714 — dual-Turing workstation llama.cpp serving
]

# Tier identifiers that runtime_profile.allocations[].tier may take.
# Aligned with § 17.1 Trinity (pulse / logic / oracle).
KNOWN_TIERS = {"pulse", "logic", "oracle"}

# Engine identifiers — these MUST map to a known backend adapter
# (R404 pinned BitnetBackend / VllmBackend / LlamaCppBackend).
KNOWN_ENGINES = {
    "bitnet.cpp",
    "vllm",
    "vllm-vulkan",  # vLLM with Vulkan backend (4090 path)
    "llama.cpp",
}


def _load(profile_id: str) -> dict:
    p = RUNTIME_DIR / f"{profile_id}.yaml"
    assert p.is_file(), f"missing runtime profile: {p}"
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def _read_text(profile_id: str) -> str:
    p = RUNTIME_DIR / f"{profile_id}.yaml"
    return p.read_text(encoding="utf-8")


# --- Structural ---


def test_all_three_runtime_profiles_exist():
    for pid in EXPECTED_PROFILES:
        p = RUNTIME_DIR / f"{pid}.yaml"
        assert p.is_file(), (
            f"runtime profile missing: {p} (operator-named § 18 "
            f"3-profile Trinity workload catalog)"
        )


def test_runtime_profile_count_matches():
    actual = sorted(p.stem for p in RUNTIME_DIR.glob("*.yaml"))
    tracked = sorted(EXPECTED_PROFILES + OPERATOR_ADDITIVE_PROFILES)
    assert actual == tracked, (
        f"profiles/runtime/ drift: actual={actual} vs tracked={tracked} "
        f"(§ 18 master-spec 3 + operator-additive: {OPERATOR_ADDITIVE_PROFILES}). "
        f"A new profile must be registered in OPERATOR_ADDITIVE_PROFILES."
    )


def test_operator_additive_profiles_pass_generic_invariants():
    """Operator-additive § 18 profiles get the same generic consistency
    checks as the master-spec 3 (id↔filename, engines known, tiers known,
    hardware_profile_compat resolves) — the master-spec-specific verbatim
    quotes below deliberately do NOT apply to them."""
    profiles_dir = REPO_ROOT / "profiles"
    for pid in OPERATOR_ADDITIVE_PROFILES:
        data = _load(pid)
        rp = data.get("runtime_profile") or {}
        assert rp.get("id") == pid, f"{pid}.yaml id={rp.get('id')!r} != filename"
        allocs = rp.get("allocations") or []
        assert allocs, f"{pid}.yaml has no allocations"
        for alloc in allocs:
            assert alloc.get("engine") in KNOWN_ENGINES, (
                f"{pid}.yaml engine={alloc.get('engine')!r} not in {KNOWN_ENGINES}"
            )
            assert alloc.get("tier") in KNOWN_TIERS, (
                f"{pid}.yaml tier={alloc.get('tier')!r} not in {KNOWN_TIERS}"
            )
        for hw_profile in rp.get("hardware_profile_compat") or []:
            assert (profiles_dir / f"{hw_profile}.yaml").is_file(), (
                f"{pid}.yaml hardware_profile_compat {hw_profile!r} doesn't exist"
            )


def test_every_profile_has_schema_version():
    for pid in EXPECTED_PROFILES:
        data = _load(pid)
        assert data.get("schema_version") == "1.0.0", (
            f"{pid}.yaml missing schema_version: 1.0.0"
        )


# --- 12th bidirectional-consistency lint ---


def test_bidirectional_runtime_profile_id_matches_filename():
    """12th bidirectional-consistency lint: runtime_profile.id MUST
    match filename stem. Drift = workload-mode set fails silently
    when invoked with one form vs the other."""
    for pid in EXPECTED_PROFILES:
        data = _load(pid)
        rp = data.get("runtime_profile") or {}
        assert rp.get("id") == pid, (
            f"{pid}.yaml runtime_profile.id={rp.get('id')!r} != "
            f"filename {pid!r} (BIDIRECTIONAL CONSISTENCY VIOLATION: "
            f"profile composition reference silently fails)"
        )


def test_bidirectional_engines_in_known_backend_set():
    """12th bidirectional consistency continued: every engine name in
    allocations[].engine MUST map to a known backend adapter (R404)."""
    for pid in EXPECTED_PROFILES:
        data = _load(pid)
        rp = data.get("runtime_profile") or {}
        allocs = rp.get("allocations") or []
        for alloc in allocs:
            engine = alloc.get("engine")
            assert engine in KNOWN_ENGINES, (
                f"{pid}.yaml has engine={engine!r} not in known set "
                f"{KNOWN_ENGINES} (bidirectional consistency: engine "
                f"must map to a backend adapter from R404)"
            )


def test_bidirectional_hardware_profile_compat_resolves():
    """hardware_profile_compat values MUST be real profile YAMLs in
    profiles/. Drift = workload-mode advertises compatibility with
    nonexistent profile."""
    profiles_dir = REPO_ROOT / "profiles"
    for pid in EXPECTED_PROFILES:
        data = _load(pid)
        rp = data.get("runtime_profile") or {}
        compat = rp.get("hardware_profile_compat") or []
        for hw_profile in compat:
            p = profiles_dir / f"{hw_profile}.yaml"
            assert p.is_file(), (
                f"{pid}.yaml hardware_profile_compat references "
                f"{hw_profile!r} but {p} doesn't exist (bidirectional "
                f"consistency violation)"
            )


# --- Tier identifier validity (§ 17.1) ---


def test_every_allocation_tier_known():
    for pid in EXPECTED_PROFILES:
        data = _load(pid)
        allocs = (data.get("runtime_profile") or {}).get("allocations") or []
        for alloc in allocs:
            tier = alloc.get("tier")
            assert tier in KNOWN_TIERS, (
                f"{pid}.yaml allocation tier={tier!r} not in § 17.1 "
                f"Trinity set {KNOWN_TIERS}"
            )


# --- § 18 Profile 1 verbatim (Ultra-Sovereign Efficiency / CPU Focused) ---


def test_ultra_sovereign_efficiency_is_cpu_only():
    """§ 18 Profile 1 verbatim: 'CPU Focused' — only pulse tier."""
    data = _load("ultra-sovereign-efficiency")
    allocs = (data.get("runtime_profile") or {}).get("allocations") or []
    tiers = [a.get("tier") for a in allocs]
    assert all(t == "pulse" for t in tiers), (
        f"ultra-sovereign-efficiency.yaml has non-pulse tier "
        f"{tiers!r} (§ 18 Profile 1 is CPU-Focused verbatim — pulse only)"
    )


def test_ultra_sovereign_efficiency_uses_bitnet():
    """§ 18 Profile 1 verbatim: bitnet.cpp engine on CPU."""
    data = _load("ultra-sovereign-efficiency")
    allocs = (data.get("runtime_profile") or {}).get("allocations") or []
    engines = [a.get("engine") for a in allocs]
    assert "bitnet.cpp" in engines, (
        f"ultra-sovereign-efficiency.yaml missing bitnet.cpp engine "
        f"(§ 18 Profile 1 verbatim — CPU ternary)"
    )


def test_ultra_sovereign_efficiency_ccd_0_core_mask():
    """§ 18 + § 17.1: Pulse is CCD 0 cores 0-7 (or 0-5 minimum).
    Drift to '8-15' (CCD 1) = SRP violation."""
    data = _load("ultra-sovereign-efficiency")
    allocs = (data.get("runtime_profile") or {}).get("allocations") or []
    for alloc in allocs:
        if alloc.get("tier") == "pulse":
            mask = alloc.get("core_mask", "")
            # Mask should be 0-N where N ≤ 7 (CCD 0 has 8 cores 0-7)
            assert mask.startswith("0-"), (
                f"ultra-sovereign-efficiency.yaml pulse core_mask="
                f"{mask!r} doesn't start at core 0 (CCD 0 violation)"
            )


def test_ultra_sovereign_efficiency_verbatim_quote():
    """§ 18 Profile 1 verbatim operator framing in YAML comments."""
    body = _read_text("ultra-sovereign-efficiency")
    has_verbatim = (
        "continuous background state monitoring" in body
        or "log auditing" in body
        or "near-zero power draw" in body
    )
    assert has_verbatim, (
        "ultra-sovereign-efficiency.yaml missing § 18 Profile 1 "
        "verbatim quote ('continuous background state monitoring' / "
        "'near-zero power draw') — operator-discovery loses the WHY"
    )


# --- § 18 Profile 2 verbatim (Deep-Context Synthesis / Oracle) ---


def test_deep_context_synthesis_uses_oracle_tier():
    """§ 18 Profile 2 verbatim: Oracle-tier reasoning (Blackwell)."""
    data = _load("deep-context-synthesis")
    allocs = (data.get("runtime_profile") or {}).get("allocations") or []
    tiers = [a.get("tier") for a in allocs]
    assert "oracle" in tiers, (
        "deep-context-synthesis.yaml missing oracle tier "
        "(§ 18 Profile 2 verbatim — Oracle synthesis on Blackwell)"
    )


def test_deep_context_synthesis_uses_vllm():
    """§ 18 Profile 2: vLLM on Blackwell (matches R404 VllmBackend
    for_oracle_core)."""
    data = _load("deep-context-synthesis")
    allocs = (data.get("runtime_profile") or {}).get("allocations") or []
    engines = [a.get("engine") for a in allocs]
    assert "vllm" in engines, (
        "deep-context-synthesis.yaml missing vllm engine "
        "(§ 18 Profile 2 verbatim — Oracle uses vLLM)"
    )


# --- § 18 Profile 3 verbatim (High-Concurrency Burst / full Trinity) ---


def test_high_concurrency_burst_engages_all_three_tiers():
    """§ 18 Profile 3 verbatim: full Trinity simultaneously — pulse
    AND logic AND oracle all active. Drift dropping any one = not
    a 'burst' anymore."""
    data = _load("high-concurrency-burst")
    allocs = (data.get("runtime_profile") or {}).get("allocations") or []
    tiers = {a.get("tier") for a in allocs}
    assert tiers == KNOWN_TIERS, (
        f"high-concurrency-burst.yaml tiers={tiers} != Trinity "
        f"{KNOWN_TIERS} (§ 18 Profile 3 verbatim — full burst)"
    )


def test_high_concurrency_burst_pulse_uses_more_cores():
    """In burst mode, pulse expands beyond CCD 0 (operator wants
    full CCD0 + spillover allowed for burst window). core_mask
    should cover at least cores 0-11 (CCD0 8 + CCD1 first 4)."""
    data = _load("high-concurrency-burst")
    allocs = (data.get("runtime_profile") or {}).get("allocations") or []
    pulse_alloc = next(
        (a for a in allocs if a.get("tier") == "pulse"), None
    )
    assert pulse_alloc, (
        "high-concurrency-burst.yaml missing pulse allocation"
    )
    mask = pulse_alloc.get("core_mask", "")
    # Burst mode pulse should use more cores than steady ultra-sovereign
    assert "0-" in mask, (
        f"high-concurrency-burst.yaml pulse core_mask={mask!r} "
        f"doesn't start at 0 (operator-named CCD pinning baseline)"
    )


# --- Master spec § 18 reference verbatim ---


def test_every_profile_references_section_18():
    for pid in EXPECTED_PROFILES:
        body = _read_text(pid)
        has_ref = "§ 18" in body or "section 18" in body.lower()
        assert has_ref, (
            f"{pid}.yaml missing master spec § 18 reference "
            f"(operator-discovery — drift loses binding to spec section)"
        )


def test_every_profile_has_description():
    for pid in EXPECTED_PROFILES:
        data = _load(pid)
        rp = data.get("runtime_profile") or {}
        desc = (rp.get("description") or "").strip()
        assert desc, (
            f"{pid}.yaml missing runtime_profile.description "
            f"(operator-discovery context)"
        )


def test_every_profile_has_at_least_one_allocation():
    """A runtime profile with no allocations is a no-op. Drift
    silently disables the workload mode."""
    for pid in EXPECTED_PROFILES:
        data = _load(pid)
        allocs = (data.get("runtime_profile") or {}).get("allocations") or []
        assert allocs, (
            f"{pid}.yaml has no allocations (drift = workload mode "
            f"is a silent no-op)"
        )
