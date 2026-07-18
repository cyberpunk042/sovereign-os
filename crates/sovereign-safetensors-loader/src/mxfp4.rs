//! MXFP4 (OCP Microscaling FP4) dequantization.
//!
//! MXFP4 is the format `gpt-oss` ships its MoE expert weights in on the Hub: a
//! weight is stored as a pair of `uint8` safetensors tensors — a `*_blocks`
//! tensor of packed 4-bit values and a `*_scales` tensor of per-block exponents.
//!
//! - **Element**: 4-bit **E2M1** (1 sign, 2 exponent, 1 mantissa). The 16 bit
//!   patterns map to a fixed table: `{0, 0.5, 1, 1.5, 2, 3, 4, 6}` and their
//!   negatives ([`FP4_LUT`]). Two elements pack into one byte — the **low**
//!   nibble is the earlier element, the **high** nibble the next.
//! - **Block**: 32 consecutive elements (16 packed bytes) share one **E8M0**
//!   scale byte `s`, whose multiplier is `2^(s - 127)`.
//!
//! Dequantization is exact (a table lookup times a power of two — no rounding),
//! so it is verifiable against hand-computed vectors without a real checkpoint.
//! This is the dtype the safetensors loader needs before it can read a real
//! gpt-oss release; assembling those dequantized experts into the decoder (the
//! fused `gate_up` split + per-expert reshape) is the remaining follow-up.

use thiserror::Error;

/// FP4 (E2M1) value table: the low 3 bits index the magnitude, bit 3 is the
/// sign. Matches the OCP Microscaling spec and HF transformers' `FP4_VALUES`.
const FP4_LUT: [f32; 16] = [
    0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0, -0.0, -0.5, -1.0, -1.5, -2.0, -3.0, -4.0, -6.0,
];

/// Elements per MXFP4 block — 32 values share one E8M0 scale.
pub const BLOCK_ELEMS: usize = 32;
/// Packed bytes per block — 32 4-bit values = 16 bytes.
pub const BLOCK_BYTES: usize = 16;

/// What can go wrong decoding an MXFP4 `blocks` / `scales` tensor pair.
#[derive(Debug, Error, PartialEq, Eq)]
pub enum Mxfp4Error {
    /// The packed-blocks byte count is not a whole number of 16-byte blocks.
    #[error("mxfp4 blocks length {0} is not a multiple of {BLOCK_BYTES} (one 32-value block)")]
    NotBlockAligned(usize),
    /// Exactly one E8M0 scale byte is required per 16-byte block.
    #[error("mxfp4 scale count {scales} does not match block count {blocks}")]
    ScaleCountMismatch {
        /// Blocks implied by the packed-bytes length.
        blocks: usize,
        /// Scale bytes actually provided.
        scales: usize,
    },
}

/// Decode an E8M0 scale byte to its multiplier `2^(byte - 127)`. `127` ⇒ `1.0`.
#[inline]
fn e8m0(byte: u8) -> f32 {
    2f32.powi(byte as i32 - 127)
}

/// Dequantize MXFP4-packed weights to `f32`.
///
/// `blocks` holds 4-bit E2M1 elements, two per byte (low nibble = the earlier
/// element, high nibble = the next); `scales` holds one E8M0 exponent byte per
/// 32-element (16-byte) block. Returns `blocks.len() * 2` values in input order.
///
/// # Errors
/// [`Mxfp4Error::NotBlockAligned`] if `blocks.len()` is not a multiple of 16, or
/// [`Mxfp4Error::ScaleCountMismatch`] if `scales.len()` is not `blocks.len() / 16`.
pub fn dequant(blocks: &[u8], scales: &[u8]) -> Result<Vec<f32>, Mxfp4Error> {
    if blocks.len() % BLOCK_BYTES != 0 {
        return Err(Mxfp4Error::NotBlockAligned(blocks.len()));
    }
    let n_blocks = blocks.len() / BLOCK_BYTES;
    if scales.len() != n_blocks {
        return Err(Mxfp4Error::ScaleCountMismatch {
            blocks: n_blocks,
            scales: scales.len(),
        });
    }
    let mut out = Vec::with_capacity(blocks.len() * 2);
    for (blk, chunk) in blocks.chunks_exact(BLOCK_BYTES).enumerate() {
        let scale = e8m0(scales[blk]);
        for &byte in chunk {
            out.push(FP4_LUT[(byte & 0x0F) as usize] * scale);
            out.push(FP4_LUT[(byte >> 4) as usize] * scale);
        }
    }
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn nibble_order_and_lut() {
        // scale 127 ⇒ ×1. Low nibble first: 0x10 ⇒ [0.0, 0.5]; 0x72 ⇒ [1.0, 6.0].
        let mut blocks = vec![0u8; BLOCK_BYTES];
        blocks[0] = 0x10;
        blocks[1] = 0x72;
        let out = dequant(&blocks, &[127]).unwrap();
        assert_eq!(out.len(), BLOCK_ELEMS);
        assert_eq!(&out[0..4], &[0.0, 0.5, 1.0, 6.0]);
    }

    #[test]
    fn sign_bit_negates() {
        let mut blocks = vec![0u8; BLOCK_BYTES];
        blocks[0] = 0x8F; // low nibble 0xF ⇒ -6.0, high nibble 0x8 ⇒ -0.0
        let out = dequant(&blocks, &[127]).unwrap();
        assert_eq!(out[0], -6.0);
        assert!(out[1] == 0.0 && out[1].is_sign_negative()); // -0.0
    }

    #[test]
    fn e8m0_scale_is_a_power_of_two() {
        let mut blocks = vec![0u8; BLOCK_BYTES];
        blocks[0] = 0x02; // low nibble 2 ⇒ 1.0
        assert_eq!(dequant(&blocks, &[127]).unwrap()[0], 1.0); // 2^0
        assert_eq!(dequant(&blocks, &[128]).unwrap()[0], 2.0); // 2^1
        assert_eq!(dequant(&blocks, &[126]).unwrap()[0], 0.5); // 2^-1
    }

    #[test]
    fn each_block_uses_its_own_scale() {
        let mut blocks = vec![0u8; 2 * BLOCK_BYTES];
        blocks[0] = 0x02; // block 0, elem 0 ⇒ 1.0
        blocks[BLOCK_BYTES] = 0x02; // block 1, elem 0 ⇒ 1.0
        let out = dequant(&blocks, &[127, 128]).unwrap();
        assert_eq!(out.len(), 2 * BLOCK_ELEMS);
        assert_eq!(out[0], 1.0); // ×2^0
        assert_eq!(out[BLOCK_ELEMS], 2.0); // ×2^1
    }

    #[test]
    fn rejects_misaligned_blocks_and_bad_scale_count() {
        assert_eq!(
            dequant(&[0u8; 15], &[127]),
            Err(Mxfp4Error::NotBlockAligned(15))
        );
        assert_eq!(
            dequant(&[0u8; BLOCK_BYTES], &[127, 0]),
            Err(Mxfp4Error::ScaleCountMismatch {
                blocks: 1,
                scales: 2
            })
        );
    }
}
