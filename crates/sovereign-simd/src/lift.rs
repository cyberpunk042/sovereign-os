//! M085/M086 — the SIMD lift of the three-tier math references.
//!
//! M085 named three AVX-512 instruction tiers; the reference crates
//! (`sovereign-vnni`, `sovereign-bitops`) ship semantically-exact **scalar**
//! implementations (they `#![forbid(unsafe_code)]`). M086 is the plan to lift
//! each into a real `std::arch` hardware kernel in a sibling unsafe crate — this
//! one — dispatched by detected capability, with the scalar reference as the
//! differential oracle (SIMD output must equal scalar).
//!
//! | tier | kernel | flag | on the CI host? |
//! |------|--------|------|-----------------|
//! | T1 | `dot_i8` — VPDPBUSD INT8 dot | `avx512vnni` | **no** — scalar-verified, AVX path CI-gated |
//! | T1 | `dot_bf16` — VDPBF16PS BF16 dot | `avx512bf16` | **no** — scalar-verified, AVX path CI-gated |
//! | T2 | `attention_mask_fuse` — VPTERNLOG fuse | `avx512f` | **yes** — genuinely exercised |
//!
//! Per M086's P4 note: the VNNI/BF16 flags are absent on the SAIN-01 baseline
//! (`/proc/cpuinfo` = f/bw/cd/dq/vl only), so those AVX paths compile everywhere
//! but only *run* on a capable CPU. They are behind their own
//! `is_x86_feature_detected!` gate and verified against the scalar oracle here;
//! the VPTERNLOG T2 kernel uses only `avx512f` and IS exercised on CI.

/// T1 (VNNI / VPDPBUSD) — INT8 dot product `Σ a[i](u8) · b[i](i8)` into `i32`.
/// Dispatches to `_mm512_dpbusd_epi32` when the host has `avx512vnni`, else the
/// [`sovereign_vnni::dot_i8`] scalar reference (the oracle). Integer math →
/// bit-identical. Uses the shorter length if the slices differ.
#[must_use]
pub fn dot_i8(a: &[u8], b: &[i8]) -> i32 {
    let n = a.len().min(b.len());
    #[cfg(target_arch = "x86_64")]
    {
        if std::is_x86_feature_detected!("avx512vnni") && std::is_x86_feature_detected!("avx512f") {
            // SAFETY: gated by the runtime feature checks immediately above.
            return unsafe { dot_i8_avx512vnni(&a[..n], &b[..n]) };
        }
    }
    dot_i8_scalar(&a[..n], &b[..n])
}

/// Scalar reference for [`dot_i8`] — delegates to the M074 `sovereign-vnni`
/// oracle (equal-length slices).
#[must_use]
pub fn dot_i8_scalar(a: &[u8], b: &[i8]) -> i32 {
    sovereign_vnni::dot_i8(a, b).unwrap_or(0)
}

/// # Safety
/// Caller must ensure the host supports `avx512vnni` + `avx512f`.
#[cfg(target_arch = "x86_64")]
#[target_feature(enable = "avx512vnni,avx512f")]
unsafe fn dot_i8_avx512vnni(a: &[u8], b: &[i8]) -> i32 {
    use std::arch::x86_64::*;
    let n = a.len();
    let chunks = n / 64;
    // SAFETY: AVX-512F + VNNI intrinsics enabled by target_feature + caller gate;
    // each load reads 64 contiguous bytes within `c*64 + 64 <= n`.
    let mut total = unsafe {
        let mut acc = _mm512_setzero_si512();
        for c in 0..chunks {
            let va = _mm512_loadu_si512(a.as_ptr().add(c * 64) as *const __m512i);
            let vb = _mm512_loadu_si512(b.as_ptr().add(c * 64) as *const __m512i);
            // VPDPBUSD: per 32-bit lane, Σ of 4 (u8·i8) products, accumulated.
            acc = _mm512_dpbusd_epi32(acc, va, vb);
        }
        _mm512_reduce_add_epi32(acc)
    };
    // tail (n not a multiple of 64) — scalar, same math.
    for i in (chunks * 64)..n {
        total = total.wrapping_add(a[i] as i32 * b[i] as i32);
    }
    total
}

