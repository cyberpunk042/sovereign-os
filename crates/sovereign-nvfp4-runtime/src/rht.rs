//! Random Hadamard Transform (RHT) — the NVFP4 pre-quantization step.
//!
//! NVFP4 (M077) applies an RHT before quantizing: flip each element's sign by
//! a fixed random `±1` pattern, then run a normalized Walsh-Hadamard
//! transform. This *spreads outliers* across all dimensions so the 4-bit
//! per-block quantizer sees a flatter distribution — recovering accuracy.
//! The transform is orthogonal (norm-preserving) and exactly invertible, so
//! it can be undone after dequantization.
//!
//! Lengths must be a power of two (the Hadamard butterfly requirement).

use thiserror::Error;

/// RHT errors.
#[derive(Debug, Error, PartialEq, Eq)]
pub enum RhtError {
    /// The vector length is not a power of two.
    #[error("length {0} is not a power of two")]
    NotPowerOfTwo(usize),
    /// The sign vector length did not match the data length.
    #[error("sign length {signs} does not match data length {data}")]
    SignLengthMismatch {
        /// Data length.
        data: usize,
        /// Sign-vector length.
        signs: usize,
    },
}

/// In-place unnormalized fast Walsh-Hadamard transform. `a.len()` must be a
/// power of two. Applying it twice scales by `n` (it is its own inverse up
/// to that factor).
pub fn fwht(a: &mut [f32]) {
    let n = a.len();
    let mut h = 1;
    while h < n {
        let mut i = 0;
        while i < n {
            for j in i..i + h {
                let x = a[j];
                let y = a[j + h];
                a[j] = x + y;
                a[j + h] = x - y;
            }
            i += 2 * h;
        }
        h *= 2;
    }
}

/// Deterministic `±1` sign vector of length `n` from a seed (xorshift), for
/// reproducible RHT.
pub fn random_signs(n: usize, seed: u64) -> Vec<i8> {
    let mut s = seed | 1; // avoid all-zero state
    (0..n)
        .map(|_| {
            s ^= s << 13;
            s ^= s >> 7;
            s ^= s << 17;
            if s & 1 == 0 { 1 } else { -1 }
        })
        .collect()
}

fn check(data: usize, signs: usize) -> Result<(), RhtError> {
    if !data.is_power_of_two() {
        return Err(RhtError::NotPowerOfTwo(data));
    }
    if data != signs {
        return Err(RhtError::SignLengthMismatch { data, signs });
    }
    Ok(())
}

/// Forward RHT: `(1/√n) · H · (signs ⊙ x)`. Orthogonal, so `‖output‖ = ‖x‖`.
pub fn rht_forward(x: &[f32], signs: &[i8]) -> Result<Vec<f32>, RhtError> {
    check(x.len(), signs.len())?;
    let scale = 1.0 / (x.len() as f32).sqrt();
    let mut a: Vec<f32> = x.iter().zip(signs).map(|(v, &s)| v * s as f32).collect();
    fwht(&mut a);
    for v in &mut a {
        *v *= scale;
    }
    Ok(a)
}

/// Inverse RHT: recovers `x` from [`rht_forward`]'s output using the same
/// `signs`. (`H` is self-inverse up to `n`; the sign flip is its own inverse.)
pub fn rht_inverse(y: &[f32], signs: &[i8]) -> Result<Vec<f32>, RhtError> {
    check(y.len(), signs.len())?;
    let scale = 1.0 / (y.len() as f32).sqrt();
    let mut a = y.to_vec();
    fwht(&mut a);
    for v in &mut a {
        *v *= scale;
    }
    Ok(a.iter().zip(signs).map(|(v, &s)| v * s as f32).collect())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn l2(v: &[f32]) -> f32 {
        v.iter().map(|x| x * x).sum::<f32>().sqrt()
    }

    #[test]
    fn round_trip_recovers_input() {
        let x = [1.0f32, -2.0, 3.0, 0.5, -1.5, 4.0, -0.25, 2.0];
        let signs = random_signs(x.len(), 0xC0FFEE);
        let fwd = rht_forward(&x, &signs).unwrap();
        let back = rht_inverse(&fwd, &signs).unwrap();
        for (a, b) in x.iter().zip(&back) {
            assert!((a - b).abs() < 1e-4, "{a} vs {b}");
        }
    }

    #[test]
    fn forward_preserves_norm() {
        let x = [10.0f32, 0.0, 0.0, 0.0]; // a spike (outlier)
        let signs = random_signs(4, 7);
        let fwd = rht_forward(&x, &signs).unwrap();
        // orthogonal transform → same L2 norm
        assert!((l2(&fwd) - l2(&x)).abs() < 1e-4);
        // ...but the energy is spread: no single element holds it all
        assert!(fwd.iter().all(|v| v.abs() < l2(&x)));
    }

    #[test]
    fn non_power_of_two_rejected() {
        let signs = random_signs(3, 1);
        assert_eq!(
            rht_forward(&[1.0, 2.0, 3.0], &signs).unwrap_err(),
            RhtError::NotPowerOfTwo(3)
        );
    }

    #[test]
    fn sign_length_mismatch_rejected() {
        let err = rht_forward(&[1.0, 2.0, 3.0, 4.0], &[1, -1]).unwrap_err();
        assert!(matches!(err, RhtError::SignLengthMismatch { .. }));
    }

    #[test]
    fn signs_are_deterministic_and_pm_one() {
        let a = random_signs(16, 42);
        let b = random_signs(16, 42);
        assert_eq!(a, b);
        assert!(a.iter().all(|&s| s == 1 || s == -1));
    }

    #[test]
    fn fwht_twice_scales_by_n() {
        let mut a = [1.0f32, 2.0, 3.0, 4.0];
        let orig = a;
        fwht(&mut a);
        fwht(&mut a);
        for (v, o) in a.iter().zip(orig) {
            assert!((v - o * 4.0).abs() < 1e-4);
        }
    }
}
