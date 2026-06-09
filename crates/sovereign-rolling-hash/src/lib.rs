//! `sovereign-rolling-hash` — O(1)-update polynomial hashing for scan & chunk.
//!
//! A *rolling* hash summarises a sliding window of bytes and updates in constant
//! time as the window advances by one byte — drop the byte leaving on the left,
//! add the byte entering on the right — instead of rehashing the whole window.
//! Two jobs fall out of that.
//!
//! **Rabin-Karp substring search** ([`find_all`]): hash the needle once, roll a
//! same-width window across the haystack, and only do a full byte compare where
//! the hashes agree. That is `O(n + m)` expected with no false *negatives*, and
//! the explicit compare removes false positives, so the result is exact.
//!
//! **Content-defined chunking** ([`Chunker`]): instead of cutting every `N`
//! bytes (where inserting one byte shifts every later boundary), cut wherever the
//! rolling hash of the last few bytes has its low bits all zero. Because a
//! boundary depends only on local content, an edit re-chunks just its own
//! neighbourhood — the rest of the chunk boundaries, and their hashes, stay put.
//! That shift-resistance is what makes deduplication and incremental indexing of
//! edited documents practical.
//!
//! The hash is `Σ byte[i] · base^(w−1−i)  (mod 2^64)`, with wrap-around
//! arithmetic; `base` is a fixed odd constant. It is a *hash*, not a CSPRNG —
//! good for matching and chunking, not for security.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// Schema version of the rolling-hash surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// The polynomial base (a fixed odd multiplier).
pub const BASE: u64 = 1_000_000_007;

/// A rolling polynomial hash over a fixed-width window of bytes.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct RollingHash {
    width: usize,
    /// `base^(width-1) mod 2^64`, the weight of the leftmost (oldest) byte.
    high_pow: u64,
    hash: u64,
    /// The bytes currently in the window (front = oldest).
    window: std::collections::VecDeque<u8>,
}

impl RollingHash {
    /// A rolling hash over a window of `width` bytes.
    ///
    /// # Panics
    /// Panics if `width == 0`.
    pub fn new(width: usize) -> Self {
        assert!(width > 0, "window width must be > 0");
        let mut high_pow = 1u64;
        for _ in 0..width.saturating_sub(1) {
            high_pow = high_pow.wrapping_mul(BASE);
        }
        Self {
            width,
            high_pow,
            hash: 0,
            window: std::collections::VecDeque::with_capacity(width),
        }
    }

    /// The window width.
    pub fn width(&self) -> usize {
        self.width
    }

    /// The current hash value.
    pub fn hash(&self) -> u64 {
        self.hash
    }

    /// Whether the window is full (`width` bytes present).
    pub fn is_full(&self) -> bool {
        self.window.len() == self.width
    }

    /// Push one byte. If the window was full, the oldest byte rolls out (an O(1)
    /// update); otherwise the byte just fills the window. Returns the byte that
    /// left the window, if any.
    pub fn push(&mut self, byte: u8) -> Option<u8> {
        if self.window.len() == self.width {
            let old = self.window.pop_front().unwrap();
            // remove old byte's contribution, shift, add new byte
            self.hash = self
                .hash
                .wrapping_sub((old as u64).wrapping_mul(self.high_pow));
            self.hash = self.hash.wrapping_mul(BASE).wrapping_add(byte as u64);
            self.window.push_back(byte);
            Some(old)
        } else {
            self.hash = self.hash.wrapping_mul(BASE).wrapping_add(byte as u64);
            self.window.push_back(byte);
            None
        }
    }

    /// The hash of an arbitrary byte slice under this scheme (window-independent
    /// helper; useful for hashing a needle of the same width).
    pub fn hash_bytes(bytes: &[u8]) -> u64 {
        let mut h = 0u64;
        for &b in bytes {
            h = h.wrapping_mul(BASE).wrapping_add(b as u64);
        }
        h
    }
}