/// T1 (VDPBF16PS / `VPDOTBF16PLUS`) — BF16 dot product into `f32`. Dispatches to
/// `_mm512_dpbf16_ps` when the host has `avx512bf16`, else the
/// [`sovereign_vnni::dot_bf16`] scalar reference. Float reduction order differs
/// (tree vs sequential), so equality is within a small tolerance, not bitwise.
#[must_use]
pub fn dot_bf16(a: &[u16], b: &[u16]) -> f32 {
    let n = a.len().min(b.len());
    #[cfg(target_arch = "x86_64")]
    {
        if std::is_x86_feature_detected!("avx512bf16") && std::is_x86_feature_detected!("avx512f") {
            // SAFETY: gated by the runtime feature checks immediately above.
            return unsafe { dot_bf16_avx512(&a[..n], &b[..n]) };
        }
    }
    dot_bf16_scalar(&a[..n], &b[..n])
}

/// Scalar reference for [`dot_bf16`] — the M074 `sovereign-vnni` oracle.
#[must_use]
pub fn dot_bf16_scalar(a: &[u16], b: &[u16]) -> f32 {
    sovereign_vnni::dot_bf16(a, b).unwrap_or(0.0)
}

/// # Safety
/// Caller must ensure the host supports `avx512bf16` + `avx512f`.
#[cfg(target_arch = "x86_64")]
#[target_feature(enable = "avx512bf16,avx512f")]
unsafe fn dot_bf16_avx512(a: &[u16], b: &[u16]) -> f32 {
    use std::arch::x86_64::*;
    let n = a.len();
    let chunks = n / 32;
    // SAFETY: AVX-512F + BF16 intrinsics enabled by target_feature + caller gate;
    // each load reads 32 contiguous u16 (64 bytes) within bounds. The u16 bf16
    // words are reinterpreted as `__m512bh` (same 512-bit register), the type
    // `_mm512_dpbf16_ps` expects.
    let mut total = unsafe {
        let mut acc = _mm512_setzero_ps();
        for c in 0..chunks {
            let va = _mm512_loadu_si512(a.as_ptr().add(c * 32) as *const __m512i);
            let vb = _mm512_loadu_si512(b.as_ptr().add(c * 32) as *const __m512i);
            acc = _mm512_dpbf16_ps(
                acc,
                core::mem::transmute::<__m512i, __m512bh>(va),
                core::mem::transmute::<__m512i, __m512bh>(vb),
            );
        }
        _mm512_reduce_add_ps(acc)
    };
    // tail — scalar, via the bf16→f32 reference conversion.
    for i in (chunks * 32)..n {
        total += sovereign_vnni::bf16_to_f32(a[i]) * sovereign_vnni::bf16_to_f32(b[i]);
    }
    total
}

/// T2 (VPTERNLOG) — fuse three attention-mask planes `query ∧ key ∧ causal`
/// into one allow mask (E0810, M085 attention-mask-fusion consumer). One
/// `_mm512_ternarylogic_epi64::<0x80>` fuses 8 words per instruction on any
/// `avx512f` host (so this IS exercised on CI); the scalar oracle is
/// [`sovereign_bitops::vpternlog`]. Uses the shortest length across the three.
#[must_use]
pub fn attention_mask_fuse(query: &[u64], key: &[u64], causal: &[u64]) -> Vec<u64> {
    let n = query.len().min(key.len()).min(causal.len());
    #[cfg(target_arch = "x86_64")]
    {
        if std::is_x86_feature_detected!("avx512f") {
            // SAFETY: gated by the runtime feature check immediately above.
            return unsafe { attention_mask_fuse_avx512(&query[..n], &key[..n], &causal[..n]) };
        }
    }
    attention_mask_fuse_scalar(&query[..n], &key[..n], &causal[..n])
}

/// Scalar reference for [`attention_mask_fuse`] — the M008 `sovereign-bitops`
/// `vpternlog` oracle with `imm8 = 0x80` (AND of all three).
#[must_use]
pub fn attention_mask_fuse_scalar(query: &[u64], key: &[u64], causal: &[u64]) -> Vec<u64> {
    (0..query.len())
        .map(|i| sovereign_bitops::vpternlog(query[i], key[i], causal[i], 0x80))
        .collect()
}

