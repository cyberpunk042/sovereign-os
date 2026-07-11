//! `sovereign-simd` — the sanctioned SIMD carve-out.
//!
//! Every other crate in this workspace forbids `unsafe` (`[workspace.lints.rust]
//! unsafe_code = "forbid"`, inherited by all 709 crates via `[lints] workspace =
//! true`). That is a deliberate safety stance for a security-focused OS. Real
//! AVX-512 exploitation, however, needs vendor intrinsics, and those are `unsafe`.
//!
//! This crate is the single, operator-approved exception: it opts out of the
//! workspace lint and allows `unsafe` **here and nowhere else**, keeping the
//! blast radius to one small, heavily-tested module.
//!
//! ## The contract every kernel keeps
//!
//! 1. A **safe public wrapper** (`sum_of_squares`) — callers never touch `unsafe`.
//! 2. **Runtime CPU detection** (`is_x86_feature_detected!`) picks the intrinsic
//!    path only when the host actually supports it; otherwise the scalar path runs.
//!    So the same binary is correct on a machine with AVX-512 and one without.
//! 3. A **scalar reference** (`*_scalar`) that is the source of truth. The SIMD
//!    path is proven equal to it (within floating-point tolerance) by the tests
//!    in this crate — the SIMD path is an optimization, never a new behavior.
//!
//! The `DispatchPath` scaffolding in `sovereign-cpu-dispatch` selected paths that
//! had no intrinsics behind them; this crate is where those paths get real.
//!
//! ## Verifiability note (P4)
//!
//! The first kernel here (`sum_of_squares`) uses only **AVX-512F**, which is the
//! baseline AVX-512 feature and is present on the build/CI host — so its SIMD path
//! is genuinely exercised and verified. Future kernels using `avx512vnni`
//! (`VPDPBUSD`/`VDPBF16PS`) or `avx512vpopcntdq` (`VPOPCNTQ`) compile everywhere but
//! can only be *runtime-verified* on a CPU carrying those features; such kernels
//! must be added behind their own `is_x86_feature_detected!` gate and flagged
//! CI-gated until an appropriately-featured runner exists.
//!
//! Standing rule: We do not minimize anything.

#![warn(missing_docs)]

/// Schema version of the SIMD surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Whether the host CPU supports the AVX-512 Foundation feature set — the gate
/// for [`sum_of_squares`]'s fast path. Always `false` off x86-64.
#[must_use]
pub fn has_avx512f() -> bool {
    #[cfg(target_arch = "x86_64")]
    {
        std::is_x86_feature_detected!("avx512f")
    }
    #[cfg(not(target_arch = "x86_64"))]
    {
        false
    }
}

/// Sum of squares, `Σ xᵢ²` — the reduction RMSNorm computes to find the
/// root-mean-square of an activation vector.
///
/// Dispatches to an AVX-512F path when the host supports it (16 lanes of fused
/// multiply-add per step), and to the scalar reference otherwise. The result is
/// equal to [`sum_of_squares_scalar`] within floating-point tolerance (the SIMD
/// path fuses the multiply and add and reduces in a tree, so rounding differs
/// slightly — and is, if anything, more accurate).
#[must_use]
pub fn sum_of_squares(x: &[f32]) -> f32 {
    #[cfg(target_arch = "x86_64")]
    {
        if std::is_x86_feature_detected!("avx512f") {
            // SAFETY: guarded by the runtime feature check immediately above;
            // `sum_of_squares_avx512f` uses only AVX-512F loads/FMA/reduce, all
            // available whenever `avx512f` is detected. It reads `x` in-bounds
            // (exact 16-lane chunks + a scalar remainder) and writes nothing.
            return unsafe { sum_of_squares_avx512f(x) };
        }
    }
    sum_of_squares_scalar(x)
}

/// The scalar reference for [`sum_of_squares`] — the source of truth the SIMD
/// path is verified against.
#[must_use]
pub fn sum_of_squares_scalar(x: &[f32]) -> f32 {
    x.iter().map(|v| v * v).sum()
}

