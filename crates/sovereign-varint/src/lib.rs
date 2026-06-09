//! `sovereign-varint` — small numbers in small space.
//!
//! Serializing a stream of token ids or byte offsets with a fixed 4 or 8 bytes
//! each wastes most of the space, because most of those numbers are small.
//! **LEB128** variable-length coding spends one byte per 7 bits of magnitude: the
//! low 7 bits of each byte carry data, the high bit says "more bytes follow". A
//! value under 128 takes one byte, under 16384 two, and so on — so a corpus of
//! mostly-small ids compresses for free, with no table.
//!
//! Signed values use **zigzag** first ([`zigzag`]/[`unzigzag`]): it interleaves
//! positive and negative integers (`0, -1, 1, -2, …` → `0, 1, 2, 3, …`) so that
//! small-magnitude negatives also encode short, which the plain two's-complement
//! representation would not. And [`encode_deltas`]/[`decode_deltas`] turn a
//! *monotonic* sequence into its gaps before coding — a sorted posting list of
//! large ids becomes a stream of tiny deltas.
//!
//! [`encode_u64`]/[`decode_u64`] handle one value; [`encode_seq`]/[`decode_seq`]
//! a whole `&[u64]`; everything is byte-exact and round-trips.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

/// Schema version of the varint surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Errors decoding a varint stream.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum VarintError {
    /// The stream ended before a value's continuation bytes arrived.
    Truncated,
    /// A varint used more than 10 bytes (cannot fit a `u64`).
    Overflow,
}

impl std::fmt::Display for VarintError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            VarintError::Truncated => write!(f, "varint stream truncated"),
            VarintError::Overflow => write!(f, "varint too long for u64"),
        }
    }
}

impl std::error::Error for VarintError {}

/// Append the LEB128 encoding of `value` to `out`.
pub fn encode_u64(value: u64, out: &mut Vec<u8>) {
    let mut v = value;
    loop {
        let mut byte = (v & 0x7f) as u8;
        v >>= 7;
        if v != 0 {
            byte |= 0x80; // more bytes follow
        }
        out.push(byte);
        if v == 0 {
            break;
        }
    }
}

/// Decode one LEB128 value starting at `buf`, returning `(value, bytes_consumed)`.
pub fn decode_u64(buf: &[u8]) -> Result<(u64, usize), VarintError> {
    let mut value = 0u64;
    let mut shift = 0u32;
    for (i, &byte) in buf.iter().enumerate() {
        if i >= 10 {
            return Err(VarintError::Overflow);
        }
        value |= ((byte & 0x7f) as u64) << shift;
        if byte & 0x80 == 0 {
            return Ok((value, i + 1));
        }
        shift += 7;
    }
    Err(VarintError::Truncated)
}

/// Zigzag-encode a signed value to unsigned (small magnitudes stay small).
pub fn zigzag(value: i64) -> u64 {
    ((value << 1) ^ (value >> 63)) as u64
}

/// Reverse [`zigzag`].
pub fn unzigzag(value: u64) -> i64 {
    ((value >> 1) as i64) ^ -((value & 1) as i64)
}

/// Append the zigzag+LEB128 encoding of a signed `value`.
pub fn encode_i64(value: i64, out: &mut Vec<u8>) {
    encode_u64(zigzag(value), out);
}

/// Decode one signed zigzag+LEB128 value: `(value, bytes_consumed)`.
pub fn decode_i64(buf: &[u8]) -> Result<(i64, usize), VarintError> {
    let (u, n) = decode_u64(buf)?;
    Ok((unzigzag(u), n))
}

/// Encode a whole sequence of `u64` values to a byte buffer.
pub fn encode_seq(values: &[u64]) -> Vec<u8> {
    let mut out = Vec::with_capacity(values.len());
    for &v in values {
        encode_u64(v, &mut out);
    }
    out
}

/// Decode a byte buffer produced by [`encode_seq`] back into values.
pub fn decode_seq(buf: &[u8]) -> Result<Vec<u64>, VarintError> {
    let mut out = Vec::new();
    let mut pos = 0;
    while pos < buf.len() {
        let (v, n) = decode_u64(&buf[pos..])?;
        out.push(v);
        pos += n;
    }
    Ok(out)
}