/// # Safety
/// Caller must ensure the host supports `avx512f`.
#[cfg(target_arch = "x86_64")]
#[target_feature(enable = "avx512f")]
unsafe fn attention_mask_fuse_avx512(query: &[u64], key: &[u64], causal: &[u64]) -> Vec<u64> {
    use std::arch::x86_64::*;
    let n = query.len();
    let mut out = vec![0u64; n];
    let chunks = n / 8;
    // SAFETY: AVX-512F intrinsics enabled by target_feature + caller gate; each
    // load/store touches 8 contiguous u64 (one ZMM) within bounds.
    unsafe {
        for c in 0..chunks {
            let q = _mm512_loadu_si512(query.as_ptr().add(c * 8) as *const __m512i);
            let k = _mm512_loadu_si512(key.as_ptr().add(c * 8) as *const __m512i);
            let cm = _mm512_loadu_si512(causal.as_ptr().add(c * 8) as *const __m512i);
            let fused = _mm512_ternarylogic_epi64::<0x80>(q, k, cm);
            _mm512_storeu_si512(out.as_mut_ptr().add(c * 8) as *mut __m512i, fused);
        }
    }
    // tail — scalar AND of all three.
    for i in (chunks * 8)..n {
        out[i] = query[i] & key[i] & causal[i];
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;
    use rand::{Rng, SeedableRng};
    use rand_chacha::ChaCha8Rng;

    #[test]
    fn dot_i8_simd_equals_scalar() {
        let mut rng = ChaCha8Rng::seed_from_u64(0x0001_8D07);
        for &n in &[0usize, 1, 4, 63, 64, 65, 128, 200, 512] {
            let a: Vec<u8> = (0..n).map(|_| rng.random()).collect();
            let b: Vec<i8> = (0..n).map(|_| rng.random()).collect();
            // integer VNNI is exact → bit-identical to the scalar oracle
            assert_eq!(dot_i8(&a, &b), dot_i8_scalar(&a, &b), "n={n}");
            assert_eq!(dot_i8(&a, &b), sovereign_vnni::dot_i8(&a, &b).unwrap());
        }
        // a known value: [1,2,3,4]·[1,1,1,1] = 10
        assert_eq!(dot_i8(&[1, 2, 3, 4], &[1, 1, 1, 1]), 10);
    }

    #[test]
    fn dot_bf16_simd_matches_scalar_within_tolerance() {
        let mut rng = ChaCha8Rng::seed_from_u64(0xBF16_0000);
        for &n in &[0usize, 1, 31, 32, 33, 96, 257] {
            let a: Vec<u16> = (0..n)
                .map(|_| sovereign_vnni::f32_to_bf16(rng.random_range(-2.0f32..2.0)))
                .collect();
            let b: Vec<u16> = (0..n)
                .map(|_| sovereign_vnni::f32_to_bf16(rng.random_range(-2.0f32..2.0)))
                .collect();
            let simd = dot_bf16(&a, &b);
            let scalar = dot_bf16_scalar(&a, &b);
            assert!(
                (simd - scalar).abs() <= 1e-3 * (simd.abs() + scalar.abs() + 1.0),
                "n={n}: simd={simd} scalar={scalar}"
            );
        }
    }

    #[test]
    fn attention_mask_fuse_equals_scalar_and_ands() {
        let mut rng = ChaCha8Rng::seed_from_u64(0x00A7_7E70);
        for &n in &[0usize, 1, 7, 8, 9, 16, 100] {
            let q: Vec<u64> = (0..n).map(|_| rng.random()).collect();
            let k: Vec<u64> = (0..n).map(|_| rng.random()).collect();
            let c: Vec<u64> = (0..n).map(|_| rng.random()).collect();
            let simd = attention_mask_fuse(&q, &k, &c);
            assert_eq!(simd, attention_mask_fuse_scalar(&q, &k, &c), "n={n}");
            // it IS the AND of all three planes
            let expect: Vec<u64> = (0..n).map(|i| q[i] & k[i] & c[i]).collect();
            assert_eq!(simd, expect);
        }
    }
}
