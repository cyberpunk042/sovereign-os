"""SDD-401 phase 4 — GPU-fold KV attention seam contract.

Phase 2 gave `sovereign-quant-model` the top-level GPU-fold seam (mode +
`FoldBackend`). Phase 4 extends the seam **down into the attention path** where
the KV cache actually lives — `sovereign-mha-block` — so a folded-KV backend can
take over attention compute per block, while the default pure-Rust CPU path stays
untouched and bit-exact.

This lint pins that seam so it can't silently regress: the `KvExecMode` selector
(with `Cpu` as the `#[default]`), the `KvFoldBackend` plug-point (mirroring the
phase-3 `cf_kv_attn_dense_async` dense interface), and — the load-bearing honesty
property — that selecting `GpuFold` with no backend **honest-degrades** (errors)
inside `step()` rather than silently running CPU under a GPU claim.

Text-level contract (mirrors the other `test_*_contract.py` lints): it asserts
source *shape*, not runtime behaviour (the crate's own `cargo test` proves the
bit-exact CPU↔fold conformance). It reads only committed sovereign files.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB = REPO_ROOT / "crates" / "sovereign-mha-block" / "src" / "lib.rs"


def _src() -> str:
    assert LIB.is_file(), f"missing {LIB} (SDD-401 phase 4)"
    return LIB.read_text(encoding="utf-8")


def test_kv_exec_mode_enum_exists_with_cpu_default():
    s = _src()
    assert "pub enum KvExecMode" in s, "KvExecMode selector missing (SDD-401 phase 4)"
    assert "GpuFold" in s and "Cpu" in s, "KvExecMode must offer Cpu + GpuFold"
    # Cpu must be the default variant — the pure-Rust path is the default.
    assert "#[default]\n    Cpu" in s, "Cpu must be the #[default] KvExecMode variant"


def test_kv_fold_backend_plugpoint_exists_and_stays_safe():
    s = _src()
    assert "pub trait KvFoldBackend" in s, "KvFoldBackend plug-point trait missing"
    assert "fn fold_attend(" in s, "KvFoldBackend must expose fold_attend (dense interface)"
    # the seam only defines the contract; the crate stays unsafe-free.
    assert "#![forbid(unsafe_code)]" in s, "mha-block must forbid unsafe (SDD-400 rule)"
    # Arc (not Box) so the block stays Clone — a shared device handle.
    assert "Option<std::sync::Arc<dyn KvFoldBackend>>" in s, (
        "kv fold backend must be an Arc so MhaDecoderBlock stays Clone"
    )


def test_gpu_fold_honest_degrades_never_silent_cpu():
    s = _src()
    assert "GpuFoldUnavailable" in s, "the honest-degrade error variant is missing"
    # step() must branch on the mode and refuse when GpuFold + no backend, rather
    # than falling through to CPU while claiming to be folded.
    assert "match self.kv_exec_mode {" in s, (
        "step() must branch on kv_exec_mode (Cpu vs GpuFold)"
    )
    assert "KvExecMode::GpuFold =>" in s, "step() must handle the GpuFold arm"
    assert "MhaBlockError::GpuFoldUnavailable" in s, (
        "GpuFold with no backend must honest-degrade to GpuFoldUnavailable"
    )


def test_seam_is_operator_introspectable():
    s = _src()
    for sym in (
        "fn kv_exec_mode(",
        "fn set_kv_exec_mode(",
        "fn with_kv_exec_mode(",
        "fn set_kv_fold_backend(",
        "fn kv_fold_status(",
    ):
        assert sym in s, f"missing seam accessor {sym} (SDD-401 phase 4)"