/// All start offsets where `needle` occurs in `haystack`, via Rabin-Karp with an
/// exact byte-compare to eliminate hash collisions. Ascending order. An empty
/// needle yields no matches; a needle longer than the haystack yields none.
pub fn find_all(haystack: &[u8], needle: &[u8]) -> Vec<usize> {
    let m = needle.len();
    let n = haystack.len();
    if m == 0 || m > n {
        return Vec::new();
    }
    let target = RollingHash::hash_bytes(needle);
    let mut roll = RollingHash::new(m);
    let mut out = Vec::new();
    for (i, &b) in haystack.iter().enumerate() {
        roll.push(b);
        if roll.is_full() {
            let start = i + 1 - m;
            if roll.hash() == target && &haystack[start..start + m] == needle {
                out.push(start);
            }
        }
    }
    out
}

/// Whether `needle` occurs in `haystack`.
pub fn contains(haystack: &[u8], needle: &[u8]) -> bool {
    !find_all(haystack, needle).is_empty()
}

/// A content-defined chunker. Boundaries fall where the rolling hash of the last
/// `window` bytes has its low `mask_bits` all zero, subject to min/max chunk
/// sizes so chunks stay in a sane range even on adversarial input.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Chunker {
    window: usize,
    mask: u64,
    min_size: usize,
    max_size: usize,
}

impl Chunker {
    /// A chunker whose average chunk size is about `2^mask_bits` bytes. `window`
    /// is the rolling-hash width used to decide boundaries; `min_size` and
    /// `max_size` clamp chunk lengths.
    ///
    /// # Panics
    /// Panics if `window == 0`, `min_size == 0`, `mask_bits > 63`, or
    /// `max_size < min_size`.
    pub fn new(window: usize, mask_bits: u32, min_size: usize, max_size: usize) -> Self {
        assert!(window > 0, "window must be > 0");
        assert!(min_size > 0, "min_size must be > 0");
        assert!(mask_bits <= 63, "mask_bits must be <= 63");
        assert!(max_size >= min_size, "max_size must be >= min_size");
        Self {
            window,
            mask: (1u64 << mask_bits) - 1,
            min_size,
            max_size,
        }
    }

    /// The byte offsets at which chunks end (each is the exclusive end of one
    /// chunk; the final element is always `data.len()`). Returns an empty vec for
    /// empty input.
    pub fn boundaries(&self, data: &[u8]) -> Vec<usize> {
        let mut bounds = Vec::new();
        if data.is_empty() {
            return bounds;
        }
        // One continuous rolling window over the whole stream: the boundary
        // predicate then depends only on the last `window` bytes, never on where
        // the previous chunk started — that locality is what makes the cut points
        // shift-resistant. (Resetting the hash per chunk would reintroduce
        // history dependence and defeat the purpose.)
        let mut roll = RollingHash::new(self.window);
        let mut chunk_start = 0usize;
        for (i, &b) in data.iter().enumerate() {
            roll.push(b);
            let chunk_len = i + 1 - chunk_start;
            let at_max = chunk_len >= self.max_size;
            let hit =
                chunk_len >= self.min_size && roll.is_full() && (roll.hash() & self.mask) == 0;
            if at_max || hit {
                bounds.push(i + 1);
                chunk_start = i + 1;
            }
        }
        if chunk_start < data.len() {
            bounds.push(data.len());
        }
        bounds
    }