/// AVX-512F sum-of-squares. 16 f32 lanes per step via `_mm512_fmadd_ps`, a
/// horizontal reduce, then a scalar tail for the `< 16` remainder.
///
/// # Safety
/// The caller must ensure the host supports `avx512f` (guaranteed by the
/// runtime check in [`sum_of_squares`]). The function only reads `x` within
/// bounds and mutates no memory.
#[cfg(target_arch = "x86_64")]
#[target_feature(enable = "avx512f")]
unsafe fn sum_of_squares_avx512f(x: &[f32]) -> f32 {
    use core::arch::x86_64::{
        _mm512_fmadd_ps, _mm512_loadu_ps, _mm512_reduce_add_ps, _mm512_setzero_ps,
    };
    // SAFETY (whole block): the caller guarantees `avx512f`; each intrinsic below
    // is available under that feature. Loads are exact-16-lane (in-bounds); the
    // reduce and setzero touch only registers. No memory is written.
    unsafe {
        let mut acc = _mm512_setzero_ps();
        let mut chunks = x.chunks_exact(16);
        for c in &mut chunks {
            let v = _mm512_loadu_ps(c.as_ptr());
            acc = _mm512_fmadd_ps(v, v, acc); // acc_i += v_i * v_i
        }
        let mut total = _mm512_reduce_add_ps(acc);
        for &v in chunks.remainder() {
            total += v * v;
        }
        total
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use rand::{Rng, SeedableRng};
    use rand_chacha::ChaCha8Rng;

    /// Relative tolerance for SIMD-vs-scalar equality. FMA + tree-reduce round
    /// differently from a sequential scalar sum; this bounds the divergence.
    fn close(a: f32, b: f32) -> bool {
        (a - b).abs() <= 1e-4 * (a.abs() + b.abs() + 1.0)
    }

    #[test]
    fn empty_and_tiny() {
        assert_eq!(sum_of_squares(&[]), 0.0);
        assert!(close(sum_of_squares(&[3.0]), 9.0));
        assert!(close(sum_of_squares(&[1.0, 2.0, 3.0]), 14.0));
    }

    #[test]
    fn simd_equals_scalar_across_lengths() {
        let mut rng = ChaCha8Rng::seed_from_u64(0x50_1D_5A_1D);
        // lengths straddling the 16-lane boundary + the remainder tail
        for &n in &[0usize, 1, 7, 15, 16, 17, 31, 32, 33, 64, 100, 257, 1000, 4096] {
            let x: Vec<f32> = (0..n).map(|_| rng.random_range(-3.0f32..3.0)).collect();
            let simd = sum_of_squares(&x);
            let scalar = sum_of_squares_scalar(&x);
            assert!(
                close(simd, scalar),
                "n={n}: simd={simd} scalar={scalar} (Δ={})",
                (simd - scalar).abs()
            );
        }
    }

    /// Directly exercise the intrinsic path (not just the dispatcher) when the
    /// host supports it, so the AVX-512F kernel itself is verified — not merely
    /// the scalar fallback. On a host without avx512f this asserts nothing about
    /// the intrinsic (documented P4 gap) but still checks the dispatcher.
    #[test]
    fn avx512f_path_is_exercised_when_present() {
        let mut rng = ChaCha8Rng::seed_from_u64(0xA5_12_F0_0D);
        let x: Vec<f32> = (0..333).map(|_| rng.random_range(-2.0f32..2.0)).collect();
        let scalar = sum_of_squares_scalar(&x);
        if has_avx512f() {
            #[cfg(target_arch = "x86_64")]
            // SAFETY: guarded by `has_avx512f()` returning true.
            let direct = unsafe { sum_of_squares_avx512f(&x) };
            #[cfg(target_arch = "x86_64")]
            assert!(close(direct, scalar), "intrinsic {direct} vs scalar {scalar}");
        } else {
            // fallback path must still match
            assert!(close(sum_of_squares(&x), scalar));
        }
    }
}