/// Delta-encode a sequence: store the first value, then the gaps to each next
/// value (as signed zigzag varints, so non-monotonic sequences also work), into a
/// byte buffer. A sorted, large-valued sequence becomes tiny gaps.
pub fn encode_deltas(values: &[u64]) -> Vec<u8> {
    let mut out = Vec::new();
    let mut prev = 0i64;
    for &v in values {
        let v = v as i64;
        encode_i64(v - prev, &mut out);
        prev = v;
    }
    out
}

/// Decode a delta-encoded buffer back into the original sequence.
pub fn decode_deltas(buf: &[u8]) -> Result<Vec<u64>, VarintError> {
    let mut out = Vec::new();
    let mut pos = 0;
    let mut acc = 0i64;
    while pos < buf.len() {
        let (d, n) = decode_i64(&buf[pos..])?;
        acc += d;
        out.push(acc as u64);
        pos += n;
    }
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn single_byte_for_small_values() {
        for v in 0..128u64 {
            let mut buf = Vec::new();
            encode_u64(v, &mut buf);
            assert_eq!(buf.len(), 1, "value {v}");
            assert_eq!(decode_u64(&buf).unwrap(), (v, 1));
        }
    }

    #[test]
    fn multibyte_round_trips() {
        for v in [128, 300, 16_383, 16_384, u32::MAX as u64, u64::MAX] {
            let mut buf = Vec::new();
            encode_u64(v, &mut buf);
            assert_eq!(decode_u64(&buf).unwrap().0, v, "value {v}");
        }
        // 128 needs 2 bytes, 16384 needs 3, u64::MAX needs 10
        let mut b = Vec::new();
        encode_u64(128, &mut b);
        assert_eq!(b.len(), 2);
        let mut b2 = Vec::new();
        encode_u64(u64::MAX, &mut b2);
        assert_eq!(b2.len(), 10);
    }

    #[test]
    fn zigzag_keeps_small_negatives_small() {
        assert_eq!(zigzag(0), 0);
        assert_eq!(zigzag(-1), 1);
        assert_eq!(zigzag(1), 2);
        assert_eq!(zigzag(-2), 3);
        for v in [-1000i64, -1, 0, 1, 1000, i64::MIN, i64::MAX] {
            assert_eq!(unzigzag(zigzag(v)), v, "value {v}");
        }
        // -1 encodes in one byte (zigzag → 1), unlike two's complement.
        let mut buf = Vec::new();
        encode_i64(-1, &mut buf);
        assert_eq!(buf.len(), 1);
    }

    #[test]
    fn signed_round_trips() {
        for v in [-1_000_000i64, -5, 0, 5, 1_000_000, i64::MIN, i64::MAX] {
            let mut buf = Vec::new();
            encode_i64(v, &mut buf);
            assert_eq!(decode_i64(&buf).unwrap().0, v, "value {v}");
        }
    }

    #[test]
    fn sequence_round_trip() {
        let seq = [1u64, 0, 127, 128, 300, 1_000_000, 5];
        let buf = encode_seq(&seq);
        assert_eq!(decode_seq(&buf).unwrap(), seq.to_vec());
    }

    #[test]
    fn delta_encoding_compresses_sorted_ids() {
        // a sorted posting list of large ids → tiny gaps → small buffer.
        let ids: Vec<u64> = (0..100).map(|i| 1_000_000 + i * 3).collect();
        let plain = encode_seq(&ids);
        let deltas = encode_deltas(&ids);
        assert!(
            deltas.len() < plain.len(),
            "delta {} plain {}",
            deltas.len(),
            plain.len()
        );
        assert_eq!(decode_deltas(&deltas).unwrap(), ids);
    }

    #[test]
    fn delta_handles_non_monotonic() {
        let seq = [10u64, 5, 20, 1, 100];
        let buf = encode_deltas(&seq);
        assert_eq!(decode_deltas(&buf).unwrap(), seq.to_vec());
    }

    #[test]
    fn truncated_and_overflow_errors() {
        // a continuation byte with nothing after → truncated.
        assert_eq!(decode_u64(&[0x80]), Err(VarintError::Truncated));
        // 11 continuation bytes → overflow.
        let overflow = vec![0x80u8; 11];
        assert_eq!(decode_u64(&overflow), Err(VarintError::Overflow));
    }

    #[test]
    fn empty_sequence() {
        assert!(encode_seq(&[]).is_empty());
        assert_eq!(decode_seq(&[]).unwrap(), Vec::<u64>::new());
        assert_eq!(decode_deltas(&[]).unwrap(), Vec::<u64>::new());
    }
}