    /// The chunks of `data` as byte slices, split at [`boundaries`](Self::boundaries).
    pub fn chunks<'a>(&self, data: &'a [u8]) -> Vec<&'a [u8]> {
        let mut out = Vec::new();
        let mut start = 0usize;
        for end in self.boundaries(data) {
            out.push(&data[start..end]);
            start = end;
        }
        out
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Non-periodic pseudo-random bytes (splitmix64) — a representative stand-in
    /// for real content, without the confounds of a periodic fixture.
    fn prng_bytes(n: usize, seed: u64) -> Vec<u8> {
        let mut s = seed;
        (0..n)
            .map(|_| {
                s = s.wrapping_add(0x9E37_79B9_7F4A_7C15);
                let mut z = s;
                z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
                z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
                ((z ^ (z >> 31)) & 0xFF) as u8
            })
            .collect()
    }

    #[test]
    fn rolling_hash_equals_direct_hash() {
        // after pushing a full window, the rolling hash equals hashing those bytes
        let data = b"abcdefgh";
        let mut roll = RollingHash::new(4);
        for &b in data {
            roll.push(b);
        }
        // window now holds the last 4 bytes "efgh"
        assert_eq!(roll.hash(), RollingHash::hash_bytes(b"efgh"));
    }

    #[test]
    fn rolling_update_matches_recompute_at_every_step() {
        let data = b"the quick brown fox";
        let w = 5;
        let mut roll = RollingHash::new(w);
        for (i, &b) in data.iter().enumerate() {
            roll.push(b);
            if roll.is_full() {
                let expected = RollingHash::hash_bytes(&data[i + 1 - w..i + 1]);
                assert_eq!(roll.hash(), expected, "mismatch ending at {i}");
            }
        }
    }

    #[test]
    fn find_all_matches_naive() {
        let hay = b"abracadabra abracadabra";
        for needle in [&b"abra"[..], b"a", b"cad", b"ra a", b"xyz", b"abracadabra"] {
            let naive: Vec<usize> = (0..hay.len())
                .filter(|&i| hay[i..].starts_with(needle))
                .collect();
            assert_eq!(find_all(hay, needle), naive, "needle {needle:?}");
        }
    }

    #[test]
    fn find_all_edge_cases() {
        assert!(find_all(b"abc", b"").is_empty()); // empty needle
        assert!(find_all(b"ab", b"abc").is_empty()); // needle longer than hay
        assert_eq!(find_all(b"aaaa", b"aa"), vec![0, 1, 2]); // overlapping
        assert!(contains(b"hello world", b"o w"));
        assert!(!contains(b"hello world", b"xyz"));
    }

    #[test]
    fn chunker_boundaries_cover_all_data() {
        let data = prng_bytes(5000, 12345);
        let chunker = Chunker::new(16, 8, 32, 1024);
        let chunks = chunker.chunks(&data);
        // chunks concatenate back to the original, exactly
        let rejoined: Vec<u8> = chunks.concat();
        assert_eq!(rejoined, data);
        // and respect the size bounds (except possibly the last chunk for min)
        for (i, c) in chunks.iter().enumerate() {
            assert!(c.len() <= 1024, "chunk {i} too big: {}", c.len());
            if i + 1 < chunks.len() {
                assert!(c.len() >= 32, "interior chunk {i} too small: {}", c.len());
            }
        }
        assert!(chunks.len() > 1, "expected multiple chunks");
    }

    #[test]
    fn chunking_is_shift_resistant() {
        // Insert a byte near the front; only the chunks around the edit should
        // change — most trailing chunks must be byte-identical.
        let data = prng_bytes(8000, 0xDEAD_BEEF);
        let chunker = Chunker::new(16, 7, 24, 512);

        let a = chunker.chunks(&data);
        let mut edited = data.clone();
        edited.insert(100, 0xAB); // one-byte insertion early in the stream
        let b = chunker.chunks(&edited);

        // collect the set of chunk contents and check large overlap downstream
        use std::collections::HashSet;
        let set_a: HashSet<Vec<u8>> = a.iter().map(|c| c.to_vec()).collect();
        let shared = b.iter().filter(|c| set_a.contains(*c as &[u8])).count();
        // a fixed-size chunker would share ~0 after a shift; CDC should re-sync
        // and share most chunks.
        assert!(
            shared as f64 / b.len() as f64 > 0.5,
            "CDC should resync: shared {shared} of {}",
            b.len()
        );
    }

    #[test]
    fn empty_input_has_no_chunks() {
        let chunker = Chunker::new(8, 6, 4, 64);
        assert!(chunker.boundaries(b"").is_empty());
        assert!(chunker.chunks(b"").is_empty());
    }

    #[test]
    fn max_size_caps_chunk_length() {
        // all-zero data: the hash of a zero window is 0, so a boundary could fire
        // every step once past min; either way no chunk exceeds max_size.
        let data = vec![0u8; 1000];
        let chunker = Chunker::new(8, 10, 16, 100);
        for c in chunker.chunks(&data) {
            assert!(c.len() <= 100);
        }
    }

    #[test]
    fn serde_round_trip() {
        let chunker = Chunker::new(16, 8, 32, 1024);
        let j = serde_json::to_string(&chunker).unwrap();
        let back: Chunker = serde_json::from_str(&j).unwrap();
        assert_eq!(chunker, back);

        let roll = {
            let mut r = RollingHash::new(4);
            r.push(b'a');
            r.push(b'b');
            r
        };
        let jr = serde_json::to_string(&roll).unwrap();
        let backr: RollingHash = serde_json::from_str(&jr).unwrap();
        assert_eq!(roll, backr);
    }
}
