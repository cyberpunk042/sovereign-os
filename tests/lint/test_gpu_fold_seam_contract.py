"""SDD-401 phase 2 — GPU-fold hotswap seam contract.

Pins the opt-in GPU execution-mode seam in `sovereign-quant-model` so it can't
silently regress: the mode selector, the `FoldBackend` plug-point, and — the
load-bearing honesty property — that selecting `GpuFold` **honest-degrades**
(errors) rather than silently running the CPU path under a GPU claim, while the
default `Cpu` path stays untouched.

Text-level contract (mirrors the other `test_*_contract.py` lints): it asserts
the source *shape*, not runtime behaviour (the crate's own `cargo test` covers
behaviour). The CPU path is the bit-exact reference oracle (PROJECT_SYNC); this
lint guards that the GPU path can never masquerade as it.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB = REPO_ROOT / "crates" / "sovereign-quant-model" / "src" / "lib.rs"


def _src() -> str:
    assert LIB.is_file(), f"missing {LIB} (SDD-401 phase 2)"
    return LIB.read_text(encoding="utf-8")


def test_exec_mode_enum_exists_with_cpu_default():
    s = _src()
    assert "pub enum ExecMode" in s, "ExecMode selector missing (SDD-401)"
    assert "GpuFold" in s and "Cpu" in s, "ExecMode must offer Cpu + GpuFold"
    # Cpu must be the default variant — the reference path is the default.
    assert "#[default]\n    Cpu" in s, "Cpu must be the #[default] ExecMode variant"


def test_fold_backend_plugpoint_exists():
    s = _src()
    assert "pub trait FoldBackend" in s, "FoldBackend plug-point trait missing"
    # unsafe stays out of the safe engine crate.
    assert "#![forbid(unsafe_code)]" in s, "quant-model must forbid unsafe (SDD-400 rule)"
    assert "pub struct FoldCaps" in s, "FoldCaps capability descriptor missing"
    for cap in ("weights", "kv", "embedding"):
        assert cap in s, f"FoldCaps must declare the {cap} fold"


def test_gpu_fold_honest_degrades_never_silent_cpu():
    s = _src()
    assert "GpuFoldUnavailable" in s, "the honest-degrade error variant is missing"
    # The gate must live in forward(): GpuFold selected -> error, before the
    # CPU compute. Guard the exact condition so a refactor can't drop it.
    assert "self.exec_mode == ExecMode::GpuFold" in s, (
        "forward() must gate on GpuFold and honest-degrade (no silent CPU fall-through)"
    )
    assert "return Err(QuantModelError::GpuFoldUnavailable" in s, (
        "GpuFold must return GpuFoldUnavailable until the fold path is wired"
    )


def test_mode_and_backend_are_operator_introspectable():
    s = _src()
    for sym in ("fn exec_mode(", "fn set_exec_mode(", "fn set_fold_backend(", "fn fold_backend_status("):
        assert sym in s, f"missing seam accessor {sym} (SDD-401 phase 2)"
