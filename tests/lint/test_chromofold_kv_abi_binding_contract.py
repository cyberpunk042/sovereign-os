"""SDD-401 phase 3 — ChromoFold compressed-KV compute C-ABI binding contract.

Phase 2 gave `sovereign-quant-model` the GPU-fold seam (mode + `FoldBackend`
plug-point). Phase 3 binds the *compute* kernels the folded-KV path will call —
`cf_kv_attn_fused_async` (the ~8× folded-KV serving path) and
`cf_kv_attn_dense_async` (its bit-exact verification baseline) — into the
sanctioned-unsafe FFI crate `sovereign-chromofold-sys`, behind the OFF-by-default
`linked` feature, and reflects them in the safe wrapper's `CapabilityDescriptor`
(the sovereign mirror of the native `chromofold_capability.json`).

This lint pins that binding so it can't silently regress or drift from the native
ABI, and — the load-bearing property — that the FFI stays quarantined behind
`linked` (off by default → the box behaves as today, no GPU / no `libchromofold`).
It reads only committed sovereign files (no GPU, no native checkout needed).
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SYS = REPO_ROOT / "crates" / "sovereign-chromofold-sys" / "src" / "lib.rs"
WRAP = REPO_ROOT / "crates" / "sovereign-chromofold" / "src" / "lib.rs"

KV_ABI_FNS = ("cf_kv_attn_fused_async", "cf_kv_attn_dense_async")
KV_CAP_IDS = ("kv_attention_fused", "kv_attention_dense_reference")


def test_sys_binds_the_kv_attention_compute_abi():
    src = SYS.read_text(encoding="utf-8")
    for fn in KV_ABI_FNS:
        assert fn in src, f"sovereign-chromofold-sys must bind the {fn} C ABI (SDD-401 phase 3)"
    # a safe wrapper exists for each (the callable surface for the wrapper crate)
    assert "pub unsafe fn kv_attn_fused_async" in src, "missing safe wrapper kv_attn_fused_async"
    assert "pub unsafe fn kv_attn_dense_async" in src, "missing safe wrapper kv_attn_dense_async"


def test_kv_binding_stays_quarantined_behind_the_linked_feature():
    src = SYS.read_text(encoding="utf-8")
    # the sanctioned-unsafe FFI + wrappers are the only unsafe in the workspace and
    # must remain OFF by default: every KV wrapper is `#[cfg(feature = "linked")]`.
    assert 'unsafe extern "C"' in src
    for marker in (
        '#[cfg(feature = "linked")]\n#[allow(clippy::too_many_arguments)]\npub unsafe fn kv_attn_fused_async',
        '#[cfg(feature = "linked")]\n#[allow(clippy::too_many_arguments)]\npub unsafe fn kv_attn_dense_async',
    ):
        assert marker in src, "KV wrappers must stay behind the OFF-by-default `linked` feature"
    # honest-degrade default is preserved.
    assert "pub const fn linked() -> bool" in src


def test_capability_descriptor_mirrors_the_kv_capabilities():
    wrap = WRAP.read_text(encoding="utf-8")
    for cap_id, fn in zip(KV_CAP_IDS, KV_ABI_FNS):
        assert cap_id in wrap, f"CapabilityDescriptor must list the {cap_id} capability (native mirror)"
        assert fn in wrap, f"CapabilityDescriptor must name the {fn} C ABI (native mirror)"
    # the mirror carries all 10 native capabilities (8 search/access + 2 KV).
    assert "d.capabilities.len(), 10" in wrap, "descriptor must mirror all 10 native capabilities"
