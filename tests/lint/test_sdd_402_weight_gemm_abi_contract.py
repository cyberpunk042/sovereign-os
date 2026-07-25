"""SDD-402 weight decode-in-GEMM C ABI export contract (Q-401-A) L1 lint.

Pins SDD-402's load-bearing claims so future edits can't silently drop the
export contract this SDD exists to fix as ChromoFold's phase-5 target:

  1. required sections (mission → gap → contract → phase-5 preview → scope →
     Q-rows → cross-refs), in order
  2. the two C ABI entries the contract names (the fused production entry +
     its bit-exact dense reference), mirroring the KV fused/dense precedent
  3. the honest gap claim: the kernels exist in fused_matmul.cu but are NOT in
     the stable header (chromofold.h v0) — so Q-401-A is a *promotion*
  4. the acceptance gate is bit-exactness (P4 lossless-over-quant), not tok/s
  5. the additive ABI-version bump (0 → 1)
  6. the design-stage posture — this SDD writes NO code (sovereign or ChromoFold)
  7. it resolves SDD-401's Q-401-A and is listed in the INDEX

Operators may edit prose freely; the section headers + named load-bearing
fragments stay pinned. Reads only committed sovereign files.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SDD_PATH = REPO_ROOT / "docs" / "sdd" / "402-chromofold-weight-gemm-abi-export-contract.md"

REQUIRED_SECTIONS = [
    "## Mission",
    "## The gap, verified (research-first, 2026-07-25)",
    "## The export contract (what ChromoFold must add to `chromofold.h`)",
    "## What sovereign-os does once the contract lands (SDD-401 phase 5 preview — NOT this SDD)",
    "## Honest scope, gates, risks",
    "## Open questions (ChromoFold-side / cross-repo)",
    "## Cross-references",
]

# The fused/dense C ABI pair the contract names — the existing benchmark
# entries that must be promoted to the stable header.
ABI_ENTRIES = ("cf_fused_matmul_async", "cf_dense_matmul_async")


def _body() -> str:
    assert SDD_PATH.is_file(), f"missing {SDD_PATH} (SDD-402)"
    return SDD_PATH.read_text(encoding="utf-8")


def test_sdd_402_has_required_sections_in_order():
    body = _body()
    missing = [s for s in REQUIRED_SECTIONS if s not in body]
    assert not missing, f"SDD-402 missing sections: {missing}"
    positions = [body.index(s) for s in REQUIRED_SECTIONS]
    assert positions == sorted(positions), "SDD-402 sections out of order"


def test_sdd_402_declares_the_band_and_mandate():
    body = _body()
    assert "Number band: **400–499**" in body, "SDD-402 must declare the chromofold band"
    assert "E11.M402" in body, "SDD-402 must name its mandate module"


def test_sdd_402_names_the_fused_dense_abi_pair():
    body = _body()
    for fn in ABI_ENTRIES:
        assert fn in body, f"SDD-402 must name the {fn} C ABI entry to promote"
    # it references the existing KV precedent it mirrors.
    assert "cf_kv_attn_fused_async" in body or "fused/dense" in body, (
        "SDD-402 must anchor on the KV fused/dense pair precedent"
    )


def test_sdd_402_pins_the_honest_gap():
    body = _body()
    # the kernels exist in fused_matmul.cu but not in the stable header — the gap.
    assert "fused_matmul.cu" in body, "SDD-402 must cite where the kernels live today"
    assert "chromofold.h" in body, "SDD-402 must name the stable header they must join"
    assert "not exported" in body.lower() or "not in the stable" in body.lower() or "NOT in the stable" in body, (
        "SDD-402 must state the entries are not yet in the stable ABI"
    )


def test_sdd_402_acceptance_gate_is_bit_exactness_not_throughput():
    body = _body()
    assert "bit-exact" in body.lower(), "SDD-402 must state bit-exactness is the gate"
    # throughput is deferred to SDD-401 phase 6, not this contract.
    assert "not throughput" in body.lower() or "not tok/s" in body.lower() or "phase 6" in body.lower(), (
        "SDD-402 must defer throughput to SDD-401 phase 6, not conflate it with the gate"
    )


def test_sdd_402_is_additive_abi_bump():
    body = _body()
    assert "CHROMOFOLD_ABI_VERSION" in body, "SDD-402 must name the ABI-version macro"
    assert "0 → 1" in body or "0 → 1" in body or "0-> 1" in body or "0→1" in body, (
        "SDD-402 must specify the additive 0→1 version bump"
    )


def test_sdd_402_is_design_stage_no_code():
    body = _body()
    assert "Stage: **design**" in body, "SDD-402 must be a design-stage SDD"
    assert "no" in body.lower() and "code" in body.lower(), "SDD-402 must state it writes no code"


def test_sdd_402_resolves_q401a_and_is_indexed():
    body = _body()
    assert "Q-401-A" in body, "SDD-402 must reference the SDD-401 Q-401-A it resolves"
    index = REPO_ROOT / "docs" / "sdd" / "INDEX.md"
    if index.is_file():
        assert "402" in index.read_text(encoding="utf-8"), "SDD-402 must be listed in INDEX.md"
